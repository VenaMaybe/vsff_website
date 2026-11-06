"""Invitation lifecycle, identity, least privilege, and historical migration coverage."""

import io
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from review import create_app, access, invitations as invites
from review.auth import resolve_google_identity, SESSION_KEY
from review.database import MIGRATIONS, transaction, init_database
from review.documents import create_document, import_version
from review.users import create_user
from tests.auth_helpers import authenticate
from tests.test_threads import pdf_bytes


class InvitationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({'TESTING': True, 'DATA_DIR': self.temp.name, 'SECRET_KEY': 'synthetic-invitation-secret'})
        self.db = self.app.config['DATABASE']
        self.clients = {}
        for name in ('Admin', 'Trusted', 'Member', 'Other'):
            uid = create_user(self.db, name)['user_id']
            client = self.app.test_client()
            authenticate(client, uid, grant_documents=False)
            self.clients[uid] = client
            setattr(self, name.lower(), uid)
        access.set_site_admin(self.db, self.admin, True)
        invites.set_trusted(self.db, self.admin, self.trusted, True)
        self.doc = create_document(self.db, 'Private manuscript sentinel', owner_id=self.trusted)
        self.hidden = create_document(self.db, 'Other private title sentinel', owner_id=self.other)
        self.version = import_version(self.db, self.app.extensions['blob_store'], self.doc, io.BytesIO(pdf_bytes(b'invite-fixture')), 'fixture.pdf').version_id

    def sql(self, query, args=()):
        with transaction(self.db) as c:
            return [dict(r) for r in c.execute(query, args)]

    def post(self, uid, url, data, token='fixture-csrf-token'):
        return self.clients[uid].post(url, data=data, headers={'X-CSRF-Token': token})

    def create(self, email='new@example.test', document=True, actor=None, role='reviewer'):
        return invites.create_invitation(self.db, actor or self.trusted, email, self.doc if document else None, role if document else None)

    def marker(self, row):
        return invites.open_link(self.db, row['invitation_id'], invites.token_for(self.app.secret_key, row), self.app.secret_key)

    def join(self, row, email=None, subject='new-subject'):
        with self.app.app_context():
            return resolve_google_identity({'sub': subject, 'email': email or row['normalized_email'], 'email_verified': True, 'name': 'New member'}, self.marker(row))

    def test_new_invitation_atomic_join_and_exact_document_grant(self):
        row = self.create()
        self.assertFalse(self.sql('SELECT * FROM allowed_emails WHERE normalized_email=?', (row['normalized_email'],)))
        uid = self.join(row)
        self.assertEqual(self.sql('SELECT document_id,role FROM document_access WHERE user_id=?', (uid,)), [{'document_id': self.doc, 'role': 'reviewer'}])
        membership = self.sql('SELECT * FROM beta_memberships WHERE user_id=?', (uid,))[0]
        self.assertEqual(membership['invited_by'], self.trusted)
        self.assertEqual(membership['invited_at'], row['created_at'])
        self.assertTrue(membership['joined_at'])
        self.assertEqual(self.sql('SELECT status,accepted_by FROM invitations')[0], {'status': 'accepted', 'accepted_by': uid})
        actions = [r['action'] for r in self.sql('SELECT action FROM access_audit_log')]
        self.assertIn('invitation.created', actions)
        self.assertIn('invitation.accepted', actions)
        with self.assertRaises(access.AccessError):
            self.marker(row)

    def test_wrong_account_does_not_create_user_membership_or_grant(self):
        row = self.create()
        before = self.sql('SELECT * FROM users')
        with self.assertRaises(invites.WrongInvitationAccount):
            self.join(row, email='wrong@example.test')
        self.assertEqual(self.sql('SELECT * FROM users'), before)
        self.assertFalse(self.sql("SELECT * FROM allowed_emails WHERE normalized_email='wrong@example.test'"))
        self.assertEqual(self.sql('SELECT status FROM invitations')[0]['status'], 'pending')

    def test_beta_only_join_does_not_grant_any_document(self):
        row = self.create(document=False)
        uid = self.join(row)
        self.assertEqual(self.sql('SELECT * FROM document_access WHERE user_id=?', (uid,)), [])

    def test_existing_member_gets_immediate_share_without_new_identity_or_role_escalation(self):
        email = f'{self.member}@example.test'
        row = self.create(email)
        self.assertEqual(row['status'], 'accepted')
        self.assertEqual(row['accepted_by'], self.member)
        access.set_document_access(self.db, self.doc, self.member, 'owner', actor=self.trusted)
        self.create(email, role='viewer')
        self.assertEqual(self.sql('SELECT role FROM document_access WHERE document_id=? AND user_id=?', (self.doc, self.member))[0]['role'], 'owner')
        self.assertIn('invitation.immediate_share', [r['action'] for r in self.sql('SELECT action FROM access_audit_log')])
        beta = self.create(email, document=False)
        self.assertEqual(beta['status'], 'accepted')

    def test_regular_owner_can_share_existing_member_but_cannot_invite_new_member(self):
        with self.assertRaises(access.AccessDenied):
            invites.create_invitation(self.db, self.other, 'unknown@example.test', self.hidden, 'viewer')
        row = invites.create_invitation(self.db, self.other, f'{self.member}@example.test', self.hidden, 'viewer')
        self.assertEqual(row['status'], 'accepted')
        with self.assertRaises(access.AccessDenied):
            self.create(actor=self.member, document=False)
        with self.assertRaises(access.AccessError):
            self.create(role='owner')

    def test_trust_and_admin_roles_never_bypass_document_permissions(self):
        for uid in (self.trusted, self.admin):
            self.assertEqual(self.clients[uid].get('/documents/' + self.hidden).status_code, 404)
        self.assertEqual(self.clients[self.admin].get('/versions/' + self.version + '/pdf').status_code, 404)
        self.assertEqual(self.clients[self.member].get('/members').status_code, 403)
        self.assertEqual(self.clients[self.trusted].get('/admin').status_code, 403)
        self.assertEqual(self.post(self.trusted, '/admin/trusted-users', {'user_id': self.member, 'action': 'grant'}).status_code, 403)
        self.assertEqual(self.post(self.trusted, '/admin/beta-access', {'email': 'x@example.test', 'action': 'allow'}).status_code, 403)
        self.assertEqual(self.post(self.trusted, '/documents/' + self.hidden + '/invitations', {'email': 'x@example.test', 'role': 'viewer'}).status_code, 404)

    def test_directory_and_invitation_lists_do_not_disclose_document_data_or_admin_notes(self):
        access.set_allowed_email(self.db, 'new@example.test', 'allow', actor=self.admin, note='private admin note sentinel')
        self.create()
        for path in ('/members', '/invitations'):
            response = self.clients[self.trusted].get(path)
            self.assertEqual(response.status_code, 200)
            for sentinel in (b'private admin note sentinel', b'Other private title sentinel', b'Private manuscript sentinel', self.hidden.encode(), b'google_subject'):
                self.assertNotIn(sentinel, response.data)
        self.assertEqual(self.clients[self.trusted].get('/admin/history').status_code, 403)

    def test_revoking_trust_or_beta_access_retires_pending_invites(self):
        row = self.create()
        invites.set_trusted(self.db, self.admin, self.trusted, False)
        self.assertEqual(self.sql('SELECT status FROM invitations')[0]['status'], 'revoked')
        with self.assertRaises(access.AccessError):
            self.join(row)
        invites.set_trusted(self.db, self.admin, self.trusted, True)
        row2 = self.create('second@example.test')
        access.set_allowed_email(self.db, f'{self.trusted}@example.test', 'disable', actor=self.admin)
        self.assertEqual(self.sql('SELECT status FROM invitations WHERE invitation_id=?', (row2['invitation_id'],))[0]['status'], 'revoked')

    def test_owner_loss_and_unmediated_authority_changes_are_rechecked_at_acceptance(self):
        row = self.create()
        access.set_document_access(self.db, self.doc, self.other, 'owner', actor=self.trusted)
        access.set_document_access(self.db, self.doc, self.trusted, 'reviewer', actor=self.other)
        with self.assertRaises(access.AccessError):
            self.join(row)
        row = self.create(document=False)
        self.sql('DELETE FROM trusted_users WHERE user_id=?', (self.trusted,))
        with self.assertRaises(access.AccessError):
            self.join(row)

    def test_expiry_revocation_renewal_duplicates_and_tokens(self):
        row = self.create()
        self.assertEqual(self.create()['invitation_id'], row['invitation_id'])
        with self.assertRaises(access.AccessError):
            self.create(role='viewer')
        with self.assertRaises(access.AccessError):
            invites.open_link(self.db, row['invitation_id'], '0' * 64, self.app.secret_key)
        with self.assertRaises(access.AccessError):
            invites.open_link(self.db, row['invitation_id'], '\u00e9' * 64, self.app.secret_key)
        renewed = invites.renew_invitation(self.db, self.trusted, row['invitation_id'])
        with self.assertRaises(access.AccessError):
            self.marker(row)
        self.sql("UPDATE invitations SET expires_at='2000-01-01T00:00:00.000Z' WHERE invitation_id=?", (renewed['invitation_id'],))
        with self.assertRaises(access.AccessError):
            self.marker(renewed)
        result = self.app.test_cli_runner().invoke(args=['expire-invitations'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('invitation.expired', [r['action'] for r in self.sql('SELECT action FROM access_audit_log')])
        self.assertNotIn(invites.token_for(self.app.secret_key, row), json.dumps(self.sql('SELECT * FROM invitations') + self.sql('SELECT * FROM access_audit_log')))

    def test_public_landing_is_generic_and_open_requires_token_and_csrf(self):
        row = self.create()
        client = self.app.test_client()
        response = client.get('/invite/' + row['invitation_id'])
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(row['normalized_email'].encode(), response.data)
        self.assertNotIn(self.doc.encode(), response.data)
        self.assertEqual(self.sql('SELECT status FROM invitations')[0]['status'], 'pending')
        path = '/invite/' + row['invitation_id'] + '/open'
        token = invites.token_for(self.app.secret_key, row)
        self.assertEqual(client.post(path, data={'token': token}).status_code, 400)
        with client.session_transaction() as state:
            csrf = state['csrf_token']
        self.assertEqual(client.post(path, data={'token': 'invalid', 'csrf_token': csrf}).status_code, 422)
        response = client.post(path, data={'token': token, 'csrf_token': csrf})
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.location.endswith('/auth/google'))
        with client.session_transaction() as state:
            self.assertIn('pending_invitation', state)
            self.assertNotIn(SESSION_KEY, state)

    def test_every_new_mutation_has_csrf_and_rejects_forged_fields(self):
        row = self.create()
        for uid, url, data in (
            (self.admin, '/admin/trusted-users', {'user_id': self.member, 'action': 'grant'}),
            (self.admin, '/admin/attribute-legacy-members', {'confirm': 'yes'}),
            (self.trusted, '/invitations', {'email': 'beta@example.test'}),
            (self.trusted, '/documents/' + self.doc + '/invitations', {'email': 'doc@example.test', 'role': 'viewer'}),
            (self.trusted, '/invitations/' + row['invitation_id'] + '/manage', {'action': 'revoke'})):
            self.assertEqual(self.post(uid, url, data, token='').status_code, 400)
            self.assertEqual(self.post(uid, url, {**data, 'is_site_admin': '1'}).status_code, 400)

    def test_failed_acceptance_rolls_back_identity_allowlist_and_document_grant(self):
        row = self.create()
        before = self.sql('SELECT * FROM users')
        with patch('review.invitations.audit', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                self.join(row)
        self.assertEqual(self.sql('SELECT * FROM users'), before)
        self.assertFalse(self.sql('SELECT * FROM allowed_emails WHERE normalized_email=?', (row['normalized_email'],)))
        self.assertEqual(self.sql('SELECT status FROM invitations')[0]['status'], 'pending')

    def test_concurrent_duplicate_creations_produce_one_pending_invitation(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(lambda _: self.create(), range(2)))
        self.assertEqual(rows[0]['invitation_id'], rows[1]['invitation_id'])
        self.assertEqual(len(self.sql('SELECT * FROM invitations')), 1)

    def test_history_and_management_are_authorized(self):
        row = self.create()
        path = '/invitations/' + row['invitation_id'] + '/manage'
        self.assertEqual(self.clients[self.member].get(path).status_code, 403)
        self.assertEqual(self.clients[self.admin].get(path).status_code, 200)
        self.assertEqual(self.clients[self.trusted].get(path).status_code, 200)
        history = self.clients[self.admin].get('/admin/history')
        self.assertEqual(history.status_code, 200)
        self.assertIn(b'invitation.created', history.data)
        self.assertNotIn(invites.token_for(self.app.secret_key, row).encode(), history.data)

    def test_trusted_invites_cannot_restore_admin_removed_or_disabled_membership(self):
        email = f'{self.member}@example.test'
        row = self.create()
        access.set_allowed_email(self.db, row['normalized_email'], 'allow', actor=self.admin)
        access.set_allowed_email(self.db, row['normalized_email'], 'remove', actor=self.admin)
        with self.assertRaises(access.AccessError):
            self.marker(row)
        with self.assertRaises(access.AccessError):
            self.create()
        access.set_allowed_email(self.db, email, 'remove', confirmed=True, actor=self.admin)
        with self.assertRaises(access.AccessError):
            self.create(email)
        access.set_allowed_email(self.db, email, 'allow', actor=self.admin)
        self.assertEqual(self.create(email)['status'], 'accepted')

    def test_revoke_trust_while_member_is_suspended(self):
        access.set_allowed_email(self.db, f'{self.trusted}@example.test', 'disable', actor=self.admin)
        invites.set_trusted(self.db, self.admin, self.trusted, False)
        access.set_allowed_email(self.db, f'{self.trusted}@example.test', 'allow', actor=self.admin)
        self.assertFalse(invites.can_invite(self.db, self.trusted))

    def test_renew_failure_keeps_original_pending_invitation(self):
        row = self.create()
        with patch('review.invitations.create_invitation', side_effect=access.AccessError('cannot reissue')):
            with self.assertRaises(access.AccessError):
                invites.renew_invitation(self.db, self.trusted, row['invitation_id'])
        self.assertEqual(self.sql('SELECT status FROM invitations')[0]['status'], 'pending')

    def test_two_acceptances_commit_once(self):
        row = self.create()
        marker = self.marker(row)
        def accept(_):
            with self.app.app_context():
                try:
                    return resolve_google_identity({'sub': 'same-sub', 'email': row['normalized_email'], 'email_verified': True}, marker)
                except access.AccessError:
                    return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(accept, range(2)))
        self.assertEqual(sum(uid is not None for uid in results), 1)
        self.assertEqual(len(self.sql("SELECT * FROM access_audit_log WHERE action='invitation.accepted'")), 1)

    def test_share_fragment_retains_document_owner_boundary(self):
        path = '/documents/' + self.doc + '/access?share=1'
        response = self.clients[self.trusted].get(path)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-share-form="existing"', response.data)
        self.assertIn(b'data-share-form="email"', response.data)
        self.assertNotIn(b'<!doctype', response.data)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(self.clients[self.admin].get(path).status_code, 404)
        access.set_document_access(self.db, self.doc, self.member, 'reviewer')
        self.assertEqual(self.clients[self.member].get(path).status_code, 403)

    def test_share_dialog_json_submission_and_validation(self):
        headers = {'Accept': 'application/json', 'X-CSRF-Token': 'fixture-csrf-token'}
        response = self.clients[self.trusted].post('/documents/' + self.doc + '/access', headers=headers,
            data={'action': 'grant', 'user_id': self.member, 'role': 'viewer'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Access granted', response.json['message'])
        response = self.clients[self.trusted].post('/documents/' + self.doc + '/invitations', headers=headers,
            data={'email': 'dialog-new@example.test', 'role': 'reviewer'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'pending')
        self.assertIn('#token=', response.json['invitation_link'])
        response = self.clients[self.trusted].post('/documents/' + self.doc + '/invitations', headers=headers,
            data={'email': 'invalid', 'role': 'reviewer'})
        self.assertEqual(response.status_code, 422)
        self.assertIn('message', response.json['error'])


class InvitationMigrationTests(unittest.TestCase):
    def test_populated_v13_backfill_preserves_rows_and_labels_unknown_dates(self):
        with tempfile.TemporaryDirectory() as root:
            db = Path(root) / 'legacy.sqlite3'
            with patch('review.database.MIGRATIONS', MIGRATIONS[:13]):
                init_database(db)
            with transaction(db) as c:
                for uid in ('admin', 'member'):
                    c.execute('INSERT INTO users(user_id,display_name,created_at,google_subject,email,normalized_email,email_verified,last_login_at) VALUES (?,?,?, ?,?,?,1,?)', (uid, uid, '2020-01-01T00:00:00.000Z', uid, uid+'@example.test', uid+'@example.test', '2026-11-01T00:00:00.000Z'))
                    c.execute('INSERT INTO allowed_emails(normalized_email,created_at) VALUES (?,?)', (uid+'@example.test', '2026-10-01T00:00:00.000Z'))
                c.execute("INSERT INTO site_admins(user_id,created_at) VALUES ('admin','now')")
                before = [dict(r) for r in c.execute('SELECT * FROM users')]
            init_database(db)
            init_database(db)
            with transaction(db) as c:
                self.assertEqual([dict(r) for r in c.execute('SELECT * FROM users')], before)
                for row in c.execute('SELECT * FROM beta_memberships'):
                    self.assertEqual(row['invited_by'], 'admin')
                    self.assertEqual(row['date_source'], 'allowlist_record')
                    self.assertIsNone(row['joined_at'])
                    self.assertEqual(row['joined_by_at'], '2026-11-01T00:00:00.000Z')
                self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(), [])
                self.assertEqual(c.execute('SELECT count(*) FROM trusted_users').fetchone()[0], 0)
