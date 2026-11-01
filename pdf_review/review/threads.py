"""Transactional review threads, comments, revisions, and resolution state."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .anchors import (
    AnchorVersionNotFoundError,
    get_anchor,
    insert_validated_anchor,
    validate_anchor_payload,
)
from .database import connect, transaction
from .documents import now_utc
from .users import UserNotFoundError, require_active_user


MAX_COMMENT_BODY_LENGTH = 10_000
MAX_THREAD_PAYLOAD_BYTES = 2 * 1024 * 1024 + 32 * 1024


class ThreadError(RuntimeError):
    """Base class for controlled discussion errors."""


class ThreadValidationError(ThreadError):
    """A discussion request failed validation."""


class ThreadNotFoundError(ThreadError):
    """The requested thread does not exist."""


class CommentNotFoundError(ThreadError):
    """The requested comment does not exist."""


class CommentPermissionError(ThreadError):
    """Only the authenticated original author may edit or delete a comment."""


class CommentConflictError(ThreadError):
    """The editor loaded an older immutable revision."""

    def __init__(self, current_revision):
        super().__init__("This comment changed in another browser. Review the latest version before saving again.")
        self.current_revision = current_revision


def validate_comment_body(value: Any) -> str:
    if not isinstance(value, str):
        raise ThreadValidationError("Comment body must be text.")
    if not value.strip():
        raise ThreadValidationError("Comment body must not be empty.")
    if len(value) > MAX_COMMENT_BODY_LENGTH:
        raise ThreadValidationError(
            f"Comment body must be {MAX_COMMENT_BODY_LENGTH} characters or fewer."
        )
    return value


def _user_summary(row: sqlite3.Row, prefix: str) -> dict[str, Any] | None:
    user_id = row[f"{prefix}_user_id"]
    if user_id is None:
        return None
    return {
        "user_id": user_id,
        "display_name": row[f"{prefix}_display_name"],
    }


def _comment_rows(connection: sqlite3.Connection, thread_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT c.*, u.display_name AS author_display_name,
               du.display_name AS deleted_by_display_name,
               COUNT(r.revision_id) AS revision_count,
               MAX(r.revision_number) AS current_revision
        FROM comments c
        JOIN users u ON u.user_id = c.author_id
        LEFT JOIN users du ON du.user_id = c.deleted_by_user_id
        LEFT JOIN comment_revisions r ON r.comment_id = c.comment_id
        WHERE c.thread_id = ?
        GROUP BY c.comment_id
        ORDER BY c.created_at ASC, c.comment_id ASC
        """,
        (thread_id,),
    ).fetchall()
    return [
        {
            "comment_id": row["comment_id"],
            "thread_id": row["thread_id"],
            "author": {
                "user_id": row["author_id"],
                "display_name": row["author_display_name"],
            },
            "body": None if row["deleted_at"] is not None else row["body"],
            "created_at": row["created_at"],
            "edited_at": row["edited_at"],
            "is_deleted": row["deleted_at"] is not None,
            "deleted_at": row["deleted_at"],
            "deleted_by": (
                {
                    "user_id": row["deleted_by_user_id"],
                    "display_name": row["deleted_by_display_name"],
                }
                if row["deleted_by_user_id"] is not None
                else None
            ),
            "revision_count": row["revision_count"],
            "current_revision": row["current_revision"],
        }
        for row in rows
    ]


def _target_rows(
    connection: sqlite3.Connection, thread_id: str, version_id: str | None
) -> list[sqlite3.Row]:
    parameters: list[Any] = [thread_id]
    version_clause = ""
    if version_id is not None:
        version_clause = "AND a.document_version_id = ?"
        parameters.append(version_id)
    return connection.execute(
        f"""
        SELECT tt.*
        FROM thread_target_heads h
        JOIN thread_targets tt ON tt.thread_target_id = h.thread_target_id
        JOIN anchor_instances a ON a.anchor_id = tt.anchor_id
        WHERE tt.thread_id = ? {version_clause}
        ORDER BY CASE tt.role WHEN 'origin' THEN 0 WHEN 'projection' THEN 1 ELSE 2 END,
                 tt.created_at ASC, tt.thread_target_id ASC
        """,
        parameters,
    ).fetchall()


def _thread_row(connection: sqlite3.Connection, thread_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT t.*,
               creator.user_id AS creator_user_id,
               creator.display_name AS creator_display_name,
               resolver.user_id AS resolver_user_id,
               resolver.display_name AS resolver_display_name
        FROM threads t
        JOIN users creator ON creator.user_id = t.created_by_user_id
        LEFT JOIN users resolver ON resolver.user_id = t.resolved_by_user_id
        WHERE t.thread_id = ?
        """,
        (thread_id,),
    ).fetchone()
    if row is None:
        raise ThreadNotFoundError("The review thread does not exist.")
    return row


def get_thread(
    database_path: Path | str, thread_id: str, version_id: str | None = None
) -> dict[str, Any]:
    connection = connect(database_path)
    try:
        connection.execute("BEGIN")
        row = _thread_row(connection, thread_id)
        targets = _target_rows(connection, thread_id, version_id)
        comments = _comment_rows(connection, thread_id)
        status_changes = connection.execute(
            """SELECT sc.*, u.display_name FROM thread_status_changes sc
               JOIN users u ON u.user_id = sc.actor_id
               WHERE sc.thread_id = ? ORDER BY sc.sequence_number""",
            (thread_id,),
        ).fetchall()
    finally:
        connection.close()
    return {
        "thread_id": row["thread_id"],
        "document_id": row["document_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "created_by": _user_summary(row, "creator"),
        "resolved_at": row["resolved_at"],
        "resolved_by": _user_summary(row, "resolver"),
        "targets": [
            {
                "thread_target_id": target["thread_target_id"],
                "role": target["role"],
                "created_at": target["created_at"],
                "anchor": get_anchor(database_path, target["anchor_id"]),
            }
            for target in targets
        ],
        "comments": comments,
        "status_history": [
            {"change_id": change["change_id"], "action": change["action"],
             "created_at": change["created_at"],
             "actor": {"user_id": change["actor_id"], "display_name": change["display_name"]}}
            for change in status_changes
        ],
    }


def list_threads(database_path: Path | str, version_id: str) -> list[dict[str, Any]]:
    connection = connect(database_path)
    try:
        version = connection.execute(
            "SELECT 1 FROM document_versions WHERE version_id = ?", (version_id,)
        ).fetchone()
        if version is None:
            raise AnchorVersionNotFoundError("The document version does not exist.")
        rows = connection.execute(
            """
            SELECT DISTINCT t.thread_id,
                   first_segment.page_number AS first_page,
                   json_extract(first_segment.rectangles_json, '$[0][3]') AS first_top
            FROM threads t
            JOIN thread_target_heads h ON h.thread_id = t.thread_id
            JOIN thread_targets tt ON tt.thread_target_id = h.thread_target_id
            JOIN anchor_instances a ON a.anchor_id = tt.anchor_id
            JOIN anchor_segments first_segment
              ON first_segment.anchor_id = a.anchor_id
             AND first_segment.segment_index = 0
            WHERE a.document_version_id = ?
            ORDER BY first_page ASC, first_top DESC, t.created_at ASC, t.thread_id ASC
            """,
            (version_id,),
        ).fetchall()
    finally:
        connection.close()
    return [get_thread(database_path, row["thread_id"], version_id) for row in rows]


def _insert_revision(
    connection: sqlite3.Connection,
    comment_id: str,
    revision_number: int,
    body: str,
    editor_id: str,
    timestamp: str,
) -> None:
    connection.execute(
        """
        INSERT INTO comment_revisions(
            revision_id, comment_id, revision_number, body, created_at, editor_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), comment_id, revision_number, body, timestamp, editor_id),
    )


def _insert_comment(
    connection: sqlite3.Connection,
    thread_id: str,
    author_id: str,
    body: str,
    timestamp: str,
) -> str:
    comment_id = str(uuid.uuid4())
    connection.execute(
        """
        INSERT INTO comments(comment_id, thread_id, author_id, body, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (comment_id, thread_id, author_id, body, timestamp),
    )
    _insert_revision(connection, comment_id, 1, body, author_id, timestamp)
    return comment_id


def create_thread(
    database_path: Path | str,
    version_id: str,
    author_id: str,
    anchor_payload: Any,
    body: Any,
) -> dict[str, Any]:
    """Atomically create anchor, thread, origin target, root comment, and revision."""
    validated_anchor = validate_anchor_payload(anchor_payload)
    validated_body = validate_comment_body(body)
    thread_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    timestamp = now_utc()
    with transaction(database_path) as connection:
        require_active_user(connection, author_id)
        version = connection.execute(
            "SELECT document_id FROM document_versions WHERE version_id = ?",
            (version_id,),
        ).fetchone()
        if version is None:
            raise AnchorVersionNotFoundError("The document version does not exist.")
        anchor_id = insert_validated_anchor(connection, version_id, validated_anchor)
        connection.execute(
            """
            INSERT INTO threads(
                thread_id, document_id, created_by_user_id,
                origin_thread_target_id, status, created_at
            ) VALUES (?, ?, ?, ?, 'open', ?)
            """,
            (thread_id, version["document_id"], author_id, target_id, timestamp),
        )
        connection.execute(
            """
            INSERT INTO thread_targets(
                thread_target_id, thread_id, anchor_id, role, created_at
            ) VALUES (?, ?, ?, 'origin', ?)
            """,
            (target_id, thread_id, anchor_id, timestamp),
        )
        _insert_comment(connection, thread_id, author_id, validated_body, timestamp)
    return get_thread(database_path, thread_id, version_id)


def add_comment(
    database_path: Path | str, thread_id: str, author_id: str, body: Any
) -> dict[str, Any]:
    validated_body = validate_comment_body(body)
    timestamp = now_utc()
    with transaction(database_path) as connection:
        require_active_user(connection, author_id)
        if connection.execute(
            "SELECT 1 FROM threads WHERE thread_id = ?", (thread_id,)
        ).fetchone() is None:
            raise ThreadNotFoundError("The review thread does not exist.")
        _insert_comment(connection, thread_id, author_id, validated_body, timestamp)
    return get_thread(database_path, thread_id)


def edit_comment(
    database_path: Path | str, comment_id: str, editor_id: str, body: Any,
    expected_revision: Any = None,
) -> dict[str, Any]:
    validated_body = validate_comment_body(body)
    timestamp = now_utc()
    with transaction(database_path) as connection:
        require_active_user(connection, editor_id)
        comment = connection.execute(
            "SELECT * FROM comments WHERE comment_id = ?", (comment_id,)
        ).fetchone()
        if comment is None:
            raise CommentNotFoundError("The comment does not exist.")
        if comment["author_id"] != editor_id:
            raise CommentPermissionError("You can only edit your own comments.")
        if comment["deleted_at"] is not None:
            raise ThreadValidationError("A deleted comment cannot be edited.")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ThreadValidationError("expected_revision must be a positive integer.")
        current_revision = connection.execute(
            "SELECT MAX(revision_number) FROM comment_revisions WHERE comment_id = ?",
            (comment_id,),
        ).fetchone()[0]
        if expected_revision != current_revision:
            raise CommentConflictError(current_revision)
        if comment["body"] != validated_body:
            revision_number = current_revision + 1
            _insert_revision(
                connection,
                comment_id,
                revision_number,
                validated_body,
                editor_id,
                timestamp,
            )
            connection.execute(
                "UPDATE comments SET body = ?, edited_at = ? WHERE comment_id = ?",
                (validated_body, timestamp, comment_id),
            )
        thread_id = comment["thread_id"]
    return get_thread(database_path, thread_id)


def delete_comment(
    database_path: Path | str, comment_id: str, deleted_by_user_id: str
) -> dict[str, Any]:
    timestamp = now_utc()
    with transaction(database_path) as connection:
        require_active_user(connection, deleted_by_user_id)
        comment = connection.execute(
            "SELECT * FROM comments WHERE comment_id = ?", (comment_id,)
        ).fetchone()
        if comment is None:
            raise CommentNotFoundError("The comment does not exist.")
        if comment["author_id"] != deleted_by_user_id:
            raise CommentPermissionError("You can only delete your own comments.")
        if comment["deleted_at"] is None:
            connection.execute(
                """
                UPDATE comments
                SET body = NULL, deleted_at = ?, deleted_by_user_id = ?
                WHERE comment_id = ?
                """,
                (timestamp, deleted_by_user_id, comment_id),
            )
        thread_id = comment["thread_id"]
    return get_thread(database_path, thread_id)


def set_thread_resolved(
    database_path: Path | str,
    thread_id: str,
    user_id: str,
    resolved: bool,
) -> dict[str, Any]:
    timestamp = now_utc()
    with transaction(database_path) as connection:
        require_active_user(connection, user_id)
        thread = connection.execute(
            "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        if thread is None:
            raise ThreadNotFoundError("The review thread does not exist.")
        desired_status = "resolved" if resolved else "open"
        if thread["status"] != desired_status:
            connection.execute(
                """INSERT INTO thread_status_changes
                   (change_id, thread_id, sequence_number, action, actor_id, created_at)
                   SELECT ?, ?, COALESCE(MAX(sequence_number), 0) + 1, ?, ?, ?
                   FROM thread_status_changes WHERE thread_id = ?""",
                (str(uuid.uuid4()), thread_id, "resolved" if resolved else "reopened",
                 user_id, timestamp, thread_id),
            )
        if resolved and thread["status"] != "resolved":
            connection.execute(
                """
                UPDATE threads
                SET status = 'resolved', resolved_at = ?, resolved_by_user_id = ?
                WHERE thread_id = ?
                """,
                (timestamp, user_id, thread_id),
            )
        elif not resolved and thread["status"] != "open":
            connection.execute(
                """
                UPDATE threads
                SET status = 'open', resolved_at = NULL, resolved_by_user_id = NULL
                WHERE thread_id = ?
                """,
                (thread_id,),
            )
    return get_thread(database_path, thread_id)
