"""SQLite connection handling and explicit numbered migrations."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


MIGRATIONS = [
    (
        1,
        "documents_and_versions",
        """
        CREATE TABLE documents (
            document_id TEXT PRIMARY KEY,
            title TEXT NOT NULL CHECK (length(trim(title)) > 0),
            created_at TEXT NOT NULL
        );

        CREATE TABLE document_versions (
            version_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            version_label TEXT,
            original_filename TEXT NOT NULL,
            sha256 TEXT NOT NULL
                CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
            blob_path TEXT NOT NULL,
            file_size INTEGER NOT NULL CHECK (file_size >= 0),
            imported_at TEXT NOT NULL,
            external_source_type TEXT,
            external_version_id TEXT,
            extraction_tool TEXT,
            extraction_version TEXT,
            normalization_version TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(document_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            CHECK (version_label IS NULL OR length(trim(version_label)) > 0),
            CHECK (external_source_type IS NOT NULL OR external_version_id IS NULL),
            CHECK (blob_path = 'blobs/' || sha256 || '.pdf'),
            UNIQUE (external_source_type, external_version_id)
        );

        CREATE INDEX idx_document_versions_document
            ON document_versions(document_id, imported_at, version_id);
        CREATE INDEX idx_document_versions_sha256
            ON document_versions(sha256);
        CREATE INDEX idx_document_versions_external
            ON document_versions(external_source_type, external_version_id)
            WHERE external_source_type IS NOT NULL;

        CREATE TRIGGER protect_document_version_bytes
        BEFORE UPDATE OF version_id, document_id, sha256, blob_path, file_size
        ON document_versions
        BEGIN
            SELECT RAISE(ABORT, 'immutable document version bytes cannot be changed');
        END;
        """,
    ),
    (
        2,
        "persistent_anchor_instances",
        """
        CREATE TABLE anchor_instances (
            anchor_id TEXT PRIMARY KEY,
            document_version_id TEXT NOT NULL,
            anchor_kind TEXT NOT NULL
                CHECK (anchor_kind IN ('text', 'point', 'region')),
            selection_text TEXT,
            selector_version TEXT,
            anchor_schema_version INTEGER NOT NULL
                CHECK (anchor_schema_version >= 1),
            created_at TEXT NOT NULL,
            FOREIGN KEY (document_version_id)
                REFERENCES document_versions(version_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            CHECK (
                anchor_kind != 'text'
                OR (
                    selection_text IS NOT NULL
                    AND length(trim(selection_text)) > 0
                    AND selector_version IS NOT NULL
                    AND length(trim(selector_version)) > 0
                )
            )
        );

        CREATE TABLE anchor_segments (
            segment_id TEXT PRIMARY KEY,
            anchor_id TEXT NOT NULL,
            segment_index INTEGER NOT NULL CHECK (segment_index >= 0),
            page_number INTEGER NOT NULL CHECK (page_number >= 1),
            rectangles_json TEXT NOT NULL
                CHECK (
                    json_valid(rectangles_json)
                    AND json_type(rectangles_json) = 'array'
                ),
            pdf_view_box_json TEXT NOT NULL
                CHECK (
                    json_valid(pdf_view_box_json)
                    AND json_type(pdf_view_box_json) = 'array'
                ),
            capture_viewport_width REAL NOT NULL
                CHECK (capture_viewport_width > 0),
            capture_viewport_height REAL NOT NULL
                CHECK (capture_viewport_height > 0),
            capture_rotation INTEGER NOT NULL
                CHECK (capture_rotation IN (0, 90, 180, 270)),
            exact_text TEXT,
            prefix_text TEXT,
            suffix_text TEXT,
            text_start INTEGER,
            text_end INTEGER,
            page_text_sha256 TEXT
                CHECK (
                    page_text_sha256 IS NULL
                    OR (
                        length(page_text_sha256) = 64
                        AND page_text_sha256 NOT GLOB '*[^0-9a-f]*'
                    )
                ),
            FOREIGN KEY (anchor_id)
                REFERENCES anchor_instances(anchor_id)
                ON UPDATE RESTRICT ON DELETE CASCADE,
            UNIQUE (anchor_id, segment_index),
            UNIQUE (anchor_id, page_number),
            CHECK (
                (text_start IS NULL AND text_end IS NULL)
                OR (
                    text_start IS NOT NULL
                    AND text_end IS NOT NULL
                    AND text_start >= 0
                    AND text_end >= text_start
                )
            )
        );

        CREATE INDEX idx_anchor_instances_version
            ON anchor_instances(document_version_id, created_at, anchor_id);
        CREATE INDEX idx_anchor_segments_anchor
            ON anchor_segments(anchor_id, segment_index);
        CREATE INDEX idx_anchor_segments_page
            ON anchor_segments(page_number, anchor_id);

        CREATE TRIGGER protect_anchor_instance_contents
        BEFORE UPDATE ON anchor_instances
        BEGIN
            SELECT RAISE(ABORT, 'anchor instances are immutable');
        END;

        CREATE TRIGGER protect_anchor_segment_contents
        BEFORE UPDATE ON anchor_segments
        BEGIN
            SELECT RAISE(ABORT, 'anchor segments are immutable');
        END;
        """,
    ),
    (
        3,
        "review_threads_and_comments",
        """
        CREATE TABLE users (
            user_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL
                CHECK (length(trim(display_name)) BETWEEN 1 AND 100),
            is_active INTEGER NOT NULL DEFAULT 1
                CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX idx_users_display_name
            ON users(display_name COLLATE NOCASE);

        CREATE TABLE threads (
            thread_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            created_by_user_id TEXT NOT NULL,
            origin_thread_target_id TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'resolved')),
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            resolved_by_user_id TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(document_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            FOREIGN KEY (created_by_user_id) REFERENCES users(user_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            FOREIGN KEY (resolved_by_user_id) REFERENCES users(user_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            FOREIGN KEY (origin_thread_target_id)
                REFERENCES thread_targets(thread_target_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT
                DEFERRABLE INITIALLY DEFERRED,
            CHECK (
                (status = 'open' AND resolved_at IS NULL AND resolved_by_user_id IS NULL)
                OR
                (status = 'resolved' AND resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)
            )
        );

        CREATE TABLE thread_targets (
            thread_target_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            anchor_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('origin', 'projection', 'manual')),
            created_at TEXT NOT NULL,
            FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            FOREIGN KEY (anchor_id) REFERENCES anchor_instances(anchor_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            UNIQUE (thread_id, anchor_id)
        );

        CREATE UNIQUE INDEX idx_thread_targets_one_origin
            ON thread_targets(thread_id)
            WHERE role = 'origin';
        CREATE INDEX idx_thread_targets_anchor
            ON thread_targets(anchor_id, thread_id);

        CREATE TABLE comments (
            comment_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            author_id TEXT NOT NULL,
            body TEXT,
            created_at TEXT NOT NULL,
            edited_at TEXT,
            deleted_at TEXT,
            deleted_by_user_id TEXT,
            FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            FOREIGN KEY (author_id) REFERENCES users(user_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            FOREIGN KEY (deleted_by_user_id) REFERENCES users(user_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            CHECK (
                (deleted_at IS NULL AND deleted_by_user_id IS NULL
                    AND body IS NOT NULL AND length(trim(body)) > 0)
                OR
                (deleted_at IS NOT NULL AND deleted_by_user_id IS NOT NULL AND body IS NULL)
            )
        );

        CREATE INDEX idx_comments_thread
            ON comments(thread_id, created_at, comment_id);

        CREATE TABLE comment_revisions (
            revision_id TEXT PRIMARY KEY,
            comment_id TEXT NOT NULL,
            revision_number INTEGER NOT NULL CHECK (revision_number >= 1),
            body TEXT NOT NULL CHECK (length(trim(body)) > 0),
            created_at TEXT NOT NULL,
            editor_id TEXT NOT NULL,
            FOREIGN KEY (comment_id) REFERENCES comments(comment_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            FOREIGN KEY (editor_id) REFERENCES users(user_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            UNIQUE (comment_id, revision_number)
        );

        CREATE INDEX idx_comment_revisions_comment
            ON comment_revisions(comment_id, revision_number);

        CREATE TRIGGER validate_thread_target_insert
        BEFORE INSERT ON thread_targets
        BEGIN
            SELECT CASE
                WHEN (
                    SELECT t.document_id
                    FROM threads t
                    WHERE t.thread_id = NEW.thread_id
                ) != (
                    SELECT v.document_id
                    FROM anchor_instances a
                    JOIN document_versions v
                        ON v.version_id = a.document_version_id
                    WHERE a.anchor_id = NEW.anchor_id
                )
                THEN RAISE(ABORT, 'thread target document mismatch')
            END;
            SELECT CASE
                WHEN NEW.role = 'origin' AND (
                    SELECT origin_thread_target_id
                    FROM threads WHERE thread_id = NEW.thread_id
                ) != NEW.thread_target_id
                THEN RAISE(ABORT, 'origin target does not match designated thread origin')
            END;
            SELECT CASE
                WHEN NEW.role != 'origin' AND (
                    SELECT origin_thread_target_id
                    FROM threads WHERE thread_id = NEW.thread_id
                ) = NEW.thread_target_id
                THEN RAISE(ABORT, 'designated thread origin must use origin role')
            END;
        END;

        CREATE TRIGGER protect_thread_identity
        BEFORE UPDATE OF thread_id, document_id, created_by_user_id,
                         origin_thread_target_id, created_at
        ON threads
        BEGIN
            SELECT RAISE(ABORT, 'thread identity and origin are immutable');
        END;

        CREATE TRIGGER protect_thread_target_contents
        BEFORE UPDATE ON thread_targets
        BEGIN
            SELECT RAISE(ABORT, 'thread targets are immutable');
        END;

        CREATE TRIGGER protect_origin_thread_target
        BEFORE DELETE ON thread_targets
        WHEN OLD.role = 'origin'
        BEGIN
            SELECT RAISE(ABORT, 'origin thread targets cannot be deleted');
        END;

        CREATE TRIGGER protect_comment_identity
        BEFORE UPDATE OF comment_id, thread_id, author_id, created_at
        ON comments
        BEGIN
            SELECT RAISE(ABORT, 'comment identity is immutable');
        END;

        CREATE TRIGGER protect_comment_revisions
        BEFORE UPDATE ON comment_revisions
        BEGIN
            SELECT RAISE(ABORT, 'comment revisions are immutable');
        END;

        CREATE TRIGGER prevent_comment_revision_deletion
        BEFORE DELETE ON comment_revisions
        BEGIN
            SELECT RAISE(ABORT, 'comment revisions cannot be deleted');
        END;
        """,
    ),
    (
        4,
        "thread_status_history",
        """
        CREATE TABLE thread_status_changes (
            change_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL REFERENCES threads(thread_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            sequence_number INTEGER NOT NULL CHECK (sequence_number >= 1),
            action TEXT NOT NULL CHECK (action IN ('resolved', 'reopened')),
            actor_id TEXT NOT NULL REFERENCES users(user_id)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            created_at TEXT NOT NULL,
            UNIQUE (thread_id, sequence_number)
        );

        -- Only existing current resolutions have known attribution. Never invent
        -- actors or timestamps for historical reopen actions that were not stored.
        INSERT INTO thread_status_changes
            (change_id, thread_id, sequence_number, action, actor_id, created_at)
        SELECT lower(hex(randomblob(16))), thread_id, 1, 'resolved',
               resolved_by_user_id, resolved_at
        FROM threads WHERE status = 'resolved';

        CREATE TRIGGER protect_thread_status_changes
        BEFORE UPDATE ON thread_status_changes
        BEGIN
            SELECT RAISE(ABORT, 'thread status history is immutable');
        END;

        CREATE TRIGGER prevent_thread_status_change_deletion
        BEFORE DELETE ON thread_status_changes
        BEGIN
            SELECT RAISE(ABORT, 'thread status history cannot be deleted');
        END;
        """,
    ),
]


MIGRATIONS.append((5, "manual_carry_forward", Path(__file__).with_name("migration5.sql").read_text(encoding="utf-8")))
MIGRATIONS.append((6, "google_identity_and_document_access", Path(__file__).with_name("migration6.sql").read_text(encoding="utf-8")))
MIGRATIONS.append((7, "accounts_sharing_and_site_admins", Path(__file__).with_name("migration7.sql").read_text(encoding="utf-8")))
MIGRATIONS.append((8, "review_policy_preferences_and_sections", Path(__file__).with_name("migration8.sql").read_text(encoding="utf-8")))
MIGRATIONS.append((9, "tableau_review_palette", Path(__file__).with_name("migration9.sql").read_text(encoding="utf-8")))
MIGRATIONS.append((10, "document_download_controls", Path(__file__).with_name("migration10.sql").read_text(encoding="utf-8")))


def connect(database_path: Path | str) -> sqlite3.Connection:
    """Open a configured SQLite connection."""
    connection = sqlite3.connect(str(database_path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def init_database(database_path: Path | str) -> None:
    """Create the database and apply each unapplied migration once."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
        applied = {
            row["version"]
            for row in connection.execute("SELECT version FROM schema_migrations")
        }
        for version, name, sql in MIGRATIONS:
            if version in applied:
                continue
            safe_name = name.replace("'", "''")
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + sql
                + f"\nINSERT INTO schema_migrations(version, name, applied_at) "
                f"VALUES ({version}, '{safe_name}', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));\n"
                + "COMMIT;"
            )
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def transaction(database_path: Path | str) -> Iterator[sqlite3.Connection]:
    """Provide a connection whose work commits or rolls back as one unit."""
    connection = connect(database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
