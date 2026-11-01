"""Google identity, current database authorization, HTTP policy and mutation CSRF."""

import hmac
import secrets
import sqlite3
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import uuid4

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, abort, current_app, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from .database import connect, transaction
from .documents import now_utc

bp = Blueprint("auth", __name__, url_prefix="/auth")
SESSION_KEY = "authenticated_user_id"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
PROTECTED_ENDPOINTS = {
    "core.dashboard", "core.new_document", "core.document_detail", "core.new_version",
    "core.view_version", "core.version_pdf", "core.verify_version", "core.version_anchors",
    "core.create_version_anchor", "core.reviewers", "core.version_threads", "core.create_version_thread",
    "core.thread_comments", "core.comment_item_patch", "core.comment_item", "core.resolve_thread",
    "core.reopen_thread", "core.anchor_item", "carry.migration_page", "carry.document_migrations",
    "carry.new_migration", "carry.migration_item", "carry.decide_item", "carry.finish_migration",
    "carry.thread_target_history",
}


class IdentityDenied(ValueError):
    pass


def normalize_email(value):
    if not isinstance(value, str):
        raise IdentityDenied("Invalid email")
    email = value.strip().casefold()
    if len(email) > 320 or email.count("@") != 1 or any(c.isspace() for c in email) or not all(email.split("@")):
        raise IdentityDenied("Invalid email")
    return email


def safe_next(value):
    # Relative absolute-path URLs only; browsers also treat backslashes as slashes.
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        return "/"
    if any(ord(c) < 32 for c in value) or "\\" in value or "%" in value.split("?", 1)[0]:
        return "/"
    parsed = urlsplit(value)
    return value if not parsed.netloc and not parsed.scheme else "/"


def current_user():
    """Never cache authorization in the session (also used by Socket.IO)."""
    user_id = session.get(SESSION_KEY)
    if not isinstance(user_id, str):
        return None
    connection = connect(current_app.config["DATABASE"])
    try:
        row = connection.execute("""SELECT u.* FROM users u JOIN allowed_emails a
            ON a.normalized_email = u.normalized_email
            WHERE u.user_id = ? AND u.is_active = 1 AND u.email_verified = 1
              AND u.google_subject IS NOT NULL AND a.enabled = 1""", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def document_role(user, document_id):
    if user is None:
        return None
    connection = connect(current_app.config["DATABASE"])
    try:
        row = connection.execute("SELECT role FROM document_access WHERE document_id = ? AND user_id = ?",
                                 (document_id, user["user_id"])).fetchone()
        return row[0] if row else None
    finally:
        connection.close()


def resource_document(arguments):
    """Resolve only resource ownership, before reading content or touching blobs."""
    if "document_id" in arguments:
        return arguments["document_id"]
    queries = {
        "version_id": "SELECT document_id FROM document_versions WHERE version_id = ?",
        "thread_id": "SELECT document_id FROM threads WHERE thread_id = ?",
        "comment_id": "SELECT t.document_id FROM comments c JOIN threads t ON t.thread_id = c.thread_id WHERE c.comment_id = ?",
        "anchor_id": "SELECT v.document_id FROM anchor_instances a JOIN document_versions v ON v.version_id = a.document_version_id WHERE a.anchor_id = ?",
        "migration_id": "SELECT document_id FROM migration_runs WHERE migration_id = ?",
    }
    connection = connect(current_app.config["DATABASE"])
    try:
        for key, query in queries.items():
            if key in arguments:
                row = connection.execute(query, (arguments[key],)).fetchone()
                return row[0] if row else None
    finally:
        connection.close()
    return None


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def check_csrf():
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not isinstance(expected, str) or not isinstance(supplied, str) or not hmac.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8")):
        abort(400, description="Invalid CSRF token.")


def resolve_google_identity(claims):
    """Called ONLY with Authlib-validated ID-token claims; tokens never persisted."""
    if not claims or claims.get("email_verified") is not True:
        raise IdentityDenied("Verified email required")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
        raise IdentityDenied("Subject required")
    email = normalize_email(claims.get("email"))
    with transaction(current_app.config["DATABASE"]) as connection:
        if connection.execute("SELECT 1 FROM allowed_emails WHERE normalized_email = ? AND enabled = 1", (email,)).fetchone() is None:
            raise IdentityDenied("Account not allowed")
        user = connection.execute("SELECT * FROM users WHERE google_subject = ?", (subject,)).fetchone()
        matches = connection.execute("SELECT * FROM users WHERE normalized_email = ?", (email,)).fetchall()
        if len(matches) > 1 or (user and matches and matches[0]["user_id"] != user["user_id"]):
            raise IdentityDenied("Ambiguous identity")
        if user is None and matches:
            user = matches[0]
            if user["google_subject"] is not None:
                raise IdentityDenied("Email already linked")
        if user and not user["is_active"]:
            raise IdentityDenied("Inactive account")
        user_id = user["user_id"] if user else str(uuid4())
        # Legacy names are unique. Do not merge identities by display name.
        name = claims.get("name")
        name = name.strip()[:100] if isinstance(name, str) and name.strip() else email[:100]
        collision = connection.execute("SELECT user_id FROM users WHERE display_name = ? COLLATE NOCASE AND user_id != ?", (name, user_id)).fetchone()
        if collision:
            name = f"{name[:62]} ({user_id})"
        if user is None:
            connection.execute("INSERT INTO users(user_id, display_name, created_at) VALUES (?, ?, ?)", (user_id, name, now_utc()))
        connection.execute("""UPDATE users SET google_subject = ?, email = ?, normalized_email = ?,
            email_verified = 1, display_name = ?, last_login_at = ? WHERE user_id = ?""",
            (subject, claims["email"].strip(), email, name, now_utc(), user_id))
    return user_id


@bp.get("/login")
def login():
    return render_template("login.html", next_url=safe_next(request.args.get("next")))


@bp.get("/google")
def google_login():
    if not current_app.config.get("GOOGLE_CLIENT_ID") or not current_app.config.get("GOOGLE_CLIENT_SECRET"):
        return render_template("error.html", title="Sign-in unavailable", message="Google sign-in is not configured."), 503
    next_url = safe_next(request.args.get("next"))
    session.clear()
    session["login_next"] = next_url
    return current_app.extensions["google_oidc"].authorize_redirect(
        url_for("auth.google_callback", _external=True, _scheme=current_app.config["PREFERRED_URL_SCHEME"]), nonce=secrets.token_urlsafe(32))


@bp.get("/google/callback")
def google_callback():
    try:
        token = current_app.extensions["google_oidc"].authorize_access_token()
        # Authlib validates signature, issuer, audience, expiry and saved nonce.
        # Never fall back to userinfo supplied by a query string or a userinfo API.
        if not token.get("id_token") or not token.get("userinfo"):
            raise IdentityDenied("Missing ID token")
        user_id = resolve_google_identity(token["userinfo"])
    except (ValueError, sqlite3.IntegrityError):
        session.clear()
        return redirect(url_for("auth.denied"))
    except Exception:
        # OAuth/provider/transport failures are intentionally opaque; never log tokens.
        session.clear()
        return redirect(url_for("auth.denied"))
    destination = safe_next(session.get("login_next"))
    session.clear()
    session[SESSION_KEY] = user_id
    session.permanent = True
    csrf_token()
    return redirect(destination)


@bp.get("/denied")
def denied():
    return render_template("denied.html"), 403


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"), code=303)


def init_auth(app):
    if app.config["PDF_REVIEW_ENV"] not in {"development", "production"}:
        raise RuntimeError("PDF_REVIEW_ENV must be development or production.")
    production = app.config["PDF_REVIEW_ENV"] == "production"
    if production:
        if not app.config.get("SECRET_KEY") or len(app.config["SECRET_KEY"]) < 32:
            raise RuntimeError("Production requires a persistent SECRET_KEY of at least 32 characters.")
        if not all(app.config.get(k) for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "SERVER_NAME")):
            raise RuntimeError("Production requires Google credentials and PDF_REVIEW_SERVER_NAME.")
        if app.config["SESSION_COOKIE_SECURE"] is not True or app.config["PREFERRED_URL_SCHEME"] != "https":
            raise RuntimeError("Production requires HTTPS and secure session cookies.")
    elif not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning("Ephemeral development SECRET_KEY; set SECRET_KEY for persistent sessions.")
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=12))
    # Trust no proxy by default. One must be the sole, network-isolated ingress.
    hops = app.config["TRUSTED_PROXY_HOPS"]
    if type(hops) is not int or hops not in (0, 1):
        raise RuntimeError("PDF_REVIEW_PROXY_HOPS must be 0 or 1.")
    if hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=1, x_host=0, x_port=0, x_prefix=0)
    if app.config.get("SERVER_NAME"):
        app.config["TRUSTED_HOSTS"] = [app.config["SERVER_NAME"].split(":")[0]]
    oauth = OAuth(app)
    app.extensions["google_oidc"] = oauth.register("google",
        client_id=app.config["GOOGLE_CLIENT_ID"], client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"})
    app.register_blueprint(bp)

    @app.before_request
    def authorize_http():
        if request.routing_exception is not None:
            raise request.routing_exception
        if request.endpoint == "healthz":
            return
        if request.endpoint == "static":
            if request.path.casefold().endswith(".pdf"):
                abort(404)
            return
        if request.endpoint in {"auth.login", "auth.google_login", "auth.google_callback", "auth.denied"}:
            return
        g.auth_user = current_user()
        if g.auth_user is None:
            session.pop(SESSION_KEY, None)
            if request.path.startswith("/api/") or request.method in UNSAFE:
                abort(401)
            return redirect(url_for("auth.login", next=safe_next(request.full_path.rstrip("?"))))
        if request.endpoint == "auth.logout":
            check_csrf()
            return
        # Default deny: a future blueprint must explicitly enter the policy.
        if request.endpoint not in PROTECTED_ENDPOINTS:
            abort(404)
        arguments = request.view_args or {}
        if arguments:
            document_id = resource_document(arguments)
            role = document_role(g.auth_user, document_id)
            if role is None:
                abort(404)
            g.document_role = role
            if request.method in UNSAFE:
                if role == "viewer":
                    abort(403)
                if (request.blueprint == "carry" or request.endpoint in {"core.new_version", "core.verify_version"}) and role != "owner":
                    abort(403)
        elif request.endpoint not in {"core.dashboard", "core.new_document", "core.reviewers"}:
            abort(404)
        if request.method in UNSAFE:
            check_csrf()

    @app.context_processor
    def auth_context():
        return {"auth_user": getattr(g, "auth_user", None), "csrf_token": csrf_token,
                "document_role": getattr(g, "document_role", None)}

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store, private"
        if production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    for status in (400, 401, 403):
        def controlled_error(error):
            if request.routing_exception is not None:
                return "Request denied.", error.code
            if request.path.startswith("/api/"):
                return jsonify(error={"code": "access_denied" if error.code != 400 else "invalid_request",
                                      "message": "Request denied."}), error.code
            return render_template("error.html", title="Request denied", message="The request could not be authorized."), error.code
        app.register_error_handler(status, controlled_error)
