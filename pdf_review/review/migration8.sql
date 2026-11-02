CREATE TABLE review_palette (
    color TEXT PRIMARY KEY CHECK (color GLOB '#[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]')
);
INSERT INTO review_palette VALUES
('#c66b54'),('#bc7651'),('#ad8042'),('#998b42'),('#7f9348'),('#659a54'),
('#4f9b70'),('#429987'),('#40959a'),('#488da9'),('#5682bb'),('#6c78bf'),
('#8570bd'),('#9b6bb1'),('#b0669b'),('#be6682'),('#b77e6e'),('#a18d68'),
('#87976c'),('#6b9b85'),('#6899a5'),('#7c8db3'),('#9983b3'),('#b27f9b');
ALTER TABLE users ADD COLUMN review_color TEXT
    REFERENCES review_palette(color) ON UPDATE RESTRICT ON DELETE RESTRICT;
UPDATE users SET review_color = (SELECT color FROM review_palette WHERE rowid = 1 +
    (coalesce(unicode(substr(replace(users.user_id, '-', ''), 1, 1)),0) +
     coalesce(unicode(substr(replace(users.user_id, '-', ''), 8, 1)),0)) % 24);
CREATE TRIGGER initialize_review_color AFTER INSERT ON users WHEN NEW.review_color IS NULL
BEGIN UPDATE users SET review_color=(SELECT color FROM review_palette ORDER BY random() LIMIT 1)
    WHERE user_id=NEW.user_id; END;
CREATE TRIGGER require_review_color BEFORE UPDATE OF review_color ON users WHEN NEW.review_color IS NULL
BEGIN SELECT RAISE(ABORT,'review color is required'); END;

CREATE TABLE document_review_settings (
    document_id TEXT PRIMARY KEY REFERENCES documents(document_id) ON DELETE RESTRICT,
    visibility_policy TEXT NOT NULL DEFAULT 'shared' CHECK (visibility_policy IN ('shared','isolated')),
    default_scope TEXT NOT NULL DEFAULT 'all' CHECK (default_scope IN ('all','mine')),
    default_spread INTEGER NOT NULL DEFAULT 0 CHECK (default_spread IN (0,1,2)),
    default_display TEXT NOT NULL DEFAULT 'expanded' CHECK (default_display IN ('expanded','minimized','hidden'))
);
CREATE TABLE viewer_preferences (
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE RESTRICT,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    scope TEXT NOT NULL CHECK (scope IN ('all','mine')),
    spread INTEGER NOT NULL CHECK (spread IN (0,1,2)),
    display TEXT NOT NULL CHECK (display IN ('expanded','minimized','hidden','mobile')),
    PRIMARY KEY (document_id,user_id)
);
CREATE TABLE hidden_reviewers (
    document_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    hidden_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    PRIMARY KEY (document_id,user_id,hidden_user_id),
    FOREIGN KEY (document_id,user_id) REFERENCES viewer_preferences(document_id,user_id) ON DELETE CASCADE
);

CREATE TABLE sections (
    section_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE RESTRICT,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 200),
    position INTEGER NOT NULL CHECK (position >= 0),
    prompt TEXT NOT NULL DEFAULT '' CHECK (length(prompt) <= 2000),
    created_at TEXT NOT NULL,
    archived_at TEXT
);
CREATE INDEX idx_sections_document ON sections(document_id,position,section_id);
CREATE TRIGGER protect_section_identity BEFORE UPDATE OF section_id,document_id,created_at ON sections
BEGIN SELECT RAISE(ABORT,'section identity is immutable'); END;
CREATE TRIGGER preserve_sections BEFORE DELETE ON sections
BEGIN SELECT RAISE(ABORT,'archive sections to preserve feedback'); END;
CREATE TABLE section_placements (
    section_id TEXT NOT NULL REFERENCES sections(section_id) ON DELETE RESTRICT,
    version_id TEXT NOT NULL REFERENCES document_versions(version_id) ON DELETE RESTRICT,
    start_page INTEGER NOT NULL CHECK (start_page >= 1),
    start_y REAL,
    end_page INTEGER NOT NULL CHECK (end_page >= start_page),
    end_y REAL,
    start_view_box TEXT NOT NULL CHECK(json_valid(start_view_box)),
    end_view_box TEXT NOT NULL CHECK(json_valid(end_view_box)),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    updated_by TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (section_id,version_id)
);
CREATE TRIGGER validate_section_version_insert BEFORE INSERT ON section_placements
WHEN (SELECT document_id FROM sections WHERE section_id=NEW.section_id) !=
     (SELECT document_id FROM document_versions WHERE version_id=NEW.version_id)
BEGIN SELECT RAISE(ABORT,'section version document mismatch'); END;
CREATE TRIGGER protect_placement_identity BEFORE UPDATE OF section_id,version_id ON section_placements
BEGIN SELECT RAISE(ABORT,'placement identity is immutable'); END;

CREATE TABLE section_responses (
    response_id TEXT PRIMARY KEY,
    section_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    author_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    UNIQUE(section_id,version_id,author_id),
    FOREIGN KEY(section_id,version_id) REFERENCES section_placements(section_id,version_id) ON DELETE RESTRICT
);
CREATE TRIGGER protect_section_response_update BEFORE UPDATE ON section_responses
BEGIN SELECT RAISE(ABORT,'section response identity is immutable'); END;
CREATE TRIGGER protect_section_response_delete BEFORE DELETE ON section_responses
BEGIN SELECT RAISE(ABORT,'section response history is retained'); END;
CREATE TABLE section_comments (
    comment_id TEXT PRIMARY KEY,
    response_id TEXT NOT NULL REFERENCES section_responses(response_id) ON DELETE RESTRICT,
    author_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    body TEXT,
    created_at TEXT NOT NULL,
    edited_at TEXT,
    deleted_at TEXT,
    deleted_by_user_id TEXT REFERENCES users(user_id) ON DELETE RESTRICT,
    CHECK ((deleted_at IS NULL AND deleted_by_user_id IS NULL AND body IS NOT NULL AND length(trim(body))>0)
      OR (deleted_at IS NOT NULL AND deleted_by_user_id IS NOT NULL AND body IS NULL))
);
CREATE INDEX idx_section_comments_response ON section_comments(response_id,created_at,comment_id);
CREATE TRIGGER protect_section_comment_identity BEFORE UPDATE OF comment_id,response_id,author_id,created_at ON section_comments
BEGIN SELECT RAISE(ABORT,'comment identity is immutable'); END;
CREATE TABLE section_comment_revisions (
    revision_id TEXT PRIMARY KEY,
    comment_id TEXT NOT NULL REFERENCES section_comments(comment_id) ON DELETE RESTRICT,
    revision_number INTEGER NOT NULL CHECK(revision_number>=1),
    body TEXT NOT NULL CHECK(length(trim(body))>0),
    editor_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    UNIQUE(comment_id,revision_number)
);
CREATE TRIGGER protect_section_revision_update BEFORE UPDATE ON section_comment_revisions
BEGIN SELECT RAISE(ABORT,'comment revisions are immutable'); END;
CREATE TRIGGER protect_section_revision_delete BEFORE DELETE ON section_comment_revisions
BEGIN SELECT RAISE(ABORT,'comment revisions are immutable'); END;
