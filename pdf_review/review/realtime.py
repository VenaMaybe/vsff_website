"""Ephemeral version rooms and presence; permanent writes belong to HTTP services."""

from threading import RLock
from uuid import uuid4

from flask import current_app, request
from flask_socketio import SocketIO, join_room, leave_room

from .auth import current_user, document_role, resource_document
from .database import connect
from .documents import get_version, now_utc


def version_room(version_id):
    return f"version:{version_id}"


class Presence:
    """One registry per application, serialized together with snapshot emission."""

    def __init__(self):
        self.lock = RLock()
        self.connections = {}
        self.sequence = 0

    def snapshot(self, version_id):
        users = {}
        for entry in sorted(self.connections.values(), key=lambda item: item["sequence"]):
            if entry["version_id"] != version_id or entry["user"] is None:
                continue
            user = entry["user"]
            record = users.setdefault(user["user_id"], {
                "user_id": user["user_id"], "display_name": user["display_name"],
                "connection_count": 0, "page": None,
            })
            record["connection_count"] += 1
            if entry["page"] is not None:
                record["page"] = entry["page"]
        return {"schema_version": 1, "version_id": version_id,
                "reviewers": sorted(users.values(), key=lambda user: (user["display_name"].casefold(), user["user_id"]))}


def init_realtime(app):
    # Per-factory instances prevent presence/handlers leaking between test applications.
    def same_origin(origin, environ):
        # Engine.IO's default also consults forwarded host/proto headers. Do not
        # inherit that implicit trust; use the configured public origin, or the
        # direct WSGI origin for unconfigured loopback development.
        host = app.config.get("SERVER_NAME") or environ.get("HTTP_HOST", "")
        scheme = app.config["PREFERRED_URL_SCHEME"] if app.config.get("SERVER_NAME") else environ.get("wsgi.url_scheme", "http")
        return origin == f"{scheme}://{host}"

    socketio = SocketIO(app, async_mode="threading", async_handlers=False,
                        cors_allowed_origins=same_origin)
    presence = Presence()
    app.extensions["review_presence"] = presence

    def publish(version_id):
        try:
            socketio.emit("review.presence", presence.snapshot(version_id), to=version_room(version_id))
        except Exception:
            app.logger.exception("Ephemeral presence notification failed for version %s", version_id)

    def remove(sid):
        previous = presence.connections.pop(sid, None)
        if previous:
            leave_room(version_room(previous["version_id"]), sid=sid)
            publish(previous["version_id"])

    @socketio.on("connect")
    def connected(auth=None):
        if current_user() is None:
            return False
        app.logger.debug("Review socket connected: %s", request.sid)

    @socketio.on("review.join")
    def join(payload=None):
        version_id = payload.get("version_id") if isinstance(payload, dict) else None
        if not isinstance(version_id, str) or len(version_id) > 128 or get_version(app.config["DATABASE"], version_id) is None:
            app.logger.info("Review socket rejected invalid version join: %s", request.sid)
            return {"ok": False, "error": "The document version does not exist."}
        user = current_user()
        if user is None or document_role(user, resource_document({"version_id": version_id})) is None:
            return {"ok": False, "error": "Review access denied."}
        with presence.lock:
            remove(request.sid)
            join_room(version_room(version_id))
            presence.sequence += 1
            presence.connections[request.sid] = {
                "version_id": version_id, "user": user, "page": None,
                "sequence": presence.sequence,
            }
            publish(version_id)
        return {"ok": True, "version_id": version_id}

    @socketio.on("review.leave")
    def leave(payload=None):
        with presence.lock:
            remove(request.sid)
        return {"ok": True}

    @socketio.on("review.page")
    def page(payload=None):
        number = payload.get("page") if isinstance(payload, dict) else None
        if type(number) is not int or not 1 <= number <= 1_000_000:
            return {"ok": False, "error": "Page must be a positive integer."}
        with presence.lock:
            entry = presence.connections.get(request.sid)
            if entry is None:
                return {"ok": False, "error": "Join a version first."}
            if current_user() is None or document_role(current_user(), resource_document({"version_id": entry["version_id"]})) is None:
                remove(request.sid)
                return {"ok": False, "error": "Review access denied."}
            if entry["page"] != number:
                presence.sequence += 1
                entry.update(page=number, sequence=presence.sequence)
                publish(entry["version_id"])
        return {"ok": True}

    @socketio.on("disconnect")
    def disconnected(reason=None):
        with presence.lock:
            remove(request.sid)
        app.logger.debug("Review socket disconnected: %s", request.sid)

    return socketio


def notify_thread_changed(thread, kind, comment_id=None):
    """Called by routes only AFTER a successful service return (and commit).

    Even target lookup/emit failure must never turn a committed write into an HTTP error.
    Targets are queried, not inferred from an origin-only response.
    """
    try:
        connection = connect(current_app.config["DATABASE"])
        try:
            versions = connection.execute(
                """SELECT document_version_id FROM thread_target_heads
                   WHERE thread_id = ?""", (thread["thread_id"],)
            ).fetchall()
        finally:
            connection.close()
        event = {"schema_version": 1, "event_id": str(uuid4()), "kind": kind,
                 "timestamp": now_utc(), "document_id": thread["document_id"],
                 "thread_id": thread["thread_id"], "comment_id": comment_id}
        for version in versions:
            version_id = version["document_version_id"]
            try:
                current_app.extensions["socketio"].emit(
                    "review.changed", {**event, "version_id": version_id}, to=version_room(version_id)
                )
            except Exception:
                current_app.logger.exception("Committed review notification failed for version %s", version_id)
    except Exception:
        current_app.logger.exception("Committed review notification failed for thread %s", thread["thread_id"])


def notify_migration_changed(run):
    """Notify migration UI state only after a committed HTTP service operation."""
    for version_id in {run["source_version_id"], run["target_version_id"]}:
        try:
            current_app.extensions["socketio"].emit("migration.changed", {
                "schema_version": 1, "migration_id": run["migration_id"], "version_id": version_id,
            }, to=version_room(version_id))
        except Exception:
            current_app.logger.exception("Committed migration notification failed for version %s", version_id)
