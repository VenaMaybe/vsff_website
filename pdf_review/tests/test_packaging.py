"""Runtime isolation and production entrypoint checks using disposable data."""

import importlib.util
from contextlib import closing
import io
import os
from pathlib import Path
import runpy
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from review import PROJECT_ROOT, create_app
from review.documents import create_document, import_version


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_external_data_dir_import_integrity_and_consistent_backup(self):
        with patch.dict(os.environ, {"PDF_REVIEW_DATA_DIR": str(self.root)}, clear=True):
            app = create_app({"TESTING": True})
        self.assertEqual(Path(app.config["DATABASE"]), self.root / "pdf_review.sqlite3")
        document = create_document(app.config["DATABASE"], "Synthetic runtime test")
        content = b"%PDF-1.4\n% Synthetic packaging fixture\n%%EOF\n"
        store = app.extensions["blob_store"]
        version = import_version(app.config["DATABASE"], store, document, io.BytesIO(content), "fixture.pdf", "Fixture")
        blob = store.resolve(version.blob.relative_path, version.blob.sha256)
        self.assertTrue(blob.is_relative_to(self.root / "blobs"))
        result = app.test_cli_runner().invoke(args=["backup-database"])
        self.assertEqual(result.exit_code, 0, result.output)
        backup, = (self.root / "backups").glob("*.sqlite3")
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("SELECT title FROM documents").fetchone()[0], "Synthetic runtime test")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 6)
        self.assertEqual(blob.read_bytes(), content)
        self.assertTrue(store.verify(version.blob.relative_path, version.blob.sha256, len(content)).ok)
        self.assertEqual(app.test_cli_runner().invoke(args=["verify-storage"]).exit_code, 0)
        self.assertEqual(app.test_client().get("/auth/login").status_code, 200)

    def test_config_and_explicit_database_overrides(self):
        with patch.dict(os.environ, {"PDF_REVIEW_DATA_DIR": str(self.root),
                                     "PDF_REVIEW_DATABASE": str(self.root / "db/custom.sqlite3")}, clear=True):
            app = create_app({"TESTING": True})
        self.assertEqual(Path(app.config["DATABASE"]), self.root / "db/custom.sqlite3")
        self.assertEqual(Path(app.config["STORAGE_ROOT"]), self.root)
        with patch.dict(os.environ, {}, clear=True):
            app = create_app({"TESTING": True, "DATA_DIR": str(self.root / "other")})
        self.assertEqual(Path(app.config["BACKUP_DIR"]), self.root / "other/backups")

    def load_wsgi(self):
        spec = importlib.util.spec_from_file_location("packaging_wsgi", PROJECT_ROOT / "wsgi.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.app

    def production_env(self):
        return {"PDF_REVIEW_ENV": "production", "PDF_REVIEW_DATA_DIR": str(self.root),
                "SECRET_KEY": "synthetic-production-fixture-" * 3,
                "GOOGLE_CLIENT_ID": "synthetic-client", "GOOGLE_CLIENT_SECRET": "synthetic-secret",
                "PDF_REVIEW_SERVER_NAME": "review.example.test"}

    def test_production_wsgi_initializes_socketio_without_development_server(self):
        with patch.dict(os.environ, self.production_env(), clear=True), patch("flask_socketio.SocketIO.run") as run:
            app = self.load_wsgi()
        run.assert_not_called()
        self.assertEqual(app.extensions["socketio"].async_mode, "threading")
        self.assertEqual(app.extensions["socketio"].server.eio._async["websocket"].__module__, "engineio.async_drivers._websocket_wsgi")
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertEqual(app.config["SESSION_COOKIE_NAME"], "pdf_review_session")
        self.assertEqual(app.config["TRUSTED_PROXY_HOPS"], 0)
        self.assertEqual(app.test_client().get("/auth/login", base_url="https://review.example.test").status_code, 200)

    def test_production_wsgi_rejects_missing_mode_and_internal_runtime_paths(self):
        cases = [{}, self.production_env() | {"PDF_REVIEW_DATA_DIR": "relative"},
                 self.production_env() | {"PDF_REVIEW_DATA_DIR": str(PROJECT_ROOT / "data")},
                 self.production_env() | {"PDF_REVIEW_DATABASE": str(PROJECT_ROOT / "private.sqlite3")}]
        for env in cases:
            with self.subTest(keys=list(env)), patch.dict(os.environ, env, clear=True):
                with self.assertRaises(RuntimeError): self.load_wsgi()

    def test_gunicorn_defaults_and_single_worker_guard(self):
        with patch.dict(os.environ, {}, clear=True):
            config = runpy.run_path(str(PROJECT_ROOT / "gunicorn.conf.py"))
        self.assertEqual((config["workers"], config["threads"], config["bind"]), (1, 100, "127.0.0.1:8002"))
        for workers, worker_class, threads in [(2, "gthread", 100), (1, "sync", 100), (1, "gthread", 1)]:
            server = SimpleNamespace(cfg=SimpleNamespace(workers=workers, worker_class_str=worker_class, threads=threads))
            with self.assertRaises(RuntimeError): config["on_starting"](server)
        config["on_starting"](SimpleNamespace(cfg=SimpleNamespace(workers=1, worker_class_str="gthread", threads=100)))

    def test_gunicorn_configurable_loopback_bind(self):
        with patch.dict(os.environ, {"PDF_REVIEW_HOST": "::1", "PDF_REVIEW_PORT": "8123"}, clear=True):
            self.assertEqual(runpy.run_path(str(PROJECT_ROOT / "gunicorn.conf.py"))["bind"], "[::1]:8123")
        with patch.dict(os.environ, {"PDF_REVIEW_HOST": "0.0.0.0"}, clear=True):
            with self.assertRaises(RuntimeError): runpy.run_path(str(PROJECT_ROOT / "gunicorn.conf.py"))
