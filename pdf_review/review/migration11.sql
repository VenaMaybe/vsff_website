-- Optional, approximate reading activity. Never modify PDF/review identities.
CREATE TABLE reading_consents (
    version_id TEXT NOT NULL REFERENCES document_versions(version_id) ON DELETE RESTRICT,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK(status IN ('active','paused','off')),
    generation INTEGER NOT NULL DEFAULT 1 CHECK(generation>=1),
    page_count INTEGER NOT NULL CHECK(page_count BETWEEN 1 AND 100000),
    consented_at TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(version_id,user_id)
);
CREATE TABLE reading_totals (
    version_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    active_ms INTEGER NOT NULL DEFAULT 0 CHECK(active_ms>=0),
    pages_visited INTEGER NOT NULL DEFAULT 0 CHECK(pages_visited>=0),
    pages_read INTEGER NOT NULL DEFAULT 0 CHECK(pages_read>=0),
    furthest_page INTEGER NOT NULL DEFAULT 0 CHECK(furthest_page>=0),
    last_page INTEGER,
    first_activity TEXT,
    last_activity TEXT,
    PRIMARY KEY(version_id,user_id),
    FOREIGN KEY(version_id,user_id) REFERENCES reading_consents(version_id,user_id) ON DELETE CASCADE
);
CREATE TABLE reading_pages (
    version_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    page_number INTEGER NOT NULL CHECK(page_number>=1),
    word_count INTEGER CHECK(word_count BETWEEN 0 AND 100000),
    active_ms INTEGER NOT NULL DEFAULT 0 CHECK(active_ms>=0),
    first_visited TEXT NOT NULL,
    last_visited TEXT NOT NULL,
    read_at TEXT,
    visit_count INTEGER NOT NULL DEFAULT 0 CHECK(visit_count>=0),
    PRIMARY KEY(version_id,user_id,page_number),
    FOREIGN KEY(version_id,user_id) REFERENCES reading_consents(version_id,user_id) ON DELETE CASCADE
);
CREATE TABLE reading_sessions (
    session_id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    generation INTEGER NOT NULL CHECK(generation>=1),
    last_seq INTEGER NOT NULL DEFAULT 0 CHECK(last_seq>=0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(version_id,user_id) REFERENCES reading_consents(version_id,user_id) ON DELETE CASCADE
);
CREATE INDEX idx_reading_sessions_reader ON reading_sessions(version_id,user_id);
-- One server time budget across this user's tabs, documents and devices.
CREATE TABLE reading_leases (
    user_id TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE RESTRICT,
    session_id TEXT NOT NULL REFERENCES reading_sessions(session_id) ON DELETE CASCADE,
    received_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    current_page INTEGER
);
-- One row per page visit, updated by acknowledged batches (not one row per tick).
CREATE TABLE reading_visits (
    session_id TEXT NOT NULL REFERENCES reading_sessions(session_id) ON DELETE CASCADE,
    visit_index INTEGER NOT NULL CHECK(visit_index>=1),
    page_number INTEGER NOT NULL CHECK(page_number>=1),
    first_visited TEXT NOT NULL,
    last_visited TEXT NOT NULL,
    active_ms INTEGER NOT NULL CHECK(active_ms>=0),
    PRIMARY KEY(session_id,visit_index,page_number)
);
CREATE TRIGGER protect_reading_consent_identity BEFORE UPDATE OF version_id,user_id,page_count ON reading_consents
BEGIN SELECT RAISE(ABORT,'reading version and reader are immutable'); END;
CREATE TRIGGER protect_reading_page_identity BEFORE UPDATE OF version_id,user_id,page_number ON reading_pages
BEGIN SELECT RAISE(ABORT,'reading page identity is immutable'); END;
CREATE TRIGGER protect_reading_total_identity BEFORE UPDATE OF version_id,user_id ON reading_totals
BEGIN SELECT RAISE(ABORT,'reading total identity is immutable'); END;
CREATE TRIGGER protect_reading_session_identity BEFORE UPDATE OF session_id,version_id,user_id,generation ON reading_sessions
BEGIN SELECT RAISE(ABORT,'reading session identity is immutable'); END;
CREATE TRIGGER protect_reading_visit_identity BEFORE UPDATE OF session_id,visit_index,page_number ON reading_visits
BEGIN SELECT RAISE(ABORT,'reading visit identity is immutable'); END;
CREATE TRIGGER validate_reading_lease_insert BEFORE INSERT ON reading_leases
WHEN (SELECT user_id FROM reading_sessions WHERE session_id=NEW.session_id) != NEW.user_id
BEGIN SELECT RAISE(ABORT,'reading lease reader mismatch'); END;
CREATE TRIGGER validate_reading_lease_update BEFORE UPDATE ON reading_leases
WHEN (SELECT user_id FROM reading_sessions WHERE session_id=NEW.session_id) != NEW.user_id
BEGIN SELECT RAISE(ABORT,'reading lease reader mismatch'); END;
