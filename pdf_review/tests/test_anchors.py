from __future__ import annotations

import copy
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import review.anchors as anchors_module
from review import create_app
from tests.auth_helpers import authenticate, secure_client
from review.anchors import (
    ANCHOR_SCHEMA_VERSION,
    MAX_ANCHOR_PAYLOAD_BYTES,
    TEXT_CONTEXT_LENGTH,
    TEXT_SELECTOR_VERSION,
    AnchorValidationError,
    AnchorVersionNotFoundError,
    create_anchor,
    delete_anchor,
    list_anchors,
)
from review.database import MIGRATIONS, connect, init_database, transaction
from review.documents import create_document, import_version
from review.storage import BlobStore


def pdf_bytes(marker: bytes) -> bytes:
    return b"%PDF-1.4\n% " + marker + b"\n%%EOF\n"


def segment_payload(
    index: int = 0,
    page_number: int = 1,
    page_text: str = "Before selected text after",
    exact_text: str = "selected text",
) -> dict:
    start = page_text.index(exact_text)
    end = start + len(exact_text)
    return {
        "segment_index": index,
        "page_number": page_number,
        "rectangles": [[10.0, 700.0, 110.0, 718.0]],
        "pdf_view_box": [0.0, 0.0, 612.0, 792.0],
        "capture_viewport": {"width": 816.0, "height": 1056.0, "rotation": 0},
        "exact_text": exact_text,
        "prefix": page_text[max(0, start - TEXT_CONTEXT_LENGTH) : start],
        "suffix": page_text[end : end + TEXT_CONTEXT_LENGTH],
        "text_start": start,
        "text_end": end,
        "page_text": page_text,
    }


def anchor_payload(segments: list[dict] | None = None) -> dict:
    return {
        "anchor_kind": "text",
        "selection_text": "selected text",
        "selector_version": TEXT_SELECTOR_VERSION,
        "anchor_schema_version": ANCHOR_SCHEMA_VERSION,
        "page_count": 10,
        "segments": segments if segments is not None else [segment_payload()],
    }


class AnchorTests(unittest.TestCase):
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

    def tearDown(self):
        self.temp_directory.cleanup()

    def counts(self) -> tuple[int, int]:
        connection = connect(self.database)
        try:
            return (
                connection.execute("SELECT COUNT(*) FROM anchor_instances").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM anchor_segments").fetchone()[0],
            )
        finally:
            connection.close()

    def test_migration_two_applies_idempotently_and_preserves_slice_one_data(self):
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
            connection.executescript(MIGRATIONS[0][2])
            connection.execute(
                "INSERT INTO schema_migrations VALUES (1, 'documents_and_versions', 'old')"
            )
            connection.execute(
                "INSERT INTO documents VALUES ('doc-old', 'Existing document', 'old')"
            )
            digest = "a" * 64
            connection.execute(
                """
                INSERT INTO document_versions(
                    version_id, document_id, original_filename, sha256,
                    blob_path, file_size, imported_at
                ) VALUES ('version-old', 'doc-old', 'old.pdf', ?, ?, 12, 'old')
                """,
                (digest, f"blobs/{digest}.pdf"),
            )
            connection.commit()
        finally:
            connection.close()

        init_database(legacy)
        init_database(legacy)
        connection = connect(legacy)
        try:
            self.assertEqual(
                connection.execute("SELECT title FROM documents").fetchone()[0],
                "Existing document",
            )
            self.assertEqual(
                connection.execute("SELECT original_filename FROM document_versions").fetchone()[0],
                "old.pdf",
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0],
                len(MIGRATIONS),
            )
            self.assertIsNotNone(
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='anchor_instances'"
                ).fetchone()
            )
        finally:
            connection.close()

    def test_anchor_and_segment_foreign_keys_are_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute(
                    """
                    INSERT INTO anchor_instances VALUES (
                        'bad-anchor', 'missing-version', 'text', 'text',
                        ?, 1, 'now'
                    )
                    """,
                    (TEXT_SELECTOR_VERSION,),
                )
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute(
                    """
                    INSERT INTO anchor_segments(
                        segment_id, anchor_id, segment_index, page_number,
                        rectangles_json, pdf_view_box_json,
                        capture_viewport_width, capture_viewport_height, capture_rotation
                    ) VALUES ('bad-segment', 'missing-anchor', 0, 1,
                              '[[1,1,2,2]]', '[0,0,10,10]', 10, 10, 0)
                    """
                )

    def test_valid_one_page_text_anchor_persists_selector_bundle(self):
        anchor = create_anchor(self.database, self.draft3, anchor_payload())
        self.assertEqual(anchor["document_version_id"], self.draft3)
        self.assertEqual(anchor["selection_text"], "selected text")
        self.assertEqual(anchor["selector_version"], TEXT_SELECTOR_VERSION)
        self.assertEqual(len(anchor["segments"]), 1)
        segment = anchor["segments"][0]
        self.assertEqual(segment["exact_text"], "selected text")
        self.assertEqual(
            segment["page_text_sha256"],
            hashlib.sha256("Before selected text after".encode()).hexdigest(),
        )
        self.assertEqual(segment["validation"]["selector"], "verified")

    def test_valid_multi_segment_anchor_persists_in_segment_order(self):
        segments = [
            segment_payload(0, 4, "Start first page selection", "page selection"),
            segment_payload(1, 5, "continued on second page End", "continued on second page"),
        ]
        payload = anchor_payload(segments)
        payload["selection_text"] = "page selectioncontinued on second page"
        anchor = create_anchor(self.database, self.draft3, payload)
        self.assertEqual([item["segment_index"] for item in anchor["segments"]], [0, 1])
        self.assertEqual([item["page_number"] for item in anchor["segments"]], [4, 5])

    def test_segment_failure_rolls_back_anchor_and_prior_segments(self):
        payload = anchor_payload(
            [
                segment_payload(0, 1),
                segment_payload(1, 2, "Before other text after", "other text"),
            ]
        )
        original_insert = anchors_module._insert_segment

        def fail_on_second(connection, anchor_id, segment):
            if segment.segment_index == 1:
                raise sqlite3.IntegrityError("simulated segment failure")
            return original_insert(connection, anchor_id, segment)

        with mock.patch("review.anchors._insert_segment", side_effect=fail_on_second):
            with self.assertRaises(sqlite3.IntegrityError):
                create_anchor(self.database, self.draft3, payload)
        self.assertEqual(self.counts(), (0, 0))

    def test_anchors_are_isolated_to_the_exact_document_version(self):
        created = create_anchor(self.database, self.draft3, anchor_payload())
        self.assertEqual([item["anchor_id"] for item in list_anchors(self.database, self.draft3)], [created["anchor_id"]])
        self.assertEqual(list_anchors(self.database, self.draft4), [])

    def test_retrieval_order_is_stable_and_segments_are_ordered(self):
        first = create_anchor(self.database, self.draft3, anchor_payload())
        second = create_anchor(
            self.database,
            self.draft3,
            anchor_payload(
                [
                    segment_payload(0, 2),
                    segment_payload(1, 3, "Before other text after", "other text"),
                ]
            ),
        )
        one = list_anchors(self.database, self.draft3)
        two = list_anchors(self.database, self.draft3)
        self.assertEqual([item["anchor_id"] for item in one], [item["anchor_id"] for item in two])
        self.assertEqual({item["anchor_id"] for item in one}, {first["anchor_id"], second["anchor_id"]})
        for anchor in one:
            self.assertEqual(
                [segment["segment_index"] for segment in anchor["segments"]],
                list(range(len(anchor["segments"]))),
            )

    def test_deletion_cascades_only_to_target_segments(self):
        first = create_anchor(self.database, self.draft3, anchor_payload())
        second = create_anchor(self.database, self.draft3, anchor_payload())
        delete_anchor(self.database, first["anchor_id"])
        remaining = list_anchors(self.database, self.draft3)
        self.assertEqual([item["anchor_id"] for item in remaining], [second["anchor_id"]])
        connection = connect(self.database)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0], 2
            )
        finally:
            connection.close()

    def test_anchor_and_segment_updates_are_blocked_by_immutability_triggers(self):
        anchor = create_anchor(self.database, self.draft3, anchor_payload())
        segment_id = anchor["segments"][0]["segment_id"]
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute(
                    "UPDATE anchor_instances SET selection_text = 'changed' WHERE anchor_id = ?",
                    (anchor["anchor_id"],),
                )
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute(
                    "UPDATE anchor_segments SET page_number = 2 WHERE segment_id = ?",
                    (segment_id,),
                )

    def test_missing_version_is_rejected(self):
        with self.assertRaises(AnchorVersionNotFoundError):
            create_anchor(self.database, "missing", anchor_payload())

    def test_invalid_anchor_bundles_are_rejected_without_database_rows(self):
        cases = {}
        payload = anchor_payload()
        payload["selection_text"] = "   "
        cases["empty selection"] = payload
        payload = anchor_payload()
        payload["segments"] = []
        cases["no segments"] = payload
        payload = anchor_payload()
        payload["segments"][0]["page_number"] = 0
        cases["invalid page"] = payload
        payload = anchor_payload()
        payload["segments"][0]["segment_index"] = -1
        cases["negative order"] = payload
        payload = anchor_payload([segment_payload(0, 1), segment_payload(0, 2)])
        cases["duplicate order"] = payload
        payload = anchor_payload()
        payload["segments"][0]["rectangles"] = "not-json-geometry"
        cases["malformed geometry"] = payload
        payload = anchor_payload()
        payload["segments"][0]["rectangles"] = []
        cases["no rectangles"] = payload
        payload = anchor_payload()
        payload["segments"][0]["rectangles"] = [[10, 10, float("nan"), 20]]
        cases["non-finite coordinate"] = payload
        payload = anchor_payload()
        payload["segments"][0]["rectangles"] = [[20, 10, 10, 20]]
        cases["inverted rectangle"] = payload
        payload = anchor_payload()
        payload["segments"][0]["text_start"] = -1
        cases["invalid offset"] = payload
        payload = anchor_payload()
        payload["segments"][0]["exact_text"] = "wrong slice"
        cases["selector mismatch"] = payload
        payload = anchor_payload()
        payload["document_version_id"] = self.draft4
        cases["crafted version injection"] = payload
        payload = anchor_payload()
        payload["segments"][0]["page_text"] = "x" * 1_000_001
        cases["unreasonable page text"] = payload

        for label, invalid in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(AnchorValidationError):
                    create_anchor(self.database, self.draft3, copy.deepcopy(invalid))
        self.assertEqual(self.counts(), (0, 0))

    def test_json_api_status_codes_payload_limit_and_lifecycle(self):
        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.database),
                "STORAGE_ROOT": str(self.storage_root),
                "SECRET_KEY": "test",
            }
        )
        client = secure_client(app)
        self.assertEqual(client.get("/api/versions/missing/anchors").status_code, 404)
        invalid = client.post(
            f"/api/versions/{self.draft3}/anchors", json={"anchor_kind": "text"}
        )
        self.assertEqual(invalid.status_code, 422)

        created = client.post(
            f"/api/versions/{self.draft3}/anchors", json=anchor_payload()
        )
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        anchor_id = created.get_json()["anchor"]["anchor_id"]
        retrieved = client.get(f"/api/versions/{self.draft3}/anchors")
        self.assertEqual(retrieved.status_code, 200)
        self.assertEqual(retrieved.get_json()["anchors"][0]["anchor_id"], anchor_id)
        self.assertEqual(
            client.get(f"/api/versions/{self.draft4}/anchors").get_json()["anchors"], []
        )
        deleted = client.delete(f"/api/anchors/{anchor_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(client.delete(f"/api/anchors/{anchor_id}").status_code, 404)

        oversized = b'{"value":"' + (b"x" * MAX_ANCHOR_PAYLOAD_BYTES) + b'"}'
        too_large = client.post(
            f"/api/versions/{self.draft3}/anchors",
            data=oversized,
            content_type="application/json",
        )
        self.assertEqual(too_large.status_code, 413)


if __name__ == "__main__":
    unittest.main()
