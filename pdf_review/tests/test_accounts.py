"""C1 security boundaries using disposable identities, PDFs and databases only."""

import io
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from review import create_app, access
from review.auth import resolve_google_identity
from review.database import MIGRATIONS, connect, init_database, transaction
from review.documents import create_document, import_version
from review.threads import create_thread, get_thread
from review.users import create_user
from tests.auth_helpers import authenticate
from tests.test_threads import anchor_payload, pdf_bytes


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'test.sqlite3'
        self.app = create_app({'TESTING': True, 'DATABASE': str(self.db), 'DATA_DIR': str(self.root),
                               'SECRET_KEY': 'synthetic-account-tests'})
        self.owner, self.reader, self.admin = [create_user(self.db, name)['user_id'] for name in ('Owner', 'Reader', 'Admin')]
        self.clients = {}
        for uid in (self.owner, self.reader, self.admin):
            client = self.app.test_client()
            authenticate(client, uid, grant_documents=False)
            self.clients[uid] = client
        self.doc = create_document(self.db, 'Owned fixture', owner_id=self.owner)
        self.shared = create_document(self.db, 'Shared fixture', owner_id=self.reader)
        self.hidden = create_document(self.db, 'Hidden fixture', owner_id=self.reader)
        access.set_document_access(self.db, self.shared, self.owner, 'viewer')
        access.set_site_admin(self.db, self.admin, True)
        self.version = import_version(self.db, self.app.extensions['blob_store'], self.doc,
                                      io.BytesIO(pdf_bytes(b'accounts')), 'fixture.pdf').version_id

    def sql(self, sql, args=()):
        with transaction(self.db) as c:
            return [dict(r) for r in c.execute(sql, args)]

    def post(self, uid, url, data, *, token='fixture-csrf-token'):
        return self.clients[uid].post(url, data=data, headers={'X-CSRF-Token': token})

    def grants_url(self, doc=None):
        return f'/documents/{doc or self.doc}/access'

    def grant(self, uid, role='reviewer', target=None, doc=None):
        return self.post(uid, self.grants_url(doc), {'action': 'grant', 'user_id': target or self.reader, 'role': role})

    def test_account_authentication_navigation_and_private_headers(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get('/account').status_code, 302)
        self.assertEqual(anonymous.post('/account/profile').status_code, 401)
        for uid in (self.owner, self.reader, self.admin):
            response = self.clients[uid].get('/account')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Account status', response.data)
            self.assertIn(b'no-store', response.headers['Cache-Control'].encode())
            self.assertIn('private', response.headers['Cache-Control'])
            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(b'href="/admin"' in response.data, uid == self.admin)
            self.assertNotIn(b'test-sub-', response.data)

    def test_profile_preserves_identity_authorship_acl_and_admin_membership(self):
        thread = create_thread(self.db, self.version, self.owner, anchor_payload(), 'Synthetic historic body')
        before = self.sql('SELECT * FROM users WHERE user_id = ?', (self.owner,))[0]
        grants = self.sql('SELECT * FROM document_access')
        admins = self.sql('SELECT * FROM site_admins')
        revisions = self.sql('SELECT * FROM comment_revisions')
        response = self.post(self.owner, '/account/profile', {'display_name': '  Reader  '})
        self.assertEqual(response.status_code, 303)  # duplicate presentation names allowed
        after = self.sql('SELECT * FROM users WHERE user_id = ?', (self.owner,))[0]
        self.assertEqual(after.pop('display_name'), 'Reader')
        before.pop('display_name')
        self.assertEqual(after, before)
        self.assertEqual(self.sql('SELECT * FROM document_access'), grants)
        self.assertEqual(self.sql('SELECT * FROM site_admins'), admins)
        self.assertEqual(self.sql('SELECT * FROM comment_revisions'), revisions)
        current = get_thread(self.db, thread['thread_id'])
        self.assertEqual(current['comments'][0]['author']['display_name'], 'Reader')
        self.assertEqual(current['comments'][0]['author']['user_id'], self.owner)
        with self.app.app_context():
            uid = resolve_google_identity({'sub': before['google_subject'], 'email': before['email'],
                                            'email_verified': True, 'name': 'Google reset attempt'})
        self.assertEqual(uid, self.owner)
        self.assertEqual(self.sql('SELECT display_name FROM users WHERE user_id = ?', (uid,))[0]['display_name'], 'Reader')

    def test_invalid_profile_and_forged_identity_fields(self):
        for name in ('', '   ', 'x' * 101, 'a\nb', 'a\x00b', 'a\u202eb', '\tName'):
            self.assertEqual(self.post(self.owner, '/account/profile', {'display_name': name}).status_code, 422)
        for key in ('user_id', 'email', 'google_subject', 'is_site_admin', 'is_active'):
            self.assertEqual(self.post(self.owner, '/account/profile', {'display_name': 'Spoof', key: self.reader}).status_code, 400)
        self.assertEqual(self.post(self.owner, f'/account/{self.reader}/profile', {'display_name': 'Spoof'}).status_code, 404)
        self.assertEqual(self.sql('SELECT display_name FROM users WHERE user_id = ?', (self.reader,))[0]['display_name'], 'Reader')
        self.assertEqual(self.post(self.owner, '/account/profile', {'display_name': '<script>alert(1)</script>'}).status_code, 303)
        self.assertNotIn(b'<script>alert(1)</script>', self.clients[self.owner].get('/account').data)

    def test_owned_and_shared_lists_exclude_inaccessible_documents(self):
        data = self.clients[self.owner].get('/account').get_data(as_text=True)
        self.assertIn('Owned by me', data)
        self.assertIn('Shared with me', data)
        self.assertIn('Owned fixture', data)
        self.assertIn('Shared fixture', data)
        self.assertIn('Viewer', data)
        self.assertNotIn('Hidden fixture', data)
        access.set_document_access(self.db, self.shared, self.owner, 'reviewer')
        self.assertIn(b'Reviewer', self.clients[self.owner].get('/account').data)

    def test_owner_read_policy_and_directory_restrictions(self):
        for role in ('viewer', 'reviewer'):
            access.set_document_access(self.db, self.doc, self.reader, role)
            for url in (self.grants_url(), f'/api/documents/{self.doc}/shareable-users'):
                self.assertEqual(self.clients[self.reader].get(url).status_code, 403)
            self.assertEqual(self.grant(self.reader).status_code, 403)
        self.assertEqual(self.clients[self.admin].get(self.grants_url()).status_code, 404)
        self.assertEqual(self.app.test_client().get(f'/api/documents/{self.doc}/shareable-users').status_code, 401)
        self.assertEqual(self.clients[self.owner].get(self.grants_url()).status_code, 200)

    def test_owner_grants_all_roles_changes_and_revokes(self):
        for role in ('viewer', 'reviewer', 'owner', 'reviewer'):
            self.assertEqual(self.grant(self.owner, role).status_code, 303)
            self.assertEqual(self.sql('SELECT role FROM document_access WHERE document_id = ? AND user_id = ?', (self.doc, self.reader))[0]['role'], role)
            with self.clients[self.reader].get(f'/versions/{self.version}/pdf') as response:
                self.assertEqual(response.status_code, 200)
            self.assertEqual(self.clients[self.reader].get(self.grants_url()).status_code, 200 if role == 'owner' else 403)
        self.assertEqual(self.post(self.owner, self.grants_url(), {'action': 'revoke', 'user_id': self.reader}).status_code, 303)
        self.assertEqual(self.clients[self.reader].get(f'/versions/{self.version}/pdf').status_code, 404)

    def test_final_owner_demotion_revocation_self_removal_and_cli_protected(self):
        for role in ('viewer', 'reviewer'):
            self.assertEqual(self.grant(self.owner, role, self.owner).status_code, 422)
        self.assertEqual(self.post(self.owner, self.grants_url(), {'action': 'revoke', 'user_id': self.owner}).status_code, 422)
        runner = self.app.test_cli_runner()
        self.assertNotEqual(runner.invoke(args=['revoke-access', self.doc, self.owner]).exit_code, 0)
        self.assertNotEqual(runner.invoke(args=['grant-access', self.doc, self.owner, '--role', 'viewer']).exit_code, 0)
        self.assertEqual(self.grant(self.owner, 'owner').status_code, 303)
        self.assertEqual(self.post(self.owner, self.grants_url(), {'action': 'revoke', 'user_id': self.owner}).status_code, 303)
        self.assertEqual(self.clients[self.owner].get(self.grants_url()).status_code, 404)
        self.assertEqual(self.clients[self.reader].get(self.grants_url()).status_code, 200)

    def test_shareable_directory_only_active_joined_identities_and_minimal_fields(self):
        legacy = create_user(self.db, 'Unlinked')['user_id']
        access.set_allowed_email(self.db, 'notjoined@example.test', 'allow')
        self.sql('UPDATE allowed_emails SET enabled = 0 WHERE normalized_email = ?', (f'{self.reader}@example.test',))
        data = self.clients[self.owner].get(f'/api/documents/{self.doc}/shareable-users').json['users']
        self.assertEqual({u['user_id'] for u in data}, {self.owner, self.admin})
        for user in data:
            self.assertEqual(set(user), {'user_id', 'display_name', 'email'})
        for target in (legacy, self.reader, 'notjoined@example.test', 'unknown@example.test'):
            self.assertEqual(self.grant(self.owner, target=target).status_code, 422)
        self.assertNotIn('unknown@example.test', {r['normalized_email'] for r in self.sql('SELECT * FROM allowed_emails')})
        self.assertEqual(len(self.sql('SELECT * FROM users')), 4)
        self.sql('UPDATE users SET is_active = 0 WHERE user_id = ?', (self.admin,))
        self.assertEqual({u['user_id'] for u in access.shareable_users(self.db)}, {self.owner})

    def test_owner_cannot_invite_or_promote_site_admin(self):
        for url, data in [('/admin/beta-access', {'action': 'allow', 'email': 'unknown@example.test'}),
                          ('/admin/site-admins', {'action': 'grant', 'user_id': self.owner})]:
            self.assertEqual(self.post(self.owner, url, data).status_code, 403)
        self.assertEqual(self.clients[self.owner].get('/admin').status_code, 403)
        self.assertEqual(self.clients[self.reader].get('/admin').status_code, 403)
        self.assertEqual(self.clients[self.admin].get('/admin').status_code, 200)

    def test_site_admin_does_not_bypass_document_pdf_range_acl(self):
        client = self.clients[self.admin]
        for url in (f'/documents/{self.doc}', f'/versions/{self.version}/view', f'/versions/{self.version}/pdf', self.grants_url()):
            for method in ('GET', 'HEAD'):
                with patch('review.storage.BlobStore.resolve', side_effect=AssertionError('unauthorized blob lookup')):
                    self.assertEqual(client.open(url, method=method, headers={'Range': 'bytes=0-3'}).status_code, 404)

    def test_admin_allow_login_share_disable_reenable_and_remove(self):
        email = 'newbeta@example.test'
        self.assertEqual(self.post(self.admin, '/admin/beta-access', {'action': 'allow', 'email': email, 'note': 'Synthetic invite'}).status_code, 303)
        self.assertFalse(any(u['email'] == email for u in access.shareable_users(self.db)))
        with self.app.app_context():
            uid = resolve_google_identity({'sub': 'synthetic-new-sub', 'email': email, 'email_verified': True, 'name': 'New beta'})
        self.assertTrue(any(u['user_id'] == uid for u in access.shareable_users(self.db)))
        self.assertEqual(self.grant(self.owner, target=uid).status_code, 303)
        for action in ('disable', 'allow'):
            self.assertEqual(self.post(self.admin, '/admin/beta-access', {'action': action, 'email': email}).status_code, 303)
        response = self.post(self.admin, '/admin/beta-access', {'action': 'remove', 'email': email})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.post(self.admin, '/admin/beta-access', {'action': 'remove', 'email': email, 'confirm_established': 'yes'}).status_code, 303)
        self.assertEqual(len(self.sql('SELECT * FROM users WHERE user_id = ?', (uid,))), 1)
        self.assertEqual(len(self.sql('SELECT * FROM document_access WHERE user_id = ?', (uid,))), 1)
        self.assertEqual(self.sql('SELECT * FROM allowed_emails WHERE normalized_email = ?', (email,)), [])
        access.set_allowed_email(self.db, 'typo@example.test', 'allow')
        access.set_allowed_email(self.db, 'typo@example.test', 'disable')
        self.assertEqual(self.post(self.admin, '/admin/beta-access', {'action': 'remove', 'email': 'typo@example.test'}).status_code, 303)

    def test_admin_grant_revoke_final_admin_and_disabled_successor_protection(self):
        for action in ('revoke',):
            self.assertEqual(self.post(self.admin, '/admin/site-admins', {'action': action, 'user_id': self.admin}).status_code, 422)
        for action in ('disable', 'remove'):
            self.assertEqual(self.post(self.admin, '/admin/beta-access', {'action': action, 'email': f'{self.admin}@example.test', 'confirm_established': 'yes'}).status_code, 422)
        self.assertEqual(self.post(self.admin, '/admin/site-admins', {'action': 'grant', 'user_id': self.reader}).status_code, 303)
        self.assertEqual(self.post(self.admin, '/admin/site-admins', {'action': 'revoke', 'user_id': self.reader}).status_code, 303)
        self.assertEqual(self.clients[self.reader].get('/admin').status_code, 403)
        access.set_site_admin(self.db, self.reader, True)
        access.set_allowed_email(self.db, f'{self.reader}@example.test', 'disable')
        self.assertEqual(self.post(self.admin, '/admin/site-admins', {'action': 'revoke', 'user_id': self.admin}).status_code, 422)

    def test_allowlist_disable_and_removal_preserve_authorship_history_and_grants(self):
        create_thread(self.db, self.version, self.owner, anchor_payload(), 'Synthetic retained history')
        tables = ('users', 'threads', 'comments', 'comment_revisions', 'document_access')
        before = {table: self.sql(f'SELECT * FROM {table} ORDER BY 1') for table in tables}
        email = f'{self.owner}@example.test'
        for action in ('disable', 'allow', 'remove'):
            self.assertEqual(self.post(self.admin, '/admin/beta-access', {'action': action, 'email': email, 'confirm_established': 'yes'}).status_code, 303)
        for table in tables:
            self.assertEqual(self.sql(f'SELECT * FROM {table} ORDER BY 1'), before[table])
        self.assertEqual(self.clients[self.owner].get('/account').status_code, 302)
        self.assertEqual(self.clients[self.owner].post('/account/profile', data={'display_name': 'Blocked'}).status_code, 401)
        actions = [row['action'] for row in self.sql('SELECT action FROM access_audit_log WHERE target_identifier = ?', (email,))]
        self.assertEqual(actions, ['beta_email.disable', 'beta_email.reenable', 'beta_email.remove'])

    def test_cli_admin_bootstrap_remove_confirmation_and_recovery(self):
        runner = self.app.test_cli_runner()
        for args in (['list-site-admins'], ['grant-site-admin', self.reader], ['revoke-site-admin', self.reader], ['allow-email', 'typo@example.test'], ['remove-email', 'typo@example.test']):
            result = runner.invoke(args=args)
            self.assertEqual(result.exit_code, 0, result.output)
        for args in (['revoke-site-admin', self.admin], ['grant-site-admin', 'unknown-id'], ['remove-email', f'{self.reader}@example.test']):
            self.assertNotEqual(runner.invoke(args=args).exit_code, 0)
        self.assertEqual(runner.invoke(args=['remove-email', f'{self.reader}@example.test', '--confirm-established']).exit_code, 0)

    def test_every_mutation_requires_valid_csrf_and_no_get_writes(self):
        operations = [(self.owner, '/account/profile', {'display_name': 'Change'}),
            (self.owner, self.grants_url(), {'action': 'grant', 'user_id': self.reader, 'role': 'viewer'}),
            (self.owner, self.grants_url(), {'action': 'revoke', 'user_id': self.reader}),
            (self.admin, '/admin/site-admins', {'action': 'grant', 'user_id': self.reader}),
            (self.admin, '/admin/site-admins', {'action': 'revoke', 'user_id': self.admin})]
        operations += [(self.admin, '/admin/beta-access', {'email': 'synthetic@example.test', 'action': action}) for action in ('allow', 'disable', 'remove')]
        before = self.sql('SELECT * FROM access_audit_log')
        for uid, url, data in operations:
            for token in ('', 'wrong', '\u00e9'):
                self.assertEqual(self.post(uid, url, data, token=token).status_code, 400)
            self.assertIn(self.clients[uid].get(url).status_code, (200, 405))
        self.assertEqual(self.sql('SELECT * FROM access_audit_log'), before)

    def test_current_state_revocation_not_session_or_submitted_roles(self):
        self.sql('DELETE FROM site_admins WHERE user_id = ?', (self.admin,))
        with self.clients[self.admin].session_transaction() as state:
            state['is_site_admin'] = True
        self.assertEqual(self.clients[self.admin].get('/admin').status_code, 403)
        access.set_document_access(self.db, self.doc, self.reader, 'owner')
        access.set_document_access(self.db, self.doc, self.owner, 'viewer')
        self.assertEqual(self.grant(self.owner).status_code, 403)
        self.sql('UPDATE allowed_emails SET enabled = 0 WHERE normalized_email = ?', (f'{self.reader}@example.test',))
        self.assertEqual(self.clients[self.reader].get('/account').status_code, 302)
        with self.assertRaises(access.AccessDenied):
            access.set_document_access(self.db, self.doc, self.admin, 'viewer', actor=self.owner)

    def test_http_handles_authority_change_between_policy_and_transaction(self):
        with patch('review.access.authorize_actor', side_effect=access.AccessDenied('changed')):
            self.assertEqual(self.grant(self.owner).status_code, 403)
            self.assertEqual(self.post(self.admin, '/admin/site-admins', {'action': 'grant', 'user_id': self.reader}).status_code, 403)
            self.assertEqual(self.post(self.admin, '/admin/beta-access', {'action': 'allow', 'email': 'no@example.test'}).status_code, 403)

    def test_audit_atomic_append_only_sanitized_and_failed_operations_absent(self):
        before = len(self.sql('SELECT * FROM access_audit_log'))
        self.assertEqual(self.grant(self.owner, 'owner', self.owner).status_code, 303)  # no-op
        self.assertEqual(self.grant(self.owner, 'invalid').status_code, 422)
        self.assertEqual(len(self.sql('SELECT * FROM access_audit_log')), before)
        for operation in (
            lambda: access.set_document_access(self.db, self.doc, self.reader, 'reviewer', actor=self.owner),
            lambda: access.set_allowed_email(self.db, 'rollback@example.test', 'allow', actor=self.admin),
            lambda: access.set_site_admin(self.db, self.reader, True, actor=self.admin)):
            with patch('review.access.audit', side_effect=RuntimeError('audit unavailable')):
                with self.assertRaises(RuntimeError):
                    operation()
        self.assertEqual(self.sql('SELECT * FROM document_access WHERE document_id = ? AND user_id = ?', (self.doc, self.reader)), [])
        self.assertEqual(self.sql("SELECT * FROM allowed_emails WHERE normalized_email = 'rollback@example.test'"), [])
        self.assertFalse(access.is_site_admin(self.db, self.reader))
        self.grant(self.owner)
        entry = self.sql('SELECT * FROM access_audit_log ORDER BY id DESC LIMIT 1')[0]
        self.assertEqual(entry['actor_user_id'], self.owner)
        self.assertEqual(entry['action'], 'document.grant')
        self.assertEqual(set(json.loads(entry['details'])), {'user_id', 'previous_role', 'role'})
        secret_markers = ('private-note-sentinel', 'token-sentinel', 'cookie-sentinel')
        access.set_allowed_email(self.db, 'audit@example.test', 'allow', note=secret_markers[0], actor=self.admin)
        audit_text = json.dumps(self.sql('SELECT * FROM access_audit_log'))
        for value in secret_markers:
            self.assertNotIn(value, audit_text)
        for statement in ('UPDATE access_audit_log SET action = \'spoof\'', 'DELETE FROM access_audit_log'):
            with self.assertRaises(sqlite3.IntegrityError):
                self.sql(statement)

    def test_concurrent_owner_and_admin_removals_retain_one(self):
        access.set_document_access(self.db, self.doc, self.reader, 'owner')
        access.set_site_admin(self.db, self.reader, True)
        def remove_owner(uid):
            try:
                access.set_document_access(self.db, self.doc, uid, None)
                return True
            except access.AccessError:
                return False
        def remove_admin(uid):
            try:
                access.set_site_admin(self.db, uid, False)
                return True
            except access.AccessError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(remove_owner, (self.owner, self.reader))), [False, True])
            self.assertEqual(sorted(pool.map(remove_admin, (self.admin, self.reader))), [False, True])

    def test_migration7_preserves_all_rows_and_foreign_keys_idempotently(self):
        legacy = self.root / 'legacy6.sqlite3'
        c = connect(legacy)
        c.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT UNIQUE, applied_at TEXT)')
        for version, name, sql in MIGRATIONS[:6]:
            c.executescript(sql)
            c.execute('INSERT INTO schema_migrations VALUES (?, ?, ?)', (version, name, 'before'))
        c.commit()
        c.close()
        user = create_user(legacy, 'Legacy')['user_id']
        doc = create_document(legacy, 'Legacy fixture', owner_id=user)
        c = connect(legacy)
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'schema_migrations'")]
        columns = {table: ','.join(r['name'] for r in c.execute(f'PRAGMA table_info({table})')) for table in tables}
        before = {table: [tuple(r) for r in c.execute(f'SELECT {columns[table]} FROM {table} ORDER BY 1')] for table in tables}
        c.close()
        init_database(legacy)
        init_database(legacy)
        c = connect(legacy)
        try:
            for table in tables:
                self.assertEqual([tuple(r) for r in c.execute(f'SELECT {columns[table]} FROM {table} ORDER BY 1')], before[table])
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(c.execute('SELECT count(*) FROM site_admins').fetchone()[0], 0)
            self.assertEqual(c.execute('SELECT count(*) FROM access_audit_log').fetchone()[0], 0)
        finally:
            c.close()
        create_user(legacy, 'Legacy')  # migration removed the old name uniqueness constraint


if __name__ == '__main__':
    unittest.main()
