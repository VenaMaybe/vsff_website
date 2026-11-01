"""Socket.IO test clients exercise notifications; HTTP remains the mutation API."""

import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from review import create_app
from tests.auth_helpers import authenticate, secure_client
from review.anchors import create_anchor
from review.database import connect, transaction
from review.documents import now_utc
from review.threads import CommentConflictError, edit_comment, get_thread
import tests.test_threads as fixtures


class RealtimeTests(unittest.TestCase):
    counts = fixtures.ThreadTests.counts
    create_discussion = fixtures.ThreadTests.create_discussion

    def setUp(self):
        fixtures.ThreadTests.setUp(self)
        self.app = create_app({"TESTING": True, "DATABASE": str(self.database),
                               "STORAGE_ROOT": str(self.storage_root), "SECRET_KEY": "test"})
        self.io = self.app.extensions["socketio"]
        self.http = secure_client(self.app, self.alpha["user_id"])
        authenticate(self.http, self.alpha["user_id"])
        self.sockets = []

    def tearDown(self):
        for client in self.sockets:
            if client.is_connected():
                client.disconnect()
        fixtures.ThreadTests.tearDown(self)

    def socket(self, http=None, version=None):
        client = self.io.test_client(self.app, flask_test_client=http or self.http)
        self.sockets.append(client)
        self.assertTrue(client.is_connected())
        result = client.emit("review.join", {"version_id": version or self.draft3,
                                             "display_name": "Forged"}, callback=True)
        self.assertTrue(result["ok"])
        return client

    def events(self, client, name="review.changed"):
        return [event["args"][0] for event in client.get_received() if event["name"] == name]

    def create_http(self):
        return self.http.post(f"/api/versions/{self.draft3}/threads",
                              json={"anchor": fixtures.anchor_payload(), "body": "Root"})

    def test_connection_validation_leave_switch_and_cleanup(self):
        client = self.socket()
        self.assertFalse(client.emit("review.join", callback=True)["ok"])
        self.assertFalse(client.emit("review.page", callback=True)["ok"])
        for payload in [None, {}, {"version_id": "missing"}, {"version_id": []}, {"version_id": 2}]:
            self.assertFalse(client.emit("review.join", payload, callback=True)["ok"])
        self.assertTrue(client.emit("review.join", {"version_id": self.draft4}, callback=True)["ok"])
        registry = self.app.extensions["review_presence"]
        with registry.lock:
            self.assertEqual(len(registry.connections), 1)
            self.assertEqual(registry.snapshot(self.draft3)["reviewers"], [])
        self.assertTrue(client.emit("review.leave", callback=True)["ok"])
        self.assertEqual(registry.connections, {})
        client.emit("review.join", {"version_id": self.draft3})
        client.disconnect()
        self.assertEqual(registry.connections, {})

    def test_anonymous_socket_is_rejected(self):
        client = self.io.test_client(self.app, flask_test_client=self.app.test_client())
        self.assertFalse(client.is_connected())

    def test_presence_database_names_pages_and_multi_tab_aggregation(self):
        first = self.socket()
        second = self.socket()
        snapshot = self.events(first, "review.presence")[-1]["reviewers"]
        self.assertEqual(len(snapshot), 1)
        self.assertEqual(snapshot[0]["display_name"], "ReviewerAlpha")
        self.assertEqual(snapshot[0]["connection_count"], 2)
        for value in [True, 0, -1, 1.5, "2", None, 1_000_001]:
            self.assertFalse(second.emit("review.page", {"page": value}, callback=True)["ok"])
        self.assertTrue(second.emit("review.page", {"page": 83}, callback=True)["ok"])
        self.assertEqual(self.events(first, "review.presence")[-1]["reviewers"][0]["page"], 83)
        second.disconnect()
        remaining = self.events(first, "review.presence")[-1]["reviewers"]
        self.assertEqual(remaining[0]["connection_count"], 1)
        observer_http = secure_client(self.app, self.beta["user_id"])
        observer = self.socket(observer_http)
        self.events(observer, "review.presence")
        first.disconnect()
        self.assertEqual(self.events(observer, "review.presence")[-1]["reviewers"][0]["display_name"], "ReviewerBeta")

    def test_identity_http_change_reconnect_preserves_authorship(self):
        thread = self.create_http().get_json()["thread"]
        client = self.socket()
        authenticate(self.http, self.beta["user_id"])
        client.disconnect()
        client = self.socket()
        self.assertEqual(self.events(client, "review.presence")[-1]["reviewers"][0]["display_name"], "ReviewerBeta")
        self.assertEqual(get_thread(self.database, thread["thread_id"])["comments"][0]["author"]["display_name"], "ReviewerAlpha")

    def test_creation_room_isolation_event_schema_and_post_commit(self):
        first = self.socket()
        other = self.socket(version=self.draft4)
        real_emit = self.io.emit
        def observe_commit(event, data, **kwargs):
            if event == "review.changed":
                self.assertEqual(get_thread(self.database, data["thread_id"])["comments"][0]["body"], "Root")
            return real_emit(event, data, **kwargs)
        with mock.patch.object(self.io, "emit", side_effect=observe_commit):
            self.assertEqual(self.create_http().status_code, 201)
        event = self.events(first)[0]
        self.assertEqual(event["schema_version"], 1)
        uuid.UUID(event["event_id"])
        self.assertEqual(event["kind"], "thread.created")
        self.assertEqual(event["version_id"], self.draft3)
        self.assertEqual(event["document_id"], self.document_id)
        self.assertNotIn("body", event)
        self.assertEqual(self.events(other), [])

    def test_rollback_and_invalid_creation_emit_nothing(self):
        client = self.socket()
        with self.assertLogs(self.app.logger, level="ERROR"), mock.patch("review.threads._insert_comment", side_effect=RuntimeError("late failure")):
            self.assertEqual(self.create_http().status_code, 500)
        self.assertTrue(all(value == 0 for value in self.counts().values()))
        self.assertEqual(self.events(client), [])
        response = self.http.post(f"/api/versions/{self.draft3}/threads", json={"anchor": {}, "body": "Bad"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.events(client), [])

    def test_every_mutation_announces_committed_canonical_state(self):
        client = self.socket()
        thread = self.create_http().get_json()["thread"]
        self.events(client)
        thread_id = thread["thread_id"]
        comment_id = thread["comments"][0]["comment_id"]
        operations = [
            ("post", f"/api/threads/{thread_id}/comments", {"body": "Reply"}, "comment.created"),
            ("patch", f"/api/comments/{comment_id}", {"body": "Edited", "expected_revision": 1}, "comment.edited"),
            ("delete", f"/api/comments/{comment_id}", None, "comment.deleted"),
            ("post", f"/api/threads/{thread_id}/resolve", None, "thread.resolved"),
            ("post", f"/api/threads/{thread_id}/reopen", None, "thread.reopened"),
        ]
        real_emit = self.io.emit
        observed = []
        def observe_commit(event, data, **kwargs):
            if event == "review.changed":
                canonical = get_thread(self.database, thread_id)
                observed.append(canonical)
                root = canonical["comments"][0]
                if data["kind"] == "comment.created": self.assertEqual(len(canonical["comments"]), 2)
                if data["kind"] == "comment.edited": self.assertEqual(root["current_revision"], 2)
                if data["kind"] == "comment.deleted": self.assertTrue(root["is_deleted"])
                if data["kind"] == "thread.resolved": self.assertEqual(canonical["status"], "resolved")
                if data["kind"] == "thread.reopened": self.assertEqual(canonical["status"], "open")
            return real_emit(event, data, **kwargs)
        with mock.patch.object(self.io, "emit", side_effect=observe_commit):
            for method, url, payload, kind in operations:
                response = getattr(self.http, method)(url, **({"json": payload} if payload else {}))
                self.assertIn(response.status_code, [200, 201])
                self.assertEqual(self.events(client)[0]["kind"], kind)
        self.assertEqual(len(observed), 5)
        self.assertEqual(len(observed[0]["comments"]), 2)
        self.assertEqual(observed[1]["comments"][0]["current_revision"], 2)
        self.assertTrue(observed[2]["comments"][0]["is_deleted"])
        self.assertEqual(observed[3]["status"], "resolved")
        self.assertEqual(observed[4]["status"], "open")

    def test_multi_target_notification_reaches_both_versions(self):
        thread = self.create_discussion()
        anchor = create_anchor(self.database, self.draft4, fixtures.anchor_payload())
        with transaction(self.database) as connection:
            target_id = str(uuid.uuid4())
            connection.execute("INSERT INTO thread_targets VALUES (?, ?, ?, 'manual', ?)",
                               (target_id, thread["thread_id"], anchor["anchor_id"], now_utc()))
            connection.execute("INSERT INTO thread_target_heads VALUES (?, ?, ?, ?, ?)",
                               (thread["thread_id"], self.draft4, target_id, now_utc(), self.alpha["user_id"]))
        first = self.socket()
        second = self.socket(version=self.draft4)
        response = self.http.post(f"/api/threads/{thread['thread_id']}/comments", json={"body": "Shared"})
        self.assertEqual(response.status_code, 201)
        for client, version in [(first, self.draft3), (second, self.draft4)]:
            self.assertEqual(self.events(client)[0]["version_id"], version)
            canonical = self.http.get(f"/api/versions/{version}/threads").get_json()["threads"]
            self.assertEqual(canonical[0]["comments"][-1]["body"], "Shared")

    def test_emit_failure_does_not_report_committed_mutation_as_failure(self):
        with self.assertLogs(self.app.logger, level="ERROR"), mock.patch.object(self.io, "emit", side_effect=RuntimeError("emit failure")):
            response = self.create_http()
        self.assertEqual(response.status_code, 201)
        thread = response.get_json()["thread"]
        self.assertEqual(get_thread(self.database, thread["thread_id"])["comments"][0]["body"], "Root")

    def test_optimistic_conflict_no_overwrite_revision_or_notification(self):
        client = self.socket()
        thread = self.create_http().get_json()["thread"]
        self.events(client)
        comment_id = thread["comments"][0]["comment_id"]
        url = f"/api/comments/{comment_id}"
        self.assertEqual(self.http.patch(url, json={"body": "A", "expected_revision": 1}).status_code, 200)
        self.events(client)
        stale = self.http.patch(url, json={"body": "B", "expected_revision": 1})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.get_json()["error"]["current_revision"], 2)
        canonical = get_thread(self.database, thread["thread_id"])["comments"][0]
        self.assertEqual((canonical["body"], canonical["revision_count"]), ("A", 2))
        self.assertEqual(self.events(client), [])
        self.assertEqual(self.http.patch(url, json={"body": "B", "expected_revision": 2}).status_code, 200)
        self.assertEqual(get_thread(self.database, thread["thread_id"])["comments"][0]["current_revision"], 3)

    def test_expected_revision_is_required_and_strict(self):
        thread = self.create_http().get_json()["thread"]
        url = f"/api/comments/{thread['comments'][0]['comment_id']}"
        self.assertEqual(self.http.patch(url, json={"body": "No token"}).status_code, 400)
        for token in [True, 0, -1, "1", 1.5, None]:
            self.assertEqual(self.http.patch(url, json={"body": "Bad", "expected_revision": token}).status_code, 422)

    def test_reconnect_refetch_recovers_missed_notifications(self):
        client = self.socket()
        client.disconnect()
        thread = self.create_http().get_json()["thread"]
        client.connect()
        client.emit("review.join", {"version_id": self.draft3})
        canonical = self.http.get(f"/api/versions/{self.draft3}/threads").get_json()["threads"]
        self.assertEqual(canonical[0]["thread_id"], thread["thread_id"])

    def test_no_socket_discussion_mutation_handlers(self):
        self.assertEqual(set(self.io.server.handlers["/"]),
                         {"connect", "disconnect", "review.join", "review.leave", "review.page"})

    def test_simultaneous_service_edits_have_one_winner(self):
        from threading import Barrier
        thread = self.create_discussion()
        comment_id = thread["comments"][0]["comment_id"]
        ready = Barrier(2)
        def attempt(body):
            ready.wait(timeout=5)
            try:
                edit_comment(self.database, comment_id, self.alpha["user_id"], body, 1)
                return "saved"
            except CommentConflictError:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, ["First contender", "Second contender"]))
        self.assertCountEqual(outcomes, ["saved", "conflict"])
        self.assertEqual(get_thread(self.database, thread["thread_id"])["comments"][0]["current_revision"], 2)

    def test_app_factory_does_not_share_presence_or_socket_server(self):
        self.socket()
        other = create_app({"TESTING": True, "DATABASE": str(self.database),
                            "STORAGE_ROOT": str(self.storage_root)})
        self.assertIsNot(other.extensions["socketio"], self.io)
        self.assertEqual(other.extensions["review_presence"].connections, {})

    def test_socket_transport_rejects_cross_origin(self):
        with self.assertLogs("engineio.server", level="ERROR"):
            response = self.http.get("/socket.io/?EIO=4&transport=polling", headers={"Origin": "https://unrelated.example"})
        self.assertEqual(response.status_code, 400)
