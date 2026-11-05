"""Durable reading invariants and HTTP privacy, using isolated SQLite fixtures."""
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from review import create_app, reading
from review.database import connect, transaction, init_database
from review.preferences import save_defaults
import tests.test_threads as thread_fixtures
from tests.auth_helpers import secure_client, authenticate


class ReadingTests(unittest.TestCase):
    def setUp(self):
        thread_fixtures.ThreadTests.setUp(self)
        self.app=create_app({'TESTING':True,'DATABASE':str(self.database),'STORAGE_ROOT':str(self.storage_root),'SECRET_KEY':'reading-test'})
        self.http=secure_client(self.app,self.alpha['user_id'])
        self.other=secure_client(self.app,self.beta['user_id'])
        with transaction(self.database) as c:
            c.execute("UPDATE document_access SET role='reviewer' WHERE user_id=?",(self.beta['user_id'],))
        self.user=self.alpha['user_id'];self.version=self.draft3
        self.url=f'/api/versions/{self.version}/reading'

    def tearDown(self):
        thread_fixtures.ThreadTests.tearDown(self)

    def enable(self,user=None,version=None):
        uid=user or self.user;vid=version or self.version
        return reading.change_consent(self.database,vid,self.user,'enable',10,reader_id=uid)

    def session(self,user=None,version=None):
        uid=user or self.user;vid=version or self.version
        c=connect(self.database)
        try:state=reading.consent(c,vid,uid)
        finally:c.close()
        return reading.start_session(self.database,vid,uid,state['generation'],10)['session_id']

    def batch(self,sid,seq,clock,pages=(),active=True,user=None,version=None):
        return reading.record_batch(self.database,version or self.version,user or self.user,
            dict(session_id=sid,sequence=seq,active=active,current_page=pages[-1]['page'] if pages else 1,pages=list(pages)),clock=clock)

    def page(self,number,ms,visit=1,words=0):
        return dict(page=number,ms=ms,visit=visit,words=words)

    def counts(self):
        c=connect(self.database)
        try:return {t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in
                    ('reading_consents','reading_sessions','reading_totals','reading_pages','reading_visits')}
        finally:c.close()

    def test_migration_is_additive_idempotent_and_default_is_on_without_get_writes(self):
        before=self.counts();self.assertTrue(all(v==0 for v in before.values()))
        self.assertEqual(self.http.get(self.url).json['tracking']['status'],'active')
        init_database(self.database);self.assertEqual(self.counts(),before)
        self.assertEqual(self.http.post(self.url+'/sessions',json={'generation':1}).status_code,422)
        self.assertEqual(reading.threshold_ms(400),60000)
        self.assertEqual(reading.threshold_ms(0),5000)
        self.assertEqual(reading.threshold_ms(40),6000)
        sid=self.session();other=self.session(self.beta['user_id'])
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError),transaction(self.database) as c:
            c.execute('UPDATE reading_sessions SET version_id=? WHERE session_id=?',(self.draft4,sid))
        with self.assertRaises(sqlite3.IntegrityError),transaction(self.database) as c:
            c.execute('INSERT INTO reading_leases VALUES(?,?,?,?,?)',(self.user,other,1000,1025,1))

    def test_spread_budget_revisits_thresholds_and_duplicate_acknowledgment(self):
        sid=self.session();self.batch(sid,1,1000)
        result=self.batch(sid,2,1010,[self.page(1,20000),self.page(2,20000,words=400)])
        self.assertEqual(result['accepted_ms'],10000)
        duplicate=self.batch(sid,2,1011,[self.page(1,20000),self.page(2,20000,words=400)])
        self.assertTrue(duplicate['duplicate'])
        detail=reading.reader_detail(self.database,self.version,self.user,self.user)
        self.assertEqual(detail['totals']['active_ms'],10000)
        self.assertEqual(detail['totals']['pages_read'],1)
        self.assertEqual([p['state'] for p in detail['pages'][:2]],['read','partial'])
        self.batch(sid,3,1020,[self.page(2,10000,visit=2,words=400)])
        detail=reading.reader_detail(self.database,self.version,self.user,self.user)
        self.assertEqual(detail['pages'][1]['visit_count'],2)
        self.assertEqual(detail['pages'][1]['active_ms'],15000)
        self.assertEqual(detail['totals']['furthest_page'],2)
        self.batch(sid,4,1025,[self.page(1,5000,visit=3)])
        detail=reading.reader_detail(self.database,self.version,self.user,self.user)
        self.assertEqual(detail['totals']['last_page'],1)
        self.assertEqual(detail['totals']['furthest_page'],2)
        self.assertEqual(detail['totals']['pages_read'],1)

    def test_cross_tab_and_cross_document_global_lease_and_expiry(self):
        first=self.session();second=reading.start_session(self.database,self.version,self.user,1,10)['session_id']
        self.batch(first,1,1000)
        self.assertFalse(self.batch(second,1,1000)['granted'])
        with ThreadPoolExecutor(2) as executor:
            results=list(executor.map(lambda sid:self.batch(sid,2,1010,[self.page(1,10000)]),[first,second]))
        self.assertEqual(sum(r['accepted_ms'] for r in results),10000)
        other=self.session(version=self.draft4)
        self.assertFalse(self.batch(other,1,1011,version=self.draft4)['granted'])
        self.assertTrue(self.batch(other,2,1040,version=self.draft4)['granted'])
        result=self.batch(first,3,1041,[self.page(1,10000)])
        self.assertEqual(result['accepted_ms'],0)
        self.assertFalse(result['granted'])

    def test_author_pause_resume_and_document_off_reject_stale_sessions(self):
        sid=self.session();self.batch(sid,1,1000);self.batch(sid,2,1006,[self.page(1,6000)])
        reading.change_consent(self.database,self.version,self.user,'pause',10)
        with self.assertRaises(reading.ReadingError):self.batch(sid,3,1010,[self.page(1,4000)])
        self.assertEqual(self.counts()['reading_pages'],1)
        self.enable()
        with self.assertRaises(reading.ReadingError):self.batch(sid,3,1011,[self.page(1,5000)])
        save_defaults(self.database,self.document_id,self.user,{'reading_tracking_enabled':0})
        self.assertEqual(self.http.get(self.url).json['tracking']['status'],'off')
        self.assertEqual(self.counts()['reading_pages'],1)
        with self.assertRaises(reading.ReadingError):self.session()
        save_defaults(self.database,self.document_id,self.user,{'reading_tracking_enabled':1})
        self.assertEqual(self.http.get(self.url).json['tracking']['status'],'active')

    def test_http_permissions_privacy_version_separation_and_csrf(self):
        sid=self.session();self.batch(sid,1,1000);self.batch(sid,2,1010,[self.page(1,10000)])
        other_sid=self.session(self.beta['user_id']);self.batch(other_sid,1,1000,user=self.beta['user_id'])
        self.batch(other_sid,2,1010,[self.page(2,10000)],user=self.beta['user_id'])
        self.assertEqual(len(self.http.get(self.url).json['readers']),2)
        self.assertEqual([r['user_id'] for r in self.other.get(self.url).json['readers']],[self.beta['user_id']])
        self.assertEqual(self.other.get(self.url+'/readers/'+self.user).status_code,403)
        save_defaults(self.database,self.document_id,self.user,{'visibility_policy':'isolated'})
        self.assertEqual(self.other.get(self.url+'/readers/'+self.user).status_code,403)
        self.assertEqual(self.http.get(self.url+'/readers/'+self.beta['user_id']).status_code,200)
        self.assertEqual(self.http.get(f'/api/versions/{self.draft4}/reading').json['readers'],[])
        with self.assertRaises(reading.ReadingError):self.batch(sid,3,1011,version=self.draft4)
        plain=self.app.test_client();authenticate(plain,self.user)
        self.assertEqual(plain.post(self.url+'/consent',json={'action':'enable','page_count':10}).status_code,400)
        self.assertEqual(self.http.post(self.url+'/consent',json={'action':'enable','page_count':True}).status_code,422)
        self.assertEqual(self.http.post(self.url+'/consent',json={'action':'enable','page_count':10,'user_id':self.beta['user_id']}).status_code,422)
        with transaction(self.database) as c:
            c.execute("UPDATE document_access SET role='viewer' WHERE user_id=?",(self.beta['user_id'],))
        self.assertEqual(self.other.post(self.url+'/consent',json={'action':'pause','page_count':10}).status_code,403)
        self.assertEqual(self.other.get(self.url+'/readers/'+self.beta['user_id']).status_code,200)
        with transaction(self.database) as c:c.execute('DELETE FROM document_access WHERE user_id=?',(self.beta['user_id'],))
        self.assertEqual(self.other.get(self.url).status_code,404)
        self.assertEqual([r['user_id'] for r in self.http.get(self.url).json['readers']],[self.user])

    def test_author_settings_apply_across_versions_and_http_owner_only(self):
        settings_url=f'/documents/{self.document_id}/review-settings'
        page=self.http.get(settings_url)
        self.assertEqual(page.status_code,200)
        self.assertIn(b'reading_tracking_enabled',page.data)
        self.assertIn(b'tracking_reader_',page.data)
        self.assertEqual(self.other.get(settings_url).status_code,403)
        self.assertEqual(self.other.post(settings_url,data={'reading_tracking_enabled':'0'}).status_code,403)
        sid=self.session(self.beta['user_id'])
        self.assertEqual(self.http.post(settings_url,data={'tracking_reader_'+self.beta['user_id']:'1'}).status_code,200)
        self.assertEqual(self.other.get(self.url).json['tracking']['status'],'paused')
        with self.assertRaises(reading.ReadingError):self.batch(sid,1,1000,user=self.beta['user_id'])
        c=connect(self.database)
        try:self.assertEqual(reading.consent(c,self.draft4,self.beta['user_id'])['status'],'paused')
        finally:c.close()
        self.assertEqual(self.http.post(settings_url,data={'tracking_reader_'+self.beta['user_id']:'0','reading_tracking_enabled':'0'}).status_code,200)
        self.assertEqual(self.other.get(self.url).json['tracking']['status'],'off')
        self.assertEqual(self.http.post(settings_url,data={'reading_tracking_enabled':'1'}).status_code,200)
        self.assertEqual(self.other.get(self.url).json['tracking']['status'],'active')
        # A normal reader starts automatically, without an opt-in mutation.
        state=self.other.get(self.url).json['tracking']
        self.assertEqual(self.other.post(self.url+'/sessions',json={'generation':state['generation'],'page_count':10}).status_code,200)
        self.assertEqual(self.other.post(self.url+'/consent',json={'action':'enable','page_count':10}).status_code,403)

    def test_live_reading_notifications_recheck_recipients_and_keep_data_private(self):
        io=self.app.extensions['socketio']
        owner=io.test_client(self.app,flask_test_client=self.http)
        reader=io.test_client(self.app,flask_test_client=self.other)
        other_version=io.test_client(self.app,flask_test_client=self.http)
        try:
            for socket,version in [(owner,self.version),(reader,self.version),(other_version,self.draft4)]:
                self.assertTrue(socket.emit('review.join',{'version_id':version},callback=True)['ok'])
            def events(socket):return [e for e in socket.get_received() if e['name']=='reading.changed']
            for socket in (owner,reader,other_version):socket.get_received()
            sid=self.session()
            response=self.http.post(self.url+'/batches',json=dict(session_id=sid,sequence=1,active=True,current_page=1,pages=[]))
            self.assertEqual(response.status_code,200)
            self.assertEqual(len(events(owner)),1)
            self.assertEqual(events(reader),[])
            self.assertEqual(events(other_version),[])
            sid=self.session(self.beta['user_id'])
            response=self.other.post(self.url+'/batches',json=dict(session_id=sid,sequence=1,active=True,current_page=1,pages=[]))
            self.assertEqual(response.status_code,200)
            self.assertEqual(len(events(owner)),1)
            event=events(reader)[0]['args'][0]
            self.assertEqual(set(event),{'schema_version','version_id'})
            # Policy notifications reach every affected viewer, across versions.
            settings_url=f'/documents/{self.document_id}/review-settings'
            self.assertEqual(self.http.post(settings_url,data={'reading_tracking_enabled':'0'}).status_code,200)
            for socket in (owner,reader,other_version):self.assertEqual(len(events(socket)),1)
            with transaction(self.database) as c:c.execute('DELETE FROM document_access WHERE user_id=?',(self.beta['user_id'],))
            from review.realtime import notify_reading_changed
            with self.app.app_context():notify_reading_changed(self.version)
            self.assertEqual(events(reader),[])
        finally:
            for socket in (owner,reader,other_version):
                if socket.is_connected():socket.disconnect()

    def test_page_windows_validation_long_dwell_and_fractional_sections(self):
        sid=self.session();self.batch(sid,1,1000)
        for seq in range(2,10):self.batch(sid,seq,1000+(seq-1)*20,[self.page(2,20000)])
        detail=reading.reader_detail(self.database,self.version,self.user,self.user,2,1)
        self.assertEqual(len(detail['pages']),1);self.assertTrue(detail['pages'][0]['long_dwell'])
        self.assertEqual(detail['next_page'],3)
        with self.assertRaises(reading.ReadingError):self.batch(sid,10,1180,[self.page(11,1000)])
        self.assertEqual(self.http.get(self.url+'/readers/'+self.user+'?limit=100000').status_code,422)
        from review.sections import create_section, save_placement
        # Section begins halfway through p.2 and ends at p.3's top: only half
        # the p.2 time belongs to it, and p.3 is not counted in its range.
        section=create_section(self.database,self.document_id,self.user,{'name':'Half page'})
        save_placement(self.database,section,self.version,self.user,
            dict(start_page=2,start_y=400,end_page=3,end_y=800,start_view_box=[0,0,600,800],end_view_box=[0,0,600,800],page_count=10,expected_revision=0))
        detail=reading.reader_detail(self.database,self.version,self.user,self.user)
        self.assertEqual(detail['sections'][0]['active_ms'],80000)
        self.assertEqual(detail['sections'][0]['end_page'],2)
        self.assertEqual(detail['sections'][0]['page_count'],1)
        self.assertEqual(detail['sections'][0]['pages_read'],1)
        self.assertTrue(detail['sections'][0]['is_read'])

    def test_section_read_requires_strictly_more_than_ninety_percent_of_pages(self):
        from review.sections import create_section, save_placement
        section=create_section(self.database,self.document_id,self.user,{'name':'Ten pages'})
        save_placement(self.database,section,self.version,self.user,
            dict(start_page=1,start_y=None,end_page=10,end_y=None,start_view_box=[0,0,600,800],end_view_box=[0,0,600,800],page_count=10,expected_revision=0))
        sid=self.session();self.batch(sid,1,1000)
        for number in range(1,11):
            self.batch(sid,number+1,1000+number*5,[self.page(number,5000)])
            if number in (1,9,10):
                # A paged detail request must still aggregate the entire section.
                result=reading.reader_detail(self.database,self.version,self.user,self.user,1,1)['sections'][0]
                self.assertEqual(result['page_count'],10)
                self.assertEqual(result['pages_read'],number)
                self.assertEqual(result['percentage'],number*10)
                self.assertEqual(result['is_read'],number==10)

    def test_section_read_accepts_over_ninety_percent_and_counts_partial_pages_whole(self):
        from review.sections import create_section, save_placement
        section=create_section(self.database,self.document_id,self.user,{'name':'Eleven pages'})
        payload=dict(start_page=1,start_y=None,end_page=11,end_y=None,start_view_box=[0,0,600,800],end_view_box=[0,0,600,800],page_count=11,expected_revision=0)
        save_placement(self.database,section,self.version,self.user,payload)
        sid=reading.start_session(self.database,self.version,self.user,1,11)['session_id'];self.batch(sid,1,1000)
        for number in range(1,11):self.batch(sid,number+1,1000+number*5,[self.page(number,5000)])
        result=reading.reader_detail(self.database,self.version,self.user,self.user)['sections'][0]
        self.assertEqual((result['pages_read'],result['page_count'],result['percentage'],result['is_read']),(10,11,90.9,True))
        # Almost all this range lies on read p.10, but unread p.11 still counts.
        save_placement(self.database,section,self.version,self.user,
            {**payload,'start_page':10,'end_y':799,'expected_revision':1})
        result=reading.reader_detail(self.database,self.version,self.user,self.user)['sections'][0]
        self.assertEqual((result['pages_read'],result['page_count'],result['percentage'],result['is_read']),(1,2,50,False))


if __name__=='__main__':unittest.main()
