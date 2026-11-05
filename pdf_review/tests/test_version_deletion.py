"""Owner-only version withdrawal preserves immutable history and shared blobs."""
import io
import sqlite3
import unittest
from unittest.mock import patch
from review import create_app, documents, reading
from review.access import AccessDenied
from review.database import connect, transaction, init_database
from review.threads import create_thread, get_thread
from review.anchors import get_anchor, AnchorNotFoundError
from review.migrations import create_migration, carry_item
from review import sections, section_feedback
from tests.auth_helpers import secure_client, authenticate
import tests.test_threads as fixtures


class VersionDeletionTests(unittest.TestCase):
    def setUp(self):
        fixtures.ThreadTests.setUp(self)
        self.app=create_app({'TESTING':True,'DATABASE':str(self.database),'STORAGE_ROOT':str(self.storage_root),'SECRET_KEY':'delete-test'})
        self.http=secure_client(self.app,self.alpha['user_id']);self.other=secure_client(self.app,self.beta['user_id'])
        self.user=self.alpha['user_id'];self.url=f'/versions/{self.draft3}/delete'
        with transaction(self.database) as c:c.execute("UPDATE document_access SET role='reviewer' WHERE user_id=?",(self.beta['user_id'],))
    def tearDown(self):fixtures.ThreadTests.tearDown(self)
    def rows(self,table):
        c=connect(self.database)
        try:return [tuple(r) for r in c.execute('SELECT * FROM '+table+' ORDER BY rowid')]
        finally:c.close()
    def assert_pdf(self,version):
        with self.http.get(f'/versions/{version}/pdf') as response:self.assertEqual(response.status_code,200)
    def delete(self,version=None):
        version=version or self.draft3
        return self.http.post(f'/versions/{version}/delete',data={'confirm_version_id':version})

    def test_confirmation_owner_only_csrf_and_exact_version(self):
        page=self.http.get(self.url)
        self.assertEqual(page.status_code,200);self.assertIn(b'draft-3.pdf',page.data)
        self.assertFalse(self.rows('version_deletions'))
        for role in ('reviewer','viewer'):
            with transaction(self.database) as c:c.execute('UPDATE document_access SET role=? WHERE user_id=?',(role,self.beta['user_id']))
            self.assertEqual(self.other.get(self.url).status_code,403)
            self.assertEqual(self.other.post(self.url,data={'confirm_version_id':self.draft3}).status_code,403)
        plain=self.app.test_client();authenticate(plain,self.user)
        self.assertEqual(plain.post(self.url,data={'confirm_version_id':self.draft3}).status_code,400)
        self.assertEqual(self.http.post(self.url,data={'confirm_version_id':self.draft4}).status_code,400)
        self.assertEqual(self.http.post(self.url,data={}).status_code,400)
        self.assertFalse(self.rows('version_deletions'))
        self.assertIsNotNone(documents.get_version(self.database,self.draft4))

    def test_removed_from_lists_and_all_version_links_but_bytes_stay(self):
        before=self.rows('document_versions')
        self.assertEqual(self.delete().status_code,303)
        self.assertEqual(self.rows('document_versions'),before)
        self.assertEqual([r['version_id'] for r in documents.list_versions(self.database,self.document_id)],[self.draft4])
        self.assertEqual(documents.list_documents(self.database)[0]['version_count'],1)
        for url in [f'/versions/{self.draft3}/view',f'/versions/{self.draft3}/pdf',f'/versions/{self.draft3}/delete',
                    f'/api/versions/{self.draft3}/threads',f'/api/versions/{self.draft3}/anchors',
                    f'/api/versions/{self.draft3}/reading',f'/api/versions/{self.draft3}/review-context']:
            self.assertEqual(self.http.get(url).status_code,404,url)
        with patch('review.storage.BlobStore.resolve',side_effect=AssertionError('Deleted PDF must not reach storage')):
            self.assertEqual(self.http.get(f'/versions/{self.draft3}/pdf').status_code,404)
        self.assertEqual(self.http.get(f'/versions/{self.draft4}/view').status_code,200)
        self.assert_pdf(self.draft4)
        self.assertEqual(self.delete().status_code,404)
        documents.delete_version(self.database,self.draft3,self.user,self.draft3)
        self.assertEqual(len(self.rows('version_deletions')),1)
        c=connect(self.database)
        try:self.assertEqual(c.execute("SELECT count(*) FROM access_audit_log WHERE action='version.delete'").fetchone()[0],1)
        finally:c.close()

    def test_shared_blob_last_version_and_reimport(self):
        original=documents.get_version(self.database,self.draft3)
        duplicate=documents.import_version(self.database,self.blobs,self.document_id,io.BytesIO(fixtures.pdf_bytes(b'draft 3')),'same.pdf').version_id
        self.assertEqual(documents.get_version(self.database,duplicate)['sha256'],original['sha256'])
        self.delete()
        self.assert_pdf(duplicate)
        self.assertTrue(self.blobs.resolve(original['blob_path'],original['sha256']).exists())
        self.delete(self.draft4);self.delete(duplicate)
        self.assertEqual(documents.list_versions(self.database,self.document_id),[])
        self.assertEqual(self.http.get(f'/documents/{self.document_id}').status_code,200)
        replacement=documents.import_version(self.database,self.blobs,self.document_id,io.BytesIO(fixtures.pdf_bytes(b'draft 3')),'correct.pdf').version_id
        self.assertNotEqual(replacement,self.draft3)
        self.assert_pdf(replacement)

    def test_feedback_history_preserved_and_carry_on_other_version_survives(self):
        thread=create_thread(self.database,self.draft3,self.user,fixtures.anchor_payload(),'Keep this feedback')
        run=create_migration(self.database,self.document_id,self.draft3,self.draft4,self.user)
        item=run['items'][0]
        carry_item(self.database,run['migration_id'],item['item_id'],self.user,fixtures.anchor_payload(),1,None)
        orphan=create_thread(self.database,self.draft3,self.user,fixtures.anchor_payload(),'Wrong-version only')
        section=sections.create_section(self.database,self.document_id,self.user,{'name':'Section'})
        sections.save_placement(self.database,section,self.draft3,self.user,dict(start_page=1,end_page=2,start_y=None,end_y=None,
            start_view_box=[0,0,612,792],end_view_box=[0,0,612,792],page_count=10,expected_revision=0))
        response=section_feedback.create_response(self.database,section,self.draft3,self.user,'Thoughts')
        sid=reading.start_session(self.database,self.draft3,self.user,1,10)['session_id']
        payload=dict(session_id=sid,sequence=1,active=True,current_page=1,pages=[])
        reading.record_batch(self.database,self.draft3,self.user,payload,clock=1000)
        payload.update(sequence=2,pages=[dict(page=1,ms=6000,words=0,visit=1)])
        reading.record_batch(self.database,self.draft3,self.user,payload,clock=1006)
        tables=('threads','thread_targets','thread_target_heads','anchor_instances','anchor_segments','comments','comment_revisions',
                'migration_runs','migration_items','sections','section_placements','section_responses','section_comments',
                'reading_pages','reading_totals','reading_visits','reading_consents','reading_sessions')
        before={table:self.rows(table) for table in tables}
        self.assertEqual(self.delete().status_code,303)
        self.assertEqual({table:self.rows(table) for table in tables},before)
        survivor=get_thread(self.database,thread['thread_id'],self.draft4,user_id=self.user)
        self.assertEqual(survivor['comments'][0]['body'],'Keep this feedback')
        self.assertEqual(len(survivor['targets']),1)
        self.assertEqual(self.http.post(f"/api/threads/{orphan['thread_id']}/comments",json={'body':'Blocked'}).status_code,404)
        self.assertEqual(self.http.get(f"/api/migrations/{run['migration_id']}").status_code,404)
        self.assertEqual(self.http.post(f'/api/section-responses/{response}/comments',json={'body':'No new reply'}).status_code,404)
        with self.assertRaises(AnchorNotFoundError):get_anchor(self.database,thread['targets'][0]['anchor']['anchor_id'])
        with self.assertRaises(LookupError):reading.record_batch(self.database,self.draft3,self.user,payload,clock=1007)
        self.assertFalse(self.rows('reading_leases'))
        c=connect(self.database)
        try:self.assertFalse(c.execute('PRAGMA foreign_key_check').fetchall())
        finally:c.close()

    def test_live_viewers_retired_and_deleted_version_cannot_rejoin(self):
        io=self.app.extensions['socketio'];clients=[]
        try:
            for http,version in [(self.http,self.draft3),(self.other,self.draft3),(self.http,self.draft4)]:
                socket=io.test_client(self.app,flask_test_client=http);clients.append(socket)
                self.assertTrue(socket.emit('review.join',{'version_id':version},callback=True)['ok'])
            for socket in clients:socket.get_received()
            self.assertEqual(self.delete().status_code,303)
            for socket in clients[:2]:
                events=[e for e in socket.get_received() if e['name']=='review.version_deleted']
                self.assertEqual(events[0]['args'][0],{'schema_version':1,'version_id':self.draft3})
                self.assertFalse(socket.emit('review.join',{'version_id':self.draft3},callback=True)['ok'])
            self.assertFalse([e for e in clients[2].get_received() if e['name']=='review.version_deleted'])
            registry=self.app.extensions['review_presence']
            self.assertTrue(all(e['version_id']==self.draft4 for e in registry.connections.values()))
        finally:
            for socket in clients:
                if socket.is_connected():socket.disconnect()

    def test_transactional_owner_recheck_audit_and_immutable_ledger(self):
        with transaction(self.database) as c:c.execute("UPDATE document_access SET role='reviewer' WHERE user_id=?",(self.user,))
        with self.assertRaises(AccessDenied):documents.delete_version(self.database,self.draft3,self.user,self.draft3)
        self.assertFalse(self.rows('version_deletions'))
        with transaction(self.database) as c:c.execute("UPDATE document_access SET role='owner' WHERE user_id=?",(self.user,))
        self.delete();init_database(self.database)
        for query in ['UPDATE version_deletions SET deleted_at=\'changed\'','DELETE FROM version_deletions']:
            with self.assertRaises(sqlite3.IntegrityError),transaction(self.database) as c:c.execute(query)
