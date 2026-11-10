ALTER TABLE document_review_settings ADD COLUMN section_prompts_in_compact INTEGER NOT NULL DEFAULT 1 CHECK (section_prompts_in_compact IN (0,1));
