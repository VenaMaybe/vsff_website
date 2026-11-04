-- Author-controlled, default-on document reading policy.
ALTER TABLE document_review_settings ADD COLUMN reading_tracking_enabled INTEGER NOT NULL DEFAULT 1 CHECK(reading_tracking_enabled IN (0,1));
CREATE TABLE document_reading_pauses (
 document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE RESTRICT,
 user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
 PRIMARY KEY(document_id,user_id)
);
-- Prior personal controls no longer govern document tracking. Preserve all history.
UPDATE reading_consents SET status='active',generation=generation+1;
DELETE FROM reading_leases;
