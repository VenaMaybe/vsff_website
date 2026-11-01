"""HTML entry point and strictly shaped HTTP APIs for manual migration."""

from functools import wraps

from flask import Blueprint, abort, current_app, jsonify, render_template

from .anchors import AnchorValidationError
from .documents import get_document, list_versions
from .migrations import (MigrationError, accept_existing_target, carry_item, complete_migration,
                         create_migration, get_migration, list_migrations, skip_item)
from .realtime import notify_migration_changed, notify_thread_changed
from .routes import ApiPayloadError, api_error, current_reviewer_id, database_path, exact_fields, json_payload
from .targets import target_history
from .threads import MAX_THREAD_PAYLOAD_BYTES, ThreadNotFoundError
from .users import UserNotFoundError


bp = Blueprint("carry", __name__)


def migration_api(operation):
    @wraps(operation)
    def wrapped(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except ApiPayloadError as error:
            return api_error(error.code, str(error), error.status)
        except MigrationError as error:
            return api_error(error.code, str(error), error.status)
        except UserNotFoundError as error:
            return api_error("reviewer_required", str(error), 409)
        except AnchorValidationError as error:
            return api_error("invalid_anchor", str(error), 422)
        except ThreadNotFoundError as error:
            return api_error("thread_not_found", str(error), 404)
        except Exception:
            current_app.logger.exception("Manual carry-forward operation failed")
            return api_error("migration_failed", "The carry-forward operation could not be saved. Refresh and try again.", 500)
    return wrapped


@bp.get("/documents/<document_id>/migrations")
def migration_page(document_id):
    document = get_document(database_path(), document_id)
    if document is None:
        abort(404)
    return render_template("migrations.html", document=document, versions=list_versions(database_path(), document_id),
                           migrations=list_migrations(database_path(), document_id))


@bp.get("/api/documents/<document_id>/migrations")
@migration_api
def document_migrations(document_id):
    return jsonify({"migrations": list_migrations(database_path(), document_id)})


@bp.post("/api/documents/<document_id>/migrations")
@migration_api
def new_migration(document_id):
    payload = json_payload(4096)
    exact_fields(payload, {"source_version_id", "target_version_id"})
    run = create_migration(database_path(), document_id, payload["source_version_id"], payload["target_version_id"], current_reviewer_id())
    notify_migration_changed(run)
    return jsonify({"migration": run}), 201


@bp.get("/api/migrations/<migration_id>")
@migration_api
def migration_item(migration_id):
    return jsonify({"migration": get_migration(database_path(), migration_id)})


@bp.post("/api/migrations/<migration_id>/items/<item_id>/<action>")
@migration_api
def decide_item(migration_id, item_id, action):
    if action not in {"carry", "reanchor", "skip", "accept"}:
        return api_error("not_found", "Unknown carry-forward action.", 404)
    payload = json_payload(MAX_THREAD_PAYLOAD_BYTES)
    fields = {"expected_revision", "note"} if action == "skip" else {"expected_revision", "expected_target_id"}
    if action in {"carry", "reanchor"}:
        fields.add("anchor")
    exact_fields(payload, fields)
    user_id = current_reviewer_id()
    if action in {"carry", "reanchor", "accept"}:
        value = payload["expected_target_id"]
        if value is not None and (not isinstance(value, str) or not value or len(value) > 128):
            raise MigrationError("expected_target_id must be a target ID or null.")
    if action == "skip":
        run = skip_item(database_path(), migration_id, item_id, user_id, payload["expected_revision"], payload["note"])
    elif action == "accept":
        run = accept_existing_target(database_path(), migration_id, item_id, user_id,
                                     payload["expected_revision"], payload["expected_target_id"])
    else:
        thread = carry_item(database_path(), migration_id, item_id, user_id, payload["anchor"],
                            payload["expected_revision"], payload["expected_target_id"], reanchor=action == "reanchor")
        notify_thread_changed(thread, "thread.reanchored" if action == "reanchor" else "thread.targeted")
        run = get_migration(database_path(), migration_id)
    notify_migration_changed(run)
    return jsonify({"migration": run})


@bp.post("/api/migrations/<migration_id>/complete")
@migration_api
def finish_migration(migration_id):
    payload = json_payload(4096)
    exact_fields(payload, set())
    run = complete_migration(database_path(), migration_id, current_reviewer_id())
    notify_migration_changed(run)
    return jsonify({"migration": run})


@bp.get("/api/threads/<thread_id>/targets")
@migration_api
def thread_target_history(thread_id):
    return jsonify({"thread_id": thread_id, "targets": target_history(database_path(), thread_id)})
