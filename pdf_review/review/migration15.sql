-- A designation belongs to the logical document; immutable version rows stay unchanged.
CREATE TABLE document_main_versions (
    document_id TEXT PRIMARY KEY REFERENCES documents(document_id) ON DELETE RESTRICT,
    version_id TEXT NOT NULL UNIQUE REFERENCES document_versions(version_id) ON DELETE RESTRICT,
    selected_by TEXT REFERENCES users(user_id) ON DELETE RESTRICT,
    selected_at TEXT NOT NULL
);
CREATE TRIGGER validate_main_version_insert BEFORE INSERT ON document_main_versions
WHEN NOT EXISTS (SELECT 1 FROM active_document_versions v WHERE v.version_id=NEW.version_id AND v.document_id=NEW.document_id)
BEGIN SELECT RAISE(ABORT,'main version must be active and belong to the document'); END;
CREATE TRIGGER validate_main_version_update BEFORE UPDATE ON document_main_versions
WHEN NOT EXISTS (SELECT 1 FROM active_document_versions v WHERE v.version_id=NEW.version_id AND v.document_id=NEW.document_id)
BEGIN SELECT RAISE(ABORT,'main version must be active and belong to the document'); END;
-- Existing documents start with their newest available version, deterministically.
INSERT INTO document_main_versions(document_id,version_id,selected_at)
SELECT d.document_id,
    (SELECT v.version_id FROM active_document_versions v WHERE v.document_id=d.document_id ORDER BY v.imported_at DESC,v.version_id DESC LIMIT 1),
    strftime('%Y-%m-%dT%H:%M:%fZ','now')
FROM documents d WHERE EXISTS (SELECT 1 FROM active_document_versions v WHERE v.document_id=d.document_id);
