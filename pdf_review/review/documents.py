"""Document and immutable-version persistence services."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from .database import connect, transaction
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
        return connection.execute(
            """
            SELECT d.*, COUNT(v.version_id) AS version_count,
                   MAX(v.imported_at) AS last_imported_at
            FROM documents d
            LEFT JOIN document_versions v ON v.document_id = d.document_id
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
            """
            SELECT * FROM document_versions
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
            """
            SELECT v.*, d.title AS document_title
            FROM document_versions v
            JOIN documents d ON d.document_id = v.document_id
            WHERE v.version_id = ?
            """,
            (version_id,),
        ).fetchone()
    finally:
        connection.close()


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
