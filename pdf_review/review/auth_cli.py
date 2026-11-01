"""Offline administration; possession of the database is the admin boundary."""

import sqlite3
from functools import wraps

import click
from flask import current_app

from .auth import IdentityDenied, normalize_email
from .database import connect, transaction
from .documents import now_utc


def init_auth_cli(app):
    def command(fn):
        @wraps(fn)
        def safe(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except (IdentityDenied, sqlite3.IntegrityError) as error:
                raise click.ClickException(str(error)) from error
        return app.cli.command()(safe)

    @command
    @click.argument("email")
    @click.option("--note", default=None)
    def allow_email(email, note):
        """Add or re-enable an exact normalized Google email."""
        email = normalize_email(email)
        with transaction(current_app.config["DATABASE"]) as connection:
            connection.execute("""INSERT INTO allowed_emails(normalized_email, created_at, note)
                VALUES (?, ?, ?) ON CONFLICT(normalized_email) DO UPDATE SET enabled = 1, note = excluded.note""",
                (email, now_utc(), note))
        click.echo(f"Enabled {email}")

    @command
    @click.argument("email")
    def disallow_email(email):
        """Disable an email, including existing HTTP sessions."""
        with transaction(current_app.config["DATABASE"]) as connection:
            connection.execute("UPDATE allowed_emails SET enabled = 0 WHERE normalized_email = ?", (normalize_email(email),))
        click.echo("Email disabled.")

    @command
    def list_allowed_emails():
        """List allowlist entries (offline administrators only)."""
        connection = connect(current_app.config["DATABASE"])
        try:
            for row in connection.execute("SELECT * FROM allowed_emails ORDER BY normalized_email"):
                click.echo(f"{row['normalized_email']} enabled={row['enabled']} note={row['note'] or ''}")
        finally:
            connection.close()

    @command
    @click.argument("email")
    @click.argument("user_id")
    def link_google_email(email, user_id):
        """Prepare one legacy user for first Google login; never change a linked subject."""
        email = normalize_email(email)
        with transaction(current_app.config["DATABASE"]) as connection:
            if connection.execute("SELECT 1 FROM allowed_emails WHERE normalized_email = ? AND enabled = 1", (email,)).fetchone() is None:
                raise IdentityDenied("Enable the email first.")
            user = connection.execute("SELECT * FROM users WHERE user_id = ? AND is_active = 1", (user_id,)).fetchone()
            if user is None or user["google_subject"] is not None or user["normalized_email"] not in (None, email):
                raise IdentityDenied("Choose an active, unlinked legacy user without another prepared email.")
            connection.execute("UPDATE users SET email = ?, normalized_email = ?, email_verified = 0 WHERE user_id = ?", (email, email, user_id))
        click.echo(f"Prepared {user_id}; Google must verify {email} at login.")

    @command
    @click.argument("document_id")
    @click.argument("user_id")
    @click.option("--role", type=click.Choice(["owner", "reviewer", "viewer"]), required=True)
    def grant_access(document_id, user_id, role):
        """Explicitly grant a document role; also bootstraps the first owner."""
        with transaction(current_app.config["DATABASE"]) as connection:
            connection.execute("""INSERT INTO document_access(document_id, user_id, role, created_at)
                VALUES (?, ?, ?, ?) ON CONFLICT(document_id, user_id) DO UPDATE SET role = excluded.role""",
                (document_id, user_id, role, now_utc()))
        click.echo(f"Granted {role} on {document_id} to {user_id}")

    @command
    @click.argument("document_id")
    @click.argument("user_id")
    def revoke_access(document_id, user_id):
        """Revoke document access on the next HTTP request / socket join."""
        with transaction(current_app.config["DATABASE"]) as connection:
            connection.execute("DELETE FROM document_access WHERE document_id = ? AND user_id = ?", (document_id, user_id))
        click.echo("Access revoked.")

    @command
    @click.argument("document_id")
    def list_document_access(document_id):
        """List grants for an explicitly identified document."""
        connection = connect(current_app.config["DATABASE"])
        try:
            for row in connection.execute("SELECT * FROM document_access WHERE document_id = ? ORDER BY user_id", (document_id,)):
                click.echo(f"{row['user_id']} {row['role']}")
        finally:
            connection.close()

    @command
    def list_identities():
        """List stable IDs and document IDs for safe legacy bootstrapping."""
        connection = connect(current_app.config["DATABASE"])
        try:
            for row in connection.execute("SELECT user_id, display_name, normalized_email, is_active FROM users ORDER BY created_at"):
                click.echo(f"User {row['user_id']} {row['display_name']} email={row['normalized_email']} active={row['is_active']}")
            for row in connection.execute("SELECT document_id, title FROM documents ORDER BY created_at"):
                click.echo(f"Document {row['document_id']} {row['title']}")
        finally:
            connection.close()
