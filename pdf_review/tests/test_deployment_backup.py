"""Pre-migration deployment backups use live WAL data without app startup."""

from contextlib import closing
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest


path = Path(__file__).resolve().parents[2] / "ops/pdf_review/backup_review.py"
spec = importlib.util.spec_from_file_location("review_deployment_backup", path)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class DeploymentBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_snapshot_includes_committed_live_wal_without_mutating_source_schema(self):
        database = self.root / "pdf_review.sqlite3"
        with closing(sqlite3.connect(database)) as source:
            source.execute("PRAGMA journal_mode=WAL")
            source.execute("CREATE TABLE synthetic_fixture(body TEXT)")
            source.execute("INSERT INTO synthetic_fixture VALUES ('Synthetic snapshot text')")
            source.commit()
            self.assertTrue(Path(str(database) + "-wal").exists())
            result = backup.backup_before_upgrade(self.root)
            with closing(sqlite3.connect(result)) as snapshot:
                self.assertEqual(snapshot.execute("SELECT body FROM synthetic_fixture").fetchone()[0], "Synthetic snapshot text")
                self.assertEqual(snapshot.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(source.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [("synthetic_fixture",)])
            self.assertNotEqual(backup.backup_before_upgrade(self.root), result)
        self.assertFalse(list((self.root / "backups").glob("*.tmp")))

    def test_first_startup_does_not_create_source_database(self):
        self.assertIsNone(backup.backup_before_upgrade(self.root))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_bad_database_aborts_without_publishing_or_leaving_partial_snapshot(self):
        database = self.root / "pdf_review.sqlite3"
        database.write_bytes(b"Synthetic invalid database")
        with self.assertRaises(sqlite3.DatabaseError):
            backup.backup_before_upgrade(self.root)
        self.assertEqual(database.read_bytes(), b"Synthetic invalid database")
        self.assertEqual(list((self.root / "backups").iterdir()), [])
