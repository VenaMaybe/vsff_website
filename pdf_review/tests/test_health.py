"""The public liveness endpoint never exposes or authorizes private content."""

import tempfile
import unittest
from unittest.mock import patch

from review import create_app


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({"TESTING": True, "DATA_DIR": self.temp.name,
                               "SECRET_KEY": "synthetic-health-fixture"})
        self.client = self.app.test_client()

    def test_anonymous_get_and_head_are_constant_and_do_not_read_private_state(self):
        with patch("review.auth.current_user", side_effect=AssertionError("identity read")), \
             patch("review.auth.connect", side_effect=AssertionError("database read")), \
             patch("review.storage.BlobStore.resolve", side_effect=AssertionError("blob read")):
            for method in ("GET", "HEAD"):
                response = self.client.open("/healthz", method=method, headers={"Range": "bytes=0-1"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, b"OK\n" if method == "GET" else b"")
                self.assertEqual(response.mimetype, "text/plain")
                self.assertIn("no-store", response.headers["Cache-Control"])
                self.assertNotIn("Set-Cookie", response.headers)
                self.assertNotIn("Content-Range", response.headers)

    def test_mutation_and_nearby_paths_do_not_get_health_exemption(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            self.assertEqual(self.client.open("/healthz", method=method).status_code, 405)
        self.assertEqual(self.client.get("/healthz/private").status_code, 404)
        self.assertEqual(self.client.get("/healthz/").status_code, 404)
        self.assertEqual(self.client.get("/api/reviewers").status_code, 401)
        self.assertEqual(self.client.get("/").status_code, 302)
        for path in ("/documents/fixture", "/versions/fixture/pdf", "/api/versions/fixture/threads",
                     "/api/documents/fixture/migrations"):
            self.assertIn(self.client.get(path, headers={"Range": "bytes=0-99"}).status_code, (302, 401))

    def test_production_host_validation_and_headers_still_apply(self):
        app = create_app({"TESTING": True, "DATA_DIR": self.temp.name,
                          "PDF_REVIEW_ENV": "production", "SECRET_KEY": "synthetic-health-secret-" * 3,
                          "GOOGLE_CLIENT_ID": "synthetic-client", "GOOGLE_CLIENT_SECRET": "synthetic-secret",
                          "SERVER_NAME": "review.example.test", "PREFERRED_URL_SCHEME": "https",
                          "SESSION_COOKIE_SECURE": True, "TRUSTED_PROXY_HOPS": 1})
        client = app.test_client()
        response = client.get("/healthz", base_url="http://review.example.test",
                              headers={"X-Forwarded-Proto": "https"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"OK\n")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("max-age", response.headers["Strict-Transport-Security"])
        self.assertNotIn("Set-Cookie", response.headers)
        self.assertEqual(client.get("/healthz", base_url="http://127.0.0.1:8002").status_code, 400)
