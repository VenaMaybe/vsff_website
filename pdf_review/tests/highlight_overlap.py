"""Rendering must not paint nested rectangles twice within one anchor."""
import time
import json
from tests.viewer_acceptance import PDF, SELECT, viewport, screenshot


def run_highlight_overlap(cdp,a,fixture):
    def ev(script):return cdp.evaluate(a,script)
    def wait(script):return cdp.wait(a,script)
    viewport(cdp,a,1440,900)
    ev(PDF+'.currentScale=1')
    wait(PDF+'.getPageView(0).textLayer?.div?.querySelector("span")!=null')
    ev(SELECT)
    saved=ev("""(async()=>{const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const c=JSON.parse(document.querySelector('#anchor-config').textContent),anchor=captureTextSelection(w,w.PDFViewerApplication);
      const r=anchor.segments[0].rectangles[0];
      const inner=[r[0],r[1]+.625,r[2],r[3]-.625],separate=[r[0],r[1]-30,r[2]/2,r[3]-30];
      anchor.segments[0].rectangles=[inner,r,[...r],separate];
      await createThread(c.threadsUrl,anchor,'Nested range rectangle regression');
      w.getSelection().removeAllRanges();return anchor.segments[0].rectangles;
    })()""")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight').length===2")
    # Historical geometry remains unchanged, including the duplicate and inner box.
    canonical=ev("fetch(JSON.parse(document.querySelector('#anchor-config').textContent).threadsUrl).then(r=>r.json()).then(d=>d.threads[0].targets[0].anchor)")
    assert canonical['segments'][0]['rectangles']==saved
    anchor_id=canonical['anchor_id']
    for scale in [.5,1,1.5,2]:
        ev(PDF+f'.currentScale={scale}')
        for rotation in [0,90]:
            ev(PDF+f'.pagesRotation={rotation}')
            time.sleep(.2)
            assert ev("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight').length===2")
    ev(PDF+'.pagesRotation=0;'+PDF+'.currentScale=1')
    ev("document.querySelector('iframe').contentDocument.querySelector('.pdf-review-thread-highlight').click()")
    wait("document.querySelector('.thread-card.active')!==null")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight.is-active').length===2")
    ev("document.querySelector('iframe').contentDocument.querySelector('.pdf-review-thread-highlight').scrollIntoView({block:'center'})")
    time.sleep(.2)
    screenshot(cdp,a,'highlight-contained-rectangle')
    # Separate comments on the same text must remain separate clickable anchors.
    ev(SELECT)
    ev("""(async()=>{const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const c=JSON.parse(document.querySelector('#anchor-config').textContent);
      await createThread(c.threadsUrl,captureTextSelection(w,w.PDFViewerApplication),'Separate overlapping conversation');w.getSelection().removeAllRanges();})()""")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight').length===3")
    ids=ev("[...new Set([...document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight')].map(e=>e.dataset.anchorId))]")
    assert len(ids)==2 and anchor_id in ids,ids
    # Add a third conversation covering only the left half, then use genuine
    # pointer input to exercise hit testing through overlapping DOM elements.
    ev(SELECT)
    ev("""(async()=>{const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const c=JSON.parse(document.querySelector('#anchor-config').textContent),anchor=captureTextSelection(w,w.PDFViewerApplication);
      const r=anchor.segments[0].rectangles[0];r[2]=(r[0]+r[2])/2;
      await createThread(c.threadsUrl,anchor,'Third partial overlap');w.getSelection().removeAllRanges();})()""")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight').length===4")
    ev("document.querySelector('.viewer-title').click()")
    wait("document.querySelector('.thread-card.active')===null")
    def point(fraction=.25,disjoint=False):
        selector='.pdf-review-thread-highlight[data-anchor-id="'+anchor_id+'"]'
        ev("document.querySelector('iframe').contentDocument.querySelectorAll("+json.dumps(selector)+")["+('1' if disjoint else '0')+"].scrollIntoView({block:'center'})")
        time.sleep(.2)
        return ev("""(()=>{const f=document.querySelector('iframe'),d=f.contentDocument,
          r=d.querySelectorAll(SELECTOR)[INDEX].getBoundingClientRect(),b=f.getBoundingClientRect(),
          rotated=f.contentWindow.PDFViewerApplication.pdfViewer.pagesRotation%180!==0,
          x=r.left+r.width*(rotated ? .5 : FRACTION),y=r.top+r.height*(rotated ? FRACTION : .5);
          return {x:x+b.left,y:y+b.top,ids:[...new Set(d.elementsFromPoint(x,y).filter(e=>e.classList.contains('pdf-review-thread-highlight')).map(e=>e.dataset.threadId))]};})()""".replace('SELECTOR',json.dumps(selector)).replace('INDEX','1' if disjoint else '0').replace('FRACTION',str(fraction)))
    def click(p,expected):
        for kind in ['mousePressed','mouseReleased']:
            cdp.call('Input.dispatchMouseEvent',dict(type=kind,x=p['x'],y=p['y'],button='left',clickCount=1),a)
        wait("document.querySelector('.thread-card.active')?.dataset.threadId==="+json.dumps(expected))
        wait("[...document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight.is-active')].some(e=>e.dataset.threadId==="+json.dumps(expected)+")")
    p=point()
    assert len(p['ids'])==3,p
    for index in range(4):click(p,p['ids'][index%3])
    # Clicking another part of the line cycles only through coverage there.
    p=point(.75)
    assert len(p['ids'])==2,p
    current=ev("document.querySelector('.thread-card.active').dataset.threadId")
    offset=p['ids'].index(current) if current in p['ids'] else -1
    for index in range(1,4):click(p,p['ids'][(offset+index)%2])
    p=point(disjoint=True)
    assert len(p['ids'])==1,p
    click(p,p['ids'][0]);click(p,p['ids'][0])
    for scale,rotation in [(1.5,0),(1,90)]:
        ev(PDF+f'.currentScale={scale};'+PDF+f'.pagesRotation={rotation}')
        time.sleep(.3)
        p=point()
        assert len(p['ids'])==3,p
        current=ev("document.querySelector('.thread-card.active').dataset.threadId")
        offset=p['ids'].index(current) if current in p['ids'] else -1
        for index in range(1,4):click(p,p['ids'][(offset+index)%3])
    print('PASS contained-rectangle rendering, immutable geometry, repeated overlap cycling/wraparound, partial and single coverage, distinct threads, zoom and rotation',flush=True)
