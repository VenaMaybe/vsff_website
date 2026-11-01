-- Immutable targets plus one effective pointer per thread/version.
CREATE TABLE thread_target_heads (
    thread_id TEXT NOT NULL REFERENCES threads(thread_id) ON DELETE RESTRICT,
    document_version_id TEXT NOT NULL REFERENCES document_versions(version_id) ON DELETE RESTRICT,
    thread_target_id TEXT NOT NULL REFERENCES thread_targets(thread_target_id) ON DELETE RESTRICT,
    updated_at TEXT NOT NULL,
    updated_by_user_id TEXT REFERENCES users(user_id) ON DELETE RESTRICT,
    PRIMARY KEY (thread_id, document_version_id)
);
CREATE INDEX idx_target_heads_version ON thread_target_heads(document_version_id, thread_id);

INSERT INTO thread_target_heads
SELECT thread_id, document_version_id, thread_target_id, created_at, created_by_user_id
FROM (
    SELECT tt.thread_id, a.document_version_id, tt.thread_target_id, tt.created_at,
           CASE WHEN tt.role = 'origin' THEN t.created_by_user_id ELSE NULL END AS created_by_user_id,
           ROW_NUMBER() OVER (
               PARTITION BY tt.thread_id, a.document_version_id
               ORDER BY CASE WHEN tt.role = 'origin' THEN 0 ELSE 1 END,
                        tt.created_at DESC, tt.thread_target_id DESC
           ) AS position
    FROM thread_targets tt JOIN anchor_instances a ON a.anchor_id = tt.anchor_id
    JOIN threads t ON t.thread_id = tt.thread_id
) WHERE position = 1;

CREATE TRIGGER validate_target_head_insert BEFORE INSERT ON thread_target_heads
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM thread_targets tt JOIN anchor_instances a ON a.anchor_id = tt.anchor_id
        WHERE tt.thread_target_id = NEW.thread_target_id AND tt.thread_id = NEW.thread_id
          AND a.document_version_id = NEW.document_version_id
    ) THEN RAISE(ABORT, 'effective target thread/version mismatch') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM threads t JOIN thread_targets origin ON origin.thread_target_id = t.origin_thread_target_id
        JOIN anchor_instances a ON a.anchor_id = origin.anchor_id
        WHERE t.thread_id = NEW.thread_id AND a.document_version_id = NEW.document_version_id
          AND NEW.thread_target_id != t.origin_thread_target_id
    ) THEN RAISE(ABORT, 'origin effective target is immutable') END;
END;
CREATE TRIGGER validate_target_head_update BEFORE UPDATE ON thread_target_heads
BEGIN
    SELECT CASE WHEN NEW.thread_id != OLD.thread_id OR NEW.document_version_id != OLD.document_version_id
        THEN RAISE(ABORT, 'effective target identity is immutable') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM thread_targets tt JOIN anchor_instances a ON a.anchor_id = tt.anchor_id
        WHERE tt.thread_target_id = NEW.thread_target_id AND tt.thread_id = NEW.thread_id
          AND a.document_version_id = NEW.document_version_id
    ) THEN RAISE(ABORT, 'effective target thread/version mismatch') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM threads t JOIN thread_targets origin ON origin.thread_target_id = t.origin_thread_target_id
        JOIN anchor_instances a ON a.anchor_id = origin.anchor_id
        WHERE t.thread_id = OLD.thread_id AND a.document_version_id = OLD.document_version_id
    ) THEN RAISE(ABORT, 'origin effective target is immutable') END;
END;
CREATE TRIGGER protect_target_head_delete BEFORE DELETE ON thread_target_heads
BEGIN SELECT RAISE(ABORT, 'effective targets cannot be detached'); END;
CREATE TRIGGER initialize_origin_head AFTER INSERT ON thread_targets WHEN NEW.role = 'origin'
BEGIN
    INSERT INTO thread_target_heads
    SELECT NEW.thread_id, a.document_version_id, NEW.thread_target_id, NEW.created_at, t.created_by_user_id
    FROM anchor_instances a JOIN threads t ON t.thread_id = NEW.thread_id WHERE a.anchor_id = NEW.anchor_id;
END;
CREATE TRIGGER protect_historical_target_delete BEFORE DELETE ON thread_targets
BEGIN SELECT RAISE(ABORT, 'historical thread targets cannot be deleted'); END;

CREATE TABLE migration_runs (
    migration_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE RESTRICT,
    source_version_id TEXT NOT NULL REFERENCES document_versions(version_id) ON DELETE RESTRICT,
    target_version_id TEXT NOT NULL REFERENCES document_versions(version_id) ON DELETE RESTRICT,
    created_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'manual' CHECK (length(trim(strategy)) > 0),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'completed')),
    completed_at TEXT,
    completed_by_user_id TEXT REFERENCES users(user_id) ON DELETE RESTRICT,
    CHECK (source_version_id != target_version_id),
    CHECK ((status = 'open' AND completed_at IS NULL AND completed_by_user_id IS NULL) OR
           (status = 'completed' AND completed_at IS NOT NULL AND completed_by_user_id IS NOT NULL))
);
CREATE INDEX idx_migration_runs_document ON migration_runs(document_id, created_at, migration_id);
CREATE TRIGGER validate_migration_versions BEFORE INSERT ON migration_runs
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM document_versions s JOIN document_versions d ON d.version_id = NEW.target_version_id
        WHERE s.version_id = NEW.source_version_id AND s.document_id = NEW.document_id AND d.document_id = NEW.document_id
    ) THEN RAISE(ABORT, 'migration versions must belong to the document') END;
END;

CREATE TABLE migration_items (
    item_id TEXT PRIMARY KEY,
    migration_id TEXT NOT NULL REFERENCES migration_runs(migration_id) ON DELETE RESTRICT,
    thread_id TEXT NOT NULL REFERENCES threads(thread_id) ON DELETE RESTRICT,
    source_thread_target_id TEXT NOT NULL REFERENCES thread_targets(thread_target_id) ON DELETE RESTRICT,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'carried', 'skipped')),
    target_thread_target_id TEXT REFERENCES thread_targets(thread_target_id) ON DELETE RESTRICT,
    decision_by_user_id TEXT REFERENCES users(user_id) ON DELETE RESTRICT,
    decided_at TEXT,
    skip_note TEXT CHECK (skip_note IS NULL OR length(skip_note) <= 1000),
    revision_number INTEGER NOT NULL DEFAULT 1 CHECK (revision_number >= 1),
    UNIQUE (migration_id, thread_id),
    CHECK ((state = 'pending' AND target_thread_target_id IS NULL AND decision_by_user_id IS NULL AND decided_at IS NULL AND skip_note IS NULL) OR
           (state = 'carried' AND target_thread_target_id IS NOT NULL AND decision_by_user_id IS NOT NULL AND decided_at IS NOT NULL AND skip_note IS NULL) OR
           (state = 'skipped' AND target_thread_target_id IS NULL AND decision_by_user_id IS NOT NULL AND decided_at IS NOT NULL))
);
CREATE INDEX idx_migration_items_run ON migration_items(migration_id, state, thread_id);

CREATE TRIGGER validate_migration_item_insert BEFORE INSERT ON migration_items
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM migration_runs r JOIN thread_target_heads h ON h.document_version_id = r.source_version_id
        JOIN threads t ON t.thread_id = NEW.thread_id AND t.document_id = r.document_id
        WHERE r.migration_id = NEW.migration_id AND r.status = 'open' AND h.thread_id = NEW.thread_id
          AND h.thread_target_id = NEW.source_thread_target_id
    ) THEN RAISE(ABORT, 'migration source must snapshot an effective source target in an open run') END;
    SELECT CASE WHEN NEW.target_thread_target_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM migration_runs r JOIN thread_targets tt ON tt.thread_target_id = NEW.target_thread_target_id
        JOIN anchor_instances a ON a.anchor_id = tt.anchor_id
        WHERE r.migration_id = NEW.migration_id AND tt.thread_id = NEW.thread_id AND a.document_version_id = r.target_version_id
    ) THEN RAISE(ABORT, 'migration destination target mismatch') END;
END;
CREATE TRIGGER validate_migration_item_update BEFORE UPDATE ON migration_items
BEGIN
    SELECT CASE WHEN NEW.item_id != OLD.item_id OR NEW.migration_id != OLD.migration_id OR NEW.thread_id != OLD.thread_id
        OR NEW.source_thread_target_id != OLD.source_thread_target_id
        THEN RAISE(ABORT, 'migration item source identity is immutable') END;
    SELECT CASE WHEN OLD.state = 'skipped' OR NOT EXISTS (
        SELECT 1 FROM migration_runs WHERE migration_id = OLD.migration_id AND status = 'open'
    ) THEN RAISE(ABORT, 'migration decision is closed') END;
    SELECT CASE WHEN NEW.revision_number != OLD.revision_number + 1 OR NEW.state = 'pending'
        OR (OLD.state = 'carried' AND NEW.state != 'carried')
        THEN RAISE(ABORT, 'invalid migration decision transition') END;
    SELECT CASE WHEN NEW.target_thread_target_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM migration_runs r JOIN thread_targets tt ON tt.thread_target_id = NEW.target_thread_target_id
        JOIN anchor_instances a ON a.anchor_id = tt.anchor_id
        WHERE r.migration_id = NEW.migration_id AND tt.thread_id = NEW.thread_id AND a.document_version_id = r.target_version_id
    ) THEN RAISE(ABORT, 'migration destination target mismatch') END;
END;
CREATE TRIGGER protect_migration_item_delete BEFORE DELETE ON migration_items
BEGIN SELECT RAISE(ABORT, 'migration decisions cannot be deleted'); END;
CREATE TRIGGER protect_migration_run_update BEFORE UPDATE ON migration_runs
BEGIN
    SELECT CASE WHEN NEW.migration_id != OLD.migration_id OR NEW.document_id != OLD.document_id
        OR NEW.source_version_id != OLD.source_version_id OR NEW.target_version_id != OLD.target_version_id
        OR NEW.created_by_user_id != OLD.created_by_user_id OR NEW.created_at != OLD.created_at OR NEW.strategy != OLD.strategy
        OR OLD.status = 'completed' OR NEW.status != 'completed'
        THEN RAISE(ABORT, 'migration identity and completed runs are immutable') END;
    SELECT CASE WHEN EXISTS (SELECT 1 FROM migration_items WHERE migration_id = OLD.migration_id AND state = 'pending')
        THEN RAISE(ABORT, 'pending migration items remain') END;
END;
CREATE TRIGGER protect_migration_run_delete BEFORE DELETE ON migration_runs
BEGIN SELECT RAISE(ABORT, 'migration runs cannot be deleted'); END;

CREATE TABLE thread_target_provenance (
    thread_target_id TEXT PRIMARY KEY REFERENCES thread_targets(thread_target_id) ON DELETE RESTRICT,
    source_thread_target_id TEXT NOT NULL REFERENCES thread_targets(thread_target_id) ON DELETE RESTRICT,
    migration_run_id TEXT NOT NULL REFERENCES migration_runs(migration_id) ON DELETE RESTRICT,
    supersedes_thread_target_id TEXT REFERENCES thread_targets(thread_target_id) ON DELETE RESTRICT,
    method TEXT NOT NULL CHECK (length(trim(method)) > 0),
    created_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    algorithm_version TEXT,
    CHECK (method != 'manual_selection' OR (confidence IS NULL AND algorithm_version IS NULL))
);
CREATE TRIGGER validate_target_provenance BEFORE INSERT ON thread_target_provenance
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM thread_targets d JOIN anchor_instances da ON da.anchor_id = d.anchor_id
        JOIN thread_targets s ON s.thread_target_id = NEW.source_thread_target_id AND s.thread_id = d.thread_id
        JOIN anchor_instances sa ON sa.anchor_id = s.anchor_id
        JOIN migration_runs r ON r.migration_id = NEW.migration_run_id
        JOIN migration_items i ON i.migration_id = r.migration_id AND i.thread_id = d.thread_id
        WHERE d.thread_target_id = NEW.thread_target_id AND d.role != 'origin' AND r.status = 'open'
          AND da.document_version_id = r.target_version_id AND sa.document_version_id = r.source_version_id
          AND i.source_thread_target_id = s.thread_target_id
          AND (NEW.method != 'manual_selection' OR d.role = 'manual')
    ) THEN RAISE(ABORT, 'target provenance source/run mismatch') END;
    SELECT CASE WHEN NEW.supersedes_thread_target_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM thread_targets old JOIN anchor_instances oa ON oa.anchor_id = old.anchor_id
        JOIN thread_targets replacement ON replacement.thread_target_id = NEW.thread_target_id
        JOIN anchor_instances ra ON ra.anchor_id = replacement.anchor_id
        WHERE old.thread_target_id = NEW.supersedes_thread_target_id AND old.role != 'origin'
          AND old.thread_id = replacement.thread_id AND oa.document_version_id = ra.document_version_id
          AND old.thread_target_id != replacement.thread_target_id
    ) THEN RAISE(ABORT, 'superseded target mismatch') END;
END;
CREATE TRIGGER protect_target_provenance_update BEFORE UPDATE ON thread_target_provenance
BEGIN SELECT RAISE(ABORT, 'target provenance is immutable'); END;
CREATE TRIGGER protect_target_provenance_delete BEFORE DELETE ON thread_target_provenance
BEGIN SELECT RAISE(ABORT, 'target provenance cannot be deleted'); END;
