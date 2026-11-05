"""Historical immutable targets and their current effective heads."""

from .anchors import get_anchor
from .database import version_table, connect
from .threads import ThreadNotFoundError


def target_history(database_path, thread_id):
    connection = connect(database_path)
    try:
        connection.execute("BEGIN")
        if connection.execute("SELECT 1 FROM threads WHERE thread_id = ?", (thread_id,)).fetchone() is None:
            raise ThreadNotFoundError("The review thread does not exist.")
        rows = connection.execute(
            f"""SELECT tt.*, v.version_id, v.version_label, v.original_filename,
                      h.thread_target_id AS effective_id,
                      p.source_thread_target_id, p.migration_run_id, p.supersedes_thread_target_id,
                      p.method, p.confidence, p.algorithm_version, p.created_by_user_id,
                      u.display_name
               FROM thread_targets tt JOIN anchor_instances a ON a.anchor_id = tt.anchor_id
               JOIN {version_table(connection)} v ON v.version_id = a.document_version_id
               LEFT JOIN thread_target_heads h ON h.thread_id = tt.thread_id AND h.document_version_id = v.version_id
               LEFT JOIN thread_target_provenance p ON p.thread_target_id = tt.thread_target_id
               LEFT JOIN users u ON u.user_id = p.created_by_user_id
               WHERE tt.thread_id = ? ORDER BY tt.created_at, tt.thread_target_id""", (thread_id,)
        ).fetchall()
    finally:
        connection.close()
    return [{"thread_target_id": row["thread_target_id"], "role": row["role"],
             "version_id": row["version_id"], "version_label": row["version_label"] or row["original_filename"],
             "created_at": row["created_at"], "is_effective": row["effective_id"] == row["thread_target_id"],
             "anchor": get_anchor(database_path, row["anchor_id"]),
             "provenance": ({key: row[key] for key in ["source_thread_target_id", "migration_run_id",
                             "supersedes_thread_target_id", "method", "confidence", "algorithm_version"]}
                            | {"created_by": {"user_id": row["created_by_user_id"], "display_name": row["display_name"]}}
                            if row["method"] else None)} for row in rows]
