"""Ephemeral version rooms and presence; permanent writes belong to HTTP services."""

from threading import RLock
from uuid import uuid4

from flask import current_app, request
from flask_socketio import SocketIO, join_room, leave_room

from .auth import current_user, document_role, resource_document
from .database import version_table, connect
from .documents import get_version, now_utc


def version_room(version_id):
    return f"version:{version_id}"


def prune_version(version_id):
    """Recheck idle recipients before sending new review or presence information."""
    registry=current_app.extensions['review_presence']
    socketio=current_app.extensions['socketio']
    c=connect(current_app.config['DATABASE'])
    try:
        with registry.lock:
            for sid,entry in list(registry.connections.items()):
                if entry['version_id']!=version_id:
                    continue
                user=c.execute(f'''SELECT u.* FROM users u
                    JOIN allowed_emails e ON e.normalized_email=u.normalized_email AND e.enabled=1
                    JOIN document_access a ON a.user_id=u.user_id
                    JOIN {version_table(c)} v ON v.document_id=a.document_id
                    WHERE u.user_id=? AND u.is_active=1 AND u.email_verified=1
                    AND u.google_subject IS NOT NULL AND v.version_id=?''',
                    (entry['user']['user_id'],version_id)).fetchone()
                if user is None:
                    registry.connections.pop(sid,None)
                    socketio.server.leave_room(sid,version_room(version_id),namespace='/')
                else:
                    entry['user']=dict(user)
    finally:
        c.close()


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
                "pages": [], "review_color": user.get('review_color','#c66b54'),
            })
            record["connection_count"] += 1
            if entry["page"] is not None:
                record["page"] = entry["page"]
                record['pages'] = entry.get('pages',[entry['page']])
                record['review_color'] = user.get('review_color','#c66b54')
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
            prune_version(version_id)
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
        pages=payload.get('pages',[number])
        if (not isinstance(pages,list) or not 1<=len(pages)<=2 or number not in pages or
            any(type(p) is not int or not 1<=p<=1_000_000 for p in pages) or
            len(set(pages))!=len(pages) or (len(pages)==2 and abs(pages[0]-pages[1])!=1)):
            return {'ok':False,'error':'Report one page or one adjacent two-page spread.'}
        with presence.lock:
            entry = presence.connections.get(request.sid)
            if entry is None:
                return {"ok": False, "error": "Join a version first."}
            if current_user() is None or document_role(current_user(), resource_document({"version_id": entry["version_id"]})) is None:
                remove(request.sid)
                return {"ok": False, "error": "Review access denied."}
            if entry["page"] != number or entry.get('pages') != pages:
                presence.sequence += 1
                entry.update(page=number, pages=pages, sequence=presence.sequence, user=current_user())
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
            prune_version(version_id)
            from .review_policy import settings
            c=connect(current_app.config['DATABASE'])
            try:
                isolated=settings(c,thread['document_id'])['visibility_policy']=='isolated'
            finally:
                c.close()
            if isolated:
                notify_version_changed(version_id)
                continue
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
            prune_version(version_id)
            from .review_policy import settings
            c=connect(current_app.config['DATABASE'])
            try:
                isolated=settings(c,run['document_id'])['visibility_policy']=='isolated'
            finally:
                c.close()
            if isolated:
                notify_version_changed(version_id)
                continue
            current_app.extensions["socketio"].emit("migration.changed", {
                "schema_version": 1, "migration_id": run["migration_id"], "version_id": version_id,
            }, to=version_room(version_id))
        except Exception:
            current_app.logger.exception("Committed migration notification failed for version %s", version_id)


def notify_version_changed(version_id):
    """Content-free invalidation: no actor, comment, section or thread identifiers."""
    try:
        prune_version(version_id)
        current_app.extensions['socketio'].emit('review.invalidated',
            {'schema_version':1,'version_id':version_id},to=version_room(version_id))
    except Exception:
        current_app.logger.exception('Committed review invalidation failed')


def notify_user_presentation_changed(user_id):
    try:
        registry=current_app.extensions['review_presence']
        c=connect(current_app.config['DATABASE'])
        try:
            user=dict(c.execute('SELECT * FROM users WHERE user_id=?',(user_id,)).fetchone())
            versions=[r[0] for r in c.execute(f'''SELECT DISTINCT v.version_id FROM {version_table(c)} v
                JOIN document_access a USING(document_id) WHERE a.user_id=?''',(user_id,))]
        finally:
            c.close()
        with registry.lock:
            for entry in registry.connections.values():
                if entry['user']['user_id']==user_id:
                    entry['user']=user
            for version_id in versions:
                notify_version_changed(version_id)
                prune_version(version_id)
                current_app.extensions['socketio'].emit('review.presence',registry.snapshot(version_id),to=version_room(version_id))
    except Exception:
        current_app.logger.exception('Committed presentation invalidation failed')


def notify_reading_changed(version_id, reader_id=None):
    """Committed reading invalidation to eligible owners and the reader only.

    No reading data travels in the event; canonical HTTP reads recheck access.
    Policy changes reach everyone in the version so closed tools also stop timing.
    """
    try:
        prune_version(version_id)
        registry=current_app.extensions['review_presence']
        c=connect(current_app.config['DATABASE'])
        try:
            owners={r[0] for r in c.execute(f"SELECT a.user_id FROM document_access a JOIN {version_table(c)} v USING(document_id) WHERE v.version_id=? AND a.role='owner'",(version_id,))}
            with registry.lock:
                recipients=[sid for sid,entry in registry.connections.items()
                    if entry['version_id']==version_id and
                    (reader_id is None or entry['user']['user_id']==reader_id or entry['user']['user_id'] in owners)]
            for sid in recipients:
                current_app.extensions['socketio'].emit('reading.changed',
                    {'schema_version':1,'version_id':version_id},to=sid)
        finally:
            c.close()
    except Exception:
        current_app.logger.exception('Committed reading notification failed for version %s',version_id)


def notify_version_deleted(version_id):
    """After commit, retire the room and send eligible viewers back to the document."""
    try:
        from .access import ELIGIBLE
        registry=current_app.extensions['review_presence'];io=current_app.extensions['socketio']
        c=connect(current_app.config['DATABASE'])
        try:
            with registry.lock:
                recipients=[sid for sid,entry in registry.connections.items() if entry['version_id']==version_id and
                    c.execute(ELIGIBLE+" AND u.user_id=? AND EXISTS(SELECT 1 FROM document_access a JOIN document_versions v USING(document_id) WHERE a.user_id=u.user_id AND v.version_id=?)",(entry['user']['user_id'],version_id)).fetchone()]
                for sid in recipients:
                    io.emit('review.version_deleted',{'schema_version':1,'version_id':version_id},to=sid)
                prune_version(version_id)
        finally:
            c.close()
    except Exception:
        current_app.logger.exception('Committed version deletion notification failed for %s',version_id)
