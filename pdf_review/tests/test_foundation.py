from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from review import create_app
from tests.auth_helpers import authenticate, secure_client
from review.database import MIGRATIONS, connect, init_database, transaction
from review.documents import create_document, get_version, import_version, list_versions
from review.storage import BlobStore, InvalidPDFError, sha256_file


def pdf_bytes(marker: bytes) -> bytes:
    """Return sufficient PDF-shaped bytes for basic ingestion tests."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog>>endobj\n"
        b"% test payload: " + marker + b"\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.database = self.root / "data" / "test.sqlite3"
        self.storage_root = self.root / "data"
        init_database(self.database)
        self.blobs = BlobStore(self.storage_root)

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_sha256_calculation(self):
        path = self.root / "known.bin"
        path.write_bytes(b"abc")
        self.assertEqual(
            sha256_file(path),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )

    def test_non_pdf_input_is_rejected_without_publishing_a_blob(self):
        with self.assertRaises(InvalidPDFError):
            self.blobs.ingest(io.BytesIO(b"This is not a PDF."))
        self.assertEqual(list(self.blobs.blob_dir.glob("*.pdf")), [])

    def test_import_copies_and_never_changes_or_moves_source(self):
        document_id = create_document(self.database, "Synthetic Document")
        source = self.root / "draft.pdf"
        original = pdf_bytes(b"draft three")
        source.write_bytes(original)

        with source.open("rb") as stream:
            result = import_version(
                self.database, self.blobs, document_id, stream, source.name, "Draft 3"
            )

        self.assertTrue(source.exists())
        self.assertEqual(source.read_bytes(), original)
        stored = self.blobs.resolve(result.blob.relative_path, result.blob.sha256)
        self.assertNotEqual(source.resolve(), stored.resolve())
        self.assertEqual(stored.read_bytes(), original)

    def test_identical_pdf_imports_deduplicate_blob_but_keep_version_records(self):
        document_id = create_document(self.database, "Synthetic Document")
        content = pdf_bytes(b"same")
        first = import_version(
            self.database, self.blobs, document_id, io.BytesIO(content), "a.pdf", "A"
        )
        second = import_version(
            self.database, self.blobs, document_id, io.BytesIO(content), "b.pdf", "B"
        )

        self.assertTrue(first.blob.created)
        self.assertFalse(second.blob.created)
        self.assertEqual(first.blob.sha256, second.blob.sha256)
        self.assertNotEqual(first.version_id, second.version_id)
        self.assertEqual(len(list(self.blobs.blob_dir.glob("*.pdf"))), 1)
        self.assertEqual(len(list_versions(self.database, document_id)), 2)

    def test_distinct_pdf_bytes_make_distinct_immutable_versions(self):
        document_id = create_document(self.database, "Synthetic Document")
        old_content = pdf_bytes(b"old")
        new_content = pdf_bytes(b"new")
        old = import_version(
            self.database, self.blobs, document_id, io.BytesIO(old_content), "book.pdf", "Draft 3"
        )
        new = import_version(
            self.database, self.blobs, document_id, io.BytesIO(new_content), "book.pdf", "Draft 4"
        )

        self.assertNotEqual(old.blob.sha256, new.blob.sha256)
        self.assertEqual(
            self.blobs.resolve(old.blob.relative_path, old.blob.sha256).read_bytes(),
            old_content,
        )
        self.assertEqual(
            self.blobs.resolve(new.blob.relative_path, new.blob.sha256).read_bytes(),
            new_content,
        )
        self.assertEqual(len(list(self.blobs.blob_dir.glob("*.pdf"))), 2)

    def test_document_version_foreign_key_is_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute(
                    """
                    INSERT INTO document_versions(
                        version_id, document_id, original_filename, sha256,
                        blob_path, file_size, imported_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "version",
                        "missing-document",
                        "test.pdf",
                        "0" * 64,
                        f"blobs/{'0' * 64}.pdf",
                        10,
                        "2026-01-01T00:00:00.000Z",
                    ),
                )

    def test_historical_version_record_and_blob_are_not_replaced(self):
        document_id = create_document(self.database, "Synthetic Document")
        source = self.root / "mutable-source.pdf"
        source.write_bytes(pdf_bytes(b"first"))
        with source.open("rb") as stream:
            first = import_version(
                self.database, self.blobs, document_id, stream, source.name, "First"
            )
        first_bytes = self.blobs.resolve(first.blob.relative_path, first.blob.sha256).read_bytes()

        source.write_bytes(pdf_bytes(b"second"))
        with source.open("rb") as stream:
            second = import_version(
                self.database, self.blobs, document_id, stream, source.name, "Second"
            )

        self.assertEqual(
            self.blobs.resolve(first.blob.relative_path, first.blob.sha256).read_bytes(),
            first_bytes,
        )
        self.assertNotEqual(first.blob.sha256, second.blob.sha256)
        self.assertEqual(get_version(self.database, first.version_id)["version_label"], "First")

        with self.assertRaises(sqlite3.IntegrityError):
            with transaction(self.database) as connection:
                connection.execute(
                    "UPDATE document_versions SET sha256 = ? WHERE version_id = ?",
                    ("0" * 64, first.version_id),
                )

    def test_migration_initialization_is_idempotent(self):
        init_database(self.database)
        init_database(self.database)
        connection = connect(self.database)
        try:
            migration_count = connection.execute(
                "SELECT COUNT(*) FROM schema_migrations"
            ).fetchone()[0]
            document_table_count = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='documents'"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(migration_count, len(MIGRATIONS))
        self.assertEqual(document_table_count, 1)

    def test_failed_database_write_removes_new_unreferenced_blob(self):
        document_id = create_document(self.database, "Synthetic Document")
        import_version(
            self.database,
            self.blobs,
            document_id,
            io.BytesIO(pdf_bytes(b"registered build")),
            "build.pdf",
            external_source_type="tracker",
            external_version_id="build-1",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            import_version(
                self.database,
                self.blobs,
                document_id,
                io.BytesIO(pdf_bytes(b"different bytes")),
                "other.pdf",
                external_source_type="tracker",
                external_version_id="build-1",
            )
        self.assertEqual(len(list_versions(self.database, document_id)), 1)
        self.assertEqual(len(list(self.blobs.blob_dir.glob("*.pdf"))), 1)

    def test_integrity_verification_success_missing_and_mismatch(self):
        document_id = create_document(self.database, "Synthetic Document")
        result = import_version(
            self.database,
            self.blobs,
            document_id,
            io.BytesIO(pdf_bytes(b"verify")),
            "verify.pdf",
        )
        good = self.blobs.verify(
            result.blob.relative_path, result.blob.sha256, result.blob.file_size
        )
        self.assertTrue(good.ok)

        path = self.blobs.resolve(result.blob.relative_path, result.blob.sha256)
        path.write_bytes(pdf_bytes(b"tampered"))
        mismatch = self.blobs.verify(
            result.blob.relative_path, result.blob.sha256, result.blob.file_size
        )
        self.assertFalse(mismatch.ok)
        self.assertNotEqual(mismatch.actual_sha256, mismatch.expected_sha256)

        path.unlink()
        missing = self.blobs.verify(
            result.blob.relative_path, result.blob.sha256, result.blob.file_size
        )
        self.assertFalse(missing.ok)
        self.assertIsNone(missing.actual_sha256)

    def test_flask_upload_viewer_and_safe_pdf_endpoint(self):
        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.database),
                "STORAGE_ROOT": str(self.storage_root),
                "SECRET_KEY": "test",
            }
        )
        client = secure_client(app)
        document_id = create_document(self.database, "Web document")
        authenticate(client)
        content = pdf_bytes(b"web route")

        response = client.post(
            f"/documents/{document_id}/versions",
            data={
                "version_label": "Web draft",
                "pdf": (io.BytesIO(content), "web.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 303)
        version = list_versions(self.database, document_id)[0]

        pdf_response = client.get(f"/versions/{version['version_id']}/pdf")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.data, content)
        self.assertEqual(pdf_response.mimetype, "application/pdf")
        pdf_response.close()

        viewer_response = client.get(f"/versions/{version['version_id']}/view")
        self.assertEqual(viewer_response.status_code, 200)
        self.assertIn(b"vendor/pdfjs/web/viewer.html?file=", viewer_response.data)
        self.assertIn(
            f"%2Fversions%2F{version['version_id']}%2Fpdf".encode(), viewer_response.data
        )
        viewer_response.close()
        self.assertEqual(client.get("/versions/not-a-version/pdf").status_code, 404)

        cli_result = app.test_cli_runner().invoke(args=["verify-storage"])
        self.assertEqual(cli_result.exit_code, 0, cli_result.output)
        self.assertIn("Checked 1 version(s); 0 failure(s).", cli_result.output)


if __name__ == "__main__":
    unittest.main()
