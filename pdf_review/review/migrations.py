"""Manual carry-forward decisions. All permanent work is transactional HTTP service work."""

from uuid import uuid4

from .anchors import get_anchor, insert_validated_anchor, validate_anchor_payload
from .database import connect, transaction
from .documents import now_utc
from .threads import get_thread
from .users import require_active_user


class MigrationError(RuntimeError):
    status = 422
    code = "invalid_migration"


class MigrationNotFoundError(MigrationError):
    status = 404
    code = "migration_not_found"


class MigrationConflictError(MigrationError):
    status = 409
    code = "migration_conflict"


def _run(connection, migration_id):
    row = connection.execute(
        """SELECT r.*, s.version_label AS source_label, s.original_filename AS source_filename,
                  d.version_label AS target_label, d.original_filename AS target_filename,
                  u.display_name AS creator_name, cu.display_name AS completer_name
           FROM migration_runs r JOIN document_versions s ON s.version_id = r.source_version_id
           JOIN document_versions d ON d.version_id = r.target_version_id
           JOIN users u ON u.user_id = r.created_by_user_id
           LEFT JOIN users cu ON cu.user_id = r.completed_by_user_id WHERE r.migration_id = ?""", (migration_id,)
    ).fetchone()
    if row is None:
        raise MigrationNotFoundError("The carry-forward run does not exist.")
    return row


def _head(connection, thread_id, version_id):
    return connection.execute(
        "SELECT * FROM thread_target_heads WHERE thread_id = ? AND document_version_id = ?",
        (thread_id, version_id),
    ).fetchone()


def _serialize_run(row, counts):
    result = dict(row)
    result.update(source_label=row["source_label"] or row["source_filename"],
                  target_label=row["target_label"] or row["target_filename"], counts=counts,
                  created_by={"user_id": row["created_by_user_id"], "display_name": row["creator_name"]},
                  completed_by=({"user_id": row["completed_by_user_id"], "display_name": row["completer_name"]}
                                if row["completed_by_user_id"] else None))
    return result


def get_migration(database_path, migration_id):
    connection = connect(database_path)
    try:
        connection.execute("BEGIN")
        run = _run(connection, migration_id)
        rows = connection.execute(
            """SELECT i.*, tt.anchor_id AS source_anchor_id, h.thread_target_id AS current_target_id,
                      (h.thread_target_id = t.origin_thread_target_id) AS destination_is_origin,
                      u.display_name AS decision_name
               FROM migration_items i JOIN thread_targets tt ON tt.thread_target_id = i.source_thread_target_id
               JOIN threads t ON t.thread_id = i.thread_id
               LEFT JOIN thread_target_heads h ON h.thread_id = i.thread_id AND h.document_version_id = ?
               LEFT JOIN users u ON u.user_id = i.decision_by_user_id
               WHERE i.migration_id = ? ORDER BY i.thread_id, i.item_id""", (run["target_version_id"], migration_id)
        ).fetchall()
    finally:
        connection.close()
    counts = {state: sum(row["state"] == state for row in rows) for state in ["pending", "carried", "skipped"]}
    result = _serialize_run(run, counts)
    result["items"] = [dict(row) | {
        "source_target": {"thread_target_id": row["source_thread_target_id"],
                          "anchor": get_anchor(database_path, row["source_anchor_id"])},
        "thread": get_thread(database_path, row["thread_id"], run["source_version_id"]),
        "decision_by": ({"user_id": row["decision_by_user_id"], "display_name": row["decision_name"]}
                        if row["decision_by_user_id"] else None),
    } for row in rows]
    return result


def list_migrations(database_path, document_id):
    connection = connect(database_path)
    try:
        if connection.execute("SELECT 1 FROM documents WHERE document_id = ?", (document_id,)).fetchone() is None:
            raise MigrationNotFoundError("The logical document does not exist.")
        rows = connection.execute(
            "SELECT migration_id FROM migration_runs WHERE document_id = ? ORDER BY created_at DESC, migration_id",
            (document_id,),
        ).fetchall()
        result = []
        for row in rows:
            run = _run(connection, row["migration_id"])
            counts = {state: 0 for state in ["pending", "carried", "skipped"]}
            for count in connection.execute(
                "SELECT state, COUNT(*) AS count FROM migration_items WHERE migration_id = ? GROUP BY state", (row["migration_id"],)
            ):
                counts[count["state"]] = count["count"]
            result.append(_serialize_run(run, counts))
        return result
    finally:
        connection.close()


def create_migration(database_path, document_id, source_version_id, target_version_id, user_id):
    if not all(isinstance(value, str) and value for value in [source_version_id, target_version_id]):
        raise MigrationError("Choose both source and target versions.")
    if source_version_id == target_version_id:
        raise MigrationError("Source and target versions must differ.")
    migration_id, timestamp = str(uuid4()), now_utc()
    with transaction(database_path) as connection:
        require_active_user(connection, user_id)
        if connection.execute("SELECT 1 FROM documents WHERE document_id = ?", (document_id,)).fetchone() is None:
            raise MigrationNotFoundError("The logical document does not exist.")
        for version_id in [source_version_id, target_version_id]:
            version = connection.execute("SELECT document_id FROM document_versions WHERE version_id = ?", (version_id,)).fetchone()
            if version is None:
                raise MigrationNotFoundError("The selected version does not exist.")
            if version["document_id"] != document_id:
                raise MigrationError("Both versions must belong to this logical document.")
        connection.execute(
            """INSERT INTO migration_runs
               (migration_id, document_id, source_version_id, target_version_id, created_by_user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""", (migration_id, document_id, source_version_id, target_version_id, user_id, timestamp)
        )
        for head in connection.execute(
            "SELECT * FROM thread_target_heads WHERE document_version_id = ? ORDER BY thread_id", (source_version_id,)
        ).fetchall():
            destination = _head(connection, head["thread_id"], target_version_id)
            connection.execute(
                """INSERT INTO migration_items
                   (item_id, migration_id, thread_id, source_thread_target_id, state,
                    target_thread_target_id, decision_by_user_id, decided_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid4()), migration_id, head["thread_id"], head["thread_target_id"],
                 "carried" if destination else "pending", destination["thread_target_id"] if destination else None,
                 user_id if destination else None, timestamp if destination else None),
            )
    return get_migration(database_path, migration_id)


def _open_item(connection, migration_id, item_id, user_id, expected_revision):
    require_active_user(connection, user_id)
    run = _run(connection, migration_id)
    if run["status"] != "open":
        raise MigrationConflictError("This run is completed. Start another run to make further corrections.")
    item = connection.execute(
        "SELECT * FROM migration_items WHERE migration_id = ? AND item_id = ?", (migration_id, item_id)
    ).fetchone()
    if item is None:
        raise MigrationNotFoundError("The carry-forward item does not belong to this run.")
    if type(expected_revision) is not int or expected_revision < 1:
        raise MigrationError("expected_revision must be a positive integer.")
    if item["revision_number"] != expected_revision:
        raise MigrationConflictError("This migration item changed elsewhere. Review the refreshed state before trying again.")
    return run, item


def _record_decision(connection, item_id, state, target_id, user_id, timestamp, note=None):
    connection.execute(
        """UPDATE migration_items SET state = ?, target_thread_target_id = ?, decision_by_user_id = ?,
                  decided_at = ?, skip_note = ?, revision_number = revision_number + 1 WHERE item_id = ?""",
        (state, target_id, user_id, timestamp, note, item_id),
    )


def carry_item(database_path, migration_id, item_id, user_id, anchor_payload,
               expected_revision, expected_target_id, *, reanchor=False):
    validated = validate_anchor_payload(anchor_payload)
    timestamp, target_id = now_utc(), str(uuid4())
    with transaction(database_path) as connection:
        run, item = _open_item(connection, migration_id, item_id, user_id, expected_revision)
        if item["state"] == "skipped":
            raise MigrationConflictError("Skipped items are final for this run. Start another run to reconsider them.")
        head = _head(connection, item["thread_id"], run["target_version_id"])
        current_id = head["thread_target_id"] if head else None
        if expected_target_id != current_id:
            raise MigrationConflictError("The destination target changed elsewhere. Review the refreshed target before trying again.")
        if (reanchor and head is None) or (not reanchor and (head is not None or item["state"] != "pending")):
            raise MigrationConflictError("Use carry for an untargeted thread or re-anchor to replace an existing target.")
        thread = connection.execute("SELECT * FROM threads WHERE thread_id = ?", (item["thread_id"],)).fetchone()
        if head and head["thread_target_id"] == thread["origin_thread_target_id"]:
            raise MigrationConflictError("The original version's target cannot be replaced.")
        anchor_id = insert_validated_anchor(connection, run["target_version_id"], validated)
        connection.execute(
            "INSERT INTO thread_targets VALUES (?, ?, ?, 'manual', ?)", (target_id, item["thread_id"], anchor_id, timestamp)
        )
        connection.execute(
            """INSERT INTO thread_target_provenance
               (thread_target_id, source_thread_target_id, migration_run_id, supersedes_thread_target_id,
                method, created_by_user_id, created_at) VALUES (?, ?, ?, ?, 'manual_selection', ?, ?)""",
            (target_id, item["source_thread_target_id"], migration_id, current_id, user_id, timestamp),
        )
        if head:
            connection.execute(
                """UPDATE thread_target_heads SET thread_target_id = ?, updated_at = ?, updated_by_user_id = ?
                   WHERE thread_id = ? AND document_version_id = ?""",
                (target_id, timestamp, user_id, item["thread_id"], run["target_version_id"]),
            )
        else:
            connection.execute("INSERT INTO thread_target_heads VALUES (?, ?, ?, ?, ?)",
                               (item["thread_id"], run["target_version_id"], target_id, timestamp, user_id))
        _record_decision(connection, item_id, "carried", target_id, user_id, timestamp)
        thread_id = item["thread_id"]
    return get_thread(database_path, thread_id, run["target_version_id"])


def skip_item(database_path, migration_id, item_id, user_id, expected_revision, note=""):
    if not isinstance(note, str) or len(note) > 1000:
        raise MigrationError("A skip note must be text with at most 1000 characters.")
    with transaction(database_path) as connection:
        run, item = _open_item(connection, migration_id, item_id, user_id, expected_revision)
        if item["state"] != "pending" or _head(connection, item["thread_id"], run["target_version_id"]):
            raise MigrationConflictError("Only pending items without a destination target can be skipped.")
        _record_decision(connection, item_id, "skipped", None, user_id, now_utc(), note.strip() or None)
    return get_migration(database_path, migration_id)


def accept_existing_target(database_path, migration_id, item_id, user_id, expected_revision, expected_target_id):
    """A concurrent run may have supplied a destination for a pending item."""
    with transaction(database_path) as connection:
        run, item = _open_item(connection, migration_id, item_id, user_id, expected_revision)
        head = _head(connection, item["thread_id"], run["target_version_id"])
        if item["state"] != "pending" or not head or head["thread_target_id"] != expected_target_id:
            raise MigrationConflictError("Review the current pending item and destination before accepting it.")
        _record_decision(connection, item_id, "carried", expected_target_id, user_id, now_utc())
    return get_migration(database_path, migration_id)


def complete_migration(database_path, migration_id, user_id):
    with transaction(database_path) as connection:
        require_active_user(connection, user_id)
        run = _run(connection, migration_id)
        if run["status"] == "open":
            if connection.execute("SELECT 1 FROM migration_items WHERE migration_id = ? AND state = 'pending'", (migration_id,)).fetchone():
                raise MigrationConflictError("Decide every pending item before completing the run.")
            connection.execute(
                "UPDATE migration_runs SET status = 'completed', completed_at = ?, completed_by_user_id = ? WHERE migration_id = ?",
                (now_utc(), user_id, migration_id),
            )
    return get_migration(database_path, migration_id)
