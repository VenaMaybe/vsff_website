-- Deletion withdraws a version without rewriting immutable PDF/review identities.
CREATE TABLE version_deletions (
 version_id TEXT PRIMARY KEY REFERENCES document_versions(version_id) ON DELETE RESTRICT,
 deleted_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
 deleted_at TEXT NOT NULL
);
CREATE TRIGGER protect_version_deletion_update BEFORE UPDATE ON version_deletions
BEGIN SELECT RAISE(ABORT,'version deletion records are immutable'); END;
CREATE TRIGGER protect_version_deletion_delete BEFORE DELETE ON version_deletions
BEGIN SELECT RAISE(ABORT,'version deletion records are immutable'); END;
CREATE VIEW active_document_versions AS
 SELECT v.* FROM document_versions v
 WHERE NOT EXISTS(SELECT 1 FROM version_deletions d WHERE d.version_id=v.version_id);
