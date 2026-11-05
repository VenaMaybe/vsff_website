"""Public policies must work without sign-in and preserve private route boundaries."""

import tempfile
import unittest
from unittest.mock import patch

from review import create_app
from review.auth import SESSION_KEY


class LegalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({"TESTING": True, "DATA_DIR": self.temp.name,
                               "SECRET_KEY": "synthetic-legal-fixture"})
        self.client = self.app.test_client()

    def test_policies_are_public_without_private_reads_or_session_creation(self):
        with patch("review.auth.current_user", side_effect=AssertionError("identity read")), \
             patch("review.auth.connect", side_effect=AssertionError("database read")), \
             patch("review.storage.BlobStore.resolve", side_effect=AssertionError("blob read")):
            for path, title in (("/privacy", b"Privacy policy"), ("/tos", b"Terms of service")):
                for method in ("GET", "HEAD"):
                    response = self.client.open(path, method=method)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.mimetype, "text/html")
                    self.assertNotIn("Set-Cookie", response.headers)
                    self.assertIn("no-store", response.headers["Cache-Control"])
                    self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                    if method == "GET":
                        self.assertIn(b"<h1>" + title + b"</h1>", response.data)
                        self.assertIn(b"mailto:yppahhappy.com@gmail.com", response.data)
                    else:
                        self.assertEqual(response.data, b"")

    def test_stale_account_cannot_block_policies_or_expose_account_metadata(self):
        with self.client.session_transaction() as state:
            state[SESSION_KEY] = "revoked-synthetic-account"
        with patch("review.auth.current_user", side_effect=AssertionError("identity read")):
            for path in ("/privacy", "/tos"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(b"revoked-synthetic-account", response.data)
                self.assertNotIn(b"/auth/logout", response.data)

    def test_only_exact_read_routes_are_public(self):
        for path in ("/privacy", "/tos"):
            for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
                self.assertEqual(self.client.open(path, method=method).status_code, 405)
            for suffix in ("/", "/private"):
                self.assertEqual(self.client.get(path + suffix).status_code, 404)
        for path in ("/", "/account", "/documents/fixture", "/versions/fixture/pdf"):
            self.assertEqual(self.client.get(path).status_code, 302)
        self.assertEqual(self.client.get("/api/versions/fixture/threads").status_code, 401)

    def test_login_links_to_both_policies_and_discloses_reading_activity(self):
        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'href="/privacy"', response.data)
        self.assertIn(b'href="/tos"', response.data)
        self.assertIn(b"document owners can see reading activity", response.data)

    def test_production_policies_keep_host_validation_and_https_headers(self):
        app = create_app({"TESTING": True, "DATA_DIR": self.temp.name,
                          "PDF_REVIEW_ENV": "production", "SECRET_KEY": "synthetic-legal-secret-" * 3,
                          "GOOGLE_CLIENT_ID": "synthetic-client", "GOOGLE_CLIENT_SECRET": "synthetic-secret",
                          "SERVER_NAME": "review.example.test", "PREFERRED_URL_SCHEME": "https",
                          "SESSION_COOKIE_SECURE": True})
        client = app.test_client()
        for path in ("/privacy", "/tos"):
            response = client.get(path, base_url="https://review.example.test")
            self.assertEqual(response.status_code, 200)
            self.assertIn("max-age", response.headers["Strict-Transport-Security"])
            self.assertNotIn("Set-Cookie", response.headers)
            self.assertEqual(client.get(path, base_url="https://untrusted.example.test").status_code, 400)
