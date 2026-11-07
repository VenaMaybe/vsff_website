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

from .database import version_table, connect, transaction
from .documents import now_utc
from .legal_routes import PUBLIC_ENDPOINTS

bp = Blueprint("auth", __name__, url_prefix="/auth")
SESSION_KEY = "authenticated_user_id"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
PROTECTED_ENDPOINTS = {
    'core.main_version',
    "core.dashboard", "core.new_document", "core.document_detail", "core.new_version",
    "core.view_version", "core.version_pdf", "core.verify_version", "core.delete_version", "core.version_anchors",
    "core.create_version_anchor", "core.reviewers", "core.version_threads", "core.create_version_thread",
    "core.thread_comments", "core.comment_item_patch", "core.comment_item", "core.resolve_thread",
    "core.reopen_thread", "core.anchor_item", "carry.migration_page", "carry.document_migrations",
    "carry.new_migration", "carry.migration_item", "carry.decide_item", "carry.finish_migration",
    "carry.thread_target_history",
}
ACCOUNT_ENDPOINTS = {'accounts.account', 'accounts.profile', 'review_options.color'}
ACCOUNT_ENDPOINTS.update({'invites.manage', 'invites.detail', 'invites.mutate'})
TRUSTED_ENDPOINTS = {'invites.members', 'invites.beta_create'}
INVITE_PUBLIC_ENDPOINTS = {'invites.landing', 'invites.open'}
OWNER_ENDPOINTS = {'accounts.access_page', 'accounts.access_mutation', 'accounts.shareable'}
ADMIN_ENDPOINTS = {'accounts.admin', 'accounts.beta_email', 'accounts.site_admin'}
ADMIN_ENDPOINTS.update({'invites.trusted', 'invites.history', 'invites.legacy'})
OWNER_ENDPOINTS.add('invites.document_create')
REVIEW_OWNER_ENDPOINTS = {'core.delete_version','core.main_version','review_options.settings_page','review_options.settings_save','reading.consent',
    'review_options.sections_page','review_options.create_section','review_options.section_update',
    'review_options.placement','review_options.shared_boundary','review_options.outline'}
PROTECTED_ENDPOINTS.update(REVIEW_OWNER_ENDPOINTS | {'review_options.viewer_preferences',
    'review_options.context','review_options.response_create','review_options.response_reply','review_options.response_comment'})
READING_ENDPOINTS = {'reading.summary', 'reading.consent', 'reading.session', 'reading.batch', 'reading.reader', 'reading.properties'}
PROTECTED_ENDPOINTS.update(READING_ENDPOINTS)


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
    """Resolve ownership and live version scope before reading content or blobs."""
    if 'document_id' in arguments:
        return arguments['document_id']
    connection=connect(current_app.config['DATABASE'])
    try:
        live=version_table(connection)
        queries={
            'version_id':f'SELECT document_id FROM {live} WHERE version_id=?',
            'thread_id':'SELECT document_id FROM threads WHERE thread_id=?',
            'comment_id':'SELECT t.document_id FROM comments c JOIN threads t USING(thread_id) WHERE c.comment_id=?',
            'anchor_id':f'SELECT v.document_id FROM anchor_instances a JOIN {live} v ON v.version_id=a.document_version_id WHERE a.anchor_id=?',
            'migration_id':f'SELECT r.document_id FROM migration_runs r JOIN {live} s ON s.version_id=r.source_version_id JOIN {live} t ON t.version_id=r.target_version_id WHERE r.migration_id=?',
            'section_id':'SELECT document_id FROM sections WHERE section_id=?',
            'response_id':f'SELECT s.document_id FROM section_responses r JOIN sections s USING(section_id) JOIN {live} v ON v.version_id=r.version_id WHERE r.response_id=?',
            'section_comment_id':f'SELECT s.document_id FROM section_comments c JOIN section_responses r USING(response_id) JOIN sections s USING(section_id) JOIN {live} v ON v.version_id=r.version_id WHERE c.comment_id=?',
        }
        for key,query in queries.items():
            if key in arguments:
                row=connection.execute(query,(arguments[key],)).fetchone()
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


def resolve_google_identity(claims, invitation=None):
    """Called ONLY with Authlib-validated ID-token claims; tokens never persisted."""
    if not claims or claims.get("email_verified") is not True:
        raise IdentityDenied("Verified email required")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
        raise IdentityDenied("Subject required")
    email = normalize_email(claims.get("email"))
    with transaction(current_app.config["DATABASE"]) as connection:
        from .invitations import validate_marker, accept_in_transaction, record_join
        invited = validate_marker(connection, invitation, email) if invitation else None
        if not invited and connection.execute("SELECT 1 FROM allowed_emails WHERE normalized_email = ? AND enabled = 1", (email,)).fetchone() is None:
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
        # Existing users retain their chosen presentation name across Google logins.
        name = claims.get("name")
        name = name.strip()[:100] if isinstance(name, str) and name.strip() else email[:100]
        if user:
            name = user['display_name']
        if user is None:
            connection.execute("INSERT INTO users(user_id, display_name, created_at) VALUES (?, ?, ?)", (user_id, name, now_utc()))
        connection.execute("""UPDATE users SET google_subject = ?, email = ?, normalized_email = ?,
            email_verified = 1, display_name = ?, last_login_at = ? WHERE user_id = ?""",
            (subject, claims["email"].strip(), email, name, now_utc(), user_id))
        if invited:
            accept_in_transaction(connection, invited, user_id)
        record_join(connection, user_id, email, first_link=user is None or user['google_subject'] is None)
    return user_id


@bp.get("/login")
def login():
    return render_template("login.html", next_url=safe_next(request.args.get("next")))


@bp.get("/google")
def google_login():
    if not current_app.config.get("GOOGLE_CLIENT_ID") or not current_app.config.get("GOOGLE_CLIENT_SECRET"):
        return render_template("error.html", title="Sign-in unavailable", message="Google sign-in is not configured."), 503
    next_url = safe_next(request.args.get("next"))
    invitation = session.get('pending_invitation')
    session.clear()
    if invitation:
        session['pending_invitation'] = invitation
    session["login_next"] = next_url
    return current_app.extensions["google_oidc"].authorize_redirect(
        url_for("auth.google_callback", _external=True, _scheme=current_app.config["PREFERRED_URL_SCHEME"]), nonce=secrets.token_urlsafe(32),
        **({'prompt': 'select_account'} if invitation else {}))


@bp.get("/google/callback")
def google_callback():
    from .invitations import WrongInvitationAccount
    invitation = session.get('pending_invitation')
    try:
        token = current_app.extensions["google_oidc"].authorize_access_token()
        # Authlib validates signature, issuer, audience, expiry and saved nonce.
        # Never fall back to userinfo supplied by a query string or a userinfo API.
        if not token.get("id_token") or not token.get("userinfo"):
            raise IdentityDenied("Missing ID token")
        user_id = resolve_google_identity(token["userinfo"], invitation)
    except WrongInvitationAccount:
        session.clear()
        session['pending_invitation'] = invitation
        return render_template('invitation_account.html'), 403
    except (ValueError, sqlite3.IntegrityError):
        session.clear()
        return redirect(url_for("auth.denied"))
    except Exception:
        # OAuth/provider/transport failures are intentionally opaque; never log tokens.
        session.clear()
        return redirect(url_for("auth.denied"))
    destination = safe_next(session.get("login_next"))
    if invitation:
        connection = connect(current_app.config['DATABASE'])
        try:
            row = connection.execute('SELECT document_id FROM invitations WHERE invitation_id=? AND accepted_by=?', (invitation['id'], user_id)).fetchone()
            destination = url_for('core.document_detail', document_id=row['document_id']) if row and row['document_id'] else url_for('core.dashboard')
        finally:
            connection.close()
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
        if request.endpoint in PUBLIC_ENDPOINTS:
            return
        if request.endpoint in INVITE_PUBLIC_ENDPOINTS:
            if request.method in UNSAFE:
                check_csrf()
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
        if request.endpoint in ACCOUNT_ENDPOINTS | OWNER_ENDPOINTS | ADMIN_ENDPOINTS | TRUSTED_ENDPOINTS:
            from .access import is_site_admin
            from .invitations import can_invite
            if request.endpoint in TRUSTED_ENDPOINTS and not can_invite(app.config['DATABASE'], g.auth_user['user_id']):
                abort(403)
            if request.endpoint in ADMIN_ENDPOINTS and not is_site_admin(app.config['DATABASE'], g.auth_user['user_id']):
                abort(403)
            if request.endpoint in OWNER_ENDPOINTS:
                role = document_role(g.auth_user, request.view_args['document_id'])
                if role is None:
                    abort(404)
                if role != 'owner':
                    abort(403)
                g.document_role = role
            if request.method in UNSAFE:
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
            if request.endpoint in REVIEW_OWNER_ENDPOINTS and role != 'owner':
                abort(403)
            from .review_policy import thread_permitted, settings
            connection = connect(app.config['DATABASE'])
            try:
                if 'section_id' in arguments and 'version_id' in arguments:
                    section_document=connection.execute('SELECT document_id FROM sections WHERE section_id=?',(arguments['section_id'],)).fetchone()
                    if not section_document or section_document[0]!=document_id:
                        abort(404)
                if (request.endpoint=='core.view_version' and request.args.get('migration') and role!='owner'
                        and settings(connection,document_id)['visibility_policy']=='isolated'):
                    abort(404)
                thread_id = arguments.get('thread_id')
                if 'comment_id' in arguments:
                    row = connection.execute('SELECT thread_id FROM comments WHERE comment_id=?', (arguments['comment_id'],)).fetchone()
                    thread_id = row[0] if row else None
                if 'anchor_id' in arguments:
                    for row in connection.execute('SELECT thread_id FROM thread_targets WHERE anchor_id=?', (arguments['anchor_id'],)):
                        if not thread_permitted(connection,row[0],g.auth_user['user_id']):
                            abort(404)
                if thread_id and not thread_permitted(connection,thread_id,g.auth_user['user_id']):
                    abort(404)
                if request.blueprint == 'carry' and role != 'owner' and settings(connection,document_id)['visibility_policy']=='isolated':
                    abort(404)
            finally:
                connection.close()
            if request.method in UNSAFE:
                if role == "viewer" and request.endpoint not in {'review_options.viewer_preferences', *READING_ENDPOINTS}:
                    abort(403)
                if (request.blueprint == "carry" or request.endpoint in {"core.new_version", "core.verify_version", "core.delete_version"}) and role != "owner":
                    abort(403)
        elif request.endpoint not in {"core.dashboard", "core.new_document", "core.reviewers"}:
            abort(404)
        if request.method in UNSAFE:
            check_csrf()

    @app.context_processor
    def auth_context():
        from .access import is_site_admin
        from .invitations import can_invite
        user = getattr(g, 'auth_user', None)
        return {"auth_user": getattr(g, "auth_user", None), "csrf_token": csrf_token,
                "is_site_admin": bool(user and is_site_admin(app.config['DATABASE'], user['user_id'])),
                "can_invite_beta": bool(user and can_invite(app.config['DATABASE'], user['user_id'])),
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
