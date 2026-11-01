"""Slice 5 domain, schema, HTTP, concurrency, and post-commit notification tests."""

import hashlib
import io
import sqlite3
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from review import create_app
from tests.auth_helpers import authenticate, secure_client
from review.anchors import AnchorValidationError, create_anchor, get_anchor, list_anchors
from review.database import MIGRATIONS, connect, init_database, transaction
from review.documents import create_document, import_version, now_utc
from review.migrations import (MigrationConflictError, MigrationError, MigrationNotFoundError,
                               accept_existing_target, carry_item, complete_migration, create_migration,
                               get_migration, list_migrations, skip_item)
from review.targets import target_history
from review.threads import add_comment, get_thread, list_threads, set_thread_resolved
import tests.test_threads as fixtures


class MigrationTests(unittest.TestCase):
    create_discussion = fixtures.ThreadTests.create_discussion

    def setUp(self):
        fixtures.ThreadTests.setUp(self)
        self.user = self.alpha["user_id"]
        self.app = create_app({"TESTING": True, "DATABASE": str(self.database),
                               "STORAGE_ROOT": str(self.storage_root), "SECRET_KEY": "test"})
        self.http = secure_client(self.app, self.alpha["user_id"])
        authenticate(self.http, self.user)
        self.sockets = []

    def tearDown(self):
        for client in self.sockets:
            if client.is_connected(): client.disconnect()
        fixtures.ThreadTests.tearDown(self)

    def run_for_thread(self, source=None, target=None):
        return create_migration(self.database, self.document_id, source or self.draft3, target or self.draft4, self.user)

    def carry(self, run, item=None, **kwargs):
        item = item or run["items"][0]
        return carry_item(self.database, run["migration_id"], item["item_id"], self.user,
                          fixtures.anchor_payload(page_number=2), item["revision_number"], item["current_target_id"], **kwargs)

    def snapshot(self, database=None):
        connection = connect(database or self.database)
        try:
            return {table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
                    for table in ["documents", "document_versions", "users", "anchor_instances", "anchor_segments",
                                  "threads", "thread_targets", "comments", "comment_revisions", "thread_status_changes"]}
        finally: connection.close()

    def counts(self):
        connection = connect(self.database)
        try:
            return {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in [
                "anchor_instances", "anchor_segments", "threads", "thread_targets", "comments", "comment_revisions",
                "thread_target_heads", "thread_target_provenance", "migration_runs", "migration_items"]}
        finally: connection.close()

    def socket(self, version):
        client = self.app.extensions["socketio"].test_client(self.app, flask_test_client=self.http)
        client.emit("review.join", {"version_id": version})
        client.get_received()
        self.sockets.append(client)
        return client

    def events(self, client):
        return [event["args"][0] for event in client.get_received() if event["name"] == "review.changed"]

    def test_migration5_backfill_preserves_all_prior_rows_and_origin_heads(self):
        thread = self.create_discussion()
        add_comment(self.database, thread["thread_id"], self.user, "Reply")
        set_thread_resolved(self.database, thread["thread_id"], self.user, True)
        before = self.snapshot()
        legacy = self.root / "legacy4.sqlite3"
        source = connect(self.database)
        destination = sqlite3.connect(legacy)
        try:
            source.backup(destination)
            # Make a genuine pre-5 schema by removing only newly added objects.
            triggers = destination.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
            old_names = {"protect_document_version_bytes", "protect_anchor_instance_contents", "protect_anchor_segment_contents",
                         "validate_thread_target_insert", "protect_thread_identity", "protect_thread_target_contents",
                         "protect_origin_thread_target", "protect_comment_identity", "protect_comment_revisions",
                         "prevent_comment_revision_deletion", "protect_thread_status_changes", "prevent_thread_status_change_deletion"}
            for (name,) in triggers:
                if name not in old_names: destination.execute(f"DROP TRIGGER {name}")
            for table in ["thread_target_provenance", "migration_items", "migration_runs", "thread_target_heads"]:
                destination.execute(f"DROP TABLE {table}")
            destination.execute("DELETE FROM schema_migrations WHERE version=5")
            destination.commit()
        finally:
            source.close(); destination.close()
        init_database(legacy); init_database(legacy)
        self.assertEqual(self.snapshot(legacy), before)
        connection = connect(legacy)
        try:
            head = connection.execute("SELECT * FROM thread_target_heads").fetchone()
            self.assertEqual((head["thread_id"], head["document_version_id"], head["thread_target_id"]),
                             (thread["thread_id"], self.draft3, thread["targets"][0]["thread_target_id"]))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], len(MIGRATIONS))
        finally: connection.close()

    def test_effective_head_constraints_and_origin_guard(self):
        first = self.create_discussion()
        second = self.create_discussion()
        origin = first["targets"][0]["thread_target_id"]
        anchor = create_anchor(self.database, self.draft3, fixtures.anchor_payload())
        replacement = str(uuid.uuid4())
        with transaction(self.database) as connection:
            connection.execute("INSERT INTO thread_targets VALUES (?, ?, ?, 'manual', ?)",
                               (replacement, first["thread_id"], anchor["anchor_id"], now_utc()))
        invalids = [
            ("INSERT INTO thread_target_heads VALUES (?, ?, ?, ?, ?)", (first["thread_id"], self.draft3, origin, now_utc(), self.user)),
            ("INSERT INTO thread_target_heads VALUES (?, ?, ?, ?, ?)", (first["thread_id"], self.draft4, origin, now_utc(), self.user)),
            ("INSERT INTO thread_target_heads VALUES (?, ?, ?, ?, ?)", (first["thread_id"], self.draft4, second["targets"][0]["thread_target_id"], now_utc(), self.user)),
            ("UPDATE thread_target_heads SET thread_target_id=? WHERE thread_id=?", (replacement, first["thread_id"])),
            ("DELETE FROM thread_target_heads WHERE thread_id=?", (first["thread_id"],)),
        ]
        for sql, values in invalids:
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                with transaction(self.database) as connection: connection.execute(sql, values)

    def test_run_creation_snapshots_source_including_resolved_without_domain_writes(self):
        first = self.create_discussion()
        second = self.create_discussion()
        set_thread_resolved(self.database, second["thread_id"], self.user, True)
        before = self.snapshot()
        run = self.run_for_thread()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(run["counts"], {"pending": 2, "carried": 0, "skipped": 0})
        self.assertEqual({item["thread_id"] for item in run["items"]}, {first["thread_id"], second["thread_id"]})

    def test_reject_invalid_runs(self):
        other_doc = create_document(self.database, "Other")
        other_version = import_version(self.database, self.blobs, other_doc, io.BytesIO(fixtures.pdf_bytes(b"other")), "other.pdf").version_id
        for document, source, target in [("missing", self.draft3, self.draft4),
                                          (self.document_id, "missing", self.draft4), (self.document_id, self.draft3, "missing"),
                                          (self.document_id, self.draft3, self.draft3), (self.document_id, self.draft3, other_version),
                                          (self.document_id, None, self.draft4)]:
            with self.subTest(source=source, target=target), self.assertRaises(MigrationError):
                create_migration(self.database, document, source, target, self.user)

    def test_carry_creates_one_target_and_shared_discussion_not_copies(self):
        thread = self.create_discussion()
        run = self.run_for_thread()
        before = self.counts()
        carried = self.carry(run)
        after = self.counts()
        self.assertEqual(carried["thread_id"], thread["thread_id"])
        for table in ["threads", "comments", "comment_revisions"]: self.assertEqual(after[table], before[table])
        for table in ["anchor_instances", "anchor_segments", "thread_targets", "thread_target_provenance", "thread_target_heads"]:
            self.assertEqual(after[table], before[table] + 1)
        source = list_threads(self.database, self.draft3)[0]
        destination = list_threads(self.database, self.draft4)[0]
        self.assertEqual(source["comments"], destination["comments"])
        self.assertEqual(source["targets"], thread["targets"])
        self.assertEqual(destination["targets"][0]["role"], "manual")
        history = target_history(self.database, thread["thread_id"])
        provenance = next(target["provenance"] for target in history if target["role"] == "manual")
        self.assertEqual(provenance["source_thread_target_id"], thread["targets"][0]["thread_target_id"])
        self.assertEqual(provenance["method"], "manual_selection")
        self.assertIsNone(provenance["confidence"])
        self.assertIsNone(provenance["algorithm_version"])

    def test_atomic_rollback_at_each_late_stage_for_carry_and_reanchor(self):
        self.create_discussion()
        initial = self.run_for_thread()
        for reanchor in [False, True]:
            if reanchor: self.carry(initial)
            for table, operation in [("thread_targets", "INSERT"), ("thread_target_provenance", "INSERT"),
                                     ("thread_target_heads", "UPDATE" if reanchor else "INSERT"), ("migration_items", "UPDATE")]:
                run = get_migration(self.database, initial["migration_id"])
                before = self.counts()
                with transaction(self.database) as connection:
                    connection.execute(f"CREATE TRIGGER fail_stage BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'test failure'); END")
                try:
                    with self.assertRaises(sqlite3.IntegrityError): self.carry(run, reanchor=reanchor)
                    self.assertEqual(self.counts(), before)
                    self.assertEqual(get_migration(self.database, run["migration_id"])["items"], run["items"])
                finally:
                    with transaction(self.database) as connection: connection.execute("DROP TRIGGER fail_stage")

    def test_reanchor_preserves_old_anchor_target_provenance_and_removes_old_effective(self):
        thread = self.create_discussion()
        run = self.run_for_thread()
        first = self.carry(run)["targets"][0]
        old_anchor = get_anchor(self.database, first["anchor"]["anchor_id"])
        run = get_migration(self.database, run["migration_id"])
        corrected = self.carry(run, reanchor=True)["targets"][0]
        self.assertNotEqual(first["thread_target_id"], corrected["thread_target_id"])
        self.assertEqual(get_anchor(self.database, old_anchor["anchor_id"]), old_anchor)
        normal = list_threads(self.database, self.draft4)
        self.assertEqual(len(normal), 1)
        self.assertEqual(normal[0]["targets"], [corrected])
        history = target_history(self.database, thread["thread_id"])
        self.assertEqual(len(history), 3)
        old = next(target for target in history if target["thread_target_id"] == first["thread_target_id"])
        current = next(target for target in history if target["thread_target_id"] == corrected["thread_target_id"])
        self.assertFalse(old["is_effective"])
        self.assertEqual(current["provenance"]["supersedes_thread_target_id"], old["thread_target_id"])
        self.assertEqual(list_threads(self.database, self.draft3)[0]["targets"], thread["targets"])
        self.assertEqual(list_anchors(self.database, self.draft4, standalone_only=True), [])

    def test_chain_uses_effective_manual_source_not_origin(self):
        thread = self.create_discussion()
        run = self.run_for_thread()
        mapped = self.carry(run)["targets"][0]
        draft5 = import_version(self.database, self.blobs, self.document_id, io.BytesIO(fixtures.pdf_bytes(b"draft5")), "draft5.pdf").version_id
        next_run = self.run_for_thread(self.draft4, draft5)
        self.assertEqual(next_run["items"][0]["source_thread_target_id"], mapped["thread_target_id"])
        self.carry(next_run)
        self.assertEqual(len(get_thread(self.database, thread["thread_id"])["targets"]), 3)

    def test_run_population_represents_existing_destination_without_duplicate(self):
        self.create_discussion()
        self.carry(self.run_for_thread())
        before = self.counts()
        another = self.run_for_thread()
        self.assertEqual(another["counts"]["carried"], 1)
        self.assertEqual(self.counts()["thread_targets"], before["thread_targets"])

    def test_skip_records_actor_note_without_changing_thread_or_creating_anchor(self):
        thread = self.create_discussion()
        run = self.run_for_thread()
        before = self.snapshot()
        item = run["items"][0]
        result = skip_item(self.database, run["migration_id"], item["item_id"], self.beta["user_id"], 1, "Not relevant")
        self.assertEqual(self.snapshot(), before)
        decision = result["items"][0]
        self.assertEqual(decision["decision_by"]["display_name"], "ReviewerBeta")
        self.assertTrue(decision["decided_at"])
        self.assertEqual(decision["skip_note"], "Not relevant")
        self.assertEqual(decision["thread"]["status"], "open")
        with self.assertRaises(MigrationConflictError): self.carry(result)

    def test_completion_pending_policy_idempotence_and_frozen_decisions(self):
        self.create_discussion()
        run = self.run_for_thread()
        with self.assertRaises(MigrationConflictError): complete_migration(self.database, run["migration_id"], self.user)
        self.carry(run)
        first = complete_migration(self.database, run["migration_id"], self.user)
        second = complete_migration(self.database, run["migration_id"], self.beta["user_id"])
        self.assertEqual(first, second)
        self.assertEqual(first["completed_by"]["user_id"], self.user)
        with self.assertRaises(MigrationConflictError): self.carry(first, reanchor=True)

    def test_optimistic_target_conflicts_across_runs_and_accept_existing(self):
        self.create_discussion()
        first, second = self.run_for_thread(), self.run_for_thread()
        self.carry(first)
        before = self.counts()
        with self.assertRaises(MigrationConflictError): self.carry(second)
        self.assertEqual(self.counts(), before)
        refreshed = get_migration(self.database, second["migration_id"])
        item = refreshed["items"][0]
        accepted = accept_existing_target(self.database, second["migration_id"], item["item_id"], self.user, 1, item["current_target_id"])
        self.assertEqual(accepted["counts"]["carried"], 1)
        self.assertEqual(self.counts()["thread_targets"], before["thread_targets"])

    def test_simultaneous_carry_has_one_winner(self):
        self.create_discussion()
        run = self.run_for_thread()
        def attempt(_):
            try: self.carry(run); return "saved"
            except MigrationConflictError: return "conflict"
        with ThreadPoolExecutor(max_workers=2) as executor: results = list(executor.map(attempt, range(2)))
        self.assertCountEqual(results, ["saved", "conflict"])
        self.assertEqual(self.counts()["thread_target_provenance"], 1)

    def test_cannot_reanchor_origin_even_when_migrating_backwards(self):
        self.create_discussion()
        self.carry(self.run_for_thread())
        backwards = self.run_for_thread(self.draft4, self.draft3)
        self.assertEqual(backwards["counts"]["carried"], 1)
        with self.assertRaises(MigrationConflictError): self.carry(backwards, reanchor=True)

    def test_api_strict_payload_identity_validation_and_html_entry(self):
        self.create_discussion()
        url = f"/api/documents/{self.document_id}/migrations"
        payload = {"source_version_id": self.draft3, "target_version_id": self.draft4}
        self.assertEqual(self.app.test_client().post(url, json=payload).status_code, 401)
        self.assertEqual(self.http.post(url, json=payload | {"author_id": self.user}).status_code, 400)
        response = self.http.post(url, json=payload)
        self.assertEqual(response.status_code, 201)
        run = response.get_json()["migration"]
        item = run["items"][0]
        carry_url = f"/api/migrations/{run['migration_id']}/items/{item['item_id']}/carry"
        self.assertEqual(self.http.post(carry_url, json={"anchor": fixtures.anchor_payload()}).status_code, 400)
        self.assertEqual(self.http.post(carry_url, json={"anchor": {}, "expected_revision": 1, "expected_target_id": None}).status_code, 422)
        self.assertEqual(self.http.get(f"/versions/{self.draft3}/view?migration={run['migration_id']}").status_code, 404)
        self.assertIn(b"Carry feedback forward", self.http.get(f"/documents/{self.document_id}/migrations").data)
        self.assertEqual(self.http.get(f"/api/migrations/{run['migration_id']}").status_code, 200)
        self.assertEqual(len(self.http.get(url).get_json()["migrations"]), 1)

    def test_post_commit_carry_reanchor_and_shared_reply_broadcasts(self):
        thread = self.create_discussion()
        run = self.run_for_thread()
        first, second = self.socket(self.draft3), self.socket(self.draft4)
        item = run["items"][0]
        base = f"/api/migrations/{run['migration_id']}/items/{item['item_id']}"
        for action in ["carry", "reanchor"]:
            item = get_migration(self.database, run["migration_id"])["items"][0]
            response = self.http.post(base + "/" + action, json={"anchor": fixtures.anchor_payload(),
                                      "expected_revision": item["revision_number"], "expected_target_id": item["current_target_id"]})
            self.assertEqual(response.status_code, 200)
            for socket in [first, second]:
                self.assertEqual(self.events(socket)[0]["kind"], "thread.targeted" if action == "carry" else "thread.reanchored")
        self.http.post(f"/api/threads/{thread['thread_id']}/comments", json={"body": "Across versions"})
        for socket in [first, second]: self.assertEqual(self.events(socket)[0]["kind"], "comment.created")

    def test_http_rollback_emits_no_review_change_and_emit_failure_keeps_commit(self):
        self.create_discussion()
        run = self.run_for_thread()
        socket = self.socket(self.draft4)
        item = run["items"][0]
        url = f"/api/migrations/{run['migration_id']}/items/{item['item_id']}/carry"
        payload = {"anchor": fixtures.anchor_payload(), "expected_revision": 1, "expected_target_id": None}
        before = self.counts()
        with self.assertLogs(self.app.logger, level="ERROR"), mock.patch("review.migrations._record_decision", side_effect=RuntimeError("last step failed")):
            self.assertEqual(self.http.post(url, json=payload).status_code, 500)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.events(socket), [])
        with self.assertLogs(self.app.logger, level="ERROR"), mock.patch.object(self.app.extensions["socketio"], "emit", side_effect=RuntimeError("emit failed")):
            self.assertEqual(self.http.post(url, json=payload).status_code, 200)
        self.assertEqual(len(list_threads(self.database, self.draft4)), 1)

    def test_historical_target_provenance_and_destination_constraints(self):
        first, other = self.create_discussion(), self.create_discussion()
        run = self.run_for_thread()
        item = next(item for item in run["items"] if item["thread_id"] == first["thread_id"])
        self.carry(run, item)
        target = list_threads(self.database, self.draft4)[0]["targets"][0]["thread_target_id"]
        statements = [
            ("DELETE FROM thread_targets WHERE thread_target_id=?", (target,)),
            ("UPDATE thread_target_provenance SET method='changed' WHERE thread_target_id=?", (target,)),
            ("DELETE FROM thread_target_provenance WHERE thread_target_id=?", (target,)),
            ("UPDATE migration_items SET target_thread_target_id=?, revision_number=revision_number+1 WHERE item_id=?",
             (other["targets"][0]["thread_target_id"], item["item_id"])),
        ]
        for sql, values in statements:
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                with transaction(self.database) as connection: connection.execute(sql, values)

    def test_pdf_storage_bytes_unchanged_by_carry_and_reanchor(self):
        files = list(self.blobs.blob_dir.glob("*.pdf"))
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        self.create_discussion()
        run = self.run_for_thread()
        self.carry(run)
        self.carry(get_migration(self.database, run["migration_id"]), reanchor=True)
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files})

    def test_database_rejects_cross_document_runs_and_incorrect_source_items(self):
        first = self.create_discussion()
        other = self.create_discussion()
        run = self.run_for_thread()
        foreign_doc = create_document(self.database, "Foreign")
        foreign_version = import_version(self.database, self.blobs, foreign_doc,
                                         io.BytesIO(fixtures.pdf_bytes(b"foreign")), "foreign.pdf").version_id
        for source, target in [(self.draft3, self.draft3), (self.draft3, foreign_version), ("missing", self.draft4)]:
            with self.assertRaises(sqlite3.IntegrityError):
                with transaction(self.database) as connection:
                    connection.execute("""INSERT INTO migration_runs
                                       (migration_id, document_id, source_version_id, target_version_id, created_by_user_id, created_at)
                                       VALUES (?, ?, ?, ?, ?, ?)""",
                                       (str(uuid.uuid4()), self.document_id, source, target, self.user, now_utc()))
        # A valid third thread avoids the unique run/thread rule masking source consistency.
        third = self.create_discussion()
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute("""INSERT INTO migration_items
                                   (item_id, migration_id, thread_id, source_thread_target_id) VALUES (?, ?, ?, ?)""",
                                   (str(uuid.uuid4()), run["migration_id"], third["thread_id"], first["targets"][0]["thread_target_id"]))

    def test_database_rejects_invalid_provenance_and_incorrect_head_updates(self):
        first = self.create_discussion()
        other = self.create_discussion()
        run = self.run_for_thread()
        item = next(item for item in run["items"] if item["thread_id"] == first["thread_id"])
        current = self.carry(run, item)["targets"][0]
        anchor = create_anchor(self.database, self.draft4, fixtures.anchor_payload())
        target_id = str(uuid.uuid4())
        with transaction(self.database) as connection:
            connection.execute("INSERT INTO thread_targets VALUES (?, ?, ?, 'manual', ?)",
                               (target_id, first["thread_id"], anchor["anchor_id"], now_utc()))
        for source, supersedes in [(other["targets"][0]["thread_target_id"], None),
                                    (first["targets"][0]["thread_target_id"], first["targets"][0]["thread_target_id"])]:
            with self.assertRaises(sqlite3.IntegrityError):
                with transaction(self.database) as connection:
                    connection.execute("""INSERT INTO thread_target_provenance
                                       (thread_target_id, source_thread_target_id, migration_run_id, supersedes_thread_target_id,
                                        method, created_by_user_id, created_at) VALUES (?, ?, ?, ?, 'manual_selection', ?, ?)""",
                                       (target_id, source, run["migration_id"], supersedes, self.user, now_utc()))
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute("UPDATE thread_target_heads SET thread_target_id=? WHERE thread_id=? AND document_version_id=?",
                                   (other["targets"][0]["thread_target_id"], first["thread_id"], self.draft4))

    def test_source_snapshot_survives_later_source_reanchor(self):
        self.create_discussion()
        original_run = self.run_for_thread()
        old_source = self.carry(original_run)["targets"][0]["thread_target_id"]
        draft5 = import_version(self.database, self.blobs, self.document_id, io.BytesIO(fixtures.pdf_bytes(b"new")), "draft5.pdf").version_id
        next_run = self.run_for_thread(self.draft4, draft5)
        self.carry(get_migration(self.database, original_run["migration_id"]), reanchor=True)
        result = self.carry(next_run)
        target = next(target for target in target_history(self.database, result["thread_id"]) if target["version_id"] == draft5)
        self.assertEqual(target["provenance"]["source_thread_target_id"], old_source)

    def test_broadcast_observes_complete_committed_target_bundle(self):
        self.create_discussion()
        run = self.run_for_thread()
        item = run["items"][0]
        observations = []
        real_emit = self.app.extensions["socketio"].emit
        def observe(event, payload, **kwargs):
            if event == "review.changed":
                observations.append((self.counts(), get_migration(self.database, run["migration_id"])["items"][0]["state"]))
            return real_emit(event, payload, **kwargs)
        with mock.patch.object(self.app.extensions["socketio"], "emit", side_effect=observe):
            response = self.http.post(f"/api/migrations/{run['migration_id']}/items/{item['item_id']}/carry",
                                      json={"anchor": fixtures.anchor_payload(), "expected_revision": 1, "expected_target_id": None})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(observations), 2)
        for counts, state in observations:
            self.assertEqual(counts["thread_target_provenance"], 1)
            self.assertEqual(counts["thread_target_heads"], 2)
            self.assertEqual(state, "carried")
