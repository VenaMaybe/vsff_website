-- Derived PDF.js text metrics, independent of readers and reading activity.
CREATE TABLE version_text_properties (
    version_id TEXT NOT NULL REFERENCES document_versions(version_id),
    algorithm INTEGER NOT NULL CHECK (algorithm = 2),
    page INTEGER NOT NULL CHECK (page > 0),
    page_count INTEGER NOT NULL CHECK (page_count >= page AND page_count <= 100000),
    metadata TEXT NOT NULL,
    PRIMARY KEY (version_id, algorithm, page)
);
