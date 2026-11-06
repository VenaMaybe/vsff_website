CREATE TABLE trusted_users (
    user_id TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE RESTRICT,
    granted_at TEXT NOT NULL,
    granted_by TEXT REFERENCES users(user_id) ON DELETE RESTRICT
);
CREATE TABLE beta_memberships (
    normalized_email TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(user_id) ON DELETE RESTRICT,
    invited_by TEXT REFERENCES users(user_id) ON DELETE RESTRICT,
    invited_at TEXT,
    date_source TEXT NOT NULL CHECK (date_source IN ('invitation', 'allowlist_record', 'unknown')),
    joined_at TEXT,
    joined_by_at TEXT,
    access_blocked INTEGER NOT NULL DEFAULT 0 CHECK (access_blocked IN (0,1)),
    legacy INTEGER NOT NULL DEFAULT 0 CHECK (legacy IN (0,1))
);
CREATE INDEX idx_membership_user ON beta_memberships(user_id);
-- Existing allowlist timestamps are evidence of access, not necessarily the original invitation.
-- A sole administrator is the explicitly intended inviter of pre-existing members.
INSERT INTO beta_memberships
    (normalized_email,user_id,invited_by,invited_at,date_source,joined_by_at,legacy)
SELECT a.normalized_email,u.user_id,
    CASE WHEN (SELECT count(*) FROM site_admins)=1 THEN (SELECT user_id FROM site_admins LIMIT 1)
         ELSE a.created_by_user_id END,
    a.created_at,'allowlist_record',
    CASE WHEN u.google_subject IS NOT NULL THEN u.last_login_at END,1
FROM allowed_emails a LEFT JOIN users u ON u.normalized_email=a.normalized_email;
INSERT OR IGNORE INTO beta_memberships
    (normalized_email,user_id,invited_by,date_source,joined_by_at,legacy)
SELECT normalized_email,user_id,
    CASE WHEN (SELECT count(*) FROM site_admins)=1 THEN (SELECT user_id FROM site_admins LIMIT 1) END,
    'unknown',CASE WHEN google_subject IS NOT NULL THEN last_login_at END,1
FROM users WHERE normalized_email IS NOT NULL;
UPDATE beta_memberships SET access_blocked=1
WHERE NOT EXISTS (SELECT 1 FROM allowed_emails a WHERE a.normalized_email=beta_memberships.normalized_email AND a.enabled=1);
INSERT INTO access_audit_log(actor_user_id,action,target_type,target_identifier,details,created_at)
SELECT NULL,'membership.legacy_backfill','email',normalized_email,
    json_object('invited_by',invited_by,'date_source',date_source),strftime('%Y-%m-%dT%H:%M:%fZ','now')
FROM beta_memberships;

CREATE TABLE invitations (
    invitation_id TEXT PRIMARY KEY,
    normalized_email TEXT NOT NULL,
    invited_by TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    document_id TEXT REFERENCES documents(document_id) ON DELETE RESTRICT,
    role TEXT CHECK (role IN ('viewer','reviewer')),
    allows_beta INTEGER NOT NULL CHECK (allows_beta IN (0,1)),
    token_nonce TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','accepted','revoked','expired')),
    accepted_by TEXT REFERENCES users(user_id) ON DELETE RESTRICT,
    accepted_at TEXT,
    CHECK ((document_id IS NULL AND role IS NULL) OR (document_id IS NOT NULL AND role IS NOT NULL)),
    CHECK (document_id IS NOT NULL OR allows_beta=1),
    CHECK ((status='accepted' AND accepted_by IS NOT NULL AND accepted_at IS NOT NULL)
           OR (status!='accepted' AND accepted_by IS NULL AND accepted_at IS NULL))
);
CREATE UNIQUE INDEX idx_pending_beta_invite ON invitations(normalized_email)
    WHERE status='pending' AND document_id IS NULL;
CREATE UNIQUE INDEX idx_pending_document_invite ON invitations(normalized_email,document_id)
    WHERE status='pending' AND document_id IS NOT NULL;
CREATE INDEX idx_invitation_creator ON invitations(invited_by,created_at);
CREATE INDEX idx_invitation_expiry ON invitations(status,expires_at);
