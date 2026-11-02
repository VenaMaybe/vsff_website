"""Stable user records; Google linking and authentication belong to auth.py."""

from __future__ import annotations

import sqlite3
import uuid
import unicodedata
from pathlib import Path
from typing import Any

from .database import connect, transaction
from .documents import now_utc


MAX_DISPLAY_NAME_LENGTH = 100


class UserError(RuntimeError):
    """Base class for controlled local-identity errors."""


class UserValidationError(UserError):
    """A local identity request failed validation."""


class UserNotFoundError(UserError):
    """The requested stable user does not exist or is inactive."""


def normalize_display_name(value: Any) -> str:
    if not isinstance(value, str):
        raise UserValidationError("Display name must be text.")
    if any(unicodedata.category(c).startswith('C') for c in value):
        raise UserValidationError("Display name must not contain control or hidden formatting characters.")
    display_name = value.strip()
    if not display_name:
        raise UserValidationError("Display name is required.")
    if len(display_name) > MAX_DISPLAY_NAME_LENGTH:
        raise UserValidationError(
            f"Display name must be {MAX_DISPLAY_NAME_LENGTH} characters or fewer."
        )
    return display_name


def _serialize_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "display_name": row["display_name"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


def create_user(database_path: Path | str, display_name: Any) -> dict[str, Any]:
    name = normalize_display_name(display_name)
    user_id = str(uuid.uuid4())
    try:
        with transaction(database_path) as connection:
            connection.execute(
                """
                INSERT INTO users(user_id, display_name, is_active, created_at)
                VALUES (?, ?, 1, ?)
                """,
                (user_id, name, now_utc()),
            )
    except sqlite3.IntegrityError as error:
        if "users.display_name" in str(error) or "idx_users_display_name" in str(error):
            raise UserValidationError("That local reviewer name already exists.") from error
        raise
    return get_user(database_path, user_id)


def get_user(
    database_path: Path | str, user_id: str, *, require_active: bool = False
) -> dict[str, Any]:
    connection = connect(database_path)
    try:
        row = connection.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    finally:
        connection.close()
    if row is None or (require_active and not row["is_active"]):
        raise UserNotFoundError("The selected local reviewer does not exist or is inactive.")
    return _serialize_user(row)


def list_users(database_path: Path | str) -> list[dict[str, Any]]:
    connection = connect(database_path)
    try:
        rows = connection.execute(
            """
            SELECT * FROM users
            WHERE is_active = 1
            ORDER BY display_name COLLATE NOCASE ASC, user_id ASC
            """
        ).fetchall()
        return [_serialize_user(row) for row in rows]
    finally:
        connection.close()


def require_active_user(connection: sqlite3.Connection, user_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM users WHERE user_id = ? AND is_active = 1", (user_id,)
    ).fetchone()
    if row is None:
        raise UserNotFoundError("An active authenticated user is required.")
    return row
