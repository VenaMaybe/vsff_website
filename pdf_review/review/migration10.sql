ALTER TABLE document_review_settings ADD COLUMN downloads_allowed INTEGER NOT NULL DEFAULT 1 CHECK (downloads_allowed IN (0,1));
