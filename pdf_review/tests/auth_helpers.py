"""Explicit isolated authentication fixtures; never installed in application routes."""

from flask.testing import FlaskClient

from review.auth import SESSION_KEY
from review.database import transaction
from review.documents import now_utc
from review.users import create_user


def authenticate(client, user_id=None, *, grant_documents=True):
    database = client.application.config["DATABASE"]
    with transaction(database) as connection:
        if user_id is None:
            row = connection.execute("SELECT user_id FROM users ORDER BY created_at, user_id LIMIT 1").fetchone()
            user_id = row[0] if row else None
    if user_id is None:
        user_id = create_user(database, "Authenticated fixture")["user_id"]
    email = f"{user_id}@example.test"
    with transaction(database) as connection:
        connection.execute("INSERT OR IGNORE INTO allowed_emails(normalized_email, created_at) VALUES (?, ?)", (email, now_utc()))
        connection.execute("UPDATE users SET google_subject = COALESCE(google_subject, ?), normalized_email = ?, email = ?, email_verified = 1 WHERE user_id = ?",
                           (f"test-sub-{user_id}", email, email, user_id))
        if grant_documents:
            connection.execute("INSERT OR IGNORE INTO document_access(document_id, user_id, role, created_at) SELECT document_id, ?, 'owner', ? FROM documents", (user_id, now_utc()))
    with client.session_transaction() as state:
        state.clear()
        state[SESSION_KEY] = user_id
        state["csrf_token"] = "fixture-csrf-token"
    return user_id


class CsrfClient(FlaskClient):
    """Simulate app-owned frontend attaching CSRF; security tests use plain clients."""
    def open(self, *args, **kwargs):
        if kwargs.get("method", "GET").upper() in {"POST", "PATCH", "PUT", "DELETE"}:
            with self.session_transaction() as state:
                token = state.get("csrf_token", "")
            kwargs.setdefault("headers", {}).setdefault("X-CSRF-Token", token)
        return super().open(*args, **kwargs)


def secure_client(app, user_id=None):
    client = CsrfClient(app, app.response_class, use_cookies=True)
    authenticate(client, user_id)
    return client
