"""Ordered normal comments with section groups inserted near their endpoints."""
import time
from tests.viewer_acceptance import PDF, SELECT, viewport, change, screenshot
from tests.beta_c2_acceptance import request


def run_section_card_packing(cdp,a,b,fixture,base):
    def ev(script):return cdp.evaluate(a,script)
    def wait(script):return cdp.wait(a,script)
    viewport(cdp,a,1600,1000)
    ev(PDF+'.currentScale=1')
    wait(PDF+'.getPageView(0).textLayer?.div?.querySelector("span")!==null')
    ev(SELECT)
    ev("""(async()=>{const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const c=JSON.parse(document.querySelector('#anchor-config').textContent),anchor=captureTextSelection(w,w.PDFViewerApplication);
      for(let i=0;i<5;i++){
        const placement=structuredClone(anchor);
        placement.segments[0].rectangles=[[10,682-i*2,110,700-i*2]];
        const body='Normal comment '+i+' checks wording and continuity around this passage.';
        await createThread(c.threadsUrl,placement,i===1?body+' '+body.repeat(15):body);
      }
      w.getSelection().removeAllRanges();
    })()""")
    wait("document.querySelectorAll('#thread-list .thread-card').length===5")
    time.sleep(.2)
    baseline=ev("[...document.querySelectorAll('#thread-list .thread-card')].sort((a,b)=>a.offsetTop-b.offsetTop).map(c=>({top:c.offsetTop,height:c.offsetHeight}))")
    doc,version=fixture['document_id'],fixture['versions'][0]
    sid=request(cdp,a,f'/api/documents/{doc}/sections','POST',{'name':'Section end feedback'})['data']['section_id']
    box=ev(PDF+'.getPageView(0).viewport.viewBox')
    assert request(cdp,a,f'/api/versions/{version}/sections/{sid}/placement','POST',{
        'start_page':1,'end_page':1,'start_y':None,'end_y':150,'start_view_box':box,'end_view_box':box,'page_count':2,'expected_revision':0})['status']==200
    for session in [a,b]:
        assert request(cdp,session,f'/api/versions/{version}/sections/{sid}/responses','POST',{'body':'Section feedback with room to consider the ending.'})['status']==201
    wait("document.querySelectorAll('.section-feedback-card').length===2")
    check="""(()=>{const cards=[...document.querySelectorAll('#thread-list .thread-card')].filter(c=>!c.hidden),
      sections=cards.filter(c=>c.classList.contains('section-feedback-card')),normal=cards.filter(c=>!c.classList.contains('section-feedback-card'));
      const ordered=[...cards].sort((a,b)=>a.offsetTop-b.offsetTop),p=PDF.getPageView(0),r=p.div.getBoundingClientRect(),
      end=r.top+p.div.clientTop+p.viewport.convertToViewportPoint(0,150)[1]*p.div.clientHeight/p.viewport.height+PDF.container.scrollTop;
      return {bottom:Math.max(...sections.map(c=>c.offsetTop+c.offsetHeight)),end,
        nonoverlap:ordered.every((c,i)=>!i||c.offsetTop>=ordered[i-1].offsetTop+ordered[i-1].offsetHeight+5),
        height:sections.reduce((sum,c)=>sum+c.offsetHeight,0)+6*(sections.length-1),
        normalOrder:normal.sort((a,b)=>a.offsetTop-b.offsetTop).map(c=>Number(c.textContent.match(/Normal comment ([0-9])/)[1])),
        contiguous:ordered.indexOf(sections[0])===ordered.indexOf(sections[1])-1||ordered.indexOf(sections[1])===ordered.indexOf(sections[0])-1,
        width:sections[0].offsetWidth-normal[0].offsetWidth,
        margins:cards.every(c=>getComputedStyle(c.querySelector('.thread-controls')).marginTop==='0px'),
        before:normal.some(c=>c.offsetTop+c.offsetHeight<=Math.min(...sections.map(s=>s.offsetTop))),
        after:normal.some(c=>c.offsetTop>=Math.max(...sections.map(s=>s.offsetTop+s.offsetHeight)))};})()""".replace('PDF',PDF)
    def verify():
        time.sleep(.25)
        result=ev(check)
        assert result['normalOrder']==list(range(5)) and result['contiguous'],result
        assert result['nonoverlap'] and result['margins'] and result['width']==30,result
        return result
    result=verify()
    # Compare every insertion boundary in the original ordinary-comment list.
    # A tall earlier comment stays ahead of all later short comments.
    choices=[]
    for index in range(len(baseline)+1):
        lower=baseline[index-1]['top']+baseline[index-1]['height']+6 if index else 8
        upper=baseline[index]['top']-6-result['height'] if index<len(baseline) else float('inf')
        preferred=result['end']-result['height']
        top=max(lower,min(preferred,upper)) if upper>=lower else lower
        choices.append(abs(top+result['height']-result['end']))
    assert abs(abs(result['bottom']-result['end'])-min(choices))<2,(result,choices)
    original=ev("[...document.querySelectorAll('#thread-list .thread-card')].map(c=>[c.dataset.threadId,c.style.top])")
    ev(PDF+'.container.scrollTop+=80');time.sleep(.2)
    assert ev("[...document.querySelectorAll('#thread-list .thread-card')].map(c=>[c.dataset.threadId,c.style.top])")==original
    ev(PDF+'.container.scrollTop=0');time.sleep(.2)
    screenshot(cdp,a,'section-feedback-ordered-insertion')
    # Selection preserves the ordinary list, including a tall early comment.
    ev("document.querySelector('#thread-list .thread-card:not(.section-feedback-card)').click()")
    verify()
    # Growing a section reply area re-evaluates its insertion without reordering ordinary cards.
    ev("document.querySelector('.section-feedback-card .reply-control').click()")
    wait("document.querySelector('.section-feedback-card .thread-reply-form:not([hidden])')!==null")
    verify()
    for spread in [0,1,2]:
        change(cdp,a,'#review-spread',spread)
        for scale in [.75,1.25]:
            ev(PDF+f'.currentScale={scale}')
            verify()
    change(cdp,a,'#comments-visibility','minimized')
    time.sleep(.2)
    assert ev("[...document.querySelectorAll('#thread-list .thread-marker')].some(c=>!c.hidden)")
    change(cdp,a,'#comments-visibility','expanded')
    verify()
    # A later section inserts after the earlier section group without changing
    # the relative order of any ordinary comments.
    sid2=request(cdp,a,f'/api/documents/{doc}/sections','POST',{'name':'Second section feedback'})['data']['section_id']
    assert request(cdp,a,f'/api/versions/{version}/sections/{sid2}/placement','POST',{
        'start_page':2,'end_page':2,'start_y':None,'end_y':None,'start_view_box':box,'end_view_box':box,'page_count':2,'expected_revision':0})['status']==200
    wait("document.querySelectorAll('.section-feedback-card').length===3")
    time.sleep(.2)
    multiple=ev("""(()=>{const cards=[...document.querySelectorAll('#thread-list .thread-card')].sort((a,b)=>a.offsetTop-b.offsetTop);
      return {order:cards.filter(c=>!c.classList.contains('section-feedback-card')).map(c=>Number(c.textContent.match(/Normal comment ([0-9])/)[1])),
        nonoverlap:cards.every((c,i)=>!i||c.offsetTop>=cards[i-1].offsetTop+cards[i-1].offsetHeight+5),
        sections:cards.filter(c=>c.classList.contains('section-feedback-card')).map(c=>c.textContent.includes('Second section feedback')?'second':'first')};})()""")
    assert multiple==dict(order=list(range(5)),nonoverlap=True,sections=['first','first','second']),multiple
    print('PASS preserved normal-comment order, closest section insertion, grouped responses, scroll stability, selection/reply resizing, width/margin, zoom/spreads and visibility modes',flush=True)
