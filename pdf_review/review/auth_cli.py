"""Offline administration; possession of the database is the admin boundary."""

import sqlite3
from functools import wraps

import click
from flask import current_app

from .auth import IdentityDenied, normalize_email
from .database import connect, transaction
from . import access


def init_auth_cli(app):
    def command(fn):
        @wraps(fn)
        def safe(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except (IdentityDenied, access.AccessError, sqlite3.IntegrityError) as error:
                raise click.ClickException(str(error)) from error
        return app.cli.command()(safe)

    @command
    @click.argument("email")
    @click.option("--note", default=None)
    def allow_email(email, note):
        """Add or re-enable an exact normalized Google email."""
        email = normalize_email(email)
        access.set_allowed_email(current_app.config['DATABASE'], email, 'allow', note=note)
        click.echo(f"Enabled {email}")

    @command
    @click.argument("email")
    def disallow_email(email):
        """Disable an email, including existing HTTP sessions."""
        access.set_allowed_email(current_app.config['DATABASE'], email, 'disable')
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
        access.set_document_access(current_app.config['DATABASE'], document_id, user_id, role)
        click.echo(f"Granted {role} on {document_id} to {user_id}")

    @command
    @click.argument("document_id")
    @click.argument("user_id")
    def revoke_access(document_id, user_id):
        """Revoke document access on the next HTTP request / socket join."""
        access.set_document_access(current_app.config['DATABASE'], document_id, user_id, None)
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

    @command
    def list_site_admins():
        """List explicit site administrators by stable local ID."""
        for user in access.list_site_admins(current_app.config['DATABASE']):
            click.echo(f"{user['user_id']} {user['display_name']} {user['email']}")

    @command
    @click.argument('user_id')
    def grant_site_admin(user_id):
        """Bootstrap/promote an existing active Google-linked beta user."""
        access.set_site_admin(current_app.config['DATABASE'], user_id, True)
        click.echo('Site administrator granted.')

    @command
    @click.argument('user_id')
    def revoke_site_admin(user_id):
        """Revoke site administration, retaining an active successor."""
        access.set_site_admin(current_app.config['DATABASE'], user_id, False)
        click.echo('Site administrator revoked.')

    @command
    @click.argument('email')
    @click.option('--confirm-established', is_flag=True, help='Acknowledge loss of sign-in for an established account; identity and history are retained.')
    def remove_email(email, confirm_established):
        """Delete only an erroneous allowlist entry, never the stable user/history."""
        access.set_allowed_email(current_app.config['DATABASE'], email, 'remove', confirmed=confirm_established)
        click.echo('Allowlist entry removed; identity and history retained.')

    @command
    def expire_invitations():
        """Record expired invitation states; run periodically if desired."""
        from .invitations import expire_pending
        with transaction(current_app.config['DATABASE']) as connection:
            expire_pending(connection)
        click.echo('Expired invitations recorded.')

    @command
    @click.argument('admin_user_id')
    def attribute_legacy_invitations(admin_user_id):
        """Attribute unassigned historical memberships to an existing admin."""
        from .invitations import backfill_legacy
        backfill_legacy(current_app.config['DATABASE'], admin_user_id)
        click.echo('Unassigned historical memberships attributed; dates unchanged.')
