import sqlite3
import unittest
from unittest import mock

from review import create_app
from tests.auth_helpers import authenticate, secure_client
from review.database import connect, init_database, transaction
from review.threads import CommentPermissionError, edit_comment, get_thread, set_thread_resolved
import tests.test_threads as fixtures


class ReviewPermissionsTests(unittest.TestCase):
    setUp = fixtures.ThreadTests.setUp
    tearDown = fixtures.ThreadTests.tearDown
    create_discussion = fixtures.ThreadTests.create_discussion

    def test_other_reviewer_cannot_edit_service_or_http_or_emit(self):
        thread = self.create_discussion("Original")
        comment_id = thread["comments"][0]["comment_id"]
        with self.assertRaises(CommentPermissionError):
            edit_comment(self.database, comment_id, self.beta["user_id"], "Forbidden", 1)
        app = create_app({"TESTING": True, "DATABASE": str(self.database),
                          "STORAGE_ROOT": str(self.storage_root), "SECRET_KEY": "test"})
        client = secure_client(app)
        authenticate(client, self.beta["user_id"])
        with mock.patch("review.routes.notify_thread_changed") as notify:
            response = client.patch(f"/api/comments/{comment_id}", json={"body": "Forbidden", "expected_revision": 1})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.get_json()["error"]["code"], "comment_edit_forbidden")
            notify.assert_not_called()
        canonical = get_thread(self.database, thread["thread_id"])["comments"][0]
        self.assertEqual((canonical["body"], canonical["current_revision"]), ("Original", 1))
        authenticate(client, self.alpha["user_id"])
        self.assertEqual(client.patch(f"/api/comments/{comment_id}", json={"body": "Allowed", "expected_revision": 1}).status_code, 200)

    def test_history_retains_every_real_transition_and_actor(self):
        thread = self.create_discussion()
        thread_id = thread["thread_id"]
        self.assertEqual(thread["status_history"], [])
        set_thread_resolved(self.database, thread_id, self.alpha["user_id"], False)
        set_thread_resolved(self.database, thread_id, self.beta["user_id"], True)
        set_thread_resolved(self.database, thread_id, self.alpha["user_id"], True)
        reopened = set_thread_resolved(self.database, thread_id, self.alpha["user_id"], False)
        self.assertIsNone(reopened["resolved_by"])
        self.assertIsNone(reopened["resolved_at"])
        set_thread_resolved(self.database, thread_id, self.beta["user_id"], False)
        thread = set_thread_resolved(self.database, thread_id, self.beta["user_id"], True)
        self.assertEqual([change["action"] for change in thread["status_history"]], ["resolved", "reopened", "resolved"])
        self.assertEqual([change["actor"]["display_name"] for change in thread["status_history"]], ["ReviewerBeta", "ReviewerAlpha", "ReviewerBeta"])
        self.assertTrue(all(change["created_at"] for change in thread["status_history"]))

    def test_history_is_immutable_and_atomic_with_status(self):
        thread = self.create_discussion()
        thread_id = thread["thread_id"]
        set_thread_resolved(self.database, thread_id, self.alpha["user_id"], True)
        for sql in ["UPDATE thread_status_changes SET action = 'reopened'", "DELETE FROM thread_status_changes"]:
            with self.assertRaises(sqlite3.IntegrityError):
                with transaction(self.database) as connection:
                    connection.execute(sql)
        with transaction(self.database) as connection:
            connection.execute("""CREATE TRIGGER fail_reopen BEFORE UPDATE ON threads
                                BEGIN SELECT RAISE(ABORT, 'simulated failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            set_thread_resolved(self.database, thread_id, self.beta["user_id"], False)
        canonical = get_thread(self.database, thread_id)
        self.assertEqual(canonical["status"], "resolved")
        self.assertEqual(len(canonical["status_history"]), 1)

    def test_migration_backfills_known_resolution_without_inventing_past_actions(self):
        resolved = self.create_discussion("Resolved")
        reopened = self.create_discussion("Reopened")
        set_thread_resolved(self.database, resolved["thread_id"], self.beta["user_id"], True)
        set_thread_resolved(self.database, reopened["thread_id"], self.alpha["user_id"], True)
        set_thread_resolved(self.database, reopened["thread_id"], self.beta["user_id"], False)
        legacy = self.root / "legacy3.sqlite3"
        source = connect(self.database)
        destination = sqlite3.connect(legacy)
        try:
            source.backup(destination)
            destination.execute("DROP TABLE thread_status_changes")
            destination.execute("DELETE FROM schema_migrations WHERE version = 4")
            destination.commit()
        finally:
            source.close()
            destination.close()
        init_database(legacy)
        init_database(legacy)
        migrated = get_thread(legacy, resolved["thread_id"])
        self.assertEqual(migrated["status_history"][0]["actor"], migrated["resolved_by"])
        self.assertEqual(migrated["status_history"][0]["created_at"], migrated["resolved_at"])
        self.assertEqual(len(migrated["status_history"]), 1)
        self.assertEqual(get_thread(legacy, reopened["thread_id"])["status_history"], [])
