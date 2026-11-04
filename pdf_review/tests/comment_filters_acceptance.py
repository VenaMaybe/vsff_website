"""Reviewer filtering in the shared left utility-card shell."""
import json
import time
from tests.viewer_acceptance import PDF, SELECT, viewport, screenshot


def run_comment_filters(cdp,a,b,fixture,base):
    def ev(script,session=a):return cdp.evaluate(session,script)
    def wait(script,session=a):return cdp.wait(session,script)
    def mode(value,session=a):ev("document.querySelector('.comment-filter-panel input[value="+value+"]').click()",session)
    def reload(session=a):
        ev('window.filtersReloading=true',session);cdp.call('Page.reload',{},session)
        wait("!window.filtersReloading&&document.querySelector('#realtime-status')?.textContent==='Live'",session)
    viewport(cdp,a,1600,1100)
    for session,body in [(a,'Alpha filter fixture'),(b,'Beta filter fixture')]:
        ev(SELECT,session)
        ev("""(async()=>{const w=document.querySelector('iframe').contentWindow;
          const {captureTextSelection}=await import('/static/review/anchor_selection.js');
          const {createThread}=await import('/static/review/thread_api.js');
          const c=JSON.parse(document.querySelector('#anchor-config').textContent);
          await createThread(c.threadsUrl,captureTextSelection(w,w.PDFViewerApplication),BODY);w.getSelection().removeAllRanges();})()""".replace('BODY',json.dumps(body)),session)
    for session in [a,b]:
        wait("document.querySelectorAll('#thread-list .thread-card').length===2",session)
        ev("document.querySelector('[data-comment-filters]').click()",session)
        assert ev("document.querySelector('.comment-filter-panel')!==null&&!document.querySelector('#comments-menu .review-people')",session)
    mode('mine')
    wait("document.querySelector('#thread-list').textContent.includes('Alpha filter fixture')&&!document.querySelector('#thread-list').textContent.includes('Beta filter fixture')")
    mode('people')
    wait("document.querySelectorAll('.filter-reviewers input').length===2")
    uid=fixture['users'][0]['user_id']
    ev("document.querySelector('.filter-reviewers input[data-reviewer-id='+CSS.escape("+json.dumps(uid)+")+']').click()")
    wait("!document.querySelector('#thread-list').textContent.includes('Alpha filter fixture')&&document.querySelector('#thread-list').textContent.includes('Beta filter fixture')")
    # Keyboard focus survives canonical refresh; checkboxes do not act like menus.
    ev("document.querySelector('.filter-reviewers input').focus()")
    assert ev("document.querySelector('.comment-filter-panel').contains(document.activeElement)")
    screenshot(cdp,a,'comment-filter-left-card')
    # All four tools can coexist and be restored, including a pinned filter card.
    for selector in ['[data-sections]','[data-review-settings]','[data-pdf-control=viewFindButton]']:
        ev('document.querySelector('+json.dumps(selector)+').click()')
    wait("document.querySelector('.settings-form')!==null&&document.querySelector('.sections-workspace')!==null")
    ev("document.querySelector('.comment-filter-panel .left-card-pin').click()")
    reload()
    assert ev("document.querySelectorAll('.left-card').length===4&&document.querySelector('.comment-filter-panel').dataset.pinned==='true'")
    assert ev("document.querySelector('.comment-filter-panel input[value=people]').checked")
    assert ev("!document.querySelector('#thread-list').textContent.includes('Alpha filter fixture')&&document.querySelector('#thread-list').textContent.includes('Beta filter fixture')")
    mode('all')
    wait("document.querySelectorAll('#thread-list .thread-card').length===2")
    assert ev("document.querySelector('.filter-reviewers').hidden")
    mode('people')
    assert ev("[...document.querySelectorAll('.filter-reviewers input')].every(i=>i.checked)")
    # Fast edits retain the optimistic checklist while canonical reads finish.
    ev("document.querySelectorAll('.filter-reviewers input').forEach(i=>i.click())")
    wait("document.querySelectorAll('#thread-list .thread-card').length===0")
    mode('all');wait("document.querySelectorAll('#thread-list .thread-card').length===2")
    doc=fixture['document_id']
    # Downgrade B to reviewer, then enforce isolated review using the real owner form.
    ev("""(async()=>{const data=new URLSearchParams({csrf_token:document.querySelector('meta[name=csrf-token]').content,user_id:USER,role:'reviewer',action:'grant'});const r=await fetch(ENDPOINT,{method:'POST',body:data});if(!r.ok)throw new Error('Fixture grant failed');})()""".replace('USER',json.dumps(fixture['users'][1]['user_id'])).replace('ENDPOINT',json.dumps(f'/documents/{doc}/access')))
    ev("document.querySelector('[name=visibility_policy]').value='isolated';document.querySelector('.settings-form').requestSubmit()")
    wait("document.querySelector('.comment-filter-policy').textContent.includes('Isolated review')",b)
    assert ev("document.querySelector('.comment-filter-panel input[value=mine]').checked&&document.querySelector('.comment-filter-panel input[value=all]').disabled&&document.querySelector('.comment-filter-panel input[value=people]').disabled&&document.querySelector('.filter-reviewers').hidden",b)
    wait("!document.querySelector('#thread-list').textContent.includes('Alpha filter fixture')&&document.querySelector('#thread-list').textContent.includes('Beta filter fixture')",b)
    # Closing stays closed after reload. Mobile opening exposes the left gutter.
    ev("document.querySelector('.comment-filter-panel .dialog-header button:last-child').click()")
    reload()
    assert ev("document.querySelector('.comment-filter-panel')===null")
    for selector in ['.settings-panel','.sections-panel','.search-panel']:
        ev("document.querySelector("+json.dumps(selector)+")?.querySelector('.dialog-header button:last-child').click()")
    viewport(cdp,a,390,844)
    ev(PDF+".container.scrollLeft=200;document.querySelector('[data-comment-filters]').click()")
    time.sleep(.25)
    assert ev("(()=>{const r=document.querySelector('.comment-filter-panel').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;})()")
    screenshot(cdp,a,'comment-filter-mobile')
    print('PASS filter card All/Mine/reviewer subset, rapid edits, persistent preferences, four-card restore/pin, isolated review, close persistence and mobile opening',flush=True)
