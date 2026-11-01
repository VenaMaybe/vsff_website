ALTER TABLE users ADD COLUMN google_subject TEXT CHECK (google_subject IS NULL OR length(google_subject) BETWEEN 1 AND 255);
ALTER TABLE users ADD COLUMN email TEXT;
ALTER TABLE users ADD COLUMN normalized_email TEXT;
ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0 CHECK (email_verified IN (0, 1));
ALTER TABLE users ADD COLUMN last_login_at TEXT;
CREATE UNIQUE INDEX idx_users_google_subject ON users(google_subject) WHERE google_subject IS NOT NULL;
CREATE UNIQUE INDEX idx_users_email ON users(normalized_email) WHERE normalized_email IS NOT NULL;

CREATE TABLE allowed_emails (
    normalized_email TEXT PRIMARY KEY CHECK (length(trim(normalized_email)) > 3),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL,
    created_by_user_id TEXT REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    note TEXT
);
CREATE TABLE document_access (
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    role TEXT NOT NULL CHECK (role IN ('owner', 'reviewer', 'viewer')),
    created_at TEXT NOT NULL,
    granted_by_user_id TEXT REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    PRIMARY KEY (document_id, user_id)
);
CREATE INDEX idx_document_access_user ON document_access(user_id, document_id);

-- A linked subject is durable. Email/profile changes never replace its identity.
CREATE TRIGGER protect_google_subject BEFORE UPDATE OF google_subject ON users
WHEN OLD.google_subject IS NOT NULL AND NEW.google_subject IS NOT OLD.google_subject
BEGIN SELECT RAISE(ABORT, 'linked Google subject is immutable'); END;
-- Deliberately no allowlist or ACL backfill.
