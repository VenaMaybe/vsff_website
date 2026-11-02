"""PDF Review Flask application factory."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, render_template

from .database import init_database
from .routes import bp
from .migration_routes import bp as migration_bp
from .storage import BlobStore
from .realtime import init_realtime
from .auth import init_auth
from .auth_cli import init_auth_cli
from .backup import init_backup_cli
from .account_routes import bp as account_bp
from .review_routes import bp as review_options_bp


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the local PDF Review application."""
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )
    data_dir = Path(os.environ.get("PDF_REVIEW_DATA_DIR") or PROJECT_ROOT / "data").expanduser().resolve()
    app.config.from_mapping(
        DATA_DIR=str(data_dir),
        DATABASE=os.environ.get("PDF_REVIEW_DATABASE"),
        STORAGE_ROOT=None,
        BACKUP_DIR=None,
        SESSION_COOKIE_NAME="pdf_review_session",
        MAX_CONTENT_LENGTH=512 * 1024 * 1024,
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        GOOGLE_CLIENT_ID=os.environ.get("GOOGLE_CLIENT_ID"),
        GOOGLE_CLIENT_SECRET=os.environ.get("GOOGLE_CLIENT_SECRET"),
        PDF_REVIEW_ENV=os.environ.get("PDF_REVIEW_ENV", "development"),
        SERVER_NAME=os.environ.get("PDF_REVIEW_SERVER_NAME"),
        PREFERRED_URL_SCHEME=os.environ.get("PDF_REVIEW_SCHEME", "https" if os.environ.get("PDF_REVIEW_ENV") == "production" else "http"),
        SESSION_COOKIE_SECURE=os.environ.get("PDF_REVIEW_COOKIE_SECURE", "1" if os.environ.get("PDF_REVIEW_ENV") == "production" else "0") == "1",
        TRUSTED_PROXY_HOPS=int(os.environ.get("PDF_REVIEW_PROXY_HOPS", "0")),
    )
    if test_config:
        app.config.update(test_config)

    data_dir = Path(app.config["DATA_DIR"]).expanduser().resolve()
    app.config["DATA_DIR"] = str(data_dir)
    for key, default in (("DATABASE", data_dir / "pdf_review.sqlite3"),
                         ("STORAGE_ROOT", data_dir), ("BACKUP_DIR", data_dir / "backups")):
        app.config[key] = str(Path(app.config[key] or default).expanduser().resolve())

    init_auth(app)
    init_database(Path(app.config["DATABASE"]))
    init_auth_cli(app)
    init_backup_cli(app)
    app.extensions["blob_store"] = BlobStore(Path(app.config["STORAGE_ROOT"]))
    app.register_blueprint(bp)
    app.register_blueprint(migration_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(review_options_bp)
    init_realtime(app)

    @app.get("/healthz", provide_automatic_options=False)
    def healthz():
        """Process liveness only; disclose no private state and perform no I/O."""
        return "OK\n", 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.errorhandler(404)
    def not_found(_error):
        return render_template(
            "error.html", title="Not found", message="That document or version does not exist."
        ), 404

    from .access import AccessDenied

    @app.errorhandler(AccessDenied)
    def authority_changed(_error):
        from werkzeug.exceptions import Forbidden
        return app.handle_http_exception(Forbidden())

    @app.errorhandler(413)
    def upload_too_large(_error):
        return render_template(
            "error.html", title="Upload too large", message="The PDF exceeds the 512 MB upload limit."
        ), 413

    @app.errorhandler(500)
    def internal_error(_error):
        return render_template(
            "error.html",
            title="Something went wrong",
            message="PDF Review could not complete that request. No imported PDF was changed.",
        ), 500

    return app
