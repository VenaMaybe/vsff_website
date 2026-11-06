"""Document and immutable-version persistence services."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from .database import version_table, connect, transaction
from .storage import BlobStore, StoredBlob


IMPORT_LOCK = threading.Lock()


class DocumentError(RuntimeError):
    """A controlled document-service error."""


class DocumentNotFoundError(DocumentError):
    """The requested logical document does not exist."""


class VersionNotFoundError(DocumentError):
    """The requested immutable version does not exist."""


@dataclass(frozen=True)
class ImportResult:
    version_id: str
    blob: StoredBlob


def now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def normalize_optional(value: str | None, maximum: int = 300) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > maximum:
        raise DocumentError(f"A metadata value exceeds {maximum} characters.")
    return normalized


def normalize_filename(filename: str | None) -> str:
    if not filename:
        raise DocumentError("Choose a PDF file to import.")
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].replace("\x00", "").strip()
    if not name or len(name) > 500:
        raise DocumentError("The PDF filename is invalid or too long.")
    if not name.casefold().endswith(".pdf"):
        raise DocumentError("The selected file must use the .pdf extension.")
    return name


def create_document(database_path: Path | str, title: str, *, owner_id: str | None = None) -> str:
    title = title.strip()
    if not title:
        raise DocumentError("Document title is required.")
    if len(title) > 300:
        raise DocumentError("Document title must be 300 characters or fewer.")
    document_id = str(uuid.uuid4())
    with transaction(database_path) as connection:
        connection.execute(
            "INSERT INTO documents(document_id, title, created_at) VALUES (?, ?, ?)",
            (document_id, title, now_utc()),
        )
        if owner_id is not None:
            connection.execute(
                """INSERT INTO document_access(document_id, user_id, role, created_at, granted_by_user_id)
                   VALUES (?, ?, 'owner', ?, ?)""", (document_id, owner_id, now_utc(), owner_id)
            )
    return document_id


def list_documents(database_path: Path | str) -> list[sqlite3.Row]:
    connection = connect(database_path)
    try:
        # Historical offline fixtures may predate authenticated document ownership.
        owners = "(SELECT group_concat(display_name, ', ') FROM (SELECT u.display_name FROM document_access a JOIN users u ON u.user_id=a.user_id WHERE a.document_id=d.document_id AND a.role='owner' ORDER BY u.display_name COLLATE NOCASE,u.user_id))" if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='document_access'").fetchone() else 'NULL'
        return connection.execute(
            f"""
            SELECT d.*, COUNT(v.version_id) AS version_count,
                   MAX(v.imported_at) AS last_imported_at,
                   {owners} AS owner_names
            FROM documents d
            LEFT JOIN {version_table(connection)} v ON v.document_id = d.document_id
            GROUP BY d.document_id
            ORDER BY d.created_at DESC, d.document_id DESC
            """
        ).fetchall()
    finally:
        connection.close()


def get_document(database_path: Path | str, document_id: str) -> sqlite3.Row | None:
    connection = connect(database_path)
    try:
        return connection.execute(
            "SELECT * FROM documents WHERE document_id = ?", (document_id,)
        ).fetchone()
    finally:
        connection.close()


def list_versions(database_path: Path | str, document_id: str) -> list[sqlite3.Row]:
    connection = connect(database_path)
    try:
        return connection.execute(
            f"""
            SELECT * FROM {version_table(connection)}
            WHERE document_id = ?
            ORDER BY imported_at DESC, version_id DESC
            """,
            (document_id,),
        ).fetchall()
    finally:
        connection.close()


def get_version(database_path: Path | str, version_id: str) -> sqlite3.Row | None:
    connection = connect(database_path)
    try:
        return connection.execute(
            f"""
            SELECT v.*, d.title AS document_title
            FROM {version_table(connection)} v
            JOIN documents d ON d.document_id = v.document_id
            WHERE v.version_id = ?
            """,
            (version_id,),
        ).fetchone()
    finally:
        connection.close()


def has_main_versions(connection):
    return bool(connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='document_main_versions'").fetchone())


def get_main_version(database_path, document_id):
    connection = connect(database_path)
    try:
        if has_main_versions(connection):
            row = connection.execute('SELECT m.version_id FROM document_main_versions m JOIN active_document_versions v USING(version_id) WHERE m.document_id=?', (document_id,)).fetchone()
        else:
            row = connection.execute(f'SELECT version_id FROM {version_table(connection)} WHERE document_id=? ORDER BY imported_at DESC,version_id DESC LIMIT 1', (document_id,)).fetchone()
        return row['version_id'] if row else None
    finally:
        connection.close()


def set_main_version(database_path, version_id, user_id):
    from .access import AccessDenied, authorize_actor, audit
    if not isinstance(user_id, str) or not user_id:
        raise AccessDenied('An authenticated document owner is required.')
    with transaction(database_path) as connection:
        version = connection.execute(f'SELECT document_id FROM {version_table(connection)} WHERE version_id=?', (version_id,)).fetchone()
        if not version:
            raise VersionNotFoundError('The version does not exist.')
        document_id = version['document_id']
        authorize_actor(connection, user_id, document_id)
        previous = connection.execute('SELECT version_id FROM document_main_versions WHERE document_id=?', (document_id,)).fetchone()
        if previous and previous['version_id'] == version_id:
            return document_id
        connection.execute('INSERT INTO document_main_versions(document_id,version_id,selected_by,selected_at) VALUES (?,?,?,?) ON CONFLICT(document_id) DO UPDATE SET version_id=excluded.version_id,selected_by=excluded.selected_by,selected_at=excluded.selected_at', (document_id, version_id, user_id, now_utc()))
        audit(connection, user_id, 'document.main_version', 'document', document_id, previous_version_id=previous['version_id'] if previous else None, version_id=version_id)
        return document_id


def import_version(
    database_path: Path | str,
    blob_store: BlobStore,
    document_id: str,
    source: BinaryIO,
    original_filename: str | None,
    version_label: str | None = None,
    external_source_type: str | None = None,
    external_version_id: str | None = None,
) -> ImportResult:
    """Create an immutable version record for a safely stored PDF copy."""
    filename = normalize_filename(original_filename)
    label = normalize_optional(version_label)
    source_type = normalize_optional(external_source_type, 100)
    external_id = normalize_optional(external_version_id, 300)
    if external_id and not source_type:
        raise DocumentError("An external version ID requires an external source type.")

    with IMPORT_LOCK:
        if get_document(database_path, document_id) is None:
            raise DocumentNotFoundError("The selected document does not exist.")
        blob = blob_store.ingest(source)
        version_id = str(uuid.uuid4())
        try:
            with transaction(database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO document_versions(
                        version_id, document_id, version_label, original_filename,
                        sha256, blob_path, file_size, imported_at,
                        external_source_type, external_version_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        document_id,
                        label,
                        filename,
                        blob.sha256,
                        blob.relative_path,
                        blob.file_size,
                        now_utc(),
                        source_type,
                        external_id,
                    ),
                )
                if has_main_versions(connection):
                    connection.execute('INSERT OR IGNORE INTO document_main_versions(document_id,version_id,selected_at) VALUES (?,?,?)', (document_id, version_id, now_utc()))
        except Exception:
            if blob.created:
                path = blob_store.resolve(blob.relative_path, blob.sha256)
                connection = connect(database_path)
                try:
                    referenced = connection.execute(
                        "SELECT 1 FROM document_versions WHERE sha256 = ? LIMIT 1",
                        (blob.sha256,),
                    ).fetchone()
                finally:
                    connection.close()
                if referenced is None:
                    path.unlink(missing_ok=True)
            raise
    return ImportResult(version_id, blob)


def delete_version(database_path, version_id, user_id, confirmation):
    """Withdraw exactly one version; preserve immutable bytes and review history."""
    from .access import AccessDenied, authorize_actor, audit
    if not isinstance(user_id,str) or not user_id:
        raise AccessDenied('An authenticated document owner is required.')
    with transaction(database_path) as connection:
        version=connection.execute('SELECT * FROM document_versions WHERE version_id=?',(version_id,)).fetchone()
        if version is None:
            raise VersionNotFoundError('The version does not exist.')
        authorize_actor(connection,user_id,version['document_id'])
        if confirmation!=version_id:
            raise DocumentError('Confirm the exact version to delete.')
        if connection.execute('SELECT 1 FROM version_deletions WHERE version_id=?',(version_id,)).fetchone():
            return version['document_id']
        connection.execute('INSERT INTO version_deletions VALUES(?,?,?)',(version_id,user_id,now_utc()))
        if has_main_versions(connection):
            main = connection.execute('SELECT version_id FROM document_main_versions WHERE document_id=?', (version['document_id'],)).fetchone()
            if main and main['version_id'] == version_id:
                replacement = connection.execute('SELECT version_id FROM active_document_versions WHERE document_id=? ORDER BY imported_at DESC,version_id DESC LIMIT 1', (version['document_id'],)).fetchone()
                if replacement:
                    connection.execute('UPDATE document_main_versions SET version_id=?,selected_by=?,selected_at=? WHERE document_id=?', (replacement['version_id'], user_id, now_utc(), version['document_id']))
                else:
                    connection.execute('DELETE FROM document_main_versions WHERE document_id=?', (version['document_id'],))
                audit(connection, user_id, 'document.main_version', 'document', version['document_id'], previous_version_id=version_id, version_id=replacement['version_id'] if replacement else None, reason='version_deleted')
        connection.execute('DELETE FROM reading_leases WHERE session_id IN (SELECT session_id FROM reading_sessions WHERE version_id=?)',(version_id,))
        audit(connection,user_id,'version.delete','version',version_id,document_id=version['document_id'])
        return version['document_id']
