"""Synthetic C2 confidentiality, preferences, sections and migration acceptance."""

import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from review import create_app
from review.database import connect,transaction,init_database,MIGRATIONS
from review.documents import create_document,import_version
from review.users import create_user
from review.threads import create_thread,add_comment
from review import preferences,sections,section_feedback
from review.realtime import notify_thread_changed
from tests.auth_helpers import authenticate,CsrfClient
from tests.test_threads import anchor_payload
from tests.browser_sanity import pdf_bytes


class BetaC2Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.app=create_app({'TESTING':True,'DATA_DIR':str(self.root),'SECRET_KEY':'synthetic-c2-only'})
        self.db=self.app.config['DATABASE']
        self.users=[create_user(self.db,n)['user_id'] for n in ['Owner','Alice','Bob','Viewer']]
        self.doc=create_document(self.db,'Synthetic C2',owner_id=self.users[0])
        self.versions=[import_version(self.db,self.app.extensions['blob_store'],self.doc,io.BytesIO(pdf_bytes(str(i))),f'draft{i}.pdf').version_id for i in range(2)]
        self.clients=[]
        for i,user in enumerate(self.users):
            client=CsrfClient(self.app,self.app.response_class,use_cookies=True)
            authenticate(client,user,grant_documents=False)
            if i:
                with transaction(self.db) as c:
                    c.execute("INSERT INTO document_access(document_id,user_id,role,created_at) VALUES(?,?,?,'fixture')",(self.doc,user,'viewer' if i==3 else 'reviewer'))
            self.clients.append(client)
        self.threads=[create_thread(self.db,self.versions[0],u,anchor_payload(),'Review '+str(i)) for i,u in enumerate(self.users[1:3])]
        add_comment(self.db,self.threads[0]['thread_id'],self.users[0],'Owner reply')

    def defaults(self,**values):
        preferences.save_defaults(self.db,self.doc,self.users[0],values)

    def test_download_policy_owner_validation_and_rendering(self):
        url=f'/documents/{self.doc}/review-settings'
        self.assertEqual(self.context(1)['preferences']['defaults']['downloads_allowed'],1)
        for index in [1,2,3]:
            self.assertEqual(self.clients[index].post(url,data={'downloads_allowed':'0'}).status_code,403)
        for value in ['2','true','invalid']:
            self.assertEqual(self.clients[0].post(url,data={'downloads_allowed':value}).status_code,422)
        saved=self.clients[0].post(url,data={'downloads_allowed':'0'})
        self.assertEqual(saved.status_code,200)
        self.assertEqual(saved.json['settings']['downloads_allowed'],0)
        self.defaults(default_display='hidden')
        self.assertEqual(self.context(1)['preferences']['defaults']['downloads_allowed'],0)
        for version in self.versions:
            html=self.clients[1].get(f'/versions/{version}/view').get_data(as_text=True)
            self.assertIn('data-downloads-allowed="false"',html)
            self.assertIn('data-pdf-control="downloadButton" hidden disabled',html)
            self.assertIn('data-pdf-control="printButton" hidden disabled',html)
            response=self.clients[1].get(f'/versions/{version}/pdf')
            self.assertEqual(response.status_code,200)  # Read endpoint is needed by PDF.js.
            response.close()
        self.clients[0].post(url,data={'downloads_allowed':'1'})
        self.assertEqual(self.context(1)['preferences']['defaults']['downloads_allowed'],1)

    def test_migration10_preserves_defaults_and_enables_existing_documents(self):
        path=self.root/'before10.sqlite3'
        c=sqlite3.connect(path)
        c.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,name TEXT UNIQUE,applied_at TEXT)')
        for version,name,sql in MIGRATIONS[:9]:
            c.executescript(sql)
            c.execute('INSERT INTO schema_migrations VALUES(?,?,?)',(version,name,'before'))
        c.commit();c.close()
        old_doc=create_document(str(path),'Existing settings')
        c=connect(path)
        c.execute("INSERT INTO document_review_settings VALUES(?,'isolated','mine',2,'hidden')",(old_doc,))
        c.commit();c.close()
        init_database(path);init_database(path)
        c=connect(path)
        try:
            row=dict(c.execute('SELECT * FROM document_review_settings').fetchone())
            self.assertEqual((row['visibility_policy'],row['default_scope'],row['default_spread'],row['default_display'],row['downloads_allowed']),('isolated','mine',2,'hidden',1))
            self.assertEqual(c.execute('SELECT COUNT(*) FROM schema_migrations WHERE version=10').fetchone()[0],1)
        finally: c.close()

    def thread_ids(self,index):
        response=self.clients[index].get(f'/api/versions/{self.versions[0]}/threads')
        self.assertEqual(response.status_code,200,response.data)
        return [t['thread_id'] for t in response.json['threads']]

    def context(self,index):
        response=self.clients[index].get(f'/api/versions/{self.versions[0]}/review-context')
        self.assertEqual(response.status_code,200,response.data)
        return response.json

    def section(self,name='Chapter one'):
        sid=sections.create_section(self.db,self.doc,self.users[0],{'name':name,'prompt':'What surprised you?'})
        return sid

    def place(self,sid,**values):
        payload=dict(start_page=1,start_y=None,end_page=1,end_y=400.,start_view_box=[0,0,612,792],
            end_view_box=[0,0,612,792],page_count=2,expected_revision=0)
        payload.update(values)
        sections.save_placement(self.db,sid,self.versions[0],self.users[0],payload)
        return payload

    def test_shared_boundary_atomic_revision_and_owner_guards(self):
        left,right=self.section('Left'),self.section('Right')
        a=self.place(left)
        b=self.place(right,start_y=400.,end_y=None)
        url=f'/api/versions/{self.versions[0]}/sections/shared-boundary'
        def payload(y,revision):
            return {'before_id':left,'after_id':right,
                'before':dict(a,end_y=y,expected_revision=revision),
                'after':dict(b,start_y=y,expected_revision=revision)}
        self.assertEqual(self.clients[1].post(url,json=payload(300,1)).status_code,403)
        self.assertEqual(self.clients[0].post(url,json=payload(300,1),headers={'X-CSRF-Token':'invalid'}).status_code,400)
        self.assertEqual(self.clients[0].post(url,json=payload(300,1)).status_code,200)
        current=self.context(0)['sections']
        self.assertEqual([s['placement']['revision'] for s in current],[2,2])
        self.assertEqual(current[0]['placement']['end_y'],300)
        # The first update would succeed; the second is stale. Both must roll back.
        stale=payload(500,2);stale['after']['expected_revision']=1
        self.assertEqual(self.clients[0].post(url,json=stale).status_code,409)
        self.assertEqual(self.context(0)['sections'],current)
        bad=payload(500,2);bad['before']['start_y']=600
        self.assertEqual(self.clients[0].post(url,json=bad).status_code,422)
        self.assertEqual(self.context(0)['sections'],current)
        self.assertEqual(self.clients[0].post(url,json=payload(500,2)).status_code,200)
        current=self.context(0)['sections']
        self.assertEqual([s['placement']['revision'] for s in current],[3,3])
        self.assertEqual(current[1]['placement']['start_y'],500)

    def test_shared_boundary_roundtrip_and_split(self):
        left,right=self.section('Left'),self.section('Right')
        a=self.place(left,end_y=399.123456789)
        b=self.place(right,start_y=399.1234567890001,end_y=None)
        url=f'/api/versions/{self.versions[0]}/sections/shared-boundary'
        payload={'before_id':left,'after_id':right,
            'before':dict(a,end_y=420,expected_revision=1),
            'after':dict(b,start_y=380,expected_revision=1), 'split':True}
        # Splitting only shrinks the two sections; it cannot expand across an edge.
        bad=dict(payload,before=dict(payload['before'],end_y=390))
        self.assertEqual(self.clients[0].post(url,json=bad).status_code,422)
        self.assertEqual(self.clients[0].post(url,json=payload).status_code,200)
        current=self.context(0)['sections']
        self.assertEqual(current[0]['placement']['end_y'],420)
        self.assertEqual(current[1]['placement']['start_y'],380)
        self.assertEqual([s['placement']['revision'] for s in current],[2,2])
        # An actual gap is never treated as a shared divider.
        self.assertEqual(self.clients[0].post(url,json=payload).status_code,409)
        self.assertEqual(self.context(0)['sections'],current)

    def test_shared_boundary_exact_page_edge_split(self):
        left,right=self.section('Left'),self.section('Right')
        a=self.place(left,end_y=20)
        b=self.place(right,start_y=20,end_page=2,end_y=None)
        payload={'before_id':left,'after_id':right,'split':True,
            'before':dict(a,end_y=0,expected_revision=1),
            'after':dict(b,start_page=2,start_y=792,expected_revision=1)}
        response=self.clients[0].post(f'/api/versions/{self.versions[0]}/sections/shared-boundary',json=payload)
        self.assertEqual(response.status_code,200,response.data)
        current=self.context(0)['sections']
        self.assertEqual(current[0]['placement']['end_y'],0)
        self.assertEqual(current[1]['placement']['start_page'],2)
        self.assertEqual(current[1]['placement']['start_y'],792)
        self.assertEqual([s['placement']['revision'] for s in current],[2,2])

    def test_linked_page_edit_allows_subpage_neighbors(self):
        left,right=self.section('Left'),self.section('Right')
        a=self.place(left,start_page=1,end_page=4,end_y=None,page_count=10)
        b=self.place(right,start_page=5,start_y=None,end_page=10,end_y=None,page_count=10)
        url=f'/api/versions/{self.versions[0]}/sections/shared-boundary'
        payload={'before_id':left,'after_id':right,'edited_id':left,
            'before':dict(a,end_page=5,expected_revision=1),
            'after':dict(b,start_page=6,expected_revision=1)}
        self.assertEqual(self.clients[0].post(url,json=payload).status_code,200)
        current=self.context(0)['sections']
        self.assertEqual(current[0]['placement']['end_page'],5)
        self.assertEqual(current[1]['placement']['start_page'],6)
        invalid={'before_id':left,'after_id':right,'edited_id':left,
            'before':dict(a,end_page=10,end_y=200,expected_revision=2),
            'after':dict(b,start_page=10,start_y=200,expected_revision=2)}
        self.assertEqual(self.clients[0].post(url,json=invalid).status_code,200)
        current=self.context(0)['sections']
        self.assertEqual(current[1]['placement']['start_y'],200)
        empty=dict(invalid,before=dict(invalid['before'],end_y=0,expected_revision=3),after=dict(invalid['after'],start_y=0,expected_revision=3))
        self.assertEqual(self.clients[0].post(url,json=empty).status_code,422)
        self.assertEqual(self.context(0)['sections'],current)
        # Editing the following start similarly moves the preceding end.
        reverse={'before_id':left,'after_id':right,'edited_id':right,
            'before':dict(a,end_page=3,expected_revision=3),
            'after':dict(b,start_page=4,expected_revision=3)}
        self.assertEqual(self.clients[0].post(url,json=reverse).status_code,200)
        current=self.context(0)['sections']
        self.assertEqual(current[0]['placement']['end_page'],3)
        self.assertEqual(current[1]['placement']['start_page'],4)
        html=self.clients[0].get(f'/documents/{self.doc}').get_data(as_text=True)
        self.assertNotIn('data-review-settings',html)
        self.assertNotIn('data-sections=',html)

    def test_shared_mine_and_hidden_authors_keep_conversation_replies(self):
        self.assertEqual(set(self.thread_ids(1)),{t['thread_id'] for t in self.threads})
        preferences.save_preferences(self.db,self.doc,self.users[1],{'scope':'mine'})
        self.assertEqual(self.thread_ids(1),[self.threads[0]['thread_id']])
        thread=self.clients[1].get(f'/api/versions/{self.versions[0]}/threads').json['threads'][0]
        self.assertEqual(thread['comments'][-1]['body'],'Owner reply')
        preferences.save_preferences(self.db,self.doc,self.users[1],{'scope':'all','hidden_reviewers':[self.users[2]]})
        self.assertEqual(self.thread_ids(1),[self.threads[0]['thread_id']])

    def test_isolated_api_direct_ids_history_and_anchors(self):
        self.defaults(visibility_policy='isolated')
        self.assertEqual(self.thread_ids(1),[self.threads[0]['thread_id']])
        self.assertEqual(self.thread_ids(2),[self.threads[1]['thread_id']])
        self.assertEqual(len(self.thread_ids(0)),2)
        self.assertEqual(self.thread_ids(3),[])
        hidden=self.threads[1]
        client=self.clients[1]
        for method,url,payload in [
            ('get',f"/api/threads/{hidden['thread_id']}/targets",None),
            ('post',f"/api/threads/{hidden['thread_id']}/comments",{'body':'unauthorized'}),
            ('post',f"/api/threads/{hidden['thread_id']}/resolve",{}),
            ('patch',f"/api/comments/{hidden['comments'][0]['comment_id']}",{'body':'overwrite','expected_revision':1})]:
            response=getattr(client,method)(url,**({'json':payload} if payload is not None else {}))
            self.assertEqual(response.status_code,404,response.data)
        anchors=client.get(f'/api/versions/{self.versions[0]}/anchors').json['anchors']
        self.assertNotIn(hidden['targets'][0]['anchor']['anchor_id'],[a['anchor_id'] for a in anchors])
        data=json.dumps(self.context(1))
        self.assertNotIn(hidden['thread_id'],data)
        self.assertNotIn(self.users[2],data)

    def test_defaults_first_open_override_later_owner_change_reset_and_policy(self):
        self.defaults(default_spread=1,default_display='minimized',default_scope='mine')
        first=preferences.save_preferences(self.db,self.doc,self.users[1],{})
        self.assertEqual((first['spread'],first['display'],first['scope']),(1,'minimized','mine'))
        preferences.save_preferences(self.db,self.doc,self.users[1],{'spread':0,'display':'expanded','scope':'all'})
        self.defaults(default_spread=2,default_display='hidden')
        alice=preferences.read_preferences(self.db,self.doc,self.users[1])
        bob=preferences.save_preferences(self.db,self.doc,self.users[2],{})
        self.assertEqual((alice['spread'],alice['display']),(0,'expanded'))
        self.assertEqual((bob['spread'],bob['display']),(2,'hidden'))
        reset=preferences.save_preferences(self.db,self.doc,self.users[1],{},reset=True)
        self.assertEqual((reset['spread'],reset['display']),(2,'hidden'))
        preferences.save_preferences(self.db,self.doc,self.users[1],{'scope':'all'})
        self.defaults(visibility_policy='isolated')
        self.assertEqual(preferences.read_preferences(self.db,self.doc,self.users[1])['effective_scope'],'mine')
        self.assertEqual(preferences.read_preferences(self.db,self.doc,self.users[1])['scope'],'all')

    def test_viewer_can_save_preferences_but_cannot_create_feedback(self):
        response=self.clients[3].post(f'/api/documents/{self.doc}/viewer-preferences',json={'display':'hidden'})
        self.assertEqual(response.status_code,200,response.data)
        sid=self.section();self.place(sid)
        response=self.clients[3].post(f'/api/versions/{self.versions[0]}/sections/{sid}/responses',json={'body':'No'})
        self.assertEqual(response.status_code,403)

    def test_people_directory_is_only_content_authors_and_policy_filtered(self):
        people=self.context(1)['people']
        self.assertEqual({u['user_id'] for u in people},set(self.users[1:3]))
        self.assertTrue(all(set(u)=={'user_id','display_name','review_color'} for u in people))
        self.defaults(visibility_policy='isolated')
        self.assertEqual([u['user_id'] for u in self.context(1)['people']],[self.users[1]])

    def test_color_valid_stable_duplicate_allowed_and_invalid_rejected(self):
        palette=preferences.palette(self.db);self.assertEqual(len(palette),10)
        for user in self.users:
            from review.users import get_user
            self.assertIn(get_user(self.db,user)['review_color'],palette)
        for user in self.users[:2]:preferences.save_color(self.db,user,palette[3])
        response=self.clients[1].post('/account/review-color',data={'review_color':'#ffffff'})
        self.assertEqual(response.status_code,422)
        response=self.clients[1].post('/account/review-color',data={'review_color':palette[3]})
        self.assertEqual(response.status_code,303)
        thread=self.clients[0].get(f'/api/versions/{self.versions[0]}/threads').json['threads'][0]
        self.assertEqual(thread['review_color'],palette[3])

    def test_owner_settings_and_section_operations_are_forbidden_to_reviewers(self):
        for route in [f'/documents/{self.doc}/review-settings',f'/documents/{self.doc}/sections']:
            self.assertEqual(self.clients[1].get(route).status_code,403)
        self.assertEqual(self.clients[1].post(f'/api/documents/{self.doc}/sections',json={'name':'No'}).status_code,403)
        self.assertEqual(self.clients[1].post(f'/documents/{self.doc}/review-settings',data={'visibility_policy':'isolated'}).status_code,403)

    def test_sections_rename_reorder_prompt_archive_and_history_retention(self):
        sid=self.section();self.place(sid)
        rid=section_feedback.create_response(self.db,sid,self.versions[0],self.users[1],'Thoughts')
        sections.update_section(self.db,sid,self.users[0],{'name':'Interlude','position':3,'prompt':'Why?'})
        row=sections.list_sections(self.db,self.doc,self.versions[0])[0]
        self.assertEqual((row['name'],row['position'],row['prompt']),('Interlude',3,'Why?'))
        sections.update_section(self.db,sid,self.users[0],{'archive':True})
        self.assertEqual(sections.list_sections(self.db,self.doc,self.versions[0]),[])
        c=connect(self.db)
        try:self.assertEqual(c.execute('SELECT response_id FROM section_responses').fetchone()[0],rid)
        finally:c.close()

    def test_adjacent_ranges_gaps_overlap_and_stale_placement(self):
        first=self.section();self.place(first)
        second=self.section('Second')
        self.place(second,start_y=400,end_y=200)
        third=self.section('Third');self.place(third,start_page=2,end_page=2,end_y=None)
        with self.assertRaises(sections.SectionError):self.place(second,start_y=500,end_y=100,expected_revision=1)
        with self.assertRaises(sections.SectionConflict):self.place(first)
        with self.assertRaises(sections.SectionError):self.place(first,start_y=float('nan'),expected_revision=1)

    def test_new_version_unmapped_and_previous_placements_retained(self):
        sid=self.section();self.place(sid)
        row=sections.list_sections(self.db,self.doc,self.versions[1])[0]
        self.assertIsNone(row['placement'])
        self.assertEqual(row['previous_placements'][0]['version_id'],self.versions[0])

    def test_feedback_one_response_exact_version_and_replies(self):
        sid=self.section();payload=self.place(sid)
        rid=section_feedback.create_response(self.db,sid,self.versions[0],self.users[1],'My thoughts')
        with self.assertRaises(sections.SectionConflict):section_feedback.create_response(self.db,sid,self.versions[0],self.users[1],'Duplicate')
        section_feedback.reply(self.db,rid,self.users[0],'Owner reply')
        self.assertEqual(len(section_feedback.list_responses(self.db,self.versions[0],self.users[1])[0]['comments']),2)
        self.assertEqual(section_feedback.list_responses(self.db,self.versions[1],self.users[1]),[])
        sections.save_placement(self.db,sid,self.versions[1],self.users[0],payload)
        other=section_feedback.create_response(self.db,sid,self.versions[1],self.users[1],'New draft thoughts')
        self.assertNotEqual(rid,other)

    def test_feedback_conflict_revision_ownership_and_tombstone(self):
        sid=self.section();self.place(sid)
        rid=section_feedback.create_response(self.db,sid,self.versions[0],self.users[1],'Original')
        comment=section_feedback.list_responses(self.db,self.versions[0],self.users[1])[0]['comments'][0]
        cid=comment['comment_id'];url=f'/api/section-comments/{cid}'
        self.assertEqual(self.clients[2].patch(url,json={'body':'No','expected_revision':1}).status_code,403)
        self.assertEqual(self.clients[1].patch(url,json={'body':'Edited','expected_revision':1}).status_code,200)
        self.assertEqual(self.clients[1].patch(url,json={'body':'Stale','expected_revision':1}).status_code,409)
        self.assertEqual(self.clients[1].delete(url).status_code,200)
        c=connect(self.db)
        try:
            self.assertEqual([r[0] for r in c.execute('SELECT body FROM section_comment_revisions WHERE comment_id=? ORDER BY revision_number',(cid,))],['Original','Edited'])
            self.assertIsNone(c.execute('SELECT body FROM section_comments WHERE comment_id=?',(cid,)).fetchone()[0])
        finally:c.close()

    def test_section_feedback_shared_personal_and_isolated_privacy(self):
        sid=self.section();self.place(sid)
        ids=[section_feedback.create_response(self.db,sid,self.versions[0],u,'Private '+str(i)) for i,u in enumerate(self.users[1:3])]
        self.assertEqual(len(self.context(1)['responses']),2)
        preferences.save_preferences(self.db,self.doc,self.users[1],{'hidden_reviewers':[self.users[2]]})
        self.assertEqual([r['response_id'] for r in self.context(1)['responses']],[ids[0]])
        self.defaults(visibility_policy='isolated')
        self.assertEqual(len(self.context(0)['responses']),2)
        self.assertEqual([r['response_id'] for r in self.context(2)['responses']],[ids[1]])
        self.assertEqual(self.clients[1].post(f'/api/section-responses/{ids[1]}/comments',json={'body':'No'}).status_code,404)
        self.assertNotIn(ids[1],json.dumps(self.context(1)))

    def test_outline_confirmation_subset_and_atomic_overlap_rollback(self):
        base=dict(start_page=1,start_y=None,end_page=1,end_y=None,start_view_box=[0,0,612,792],end_view_box=[0,0,612,792],page_count=2,expected_revision=0)
        url=f'/api/versions/{self.versions[0]}/sections/outline'
        candidate={'name':'Edited outline title','prompt':'','placement':base}
        self.assertEqual(sections.list_sections(self.db,self.doc),[])
        self.assertEqual(self.clients[1].post(url,json={'candidates':[candidate]}).status_code,403)
        response=self.clients[0].post(url,json={'candidates':[candidate,candidate]})
        self.assertEqual(response.status_code,422,response.data)
        self.assertEqual(sections.list_sections(self.db,self.doc),[])
        self.assertEqual(self.clients[0].post(url,json={'candidates':[candidate]}).status_code,201)
        self.assertEqual(sections.list_sections(self.db,self.doc)[0]['name'],'Edited outline title')

    def test_csrf_all_new_mutation_families_and_default_deny(self):
        client=self.app.test_client();authenticate(client,self.users[0],grant_documents=False)
        sid=self.section();self.place(sid)
        rid=section_feedback.create_response(self.db,sid,self.versions[0],self.users[0],'Root')
        cid=self.context(0)['responses'][0]['comments'][0]['comment_id']
        for method,url in [('post',f'/documents/{self.doc}/review-settings'),('post','/account/review-color'),
            ('post',f'/api/documents/{self.doc}/viewer-preferences'),('delete',f'/api/documents/{self.doc}/viewer-preferences'),
            ('post',f'/api/documents/{self.doc}/sections'),('patch',f'/api/sections/{sid}'),
            ('post',f'/api/versions/{self.versions[0]}/sections/{sid}/placement'),('post',f'/api/versions/{self.versions[0]}/sections/shared-boundary'),('post',f'/api/versions/{self.versions[0]}/sections/outline'),
            ('post',f'/api/versions/{self.versions[0]}/sections/{sid}/responses'),('post',f'/api/section-responses/{rid}/comments'),
            ('patch',f'/api/section-comments/{cid}'),('delete',f'/api/section-comments/{cid}')]:
            self.assertEqual(getattr(client,method)(url,json={}).status_code,400,url)

    def test_isolated_socket_payload_contains_no_hidden_review_identifiers(self):
        socketio=self.app.extensions['socketio']
        socket=socketio.test_client(self.app,flask_test_client=self.clients[1])
        self.addCleanup(socket.disconnect)
        socket.emit('review.join',{'version_id':self.versions[0]});socket.get_received()
        self.defaults(visibility_policy='isolated')
        with self.app.app_context():notify_thread_changed(self.threads[1],'comment.created',self.threads[1]['comments'][0]['comment_id'])
        events=socket.get_received()
        self.assertEqual([e['name'] for e in events],['review.invalidated'])
        self.assertEqual(set(events[0]['args'][0]),{'schema_version','version_id'})

    def test_presence_single_or_adjacent_spread_and_latest_tab_only(self):
        socketio=self.app.extensions['socketio'];registry=self.app.extensions['review_presence']
        sockets=[socketio.test_client(self.app,flask_test_client=self.clients[1]) for _ in range(2)]
        for socket in sockets:
            self.addCleanup(socket.disconnect);socket.emit('review.join',{'version_id':self.versions[0]})
        self.assertTrue(sockets[0].emit('review.page',{'page':1,'pages':[1,2]},callback=True)['ok'])
        self.assertFalse(sockets[0].emit('review.page',{'page':1,'pages':[1,2,3]},callback=True)['ok'])
        self.assertFalse(sockets[0].emit('review.page',{'page':1,'pages':[1,3]},callback=True)['ok'])
        self.assertTrue(sockets[1].emit('review.page',{'page':2,'pages':[2]},callback=True)['ok'])
        self.assertEqual(registry.snapshot(self.versions[0])['reviewers'][0]['pages'],[2])

    def test_revoked_idle_socket_receives_no_new_review_or_presence(self):
        from review.realtime import notify_version_changed,notify_user_presentation_changed
        io=self.app.extensions['socketio']
        socket=io.test_client(self.app,flask_test_client=self.clients[2]);self.addCleanup(socket.disconnect)
        socket.emit('review.join',{'version_id':self.versions[0]});socket.get_received()
        with transaction(self.db) as c:c.execute('DELETE FROM document_access WHERE document_id=? AND user_id=?',(self.doc,self.users[2]))
        with self.app.app_context():
            notify_version_changed(self.versions[0]);notify_user_presentation_changed(self.users[0])
        self.assertEqual(socket.get_received(),[])

    def test_sqlite_integrity_checks_and_cross_document_placement_guard(self):
        sid=self.section();self.place(sid)
        c=connect(self.db)
        try:
            self.assertEqual(c.execute('PRAGMA quick_check').fetchone()[0],'ok')
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
            with self.assertRaises(sqlite3.IntegrityError):c.execute("UPDATE users SET review_color='#ffffff'")
        finally:c.close()

    def test_migration8_preserves_existing_rows_and_backfills_stable_palette(self):
        legacy=self.root/'legacy7.sqlite3';c=connect(legacy)
        c.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,name TEXT UNIQUE,applied_at TEXT)')
        for version,name,sql in MIGRATIONS[:7]:
            c.executescript(sql);c.execute('INSERT INTO schema_migrations VALUES(?,?,?)',(version,name,'fixture'));c.commit()
        c.close()
        user=create_user(legacy,'Legacy')['user_id'];create_document(legacy,'Legacy document',owner_id=user)
        c=connect(legacy)
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='schema_migrations'")]
        columns={t:','.join(r['name'] for r in c.execute(f'PRAGMA table_info({t})')) for t in tables}
        before={t:[tuple(r) for r in c.execute(f'SELECT {columns[t]} FROM {t} ORDER BY 1')] for t in tables};c.close()
        init_database(legacy)
        c=connect(legacy)
        color=c.execute('SELECT review_color FROM users').fetchone()[0];c.close()
        init_database(legacy);c=connect(legacy)
        try:
            for t in tables:self.assertEqual([tuple(r) for r in c.execute(f'SELECT {columns[t]} FROM {t} ORDER BY 1')],before[t])
            self.assertEqual(c.execute('SELECT review_color FROM users').fetchone()[0],color)
            self.assertIn(color,preferences.palette(legacy))
            for check in ['quick_check','integrity_check']:self.assertEqual(c.execute('PRAGMA '+check).fetchone()[0],'ok')
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:c.close()

    def test_policy_tightening_redacts_saved_hidden_person_ids(self):
        preferences.save_preferences(self.db,self.doc,self.users[1],{'hidden_reviewers':[self.users[2]]})
        self.defaults(visibility_policy='isolated')
        data=self.context(1)
        self.assertEqual(data['preferences']['hidden_reviewers'],[])
        self.assertNotIn(self.users[2],json.dumps(data))

    def test_tableau_palette_upgrade_preserves_users_and_replaces_all_old_choices(self):
        legacy=self.root/'legacy8.sqlite3';c=connect(legacy)
        c.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,name TEXT UNIQUE,applied_at TEXT)')
        for version,name,sql in MIGRATIONS[:8]:
            c.executescript(sql);c.execute('INSERT INTO schema_migrations VALUES(?,?,?)',(version,name,'fixture'));c.commit()
        old_colors=[r[0] for r in c.execute('SELECT color FROM review_palette')];c.close()
        for index,color in enumerate(old_colors):
            user=create_user(legacy,f'Palette fixture {index}')['user_id']
            with transaction(legacy) as c:c.execute('UPDATE users SET review_color=? WHERE user_id=?',(color,user))
        c=connect(legacy)
        columns=','.join(r['name'] for r in c.execute('PRAGMA table_info(users)') if r['name']!='review_color')
        before=[tuple(r) for r in c.execute(f'SELECT {columns} FROM users ORDER BY user_id')];c.close()
        init_database(legacy)
        expected=['#4e79a7','#f28e2c','#e15759','#76b7b2','#59a14f','#edc949','#af7aa1','#ff9da7','#9c755f','#bab0ab']
        self.assertEqual(preferences.palette(legacy),expected)
        c=connect(legacy)
        try:
            self.assertEqual([tuple(r) for r in c.execute(f'SELECT {columns} FROM users ORDER BY user_id')],before)
            after=[tuple(r) for r in c.execute('SELECT user_id,review_color FROM users ORDER BY user_id')]
            self.assertTrue(all(color in expected for _,color in after))
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
            self.assertEqual(c.execute('PRAGMA quick_check').fetchone()[0],'ok')
            with self.assertRaises(sqlite3.IntegrityError):c.execute('UPDATE users SET review_color=?',(old_colors[0],))
        finally:c.close()
        init_database(legacy);c=connect(legacy)
        try:self.assertEqual([tuple(r) for r in c.execute('SELECT user_id,review_color FROM users ORDER BY user_id')],after)
        finally:c.close()
        self.assertIn(create_user(legacy,'New palette user')['review_color'],expected)

    def test_mutation_rechecks_policy_inside_transaction(self):
        from unittest.mock import patch
        from review import routes
        original=routes.add_comment
        def tighten(*args,**kwargs):
            self.defaults(visibility_policy='isolated')
            return original(*args,**kwargs)
        with patch.object(routes,'add_comment',side_effect=tighten):
            response=self.clients[1].post(f"/api/threads/{self.threads[1]['thread_id']}/comments",json={'body':'Must not be written'})
        self.assertEqual(response.status_code,404)
        c=connect(self.db)
        try:self.assertFalse(c.execute("SELECT 1 FROM comments WHERE body='Must not be written'").fetchone())
        finally:c.close()

    def test_preferences_get_never_initializes_and_unauthorized_version_context_is_404(self):
        preferences.read_preferences(self.db,self.doc,self.users[1])
        c=connect(self.db)
        try:self.assertEqual(c.execute('SELECT count(*) FROM viewer_preferences').fetchone()[0],0)
        finally:c.close()
        other=create_user(self.db,'No grants')['user_id']
        client=self.app.test_client();authenticate(client,other,grant_documents=False)
        self.assertEqual(client.get(f'/api/versions/{self.versions[0]}/review-context').status_code,404)

    def test_section_identity_cross_document_and_revision_immutability(self):
        sid=self.section();payload=self.place(sid)
        other=create_document(self.db,'Other',owner_id=self.users[0])
        other_section=sections.create_section(self.db,other,self.users[0],{'name':'Other section'})
        response=self.clients[0].post(f'/api/versions/{self.versions[0]}/sections/{other_section}/placement',json=payload)
        self.assertEqual(response.status_code,404)
        rid=section_feedback.create_response(self.db,sid,self.versions[0],self.users[1],'Immutable original')
        c=connect(self.db)
        try:
            for sql in ["UPDATE section_responses SET author_id=author_id", "UPDATE section_comment_revisions SET body='No'",'DELETE FROM section_comment_revisions']:
                with self.assertRaises(sqlite3.IntegrityError):c.execute(sql)
        finally:c.close()


if __name__=='__main__':unittest.main()
