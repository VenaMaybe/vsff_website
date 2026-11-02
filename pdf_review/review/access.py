"""Transactional account/access services shared by HTTP and offline recovery CLI.

An absent actor is reserved for the offline CLI; HTTP always supplies its session
user. Authorization is rechecked inside the write transaction to avoid stale
owner/admin decisions. Audit details use fixed keys, never arbitrary form data.
"""

import json

from .database import connect, transaction
from .documents import now_utc
from .users import normalize_display_name


class AccessError(ValueError):
    pass


class AccessDenied(PermissionError):
    pass


ELIGIBLE = """SELECT u.user_id, u.display_name, u.email FROM users u
    JOIN allowed_emails a ON a.normalized_email = u.normalized_email
    WHERE u.is_active = 1 AND u.email_verified = 1
      AND u.google_subject IS NOT NULL AND a.enabled = 1"""


def rows(database, sql, args=()):
    connection = connect(database)
    try:
        return [dict(row) for row in connection.execute(sql, args)]
    finally:
        connection.close()


def is_site_admin(database, user_id):
    return bool(rows(database, "SELECT 1 FROM site_admins WHERE user_id = ?", (user_id,)))


def authorize_actor(connection, actor, document_id=None):
    if actor is None:  # Trusted offline operator, not an HTTP option.
        return
    if not connection.execute(ELIGIBLE + " AND u.user_id = ?", (actor,)).fetchone():
        raise AccessDenied("An active beta account is required.")
    if document_id is not None:
        permitted = connection.execute("SELECT 1 FROM document_access WHERE document_id = ? AND user_id = ? AND role = 'owner'", (document_id, actor)).fetchone()
    else:
        permitted = connection.execute("SELECT 1 FROM site_admins WHERE user_id = ?", (actor,)).fetchone()
    if not permitted:
        raise AccessDenied("Permission has changed. Refresh and try again.")


def audit(connection, actor, action, target_type, target, **details):
    connection.execute("""INSERT INTO access_audit_log
        (actor_user_id, action, target_type, target_identifier, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)""", (actor, action, target_type, target,
        json.dumps(details, sort_keys=True), now_utc()))


def update_profile(database, user_id, display_name):
    name = normalize_display_name(display_name)
    with transaction(database) as connection:
        if not connection.execute(ELIGIBLE + " AND u.user_id = ?", (user_id,)).fetchone():
            raise AccessDenied("An active beta account is required.")
        connection.execute("UPDATE users SET display_name = ? WHERE user_id = ?", (name, user_id))


def account_documents(database, user_id):
    return rows(database, """SELECT d.document_id, d.title, a.role FROM documents d
        JOIN document_access a ON a.document_id = d.document_id WHERE a.user_id = ?
        ORDER BY d.title COLLATE NOCASE, d.document_id""", (user_id,))


def shareable_users(database):
    return rows(database, ELIGIBLE + " ORDER BY u.display_name COLLATE NOCASE, u.email")


def document_grants(database, document_id):
    return rows(database, """SELECT u.user_id, u.display_name, u.email, u.email_verified, a.role
        FROM document_access a JOIN users u ON u.user_id = a.user_id
        WHERE a.document_id = ? ORDER BY u.display_name COLLATE NOCASE, u.user_id""", (document_id,))


def set_document_access(database, document_id, user_id, role, *, actor=None):
    if role not in {None, 'owner', 'reviewer', 'viewer'}:
        raise AccessError("Choose owner, reviewer or viewer.")
    with transaction(database) as connection:
        authorize_actor(connection, actor, document_id)
        if not connection.execute("SELECT 1 FROM documents WHERE document_id = ?", (document_id,)).fetchone():
            raise AccessError("Document does not exist.")
        old = connection.execute("SELECT role FROM document_access WHERE document_id = ? AND user_id = ?", (document_id, user_id)).fetchone()
        if old and old['role'] == 'owner' and role != 'owner':
            count = connection.execute("SELECT count(*) FROM document_access WHERE document_id = ? AND role = 'owner'", (document_id,)).fetchone()[0]
            if count <= 1:
                raise AccessError("A document must retain at least one owner. Add another owner first.")
        if role is not None:
            # Offline CLI retains legacy-user bootstrap; owner UI requires a joined beta identity.
            query = ELIGIBLE + " AND u.user_id = ?" if actor is not None else "SELECT 1 FROM users WHERE user_id = ?"
            if not connection.execute(query, (user_id,)).fetchone():
                raise AccessError("Choose an existing active beta account. Ask the site administrator to invite new people; they must sign in first.")
        if (old and old['role'] == role) or (not old and role is None):
            return
        if role is None:
            connection.execute("DELETE FROM document_access WHERE document_id = ? AND user_id = ?", (document_id, user_id))
        else:
            connection.execute("""INSERT INTO document_access(document_id, user_id, role, created_at, granted_by_user_id)
                VALUES (?, ?, ?, ?, ?) ON CONFLICT(document_id, user_id) DO UPDATE
                SET role = excluded.role, granted_by_user_id = excluded.granted_by_user_id""", (document_id, user_id, role, now_utc(), actor))
        audit(connection, actor, 'document.revoke' if role is None else ('document.role_change' if old else 'document.grant'),
              'document', document_id, user_id=user_id, previous_role=old['role'] if old else None, role=role)


def list_identities(database):
    return rows(database, """SELECT u.user_id, u.display_name, u.email, u.email_verified, u.is_active,
        COALESCE(a.enabled, 0) AS allowed, s.user_id IS NOT NULL AS is_site_admin,
        u.google_subject IS NOT NULL AS has_identity FROM users u
        LEFT JOIN allowed_emails a ON a.normalized_email = u.normalized_email
        LEFT JOIN site_admins s ON s.user_id = u.user_id ORDER BY u.display_name COLLATE NOCASE""")


def list_allowed_emails(database):
    return rows(database, """SELECT a.*, EXISTS(SELECT 1 FROM users u WHERE
        u.normalized_email = a.normalized_email) AS has_account, EXISTS(SELECT 1 FROM users u WHERE
        u.normalized_email = a.normalized_email AND u.google_subject IS NOT NULL) AS has_identity
        FROM allowed_emails a ORDER BY a.normalized_email""")


def list_site_admins(database):
    return rows(database, """SELECT s.*, u.display_name, u.email FROM site_admins s
        JOIN users u ON u.user_id = s.user_id ORDER BY u.display_name COLLATE NOCASE""")


def set_site_admin(database, user_id, enabled, *, actor=None):
    with transaction(database) as connection:
        authorize_actor(connection, actor)
        exists = connection.execute("SELECT 1 FROM site_admins WHERE user_id = ?", (user_id,)).fetchone()
        if bool(exists) == enabled:
            return
        if enabled:
            if not connection.execute(ELIGIBLE + " AND u.user_id = ?", (user_id,)).fetchone():
                raise AccessError("A site admin must be an existing active beta identity.")
            connection.execute("INSERT INTO site_admins(user_id, created_at, created_by) VALUES (?, ?, ?)", (user_id, now_utc(), actor))
        else:
            # Count usable successors, so a disabled admin cannot strand recovery.
            successors = connection.execute(ELIGIBLE + " AND u.user_id IN (SELECT user_id FROM site_admins) AND u.user_id != ?", (user_id,)).fetchall()
            if not successors:
                raise AccessError("The final active site administrator cannot be removed. Add another active admin first.")
            connection.execute("DELETE FROM site_admins WHERE user_id = ?", (user_id,))
        audit(connection, actor, 'site_admin.grant' if enabled else 'site_admin.revoke', 'user', user_id)


def set_allowed_email(database, email, action, *, note=None, confirmed=False, actor=None):
    from .auth import normalize_email
    email = normalize_email(email)
    if action not in {'allow', 'disable', 'remove'}:
        raise AccessError("Unknown beta access action.")
    if note is not None and (not isinstance(note, str) or len(note) > 500):
        raise AccessError("Note must be 500 characters or fewer.")
    with transaction(database) as connection:
        authorize_actor(connection, actor)
        old = connection.execute("SELECT * FROM allowed_emails WHERE normalized_email = ?", (email,)).fetchone()
        if action != 'allow' and old is None:
            raise AccessError("Allowlist entry does not exist.")
        if action in {'disable', 'remove'}:
            admins = connection.execute(ELIGIBLE + " AND u.user_id IN (SELECT user_id FROM site_admins)").fetchall()
            if admins and any(u['user_id'] for u in admins if u['email'].casefold() == email) and len(admins) == 1:
                raise AccessError("Keep an active site administrator. Add another active admin first.")
        if action == 'remove':
            established = connection.execute("SELECT 1 FROM users WHERE normalized_email = ?", (email,)).fetchone()
            if established and not confirmed:
                raise AccessError("Confirm removal for this established account. Sign-in and existing sessions will stop; identity, comments and document grants are retained.")
            connection.execute("DELETE FROM allowed_emails WHERE normalized_email = ?", (email,))
        elif action == 'disable':
            if old['enabled'] == 0:
                return
            connection.execute("UPDATE allowed_emails SET enabled = 0 WHERE normalized_email = ?", (email,))
        else:
            connection.execute("""INSERT INTO allowed_emails(normalized_email, created_at, created_by_user_id, note)
                VALUES (?, ?, ?, ?) ON CONFLICT(normalized_email) DO UPDATE SET enabled = 1, note = excluded.note""", (email, now_utc(), actor, note))
        event = 'reenable' if action == 'allow' and old and not old['enabled'] else action
        audit(connection, actor, 'beta_email.' + event, 'email', email)
