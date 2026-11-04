"""Rendering must not paint nested rectangles twice within one anchor."""
import time
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
    print('PASS nested/exact duplicate rectangles paint once per anchor, disjoint coverage retained, immutable geometry, zoom/rotation, click selection and distinct overlapping conversations',flush=True)
