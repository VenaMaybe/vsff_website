-- Presentation names are not security identities.
DROP INDEX idx_users_display_name;
CREATE INDEX idx_users_display_name ON users(display_name COLLATE NOCASE);

CREATE TABLE site_admins (
    user_id TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    created_at TEXT NOT NULL,
    created_by TEXT REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
);
CREATE TABLE access_audit_log (
    id INTEGER PRIMARY KEY,
    actor_user_id TEXT REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_identifier TEXT NOT NULL,
    details TEXT NOT NULL CHECK (json_valid(details)),
    created_at TEXT NOT NULL
);
CREATE TRIGGER protect_access_audit_update BEFORE UPDATE ON access_audit_log
BEGIN SELECT RAISE(ABORT, 'access audit is append-only'); END;
CREATE TRIGGER protect_access_audit_delete BEFORE DELETE ON access_audit_log
BEGIN SELECT RAISE(ABORT, 'access audit is append-only'); END;
