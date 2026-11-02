"""Private beta boundaries, using real Authlib state/nonce/JWT validation offline."""

import io
import sqlite3
import time
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from joserfc import jwt
from joserfc.jwk import RSAKey

from review import create_app
from review.auth import PROTECTED_ENDPOINTS, ACCOUNT_ENDPOINTS, OWNER_ENDPOINTS, ADMIN_ENDPOINTS, SESSION_KEY, normalize_email, safe_next
from review.database import MIGRATIONS, init_database, transaction
from review.documents import create_document, import_version
from review.migrations import carry_item, create_migration
from review.threads import create_thread, get_thread
from review.users import create_user
from tests.auth_helpers import authenticate
import tests.test_threads as fixtures
from tests.test_threads import anchor_payload, pdf_bytes


class AuthTests(unittest.TestCase):
    setUp_fixtures = fixtures.ThreadTests.setUp
    tearDown_fixtures = fixtures.ThreadTests.tearDown

    @classmethod
    def setUpClass(cls):
        cls.key = RSAKey.generate_key(2048, parameters={"kid": "fixture"})
        cls.wrong_key = RSAKey.generate_key(2048, parameters={"kid": "fixture"})

    def setUp(self):
        self.setUp_fixtures()
        self.app = create_app({"TESTING": True, "DATABASE": str(self.database),
            "STORAGE_ROOT": str(self.storage_root), "SECRET_KEY": "test-secret",
            "GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "test-client-secret"})
        self.client = self.app.test_client()
        self.provider = self.app.extensions["google_oidc"]
        self.provider.server_metadata.update({
            "issuer": "https://accounts.google.com", "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_endpoint": "https://oauth2.googleapis.com/token", "jwks_uri": "https://example.test/keys",
            "id_token_signing_alg_values_supported": ["RS256"],
        })
        # Discovery and JWKS are the network boundary. Authlib still validates JWTs.
        self.metadata = patch.object(self.provider, "load_server_metadata", return_value=self.provider.server_metadata)
        self.keys = patch.object(self.provider, "fetch_jwk_set", return_value={"keys": [self.key.as_dict(private=False)]})
        self.metadata.start(); self.keys.start()
        self.addCleanup(self.metadata.stop); self.addCleanup(self.keys.stop)
        self.sockets = []

    def tearDown(self):
        for socket in self.sockets:
            if socket.is_connected(): socket.disconnect()
        self.tearDown_fixtures()

    def sql(self, query, values=()):
        with transaction(self.database) as connection:
            return connection.execute(query, values).fetchall()

    def allow(self, email="reader@example.test"):
        self.sql("INSERT OR REPLACE INTO allowed_emails(normalized_email, enabled, created_at) VALUES (?, 1, 'now')", (email,))

    def begin(self, next_url="/"):
        response = self.client.get("/auth/google", query_string={"next": next_url})
        self.assertEqual(response.status_code, 302)
        return {key: value[0] for key, value in parse_qs(urlsplit(response.location).query).items()}

    def login(self, claims=None, *, bad_state=False, signing_key=None, missing_token=False, query=None):
        auth = self.begin()
        now = int(time.time())
        data = {"iss": "https://accounts.google.com", "aud": "test-client", "exp": now + 600,
                "iat": now, "nonce": auth["nonce"], "sub": "google-reader-123",
                "email": "reader@example.test", "email_verified": True, "name": "Reader"}
        if claims: data.update(claims)
        token = {"access_token": "ephemeral-only", "token_type": "Bearer"}
        if not missing_token:
            token["id_token"] = jwt.encode({"alg": "RS256", "kid": "fixture"}, data, signing_key or self.key)
        with patch.object(self.provider, "fetch_access_token", return_value=token) as exchange:
            result = self.client.get("/auth/google/callback", query_string={"code": "single-use", "state": "wrong" if bad_state else auth["state"], **(query or {})})
        if bad_state: exchange.assert_not_called()
        return result

    def auth(self, user=None, role="owner"):
        user_id = authenticate(self.client, (user or self.alpha)["user_id"])
        self.sql("UPDATE document_access SET role = ? WHERE user_id = ?", (role, user_id))
        with self.client.session_transaction() as state:
            return {"X-CSRF-Token": state["csrf_token"]}

    def protected_urls(self):
        thread = create_thread(self.database, self.draft3, self.alpha["user_id"], anchor_payload(), "Private discussion")
        run = create_migration(self.database, self.document_id, self.draft3, self.draft4, self.alpha["user_id"])
        return ["/", f"/documents/{self.document_id}", f"/versions/{self.draft3}/view", f"/versions/{self.draft3}/pdf",
                f"/api/versions/{self.draft3}/anchors", f"/api/versions/{self.draft3}/threads",
                f"/documents/{self.document_id}/migrations", f"/api/documents/{self.document_id}/migrations",
                f"/api/migrations/{run['migration_id']}", f"/api/threads/{thread['thread_id']}/targets", "/api/reviewers"]

    def test_unauthenticated_routes_refuse_without_metadata_or_blob_reads(self):
        with patch("review.storage.BlobStore.resolve", side_effect=AssertionError("Unauthorized blob read")):
            for url in self.protected_urls():
                for method in ("GET", "HEAD"):
                    response = self.client.open(url, method=method, headers={"Range": "bytes=0-12"})
                    self.assertIn(response.status_code, (302, 401))
                    self.assertNotIn(b"Synthetic Document", response.data)
                    self.assertNotIn(b"%PDF", response.data)
                    self.assertNotIn(b"blobs/", response.data)

    def test_oidc_login_requests_only_identity_scopes_state_nonce_and_pkce(self):
        auth = self.begin()
        self.assertEqual(set(auth["scope"].split()), {"openid", "email", "profile"})
        self.assertEqual(auth["response_type"], "code")
        self.assertEqual(auth["redirect_uri"], "http://localhost/auth/google/callback")
        self.assertTrue(auth["state"]); self.assertTrue(auth["nonce"])
        self.assertEqual(auth["code_challenge_method"], "S256")
        self.assertNotIn("access_type", auth)

    def test_all_application_routes_have_explicit_policy(self):
        endpoints = {rule.endpoint for rule in self.app.url_map.iter_rules()
                     if rule.endpoint.startswith(("core.", "carry.", "accounts.", "review_options."))}
        self.assertEqual(endpoints, PROTECTED_ENDPOINTS | ACCOUNT_ENDPOINTS | OWNER_ENDPOINTS | ADMIN_ENDPOINTS)

    def test_state_mismatch_and_unsolicited_callback_fail(self):
        self.allow()
        self.assertIn("/auth/denied", self.login(bad_state=True).location)
        self.assertIn("/auth/denied", self.client.get("/auth/google/callback?email=reader@example.test&sub=forged").location)
        with self.client.session_transaction() as state: self.assertNotIn(SESSION_KEY, state)

    def test_callback_replay_is_rejected_and_next_destination_is_safe(self):
        self.allow()
        auth = self.begin("//evil.test/")
        now = int(time.time())
        claims = {"iss": "https://accounts.google.com", "aud": "test-client", "exp": now + 600,
                  "iat": now, "sub": "reader", "email": "reader@example.test", "email_verified": True, "nonce": auth["nonce"]}
        token = {"access_token": "temporary", "id_token": jwt.encode({"alg": "RS256", "kid": "fixture"}, claims, self.key)}
        query = {"state": auth["state"], "code": "single-use"}
        with patch.object(self.provider, "fetch_access_token", return_value=token):
            self.assertEqual(self.client.get("/auth/google/callback", query_string=query).location, "/")
        with patch.object(self.provider, "fetch_access_token") as exchange:
            self.assertIn("/auth/denied", self.client.get("/auth/google/callback", query_string=query).location)
            exchange.assert_not_called()

    def test_authlib_rejects_bad_issuer_audience_expiry_nonce_signature_and_missing_claims(self):
        self.allow()
        for claims in [{"iss": "https://evil.test"}, {"aud": "other-client"}, {"exp": 1}, {"nonce": "wrong"}, {"sub": ""}, {"email": ""}]:
            with self.subTest(claims=claims):
                self.assertIn("/auth/denied", self.login(claims).location)
                with self.client.session_transaction() as state: self.assertNotIn(SESSION_KEY, state)
        self.assertIn("/auth/denied", self.login(signing_key=self.wrong_key).location)
        self.assertIn("/auth/denied", self.login(missing_token=True).location)

    def test_unverified_or_nonallowlisted_account_cannot_establish_session(self):
        self.assertIn("/auth/denied", self.login().location)
        self.allow()
        for verified in (False, "true", 1, None):
            self.assertIn("/auth/denied", self.login({"email_verified": verified}).location)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM users WHERE google_subject = 'google-reader-123'")[0][0], 0)
        denied = self.client.get("/auth/denied")
        self.assertNotIn(b"reader@example.test", denied.data)
        self.assertNotIn(b"Synthetic Document", denied.data)

    def test_allowed_login_persists_sub_session_and_safe_profile_updates(self):
        self.allow()
        self.assertEqual(self.login().location, "/")
        row = self.sql("SELECT * FROM users WHERE google_subject = 'google-reader-123'")[0]
        original_id = row["user_id"]
        with self.client.session_transaction() as state:
            self.assertEqual(state[SESSION_KEY], original_id)
            self.assertEqual(set(state), {SESSION_KEY, "_permanent", "csrf_token"})
        self.assertEqual(self.client.get("/").status_code, 200)
        self.allow("new@example.test")
        self.login({"email": "NEW@example.test", "name": "Updated"})
        row = self.sql("SELECT * FROM users WHERE google_subject = 'google-reader-123'")[0]
        self.assertEqual(row["user_id"], original_id)
        self.assertEqual(row["normalized_email"], "new@example.test")
        self.assertEqual(row["display_name"], "Reader")
        self.assertTrue(row["last_login_at"])
        self.assertEqual(len(self.sql("SELECT * FROM users")), 3)

    def test_explicit_legacy_link_preserves_authorship_without_name_matching(self):
        thread = create_thread(self.database, self.draft3, self.alpha["user_id"], anchor_payload(), "Historical")
        self.allow()
        runner = self.app.test_cli_runner()
        linked = runner.invoke(args=["link-google-email", "reader@example.test", self.alpha["user_id"]])
        self.assertEqual(linked.exit_code, 0, linked.output)
        self.assertEqual(self.login({"name": "New profile name"}).location, "/")
        with self.client.session_transaction() as state: self.assertEqual(state[SESSION_KEY], self.alpha["user_id"])
        self.assertEqual(get_thread(self.database, thread["thread_id"])["comments"][0]["author"]["user_id"], self.alpha["user_id"])

    def test_email_conflict_and_duplicate_preparation_fail_safely(self):
        self.allow()
        self.sql("UPDATE users SET normalized_email='reader@example.test', google_subject='another-sub' WHERE user_id=?", (self.alpha["user_id"],))
        self.assertIn("/auth/denied", self.login().location)
        with self.assertRaises(sqlite3.IntegrityError):
            self.sql("UPDATE users SET normalized_email='reader@example.test' WHERE user_id=?", (self.beta["user_id"],))
        # Defensive failure even if a damaged legacy DB has lost its unique index.
        self.sql("DROP INDEX idx_users_email")
        self.sql("UPDATE users SET normalized_email='reader@example.test' WHERE user_id=?", (self.beta["user_id"],))
        self.assertIn("/auth/denied", self.login().location)

    def test_display_name_collision_never_links_legacy_user(self):
        self.allow()
        self.login({"name": "ReviewerAlpha"})
        with self.client.session_transaction() as state: self.assertNotEqual(state[SESSION_KEY], self.alpha["user_id"])

    def test_normalization_is_conservative_and_return_urls_are_local(self):
        self.assertEqual(normalize_email(" A.B+Tag@Example.test "), "a.b+tag@example.test")
        for url in ["//evil.test", "https://evil.test/", "/\\evil.test", "/%2fevil.test", "javascript:foo", "/\nevil.test"]:
            self.assertEqual(safe_next(url), "/")
        self.assertEqual(safe_next("/documents/example?tab=2"), "/documents/example?tab=2")

    def test_logout_csrf_and_live_database_revocation(self):
        headers = self.auth()
        self.assertEqual(self.client.post("/auth/logout").status_code, 400)
        self.assertEqual(self.client.post("/auth/logout", headers=headers).status_code, 303)
        self.assertEqual(self.client.get("/").status_code, 302)
        self.auth()
        self.sql("UPDATE users SET is_active=0 WHERE user_id=?", (self.alpha["user_id"],))
        self.assertEqual(self.client.get("/").status_code, 302)
        self.sql("UPDATE users SET is_active=1 WHERE user_id=?", (self.alpha["user_id"],))
        self.auth()
        self.sql("UPDATE allowed_emails SET enabled=0")
        self.assertEqual(self.client.get("/").status_code, 302)
        self.sql("UPDATE allowed_emails SET enabled=1")
        self.auth()
        self.sql("DELETE FROM allowed_emails")
        self.assertEqual(self.client.get("/api/reviewers").status_code, 401)

    def test_no_document_permission_protects_all_resources(self):
        urls = self.protected_urls()
        self.auth()
        self.sql("DELETE FROM document_access")
        with patch("review.storage.BlobStore.resolve", side_effect=AssertionError("Unauthorized blob read")):
            for url in urls:
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200 if url in ("/", "/api/reviewers") else 404)
                self.assertNotIn(b"Synthetic Document", response.data)
                self.assertNotIn(b"Private discussion", response.data)
                self.assertNotIn(b"%PDF", response.data)

    def test_pdf_authorization_precedes_get_head_range_conditional_and_invalid_range(self):
        self.auth()
        url = f"/versions/{self.draft3}/pdf"
        expected = pdf_bytes(b"draft 3")
        for role in ("owner", "reviewer", "viewer"):
            self.sql("UPDATE document_access SET role=?", (role,))
            with self.client.get(url) as response:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, expected)
                etag = response.headers["ETag"]
            with self.client.get(url, headers={"Range": "bytes=0-9"}) as response:
                self.assertEqual(response.status_code, 206)
                self.assertEqual(response.data, expected[:10])
            with self.client.head(url) as response: self.assertEqual(response.status_code, 200)
        self.sql("DELETE FROM document_access")
        with patch("review.storage.BlobStore.resolve", side_effect=AssertionError("Unauthorized blob read")):
            for headers in ({}, {"Range": "bytes=0-9"}, {"Range": "bytes=999999-"}, {"Range": "invalid"}, {"If-None-Match": etag}):
                for method in ("GET", "HEAD"):
                    response = self.client.open(url, method=method, headers=headers)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn(b"%PDF", response.data)
                    self.assertNotIn("Content-Range", response.headers)

    def test_access_to_document_a_does_not_grant_b(self):
        self.auth()
        doc = create_document(self.database, "Private B")
        version = import_version(self.database, self.blobs, doc, io.BytesIO(pdf_bytes(b"B")), "b.pdf").version_id
        for url in (f"/documents/{doc}", f"/versions/{version}/pdf", f"/versions/{version}/view", f"/api/versions/{version}/threads", f"/api/documents/{doc}/migrations"):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotIn(b"Private B", self.client.get("/").data)

    def test_viewer_cannot_mutate_any_document_resource(self):
        headers = self.auth(role="viewer")
        thread = create_thread(self.database, self.draft3, self.alpha["user_id"], anchor_payload(), "Root")
        run = create_migration(self.database, self.document_id, self.draft3, self.draft4, self.alpha["user_id"])
        cid = thread["comments"][0]["comment_id"]
        aid = thread["targets"][0]["anchor"]["anchor_id"]
        for method, url in [("POST", f"/api/versions/{self.draft3}/threads"), ("POST", f"/api/versions/{self.draft3}/anchors"),
            ("DELETE", f"/api/anchors/{aid}"), ("PATCH", f"/api/comments/{cid}"), ("DELETE", f"/api/comments/{cid}"),
            ("POST", f"/api/threads/{thread['thread_id']}/comments"), ("POST", f"/api/threads/{thread['thread_id']}/resolve"),
            ("POST", f"/api/threads/{thread['thread_id']}/reopen"), ("POST", f"/documents/{self.document_id}/versions"),
            ("POST", f"/api/documents/{self.document_id}/migrations"), ("POST", f"/api/migrations/{run['migration_id']}/complete")]:
            with self.subTest(method=method, url=url):
                self.assertEqual(self.client.open(url, method=method, headers=headers, json={}).status_code, 403)
        self.assertEqual(self.client.get(f"/api/versions/{self.draft3}/threads").status_code, 200)

    def test_csrf_and_authenticated_attribution_on_mutations(self):
        headers = self.auth(role="reviewer")
        url = f"/api/versions/{self.draft3}/threads"
        payload = {"anchor": anchor_payload(), "body": "Authorized"}
        self.assertEqual(self.client.post(url, json=payload).status_code, 400)
        self.assertEqual(self.client.post(url, json=payload, headers={"X-CSRF-Token": "bad"}).status_code, 400)
        self.assertEqual(self.client.post(url, json=payload, headers={"X-CSRF-Token": "\u00e9"}).status_code, 400)
        response = self.client.post(url, json=payload, headers=headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["thread"]["comments"][0]["author"]["user_id"], self.alpha["user_id"])
        self.assertEqual(self.client.post(url, json=payload | {"author_id": self.beta["user_id"]}, headers=headers).status_code, 400)
        cid = response.json["thread"]["comments"][0]["comment_id"]
        other = self.auth(self.beta, role="reviewer")
        self.assertEqual(self.client.patch(f"/api/comments/{cid}", json={"body": "Spoof", "expected_revision": 1}, headers=other).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/comments/{cid}", headers=other).status_code, 403)
        self.assertEqual(self.client.post("/api/reviewer", json={"user_id": self.alpha["user_id"]}, headers=other).status_code, 404)

    def test_owner_migration_workflow_and_reviewer_restriction(self):
        thread = create_thread(self.database, self.draft3, self.alpha["user_id"], anchor_payload(), "Root")
        headers = self.auth()
        url = f"/api/documents/{self.document_id}/migrations"
        response = self.client.post(url, json={"source_version_id": self.draft3, "target_version_id": self.draft4}, headers=headers)
        self.assertEqual(response.status_code, 201)
        run = response.json["migration"]
        item = run["items"][0]
        carry = f"/api/migrations/{run['migration_id']}/items/{item['item_id']}/carry"
        self.assertEqual(self.client.post(carry, json={"anchor": anchor_payload(), "expected_revision": 1, "expected_target_id": None}, headers=headers).status_code, 200)
        self.assertEqual(self.client.post(f"/api/migrations/{run['migration_id']}/complete", json={}, headers=headers).status_code, 200)
        self.sql("UPDATE document_access SET role='reviewer'")
        self.assertEqual(self.client.post(url, json={}, headers=headers).status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_socket_identity_acl_spoofing_and_revocation(self):
        socketio = self.app.extensions["socketio"]
        rejected = socketio.test_client(self.app, flask_test_client=self.client)
        self.assertFalse(rejected.is_connected())
        self.auth(role="viewer")
        socket = socketio.test_client(self.app, flask_test_client=self.client)
        self.sockets.append(socket)
        self.assertTrue(socket.is_connected())
        ack = socket.emit("review.join", {"version_id": self.draft3, "user_id": self.beta["user_id"], "display_name": "Forged"}, callback=True)
        self.assertTrue(ack["ok"])
        events = socket.get_received()
        presence = next(e["args"][0] for e in events if e["name"] == "review.presence")
        self.assertEqual(presence["reviewers"][0]["user_id"], self.alpha["user_id"])
        self.assertEqual(presence["reviewers"][0]["display_name"], "ReviewerAlpha")
        self.sql("DELETE FROM document_access")
        self.assertFalse(socket.emit("review.join", {"version_id": self.draft4}, callback=True)["ok"])
        socket.disconnect()
        socket.connect()
        self.assertFalse(socket.emit("review.join", {"version_id": self.draft3}, callback=True)["ok"])
        socket.disconnect()
        self.sql("UPDATE allowed_emails SET enabled=0")
        denied = socketio.test_client(self.app, flask_test_client=self.client)
        self.assertFalse(denied.is_connected())

    def test_cli_allow_link_grant_revoke_and_disable(self):
        runner = self.app.test_cli_runner()
        for args in [["allow-email", " Reader@Example.test "], ["link-google-email", "reader@example.test", self.alpha["user_id"]],
                     ["grant-access", self.document_id, self.alpha["user_id"], "--role", "owner"],
                     ["list-document-access", self.document_id], ["list-allowed-emails"], ["list-identities"],
                     ["grant-access", self.document_id, self.beta["user_id"], "--role", "owner"],
                     ["disallow-email", "reader@example.test"], ["revoke-access", self.document_id, self.alpha["user_id"]]]:
            result = runner.invoke(args=args)
            self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.sql("SELECT enabled FROM allowed_emails")[0][0], 0)
        self.assertEqual([row['user_id'] for row in self.sql("SELECT * FROM document_access")], [self.beta['user_id']])

    def test_configuration_failures_headers_and_public_static_pdf_denial(self):
        for config in [{"SECRET_KEY": None}, {"SESSION_COOKIE_SECURE": False}, {"GOOGLE_CLIENT_ID": None}, {"PREFERRED_URL_SCHEME": "http"}, {"SERVER_NAME": None}]:
            with self.assertRaises(RuntimeError):
                create_app(dict(self.app.config, PDF_REVIEW_ENV="production", SESSION_COOKIE_SECURE=True,
                                PREFERRED_URL_SCHEME="https", SERVER_NAME="review.example.test", SECRET_KEY="x" * 48) | config)
        response = self.client.get("/auth/login")
        for header in ("X-Content-Type-Options", "Referrer-Policy", "X-Frame-Options", "Cache-Control"):
            self.assertIn(header, response.headers)
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(self.client.get("/static/vendor/pdfjs/web/compressed.tracemonkey-pldi-09.pdf").status_code, 404)
        self.assertEqual(self.client.get("/static/../data/pdf_review.sqlite3").status_code, 404)
        self.app.config["GOOGLE_CLIENT_ID"] = None
        self.assertEqual(self.client.get("/auth/google").status_code, 503)

    def test_production_cookie_callback_host_scheme_and_proxy_configuration(self):
        config = dict(self.app.config, PDF_REVIEW_ENV="production", SECRET_KEY="persistent-test-secret-" * 3,
                      SESSION_COOKIE_SECURE=True, SERVER_NAME="review.example.test", PREFERRED_URL_SCHEME="https")
        production = create_app(config)
        google = production.extensions["google_oidc"]
        client = production.test_client()
        metadata = self.provider.server_metadata
        with patch.object(google, "load_server_metadata", return_value=metadata):
            response = client.get("/auth/google", base_url="https://review.example.test",
                headers={"X-Forwarded-Host": "evil.test", "X-Forwarded-Proto": "http"})
        callback = parse_qs(urlsplit(response.location).query)["redirect_uri"][0]
        self.assertEqual(callback, "https://review.example.test/auth/google/callback")
        cookie = response.headers["Set-Cookie"]
        for flag in ("Secure", "HttpOnly", "SameSite=Lax"): self.assertIn(flag, cookie)
        self.assertEqual(response.headers["Strict-Transport-Security"], "max-age=31536000")
        self.assertEqual(client.get("/auth/login", base_url="https://evil.test").status_code, 400)
        trusted = create_app(config | {"TRUSTED_PROXY_HOPS": 1})
        self.assertEqual(trusted.wsgi_app.wsgi_app.x_proto, 1)
        self.assertEqual(trusted.wsgi_app.wsgi_app.x_host, 0)
        with self.assertRaises(RuntimeError): create_app(config | {"TRUSTED_PROXY_HOPS": 2})

    def test_socket_origin_cannot_be_spoofed_with_forwarded_headers(self):
        with self.assertLogs("engineio.server", level="ERROR"):
            response = self.client.get("/socket.io/?EIO=4&transport=polling", headers={
                "Origin": "https://evil.test", "X-Forwarded-Host": "evil.test", "X-Forwarded-Proto": "https"})
        self.assertEqual(response.status_code, 400)

    def test_migration6_preserves_complete_legacy_history_without_grants(self):
        legacy = self.root / "legacy5.sqlite3"
        connection = sqlite3.connect(legacy)
        connection.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL)")
        for number, name, sql in MIGRATIONS[:5]:
            connection.executescript(sql)
            connection.execute("INSERT INTO schema_migrations VALUES (?, ?, 'before')", (number, name))
        connection.commit(); connection.close()
        user = create_user(legacy, "Historical")
        document = create_document(legacy, "Historical work")
        versions = [import_version(legacy, self.blobs, document, io.BytesIO(pdf_bytes(str(i).encode())), f"v{i}.pdf").version_id for i in (1, 2)]
        thread = create_thread(legacy, versions[0], user["user_id"], anchor_payload(), "Historical comment")
        run = create_migration(legacy, document, *versions, user["user_id"])
        item = run["items"][0]
        carry_item(legacy, run["migration_id"], item["item_id"], user["user_id"], anchor_payload(), 1, None)
        connection = sqlite3.connect(legacy)
        tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'schema_migrations'")]
        columns = {table: [r[1] for r in connection.execute(f"PRAGMA table_info({table})")] for table in tables}
        before = {table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall() for table in tables}
        connection.close()
        init_database(legacy); init_database(legacy)
        connection = sqlite3.connect(legacy)
        for table in tables:
            self.assertEqual(connection.execute(f"SELECT {','.join(columns[table])} FROM {table} ORDER BY 1").fetchall(), before[table])
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM allowed_emails").fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM document_access").fetchone()[0], 0)
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        connection.close()


if __name__ == "__main__":
    unittest.main()
