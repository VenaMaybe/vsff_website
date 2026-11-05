"""HTTP and maintenance-command interface for PDF Review."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import click
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from .anchors import (
    MAX_ANCHOR_PAYLOAD_BYTES,
    AnchorInUseError,
    AnchorNotFoundError,
    AnchorValidationError,
    AnchorVersionNotFoundError,
    create_anchor,
    delete_anchor,
    list_anchors,
)
from .database import connect
from .auth import current_user, document_role
from .access import AccessDenied
from .documents import (
    DocumentError,
    create_document,
    get_document,
    delete_version as withdraw_version,
    VersionNotFoundError,
    get_version,
    import_version,
    list_documents,
    list_versions,
)
from .storage import BlobIntegrityError, InvalidPDFError, StorageError
from .realtime import notify_thread_changed
from .migrations import MigrationError, get_migration
from .threads import (
    MAX_THREAD_PAYLOAD_BYTES,
    CommentNotFoundError,
    CommentConflictError,
    CommentPermissionError,
    ThreadNotFoundError,
    ThreadValidationError,
    add_comment,
    create_thread,
    delete_comment,
    edit_comment,
    list_threads,
    set_thread_resolved,
)
from .users import (
    UserNotFoundError,
)


bp = Blueprint("core", __name__, cli_group=None)


def database_path() -> Path:
    return Path(current_app.config["DATABASE"])


def blob_store():
    return current_app.extensions["blob_store"]


def api_error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def json_payload(maximum_bytes: int):
    if request.content_length is not None and request.content_length > maximum_bytes:
        raise ApiPayloadError(
            "payload_too_large", "The JSON request exceeds the allowed size.", 413
        )
    if not request.is_json:
        raise ApiPayloadError("invalid_json", "A JSON request body is required.", 400)
    body = request.get_data(cache=True)
    if len(body) > maximum_bytes:
        raise ApiPayloadError(
            "payload_too_large", "The JSON request exceeds the allowed size.", 413
        )
    try:
        payload = request.get_json(silent=False)
    except Exception as error:
        raise ApiPayloadError(
            "invalid_json", "The request body is not valid JSON.", 400
        ) from error
    if not isinstance(payload, dict):
        raise ApiPayloadError("invalid_request", "The JSON body must be an object.", 400)
    return payload


def exact_fields(payload: dict, expected: set[str]) -> None:
    if set(payload) != expected:
        raise ApiPayloadError(
            "invalid_request",
            f"The request must contain exactly: {', '.join(sorted(expected))}.",
            400,
        )


class ApiPayloadError(RuntimeError):
    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code = code
        self.status = status


def current_reviewer_id() -> str:
    user = current_user()
    if user is None:
        abort(401)
    return user["user_id"]


@bp.get("/")
def dashboard():
    return render_template("dashboard.html", documents=[doc for doc in list_documents(database_path()) if document_role(g.auth_user, doc["document_id"])])


@bp.post("/documents")
def new_document():
    try:
        document_id = create_document(database_path(), request.form.get("title", ""), owner_id=current_reviewer_id())
    except DocumentError as error:
        flash(str(error), "error")
        return redirect(url_for("core.dashboard")), 303
    flash("Document created.", "success")
    return redirect(url_for("core.document_detail", document_id=document_id)), 303


@bp.get("/documents/<document_id>")
def document_detail(document_id: str):
    document = get_document(database_path(), document_id)
    if document is None:
        abort(404)
    return render_template(
        "document.html",
        document=document,
        versions=list_versions(database_path(), document_id),
    )


@bp.post("/documents/<document_id>/versions")
def new_version(document_id: str):
    if get_document(database_path(), document_id) is None:
        abort(404)
    upload = request.files.get("pdf")
    try:
        if upload is None:
            raise DocumentError("Choose a PDF file to import.")
        result = import_version(
            database_path(),
            blob_store(),
            document_id,
            upload.stream,
            upload.filename,
            request.form.get("version_label"),
        )
    except (DocumentError, InvalidPDFError, BlobIntegrityError, StorageError) as error:
        flash(str(error), "error")
        return redirect(url_for("core.document_detail", document_id=document_id)), 303
    except OSError:
        current_app.logger.exception("PDF filesystem import failed")
        flash("The PDF could not be copied into application storage.", "error")
        return redirect(url_for("core.document_detail", document_id=document_id)), 303
    except Exception:
        current_app.logger.exception("PDF version database import failed")
        flash("The version record could not be saved; no historical PDF was changed.", "error")
        return redirect(url_for("core.document_detail", document_id=document_id)), 303

    if result.blob.created:
        message = "Version imported into a new immutable blob."
    else:
        message = "Version imported; identical stored bytes were safely deduplicated."
    flash(message, "success")
    return redirect(url_for("core.document_detail", document_id=document_id)), 303


@bp.route('/versions/<version_id>/delete',methods=['GET','POST'])
def delete_version(version_id):
    version=get_version(database_path(),version_id)
    if version is None:
        abort(404)
    if request.method=='GET':
        return render_template('delete_version.html',version=version)
    if set(request.form)-{'csrf_token','confirm_version_id'}:
        abort(400)
    try:
        document_id=withdraw_version(database_path(),version_id,current_reviewer_id(),request.form.get('confirm_version_id'))
    except AccessDenied:
        abort(403)
    except VersionNotFoundError:
        abort(404)
    except DocumentError as error:
        return render_template('delete_version.html',version=version,error=str(error)),400
    from .realtime import notify_version_deleted
    notify_version_deleted(version_id)
    flash('Version deleted. Other versions are unchanged.','success')
    return redirect(url_for('core.document_detail',document_id=document_id)),303


@bp.get("/versions/<version_id>/view")
def view_version(version_id: str):
    version = get_version(database_path(), version_id)
    if version is None:
        abort(404)
    integrity = blob_store().verify(
        version["blob_path"], version["sha256"], version["file_size"]
    )
    if integrity.actual_sha256 is None:
        return render_template(
            "error.html",
            title="PDF missing",
            message="This immutable version is recorded, but its stored PDF blob is missing.",
        ), 404
    viewer_base = url_for("static", filename="vendor/pdfjs/web/viewer.html")
    pdf_url = url_for("core.version_pdf", version_id=version_id)
    viewer_url = f"{viewer_base}?file={quote(pdf_url, safe='')}"
    from .review_policy import settings
    connection = connect(database_path())
    try:
        downloads_allowed = bool(settings(connection, version['document_id'])['downloads_allowed'])
    finally:
        connection.close()
    anchor_config = {
        "versionId": version_id,
        "downloadsAllowed": downloads_allowed,
        "anchorsUrl": url_for("core.version_anchors", version_id=version_id, standalone="1"),
        "deleteUrlTemplate": url_for("core.anchor_item", anchor_id="__ANCHOR_ID__"),
        "threadsUrl": url_for("core.version_threads", version_id=version_id),
        "threadCommentsUrlTemplate": url_for(
            "core.thread_comments", thread_id="__THREAD_ID__"
        ),
        "commentUrlTemplate": url_for(
            "core.comment_item", comment_id="__COMMENT_ID__"
        ),
        "resolveUrlTemplate": url_for(
            "core.resolve_thread", thread_id="__THREAD_ID__"
        ),
        "reopenUrlTemplate": url_for(
            "core.reopen_thread", thread_id="__THREAD_ID__"
        ),
        "reviewersUrl": url_for("core.reviewers"),
        "canMutate": g.document_role != "viewer",
        "isOwner": g.document_role == "owner",
        "documentId": version['document_id'],
        "currentUserId": g.auth_user['user_id'],
        "contextUrl": url_for('review_options.context',version_id=version_id),
        "preferencesUrl": url_for('review_options.viewer_preferences',document_id=version['document_id']),
    }
    migration_id = request.args.get("migration")
    migration = None
    if migration_id:
        try:
            migration = get_migration(database_path(), migration_id)
        except MigrationError:
            abort(404)
        if migration["target_version_id"] != version_id:
            abort(404)
        anchor_config["migrationUrl"] = url_for("carry.migration_item", migration_id=migration_id)
    anchor_config["initialThreadId"] = request.args.get("thread")
    return render_template(
        "viewer.html",
        version=version,
        viewer_url=viewer_url,
        anchor_config=anchor_config,
        migration=migration,
    )


@bp.get("/versions/<version_id>/pdf")
def version_pdf(version_id: str):
    version = get_version(database_path(), version_id)
    if version is None:
        abort(404)
    try:
        path = blob_store().resolve(version["blob_path"], version["sha256"])
    except StorageError:
        abort(404)
    if not path.is_file():
        abort(404)
    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=version["original_filename"],
        conditional=True,
        etag=version["sha256"],
    )


@bp.post("/versions/<version_id>/verify")
def verify_version(version_id: str):
    version = get_version(database_path(), version_id)
    if version is None:
        abort(404)
    try:
        result = blob_store().verify(
            version["blob_path"], version["sha256"], version["file_size"]
        )
    except StorageError as error:
        flash(f"Integrity check failed: {error}", "error")
    else:
        category = "success" if result.ok else "error"
        detail = result.message
        if result.actual_sha256 and not result.ok:
            detail += f" Actual SHA-256: {result.actual_sha256}."
        flash(detail, category)
    return redirect(
        url_for("core.document_detail", document_id=version["document_id"])
    ), 303


@bp.get("/api/versions/<version_id>/anchors")
def version_anchors(version_id: str):
    try:
        anchors = list_anchors(database_path(), version_id, standalone_only=request.args.get("standalone") == "1", user_id=current_reviewer_id())
    except AnchorVersionNotFoundError as error:
        return api_error("version_not_found", str(error), 404)
    return jsonify({"version_id": version_id, "anchors": anchors})


@bp.post("/api/versions/<version_id>/anchors")
def create_version_anchor(version_id: str):
    if request.content_length is not None and request.content_length > MAX_ANCHOR_PAYLOAD_BYTES:
        return api_error(
            "payload_too_large",
            "The anchor payload exceeds the 2 MB limit.",
            413,
        )
    if not request.is_json:
        return api_error("invalid_json", "A JSON request body is required.", 400)
    body = request.get_data(cache=True)
    if len(body) > MAX_ANCHOR_PAYLOAD_BYTES:
        return api_error(
            "payload_too_large",
            "The anchor payload exceeds the 2 MB limit.",
            413,
        )
    try:
        payload = request.get_json(silent=False)
    except Exception:
        return api_error("invalid_json", "The request body is not valid JSON.", 400)
    try:
        anchor = create_anchor(database_path(), version_id, payload)
    except AnchorVersionNotFoundError as error:
        return api_error("version_not_found", str(error), 404)
    except AnchorValidationError as error:
        return api_error("invalid_anchor", str(error), 422)
    except Exception:
        current_app.logger.exception("Anchor creation failed")
        return api_error(
            "anchor_creation_failed",
            "The anchor could not be saved; no partial anchor was retained.",
            500,
        )
    return jsonify({"anchor": anchor}), 201


@bp.get("/api/reviewers")
def reviewers():
    user = current_user()
    summary = {key: user[key] for key in ("user_id", "display_name", "email", "review_color")}
    return jsonify({"reviewers": [summary], "current_reviewer": summary})


@bp.get("/api/versions/<version_id>/threads")
def version_threads(version_id: str):
    try:
        threads = list_threads(database_path(), version_id, current_reviewer_id())
    except AnchorVersionNotFoundError as error:
        return api_error("version_not_found", str(error), 404)
    return jsonify({"version_id": version_id, "threads": threads})


@bp.post("/api/versions/<version_id>/threads")
def create_version_thread(version_id: str):
    try:
        payload = json_payload(MAX_THREAD_PAYLOAD_BYTES)
        exact_fields(payload, {"anchor", "body"})
        user_id = current_reviewer_id()
        thread = create_thread(
            database_path(), version_id, user_id, payload["anchor"], payload["body"], enforce_access=True
        )
    except ApiPayloadError as error:
        return api_error(error.code, str(error), error.status)
    except UserNotFoundError as error:
        return api_error("reviewer_required", str(error), 409)
    except AnchorVersionNotFoundError as error:
        return api_error("version_not_found", str(error), 404)
    except AnchorValidationError as error:
        return api_error("invalid_anchor", str(error), 422)
    except ThreadValidationError as error:
        return api_error("invalid_comment", str(error), 422)
    except AccessDenied:
        abort(403)
    except Exception:
        current_app.logger.exception("Atomic thread creation failed")
        return api_error(
            "thread_creation_failed",
            "The review thread could not be saved; no partial discussion was retained.",
            500,
        )
    notify_thread_changed(thread, "thread.created")
    return jsonify({"thread": thread}), 201


@bp.post("/api/threads/<thread_id>/comments")
def thread_comments(thread_id: str):
    try:
        payload = json_payload(16 * 1024)
        exact_fields(payload, {"body"})
        thread = add_comment(
            database_path(), thread_id, current_reviewer_id(), payload["body"], enforce_access=True
        )
    except ApiPayloadError as error:
        return api_error(error.code, str(error), error.status)
    except UserNotFoundError as error:
        return api_error("reviewer_required", str(error), 409)
    except ThreadNotFoundError as error:
        return api_error("thread_not_found", str(error), 404)
    except ThreadValidationError as error:
        return api_error("invalid_comment", str(error), 422)
    notify_thread_changed(thread, "comment.created")
    return jsonify({"thread": thread}), 201


@bp.patch("/api/comments/<comment_id>")
def comment_item_patch(comment_id: str):
    try:
        payload = json_payload(16 * 1024)
        exact_fields(payload, {"body", "expected_revision"})
        thread = edit_comment(
            database_path(), comment_id, current_reviewer_id(), payload["body"],
            payload["expected_revision"], enforce_access=True,
        )
    except ApiPayloadError as error:
        return api_error(error.code, str(error), error.status)
    except UserNotFoundError as error:
        return api_error("reviewer_required", str(error), 409)
    except CommentNotFoundError as error:
        return api_error("comment_not_found", str(error), 404)
    except CommentConflictError as error:
        return jsonify({"error": {"code": "comment_conflict", "message": str(error),
                                  "current_revision": error.current_revision}}), 409
    except CommentPermissionError as error:
        return api_error("comment_edit_forbidden", str(error), 403)
    except ThreadValidationError as error:
        return api_error("invalid_comment", str(error), 422)
    notify_thread_changed(thread, "comment.edited", comment_id)
    return jsonify({"thread": thread})


@bp.delete("/api/comments/<comment_id>")
def comment_item(comment_id: str):
    try:
        thread = delete_comment(database_path(), comment_id, current_reviewer_id(), enforce_access=True)
    except UserNotFoundError as error:
        return api_error("reviewer_required", str(error), 409)
    except CommentNotFoundError as error:
        return api_error("comment_not_found", str(error), 404)
    except CommentPermissionError as error:
        return api_error("comment_delete_forbidden", str(error), 403)
    notify_thread_changed(thread, "comment.deleted", comment_id)
    return jsonify({"thread": thread})


@bp.post("/api/threads/<thread_id>/resolve")
def resolve_thread(thread_id: str):
    try:
        thread = set_thread_resolved(
            database_path(), thread_id, current_reviewer_id(), True, enforce_access=True
        )
    except UserNotFoundError as error:
        return api_error("reviewer_required", str(error), 409)
    except ThreadNotFoundError as error:
        return api_error("thread_not_found", str(error), 404)
    notify_thread_changed(thread, "thread.resolved")
    return jsonify({"thread": thread})


@bp.post("/api/threads/<thread_id>/reopen")
def reopen_thread(thread_id: str):
    try:
        thread = set_thread_resolved(
            database_path(), thread_id, current_reviewer_id(), False, enforce_access=True
        )
    except UserNotFoundError as error:
        return api_error("reviewer_required", str(error), 409)
    except ThreadNotFoundError as error:
        return api_error("thread_not_found", str(error), 404)
    notify_thread_changed(thread, "thread.reopened")
    return jsonify({"thread": thread})


@bp.delete("/api/anchors/<anchor_id>")
def anchor_item(anchor_id: str):
    try:
        delete_anchor(database_path(), anchor_id)
    except AnchorNotFoundError as error:
        return api_error("anchor_not_found", str(error), 404)
    except AnchorInUseError as error:
        return api_error("anchor_in_use", str(error), 409)
    return jsonify({"deleted_anchor_id": anchor_id})


@bp.cli.command("verify-storage")
def verify_storage_command():
    """Verify every recorded immutable PDF blob."""
    connection = connect(database_path())
    try:
        versions = connection.execute(
            "SELECT version_id, sha256, blob_path, file_size FROM document_versions"
        ).fetchall()
    finally:
        connection.close()
    failures = 0
    for version in versions:
        try:
            result = blob_store().verify(
                version["blob_path"], version["sha256"], version["file_size"]
            )
        except StorageError as error:
            failures += 1
            click.echo(f"FAIL {version['version_id']}: {error}")
            continue
        label = "OK" if result.ok else "FAIL"
        click.echo(f"{label} {version['version_id']}: {result.message}")
        failures += int(not result.ok)
    click.echo(f"Checked {len(versions)} version(s); {failures} failure(s).")
    if failures:
        raise click.ClickException("Stored PDF integrity verification failed.")
