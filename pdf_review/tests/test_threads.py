from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from review import create_app
from tests.auth_helpers import authenticate, secure_client
from review.anchors import create_anchor
from review.database import MIGRATIONS, connect, init_database, transaction
from review.documents import create_document, import_version, now_utc
from review.storage import BlobStore
from review.threads import (
    ThreadValidationError,
    add_comment,
    create_thread,
    delete_comment,
    edit_comment,
    get_thread,
    list_threads,
    set_thread_resolved,
)
from review.users import create_user


def pdf_bytes(marker: bytes) -> bytes:
    return b"%PDF-1.4\n% " + marker + b"\n%%EOF\n"


def anchor_payload(page_number: int = 1, top: float = 718.0) -> dict:
    page_text = "Before selected text after"
    exact = "selected text"
    start = page_text.index(exact)
    end = start + len(exact)
    return {
        "anchor_kind": "text",
        "selection_text": exact,
        "selector_version": "pdfjs-dom-text-v1",
        "anchor_schema_version": 1,
        "page_count": 10,
        "segments": [
            {
                "segment_index": 0,
                "page_number": page_number,
                "rectangles": [[10.0, top - 18.0, 110.0, top]],
                "pdf_view_box": [0.0, 0.0, 612.0, 792.0],
                "capture_viewport": {
                    "width": 816.0,
                    "height": 1056.0,
                    "rotation": 0,
                },
                "exact_text": exact,
                "prefix": page_text[:start],
                "suffix": page_text[end:],
                "text_start": start,
                "text_end": end,
                "page_text": page_text,
            }
        ],
    }


class ThreadTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.database = self.root / "data" / "test.sqlite3"
        self.storage_root = self.root / "data"
        init_database(self.database)
        self.blobs = BlobStore(self.storage_root)
        self.document_id = create_document(self.database, "Synthetic Document")
        self.draft3 = import_version(
            self.database,
            self.blobs,
            self.document_id,
            io.BytesIO(pdf_bytes(b"draft 3")),
            "draft-3.pdf",
            "Draft 3",
        ).version_id
        self.draft4 = import_version(
            self.database,
            self.blobs,
            self.document_id,
            io.BytesIO(pdf_bytes(b"draft 4")),
            "draft-4.pdf",
            "Draft 4",
        ).version_id
        self.alpha = create_user(self.database, "ReviewerAlpha")
        self.beta = create_user(self.database, "ReviewerBeta")

    def tearDown(self):
        self.temp_directory.cleanup()

    def counts(self) -> dict[str, int]:
        connection = connect(self.database)
        try:
            names = [
                "anchor_instances",
                "anchor_segments",
                "threads",
                "thread_targets",
                "comments",
                "comment_revisions",
            ]
            return {
                name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in names
            }
        finally:
            connection.close()

    def create_discussion(self, body: str = "This sentence confused me.", **anchor_kwargs):
        return create_thread(
            self.database,
            self.draft3,
            self.alpha["user_id"],
            anchor_payload(**anchor_kwargs),
            body,
        )

    def test_migration_three_is_idempotent_and_preserves_existing_anchor_data(self):
        legacy = self.root / "legacy.sqlite3"
        connection = connect(legacy)
        try:
            connection.execute(
                """
                CREATE TABLE schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    applied_at TEXT NOT NULL
                )
                """
            )
            for version, name, sql in MIGRATIONS[:2]:
                connection.executescript(sql)
                connection.execute(
                    "INSERT INTO schema_migrations VALUES (?, ?, 'old')", (version, name)
                )
            connection.execute("INSERT INTO documents VALUES ('doc', 'Existing', 'old')")
            digest = "a" * 64
            connection.execute(
                """
                INSERT INTO document_versions(
                    version_id, document_id, original_filename, sha256,
                    blob_path, file_size, imported_at
                ) VALUES ('version', 'doc', 'old.pdf', ?, ?, 12, 'old')
                """,
                (digest, f"blobs/{digest}.pdf"),
            )
            connection.execute(
                """
                INSERT INTO anchor_instances VALUES (
                    'anchor', 'version', 'text', 'old text',
                    'pdfjs-dom-text-v1', 1, 'old'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO anchor_segments(
                    segment_id, anchor_id, segment_index, page_number,
                    rectangles_json, pdf_view_box_json,
                    capture_viewport_width, capture_viewport_height, capture_rotation
                ) VALUES ('segment', 'anchor', 0, 1, '[[1,1,2,2]]',
                          '[0,0,10,10]', 10, 10, 0)
                """
            )
            connection.commit()
        finally:
            connection.close()

        init_database(legacy)
        init_database(legacy)
        connection = connect(legacy)
        try:
            self.assertEqual(
                connection.execute("SELECT selection_text FROM anchor_instances").fetchone()[0],
                "old text",
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0],
                len(MIGRATIONS),
            )
            for table in ("users", "threads", "thread_targets", "comments", "comment_revisions"):
                self.assertIsNotNone(
                    connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    ).fetchone()
                )
        finally:
            connection.close()

    def test_atomic_creation_writes_exactly_one_complete_discussion_bundle(self):
        thread = self.create_discussion()
        self.assertEqual(
            self.counts(),
            {
                "anchor_instances": 1,
                "anchor_segments": 1,
                "threads": 1,
                "thread_targets": 1,
                "comments": 1,
                "comment_revisions": 1,
            },
        )
        self.assertEqual(thread["status"], "open")
        self.assertEqual(thread["targets"][0]["role"], "origin")
        self.assertEqual(thread["comments"][0]["body"], "This sentence confused me.")
        self.assertEqual(thread["comments"][0]["revision_count"], 1)

    def test_atomic_creation_rolls_back_every_object_after_late_failure(self):
        with mock.patch("review.threads._insert_comment", side_effect=RuntimeError("late failure")):
            with self.assertRaises(RuntimeError):
                self.create_discussion()
        self.assertEqual(
            self.counts(),
            {
                "anchor_instances": 0,
                "anchor_segments": 0,
                "threads": 0,
                "thread_targets": 0,
                "comments": 0,
                "comment_revisions": 0,
            },
        )

    def test_thread_target_constraints_reject_cross_document_and_duplicate_origin(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute(
                    """
                    INSERT INTO threads(
                        thread_id, document_id, created_by_user_id,
                        origin_thread_target_id, status, created_at
                    ) VALUES (?, ?, ?, ?, 'open', ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        self.document_id,
                        self.alpha["user_id"],
                        str(uuid.uuid4()),
                        now_utc(),
                    ),
                )
        thread = self.create_discussion()
        other_document = create_document(self.database, "Other")
        other_version = import_version(
            self.database,
            self.blobs,
            other_document,
            io.BytesIO(pdf_bytes(b"other")),
            "other.pdf",
        ).version_id
        other_anchor = create_anchor(self.database, other_version, anchor_payload())
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute(
                    """
                    INSERT INTO thread_targets VALUES (?, ?, ?, 'manual', ?)
                    """,
                    (str(uuid.uuid4()), thread["thread_id"], other_anchor["anchor_id"], now_utc()),
                )

        second_anchor = create_anchor(self.database, self.draft3, anchor_payload(page_number=2))
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute(
                    """
                    INSERT INTO thread_targets VALUES (?, ?, ?, 'origin', ?)
                    """,
                    (str(uuid.uuid4()), thread["thread_id"], second_anchor["anchor_id"], now_utc()),
                )
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute(
                    "DELETE FROM thread_targets WHERE thread_target_id = ?",
                    (thread["targets"][0]["thread_target_id"],),
                )

    def test_replies_are_stable_and_preserve_authorship_after_identity_switch(self):
        thread = self.create_discussion()
        thread = add_comment(
            self.database, thread["thread_id"], self.beta["user_id"], "ReviewerBeta reply"
        )
        thread = add_comment(
            self.database, thread["thread_id"], self.alpha["user_id"], "ReviewerAlpha reply"
        )
        self.assertEqual(
            [comment["body"] for comment in thread["comments"]],
            ["This sentence confused me.", "ReviewerBeta reply", "ReviewerAlpha reply"],
        )
        self.assertEqual(
            [comment["author"]["display_name"] for comment in thread["comments"]],
            ["ReviewerAlpha", "ReviewerBeta", "ReviewerAlpha"],
        )

    def test_edits_append_revisions_and_retain_original_text(self):
        thread = self.create_discussion("Original")
        comment_id = thread["comments"][0]["comment_id"]
        edit_comment(self.database, comment_id, self.alpha["user_id"], "Second", 1)
        thread = edit_comment(self.database, comment_id, self.alpha["user_id"], "Third", 2)
        comment = thread["comments"][0]
        self.assertEqual(comment["body"], "Third")
        self.assertIsNotNone(comment["edited_at"])
        self.assertEqual(comment["revision_count"], 3)
        connection = connect(self.database)
        try:
            revisions = connection.execute(
                """
                SELECT revision_number, body, editor_id FROM comment_revisions
                WHERE comment_id = ? ORDER BY revision_number
                """,
                (comment_id,),
            ).fetchall()
            self.assertEqual([row["body"] for row in revisions], ["Original", "Second", "Third"])
            self.assertEqual(revisions[1]["editor_id"], self.alpha["user_id"])
        finally:
            connection.close()

    def test_soft_delete_tombstones_body_but_preserves_reply_history_and_anchor(self):
        thread = self.create_discussion("Root")
        root_id = thread["comments"][0]["comment_id"]
        thread = add_comment(
            self.database, thread["thread_id"], self.beta["user_id"], "Reply survives"
        )
        thread = delete_comment(self.database, root_id, self.alpha["user_id"])
        self.assertTrue(thread["comments"][0]["is_deleted"])
        self.assertIsNone(thread["comments"][0]["body"])
        self.assertEqual(thread["comments"][1]["body"], "Reply survives")
        self.assertEqual(self.counts()["anchor_instances"], 1)
        self.assertEqual(self.counts()["comment_revisions"], 2)
        with self.assertRaises(ThreadValidationError):
            edit_comment(self.database, root_id, self.alpha["user_id"], "Restore")

    def test_thread_origin_anchor_cannot_be_deleted(self):
        thread = self.create_discussion()
        anchor_id = thread["targets"][0]["anchor"]["anchor_id"]
        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.database),
                "STORAGE_ROOT": str(self.storage_root),
                "SECRET_KEY": "test",
            }
        )
        response = secure_client(app).delete(f"/api/anchors/{anchor_id}")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "anchor_in_use")
        self.assertEqual(self.counts()["anchor_instances"], 1)

    def test_resolution_and_reopen_are_idempotent_and_preserve_discussion(self):
        thread = self.create_discussion()
        resolved = set_thread_resolved(
            self.database, thread["thread_id"], self.beta["user_id"], True
        )
        first_resolved_at = resolved["resolved_at"]
        self.assertEqual(resolved["status"], "resolved")
        self.assertEqual(resolved["resolved_by"]["display_name"], "ReviewerBeta")
        resolved_again = set_thread_resolved(
            self.database, thread["thread_id"], self.alpha["user_id"], True
        )
        self.assertEqual(resolved_again["resolved_at"], first_resolved_at)
        self.assertEqual(resolved_again["resolved_by"]["display_name"], "ReviewerBeta")
        reopened = set_thread_resolved(
            self.database, thread["thread_id"], self.alpha["user_id"], False
        )
        self.assertEqual(reopened["status"], "open")
        self.assertIsNone(reopened["resolved_at"])
        self.assertEqual(len(reopened["comments"]), 1)
        reopened_again = set_thread_resolved(
            self.database, thread["thread_id"], self.beta["user_id"], False
        )
        self.assertEqual(reopened_again["status"], "open")

    def test_version_filtering_and_page_position_order_are_deterministic(self):
        page_two_low = self.create_discussion("Page 2 low", page_number=2, top=200)
        page_one = self.create_discussion("Page 1", page_number=1, top=100)
        page_two_high = self.create_discussion("Page 2 high", page_number=2, top=700)
        ordered = list_threads(self.database, self.draft3)
        self.assertEqual(
            [item["thread_id"] for item in ordered],
            [page_one["thread_id"], page_two_high["thread_id"], page_two_low["thread_id"]],
        )
        self.assertEqual(list_threads(self.database, self.draft4), [])

    def test_api_identity_session_crud_and_version_isolation(self):
        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.database),
                "STORAGE_ROOT": str(self.storage_root),
                "SECRET_KEY": "test",
            }
        )
        client = secure_client(app)
        with client.session_transaction() as state:
            state.clear()
        missing_identity = client.post(
            f"/api/versions/{self.draft3}/threads",
            json={"anchor": anchor_payload(), "body": "No identity"},
        )
        self.assertEqual(missing_identity.status_code, 401)

        alice = create_user(self.database, "Alice")
        authenticate(client, alice["user_id"])
        self.assertEqual(client.post("/api/reviewers", json={"display_name": "Spoof"}).status_code, 405)
        self.assertEqual(client.post("/api/reviewer", json={"user_id": self.alpha["user_id"]}).status_code, 404)
        created = client.post(
            f"/api/versions/{self.draft3}/threads",
            json={"anchor": anchor_payload(), "body": "Root from Alice"},
        )
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        thread = created.get_json()["thread"]
        self.assertEqual(thread["comments"][0]["author"]["user_id"], alice["user_id"])

        authenticate(client, self.beta["user_id"])
        reply = client.post(
            f"/api/threads/{thread['thread_id']}/comments", json={"body": "Reply"}
        )
        self.assertEqual(reply.status_code, 201)
        comments = reply.get_json()["thread"]["comments"]
        self.assertEqual(comments[0]["author"]["display_name"], "Alice")
        self.assertEqual(comments[1]["author"]["display_name"], "ReviewerBeta")

        draft3_threads = client.get(f"/api/versions/{self.draft3}/threads").get_json()["threads"]
        draft4_threads = client.get(f"/api/versions/{self.draft4}/threads").get_json()["threads"]
        self.assertEqual(len(draft3_threads), 1)
        self.assertEqual(draft4_threads, [])
        self.assertIn("anchor", draft3_threads[0]["targets"][0])

    def test_api_edit_delete_resolve_and_validation_statuses(self):
        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.database),
                "STORAGE_ROOT": str(self.storage_root),
                "SECRET_KEY": "test",
            }
        )
        client = secure_client(app)
        authenticate(client, self.alpha["user_id"])
        malformed = anchor_payload()
        malformed["segments"][0]["rectangles"] = []
        self.assertEqual(
            client.post(
                f"/api/versions/{self.draft3}/threads",
                json={"anchor": malformed, "body": "Root"},
            ).status_code,
            422,
        )
        self.assertEqual(
            client.post(
                f"/api/versions/{self.draft3}/threads",
                json={"anchor": anchor_payload(), "body": "   "},
            ).status_code,
            422,
        )
        self.assertEqual(
            client.post(
                f"/api/versions/{self.draft3}/threads",
                json={"anchor": anchor_payload(), "body": "x" * 10_001},
            ).status_code,
            422,
        )
        self.assertEqual(self.counts()["threads"], 0)

        created = client.post(
            f"/api/versions/{self.draft3}/threads",
            json={"anchor": anchor_payload(), "body": "Root"},
        ).get_json()["thread"]
        comment_id = created["comments"][0]["comment_id"]
        edited = client.patch(f"/api/comments/{comment_id}", json={"body": "Edited", "expected_revision": 1})
        self.assertEqual(edited.get_json()["thread"]["comments"][0]["body"], "Edited")
        resolved = client.post(f"/api/threads/{created['thread_id']}/resolve")
        self.assertEqual(resolved.get_json()["thread"]["status"], "resolved")
        reopened = client.post(f"/api/threads/{created['thread_id']}/reopen")
        self.assertEqual(reopened.get_json()["thread"]["status"], "open")
        deleted = client.delete(f"/api/comments/{comment_id}")
        self.assertTrue(deleted.get_json()["thread"]["comments"][0]["is_deleted"])


if __name__ == "__main__":
    unittest.main()
