"""Main-version persistence, authorization, withdrawal fallback and owner visibility."""

import io
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from review import create_app, documents, access
from review.database import MIGRATIONS, connect, transaction, init_database
from review.storage import BlobStore
from tests.auth_helpers import authenticate, secure_client
import tests.test_threads as fixtures


class DocumentControlsTests(unittest.TestCase):
    def setUp(self):
        fixtures.ThreadTests.setUp(self)
        self.app = create_app({'TESTING': True, 'DATABASE': str(self.database), 'STORAGE_ROOT': str(self.storage_root), 'SECRET_KEY': 'synthetic-document-controls'})
        self.http = secure_client(self.app, self.alpha['user_id'])
        self.reader = secure_client(self.app, self.beta['user_id'])
        access.set_document_access(self.database, self.document_id, self.beta['user_id'], 'reviewer')
        self.owner = self.alpha['user_id']

    def tearDown(self):
        fixtures.ThreadTests.tearDown(self)

    def sql(self, query, args=()):
        with transaction(self.database) as c:
            return [dict(r) for r in c.execute(query, args)]

    def test_switch_main_is_persistent_idempotent_and_keeps_original_versions(self):
        before = self.sql('SELECT * FROM document_versions ORDER BY version_id')
        current = documents.get_main_version(self.database, self.document_id)
        target = self.draft3 if current != self.draft3 else self.draft4
        self.assertEqual(self.http.post('/versions/' + target + '/main').status_code, 303)
        self.assertEqual(documents.get_main_version(self.database, self.document_id), target)
        documents.set_main_version(self.database, target, self.owner)
        self.assertEqual(len(self.sql("SELECT * FROM access_audit_log WHERE action='document.main_version'")), 1)
        self.assertEqual(self.sql('SELECT * FROM document_versions ORDER BY version_id'), before)
        self.assertIn(b'aria-pressed="true"', self.http.get('/documents/' + self.document_id).data)

    def test_main_selection_requires_owner_csrf_and_active_same_document(self):
        url = '/versions/' + self.draft3 + '/main'
        self.assertEqual(self.reader.post(url).status_code, 403)
        plain = self.app.test_client()
        authenticate(plain, self.owner)
        self.assertEqual(plain.post(url).status_code, 400)
        self.assertEqual(self.app.test_client().post(url).status_code, 401)
        self.assertEqual(self.http.get(url).status_code, 405)
        self.assertEqual(self.http.post(url, data={'version_id': self.draft4}).status_code, 400)
        hidden = documents.create_document(self.database, 'Unshared sentinel', owner_id=self.beta['user_id'])
        version = documents.import_version(self.database, self.blobs, hidden, io.BytesIO(fixtures.pdf_bytes(b'hidden')), 'hidden.pdf').version_id
        self.assertEqual(self.http.post('/versions/' + version + '/main').status_code, 404)
        with self.assertRaises(access.AccessDenied):
            documents.set_main_version(self.database, version, self.owner)
        with self.assertRaises(sqlite3.IntegrityError):
            self.sql('UPDATE document_main_versions SET version_id=? WHERE document_id=?', (version, self.document_id))

    def test_first_import_is_main_later_import_preserves_choice_and_deletion_selects_fallback(self):
        doc = documents.create_document(self.database, 'New document', owner_id=self.owner)
        self.assertIsNone(documents.get_main_version(self.database, doc))
        first = documents.import_version(self.database, self.blobs, doc, io.BytesIO(fixtures.pdf_bytes(b'first')), 'first.pdf').version_id
        second = documents.import_version(self.database, self.blobs, doc, io.BytesIO(fixtures.pdf_bytes(b'second')), 'second.pdf').version_id
        self.assertEqual(documents.get_main_version(self.database, doc), first)
        documents.delete_version(self.database, first, self.owner, first)
        self.assertEqual(documents.get_main_version(self.database, doc), second)
        with self.assertRaises(documents.VersionNotFoundError):
            documents.set_main_version(self.database, first, self.owner)
        documents.delete_version(self.database, second, self.owner, second)
        self.assertIsNone(documents.get_main_version(self.database, doc))
        self.assertEqual(self.sql('PRAGMA foreign_key_check'), [])

    def test_authority_rechecked_and_audit_failure_rolls_back_main_change(self):
        previous = documents.get_main_version(self.database, self.document_id)
        target = self.draft3 if previous != self.draft3 else self.draft4
        with patch('review.access.authorize_actor', side_effect=access.AccessDenied('changed')):
            with self.assertRaises(access.AccessDenied):
                documents.set_main_version(self.database, target, self.owner)
        with patch('review.access.audit', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                documents.set_main_version(self.database, target, self.owner)
        self.assertEqual(documents.get_main_version(self.database, self.document_id), previous)

    def test_dashboard_shows_all_owners_only_for_accessible_documents(self):
        access.set_document_access(self.database, self.document_id, self.beta['user_id'], 'owner')
        documents.create_document(self.database, 'Hidden document sentinel', owner_id=self.beta['user_id'])
        page = self.http.get('/').data
        for user in (self.alpha, self.beta):
            self.assertIn(b'Owner: ' + user['display_name'].encode(), page)
        self.assertEqual(page.count(b'class="document-owner-badge"'), 2)
        self.assertNotIn(b'Hidden document sentinel', page)
        self.assertNotIn((self.beta['user_id'] + '@example.test').encode(), page)

    def test_delete_picker_and_read_only_main_badge(self):
        page = self.http.get('/documents/' + self.document_id).data.decode()
        self.assertIn('class="toolbar-menu submenu delete-version-menu"', page)
        self.assertIn('aria-label="Choose a version to delete"', page)
        self.assertIn('href="/versions/' + self.draft3 + '/delete"', page)
        self.assertNotIn('class="button quiet danger"', page)
        readonly = self.reader.get('/documents/' + self.document_id).data
        self.assertIn(b'Main version', readonly)
        self.assertNotIn(b'Make main version', readonly)
        self.assertNotIn(b'delete-version-menu', readonly)

    def test_populated_migration14_defaults_to_newest_without_changing_version_rows(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            database = Path(root) / 'old.sqlite3'
            with patch('review.database.MIGRATIONS', MIGRATIONS[:14]):
                init_database(database)
            doc = documents.create_document(database, 'Synthetic upgrade')
            blobs = BlobStore(Path(root))
            for i in range(2):
                documents.import_version(database, blobs, doc, io.BytesIO(fixtures.pdf_bytes(str(i).encode())), str(i)+'.pdf')
            before = [dict(row) for row in documents.list_versions(database, doc)]
            init_database(database)
            init_database(database)
            self.assertEqual(documents.get_main_version(database, doc), before[0]['version_id'])
            self.assertEqual([dict(row) for row in documents.list_versions(database, doc)], before)
