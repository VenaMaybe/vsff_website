"""Email-bound invitations. Every authority decision is repeated under the write lock."""

import hashlib
import hmac
import secrets
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .access import AccessDenied, AccessError, ELIGIBLE, audit, authorize_actor
from .database import connect, transaction
from .documents import now_utc


class WrongInvitationAccount(AccessError):
    pass


def can_invite_connection(c, user_id):
    return bool(c.execute(ELIGIBLE + " AND u.user_id=? AND (EXISTS(SELECT 1 FROM site_admins WHERE user_id=u.user_id) OR EXISTS(SELECT 1 FROM trusted_users WHERE user_id=u.user_id))", (user_id,)).fetchone())


def can_invite(database, user_id):
    c = connect(database)
    try:
        return can_invite_connection(c, user_id)
    finally:
        c.close()


def require_inviter(c, actor):
    if not can_invite_connection(c, actor):
        raise AccessDenied('Trusted User or site admin access is required.')


def transition(c, row, status, actor=None, **details):
    if row['status'] != 'pending':
        return
    c.execute('UPDATE invitations SET status=? WHERE invitation_id=?', (status, row['invitation_id']))
    audit(c, actor, 'invitation.' + status, 'invitation', row['invitation_id'], **details)


def expire_pending(c):
    for row in c.execute("SELECT * FROM invitations WHERE status='pending' AND expires_at<=?", (now_utc(),)).fetchall():
        transition(c, row, 'expired', expires_at=row['expires_at'])


def revoke_invalid(c):
    """Called by all admin/owner authority mutations, including offline CLI operations."""
    for row in c.execute("SELECT * FROM invitations WHERE status='pending'").fetchall():
        if not authority_valid(c, row):
            transition(c, row, 'revoked', reason='inviter_or_recipient_access_changed')


def authority_valid(c, row):
    if not c.execute(ELIGIBLE + ' AND u.user_id=?', (row['invited_by'],)).fetchone():
        return False
    if row['allows_beta'] and not can_invite_connection(c, row['invited_by']):
        return False
    if row['document_id'] and not c.execute("SELECT 1 FROM document_access WHERE document_id=? AND user_id=? AND role='owner'", (row['document_id'], row['invited_by'])).fetchone():
        return False
    recipient = c.execute('SELECT is_active FROM users WHERE normalized_email=?', (row['normalized_email'],)).fetchone()
    allowed = c.execute('SELECT enabled FROM allowed_emails WHERE normalized_email=?', (row['normalized_email'],)).fetchone()
    blocked = c.execute('SELECT access_blocked FROM beta_memberships WHERE normalized_email=?', (row['normalized_email'],)).fetchone()
    if blocked and blocked['access_blocked']:
        return False
    if recipient and not recipient['is_active'] or allowed and not allowed['enabled']:
        return False
    if not row['allows_beta'] and not allowed:
        return False
    return True


def token_for(secret, row):
    # Only a keyed signature is a credential; the stored random nonce is not redeemable.
    message = f"pdf-review-invitation:v1:{row['invitation_id']}:{row['token_nonce']}".encode()
    return hmac.new(secret.encode() if isinstance(secret, str) else secret, message, hashlib.sha256).hexdigest()


def validate_marker(c, marker, email=None):
    if not isinstance(marker, dict):
        raise AccessError('This invitation is unavailable. Ask the inviter for a new link.')
    row = c.execute('SELECT * FROM invitations WHERE invitation_id=?', (marker.get('id'),)).fetchone()
    if not row or row['status'] != 'pending' or row['expires_at'] <= now_utc() or not hmac.compare_digest(row['token_nonce'], str(marker.get('nonce', ''))) or not authority_valid(c, row):
        raise AccessError('This invitation is expired, revoked or already used. Ask the inviter for a new link.')
    if email is not None and email != row['normalized_email']:
        raise WrongInvitationAccount('Use the Google account this invitation was sent to.')
    return row


def open_link(database, invitation_id, token, secret):
    c = connect(database)
    try:
        row = c.execute('SELECT * FROM invitations WHERE invitation_id=?', (invitation_id,)).fetchone()
        if not row or not isinstance(token, str) or len(token) != 64 or any(ch not in '0123456789abcdef' for ch in token) or not hmac.compare_digest(token_for(secret, row), token):
            raise AccessError('This invitation is unavailable. Ask the inviter for a new link.')
        marker = {'id': invitation_id, 'nonce': row['token_nonce']}
        validate_marker(c, marker)
        return marker
    finally:
        c.close()


def record_join(c, user_id, email, *, first_link):
    now = now_utc()
    previous = c.execute('SELECT min(joined_at) AS joined_at,min(joined_by_at) AS joined_by_at FROM beta_memberships WHERE user_id=?', (user_id,)).fetchone()
    c.execute("INSERT OR IGNORE INTO beta_memberships(normalized_email,date_source) VALUES (?,'unknown')", (email,))
    # Existing linked users without history get an upper bound, not a fabricated join time.
    c.execute('UPDATE beta_memberships SET user_id=?, joined_at=COALESCE(joined_at,?,CASE WHEN ? THEN ? END), joined_by_at=COALESCE(joined_by_at,?,?) WHERE normalized_email=?',
              (user_id, previous['joined_at'], first_link, now, previous['joined_by_at'], now, email))
    if first_link:
        audit(c, user_id, 'membership.joined', 'user', user_id, email=email)


def accept_in_transaction(c, row, user_id, *, immediate_actor=None):
    now = now_utc()
    if row['allows_beta']:
        c.execute('INSERT OR IGNORE INTO allowed_emails(normalized_email,created_at,created_by_user_id) VALUES (?,?,?)', (row['normalized_email'], now, row['invited_by']))
    c.execute("INSERT OR IGNORE INTO beta_memberships(normalized_email,invited_by,invited_at,date_source) VALUES (?,?,?,'invitation')", (row['normalized_email'], row['invited_by'], row['created_at']))
    if row['document_id']:
        # Never downgrade or silently elevate an established grant, especially an Owner.
        previous = c.execute('SELECT role FROM document_access WHERE document_id=? AND user_id=?', (row['document_id'], user_id)).fetchone()
        if not previous:
            c.execute('INSERT INTO document_access(document_id,user_id,role,created_at,granted_by_user_id) VALUES (?,?,?,?,?)', (row['document_id'], user_id, row['role'], now, row['invited_by']))
            audit(c, row['invited_by'], 'document.grant', 'document', row['document_id'], user_id=user_id, role=row['role'], invitation_id=row['invitation_id'])
        granted_role = previous['role'] if previous else row['role']
    else:
        granted_role = None
    c.execute("UPDATE invitations SET status='accepted',accepted_by=?,accepted_at=? WHERE invitation_id=?", (user_id, now, row['invitation_id']))
    audit(c, immediate_actor or user_id, 'invitation.immediate_share' if immediate_actor else 'invitation.accepted', 'invitation', row['invitation_id'], invited_by=row['invited_by'], accepted_by=user_id, document_id=row['document_id'], offered_role=row['role'], granted_role=granted_role)


def accept_existing(database, marker, user_id):
    with transaction(database) as c:
        user = c.execute(ELIGIBLE + ' AND u.user_id=?', (user_id,)).fetchone()
        if not user:
            raise AccessDenied('Sign in again to accept this invitation.')
        row = validate_marker(c, marker, user['email'].strip().casefold())
        accept_in_transaction(c, row, user_id)
        record_join(c, user_id, row['normalized_email'], first_link=False)
        return row['document_id']


def create_invitation(database, actor, email, document_id=None, role=None, *, _connection=None):
    from .auth import normalize_email
    email = normalize_email(email)
    if document_id is None:
        if role is not None:
            raise AccessError('A beta invitation cannot include a document role.')
    elif role not in {'viewer', 'reviewer'}:
        raise AccessError('Invite as Viewer or Reviewer. Transfer ownership separately after joining.')
    with (nullcontext(_connection) if _connection is not None else transaction(database)) as c:
        if document_id:
            authorize_actor(c, actor, document_id)
        else:
            require_inviter(c, actor)
        expire_pending(c)
        revoke_invalid(c)
        target = c.execute(ELIGIBLE + ' AND u.normalized_email=?', (email,)).fetchone()
        blocked = c.execute('SELECT 1 FROM users WHERE normalized_email=? AND is_active=0', (email,)).fetchone()
        allowed = c.execute('SELECT enabled FROM allowed_emails WHERE normalized_email=?', (email,)).fetchone()
        membership = c.execute('SELECT access_blocked FROM beta_memberships WHERE normalized_email=?', (email,)).fetchone()
        known = c.execute('SELECT 1 FROM users WHERE normalized_email=?', (email,)).fetchone()
        if blocked or allowed and not allowed['enabled'] or membership and membership['access_blocked'] or known and not allowed:
            raise AccessError('This account is unavailable for invitations. Contact the site admin.')
        allows_beta = document_id is None or not bool(target)
        if allows_beta:
            require_inviter(c, actor)
        existing = c.execute("SELECT * FROM invitations WHERE normalized_email=? AND document_id IS ? AND status='pending'", (email, document_id)).fetchone()
        if existing:
            # Do not expose another inviter's private invitation or change its offered role.
            if existing['invited_by'] != actor:
                raise AccessError('An invitation for this recipient is already pending. Ask the site admin to review it.')
            if existing['role'] != role:
                raise AccessError('Revoke the pending invitation before offering another role.')
            return dict(existing)
        if c.execute("SELECT count(*) FROM invitations WHERE invited_by=? AND status='pending'", (actor,)).fetchone()[0] >= 100:
            raise AccessError('You have 100 pending invitations. Revoke unused invitations first.')
        now = now_utc()
        invitation_id = str(uuid4())
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        c.execute("INSERT INTO invitations(invitation_id,normalized_email,invited_by,document_id,role,allows_beta,token_nonce,created_at,expires_at,status) VALUES (?,?,?,?,?,?,?,?,?,'pending')", (invitation_id, email, actor, document_id, role, int(allows_beta), secrets.token_urlsafe(24), now, expires))
        row = c.execute('SELECT * FROM invitations WHERE invitation_id=?', (invitation_id,)).fetchone()
        c.execute("INSERT OR IGNORE INTO beta_memberships(normalized_email,invited_by,invited_at,date_source) VALUES (?,?,?,'invitation')", (email, actor, now))
        audit(c, actor, 'invitation.created', 'invitation', invitation_id, email=email, document_id=document_id, role=role, allows_beta=allows_beta, expires_at=expires)
        if target:
            accept_in_transaction(c, row, target['user_id'], immediate_actor=actor)
            record_join(c, target['user_id'], email, first_link=False)
        return dict(c.execute('SELECT * FROM invitations WHERE invitation_id=?', (invitation_id,)).fetchone())


def manageable(c, actor, invitation_id):
    user = c.execute(ELIGIBLE + ' AND u.user_id=?', (actor,)).fetchone()
    row = c.execute('SELECT * FROM invitations WHERE invitation_id=?', (invitation_id,)).fetchone()
    admin = c.execute('SELECT 1 FROM site_admins WHERE user_id=?', (actor,)).fetchone()
    owner = row and row['document_id'] and c.execute("SELECT 1 FROM document_access WHERE document_id=? AND user_id=? AND role='owner'", (row['document_id'], actor)).fetchone()
    if not user or not row or not (admin or owner or row['invited_by'] == actor and can_invite_connection(c, actor)):
        raise AccessDenied('You cannot manage this invitation.')
    return row


def invitation_detail(database, actor, invitation_id):
    c = connect(database)
    try:
        return dict(manageable(c, actor, invitation_id))
    finally:
        c.close()


def revoke_invitation(database, actor, invitation_id):
    with transaction(database) as c:
        row = manageable(c, actor, invitation_id)
        expire_pending(c)
        row = c.execute('SELECT * FROM invitations WHERE invitation_id=?', (invitation_id,)).fetchone()
        transition(c, row, 'revoked', actor)


def renew_invitation(database, actor, invitation_id):
    # Revoke and reissue as distinct events. Old links remain permanently invalid.
    with transaction(database) as c:
        row = dict(manageable(c, actor, invitation_id))
        if row['status'] == 'accepted':
            raise AccessError('This invitation was already accepted.')
        if row['document_id']:
            authorize_actor(c, actor, row['document_id'])
        else:
            require_inviter(c, actor)
        transition(c, row, 'revoked', actor, reason='renewed')
        return create_invitation(database, actor, row['normalized_email'], row['document_id'], row['role'], _connection=c)


def set_trusted(database, actor, user_id, enabled):
    with transaction(database) as c:
        authorize_actor(c, actor)
        if enabled and not c.execute(ELIGIBLE + ' AND u.user_id=?', (user_id,)).fetchone():
            raise AccessError('Choose an existing active beta user.')
        exists = c.execute('SELECT 1 FROM trusted_users WHERE user_id=?', (user_id,)).fetchone()
        if bool(exists) == enabled:
            return
        if enabled:
            c.execute('INSERT INTO trusted_users(user_id,granted_at,granted_by) VALUES (?,?,?)', (user_id, now_utc(), actor))
        else:
            c.execute('DELETE FROM trusted_users WHERE user_id=?', (user_id,))
        audit(c, actor, 'trusted_user.grant' if enabled else 'trusted_user.revoke', 'user', user_id)
        revoke_invalid(c)


def directory(database, actor):
    c = connect(database)
    try:
        require_inviter(c, actor)
        return [dict(r) for r in c.execute("""SELECT m.normalized_email AS email,u.display_name,
            CASE WHEN s.user_id IS NOT NULL THEN 'Site Admin' WHEN t.user_id IS NOT NULL THEN 'Trusted User' ELSE 'Member' END AS site_role,
            CASE WHEN a.enabled=1 AND (u.user_id IS NULL OR u.is_active=1) THEN 'Enabled'
                 WHEN a.normalized_email IS NULL AND u.user_id IS NULL AND m.access_blocked=0 THEN 'Not joined' ELSE 'Disabled' END AS membership_status,
            m.invited_at,m.date_source,m.joined_at,m.joined_by_at,inviter.display_name AS inviter
            FROM beta_memberships m LEFT JOIN users u ON u.user_id=m.user_id
            LEFT JOIN allowed_emails a ON a.normalized_email=m.normalized_email
            LEFT JOIN site_admins s ON s.user_id=u.user_id LEFT JOIN trusted_users t ON t.user_id=u.user_id
            LEFT JOIN users inviter ON inviter.user_id=m.invited_by
            WHERE u.user_id IS NULL OR u.normalized_email=m.normalized_email
            ORDER BY m.normalized_email""")]
    finally:
        c.close()


def list_invitations(database, actor, document_id=None):
    c = connect(database)
    try:
        admin = bool(c.execute('SELECT 1 FROM site_admins WHERE user_id=?', (actor,)).fetchone())
        if document_id:
            authorize_actor(c, actor, document_id)
            where, args = 'i.document_id=?', (document_id,)
        else:
            require_inviter(c, actor)
            where, args = ('1=1', ()) if admin else ('i.invited_by=?', (actor,))
        # No titles, document IDs or grants from someone else's document enter this listing.
        return [dict(r) for r in c.execute(f"""SELECT i.invitation_id,i.normalized_email,i.created_at,i.expires_at,
            CASE WHEN i.status='pending' AND i.expires_at<=? THEN 'expired' ELSE i.status END AS status,
            i.accepted_at,i.role,u.display_name AS inviter
            FROM invitations i JOIN users u ON u.user_id=i.invited_by WHERE {where}
            ORDER BY i.created_at DESC LIMIT 200""", (now_utc(), *args))]
    finally:
        c.close()


def backfill_legacy(database, actor):
    with transaction(database) as c:
        authorize_actor(c, actor)
        for row in c.execute('SELECT * FROM beta_memberships WHERE legacy=1 AND invited_by IS NULL').fetchall():
            c.execute('UPDATE beta_memberships SET invited_by=? WHERE normalized_email=?', (actor, row['normalized_email']))
            audit(c, actor, 'membership.legacy_attributed', 'email', row['normalized_email'], date_source=row['date_source'])


def audit_history(database, actor, before=None):
    c = connect(database)
    try:
        authorize_actor(c, actor)
        return [dict(r) for r in c.execute('''SELECT a.id,a.action,a.target_type,a.target_identifier,a.details,a.created_at,u.display_name AS actor,
            COALESCE(i.normalized_email, target.email, CASE WHEN a.target_type='email' THEN a.target_identifier END) AS recipient,
            inviter.display_name AS inviter,i.role AS offered_role
            FROM access_audit_log a LEFT JOIN users u ON u.user_id=a.actor_user_id
            LEFT JOIN invitations i ON a.target_type='invitation' AND i.invitation_id=a.target_identifier
            LEFT JOIN users target ON a.target_type='user' AND target.user_id=a.target_identifier
            LEFT JOIN users inviter ON inviter.user_id=i.invited_by
            WHERE (? IS NULL OR a.id<?) ORDER BY a.id DESC LIMIT 100''', (before, before))]
    finally:
        c.close()
