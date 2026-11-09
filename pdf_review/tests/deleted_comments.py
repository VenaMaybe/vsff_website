"""Deleted content is hidden while live replies and stored history survive."""
from tests.viewer_acceptance import PDF, SELECT, viewport
from tests.beta_c2_acceptance import request


def run_deleted_comments(cdp,a,b,fixture):
    def ev(script): return cdp.evaluate(a,script)
    def both(expression):
        for session in [a,b]: cdp.wait(session,expression)
    viewport(cdp,a,1440,900)
    ev(PDF+'.currentScale=1')
    cdp.wait(a,PDF+'.getPageView(0).textLayer?.div?.querySelector("span")!=null')
    ev(SELECT)
    ev("""(async()=>{
      const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread,addReply}=await import('/static/review/thread_api.js');
      const c=JSON.parse(document.querySelector('#anchor-config').textContent);
      const anchor=captureTextSelection(w,w.PDFViewerApplication);
      const lone=await createThread(c.threadsUrl,anchor,'Lone deleted fixture');
      let thread=await createThread(c.threadsUrl,anchor,'Root deleted fixture');
      const url=c.threadCommentsUrlTemplate.replace('__THREAD_ID__',thread.thread_id);
      thread=await addReply(url,'Deleted reply fixture');
      thread=await addReply(url,'Surviving reply fixture');
      window.deletionFixture={lone,thread};w.getSelection().removeAllRanges();
    })()""")
    both("document.querySelectorAll('#thread-list .thread-card').length===2")
    ids=ev("({lone:deletionFixture.lone.comments[0].comment_id,comments:deletionFixture.thread.comments.map(c=>c.comment_id)})")
    assert request(cdp,a,f"/api/comments/{ids['lone']}",'DELETE')['status']==200
    both("document.querySelectorAll('#thread-list .thread-card').length===1&&!document.querySelector('#thread-list').textContent.includes('Lone deleted fixture')")
    assert request(cdp,a,f"/api/comments/{ids['comments'][1]}",'DELETE')['status']==200
    both("document.querySelectorAll('#thread-list .thread-comment').length===2&&!document.querySelector('#thread-list').textContent.includes('This comment was deleted.')")
    both("document.querySelector('.thread-controls').textContent.includes('2 comments')&&document.querySelector('.thread-marker-count').textContent==='2'")
    assert request(cdp,a,f"/api/comments/{ids['comments'][0]}",'DELETE')['status']==200
    both("document.querySelector('#thread-list').textContent.includes('This comment was deleted.')&&document.querySelector('#thread-list').textContent.includes('Surviving reply fixture')&&document.querySelector('.thread-controls').textContent.includes('1 comment')&&!document.querySelector('.thread-marker-count')")
    assert request(cdp,a,f"/api/comments/{ids['comments'][2]}",'DELETE')['status']==200
    both("document.querySelectorAll('#thread-list .thread-card,#thread-list .thread-marker').length===0&&document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight:not([hidden])').length===0")
    # The section prompt still exists before the reader writes anything.
    doc,version=fixture['document_id'],fixture['versions'][0]
    sid=request(cdp,a,f'/api/documents/{doc}/sections','POST',{'name':'Deletion section fixture'})['data']['section_id']
    box=ev(PDF+'.getPageView(0).viewport.viewBox')
    assert request(cdp,a,f'/api/versions/{version}/sections/{sid}/placement','POST',dict(start_page=1,end_page=1,start_y=None,end_y=None,start_view_box=box,end_view_box=box,page_count=2,expected_revision=0))['status']==200
    both("document.querySelector('.section-feedback-card .reply-control')?.textContent==='Add response'")
    response=request(cdp,a,f'/api/versions/{version}/sections/{sid}/responses','POST',{'body':'Section deleted fixture'})
    assert response['status']==201
    both("document.querySelector('#thread-list').textContent.includes('Section deleted fixture')")
    comment=ev("(async()=>{const c=JSON.parse(document.querySelector('#anchor-config').textContent);const data=await (await fetch(c.contextUrl)).json();return data.responses.find(r=>r.section_id==='"+sid+"').comments[0].comment_id;})()")
    assert request(cdp,a,f'/api/section-comments/{comment}','DELETE')['status']==200
    both("!document.querySelector('#thread-list').textContent.includes('Section deleted fixture')&&!document.querySelector('#thread-list').textContent.includes('This comment was deleted.')")
    assert ev("!document.querySelector('.section-feedback-card')")
    print('PASS deleted replies and empty threads disappear, live replies retain root context, counts/highlights update for both readers, section prompts preserved',flush=True)
