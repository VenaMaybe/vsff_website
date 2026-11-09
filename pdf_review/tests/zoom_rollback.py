"""Replay the stale scroll ordering observed in the physical iPhone trace.

Chrome does not reproduce WebKit's asynchronous rollback by itself. Inject an
older camera between native pinch updates and compare with the same clean run.
No user document, comment content or raw phone trace is used by this fixture.
"""
from tests.viewer_acceptance import change
from tests.comment_touch_zoom import seed_touch_comment


def run_zoom_rollback(cdp, session):
    cdp.call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=3, mobile=True), session)
    cdp.call('Emulation.setTouchEmulationEnabled', dict(enabled=True, maxTouchPoints=2), session)
    ev = lambda script: cdp.evaluate(session, script)
    for page in [1, 109, 120]:
        seed_touch_comment(cdp, session, page)
    worst = 0
    for mode in ['hidden', 'mobile', 'minimized', 'expanded']:
        change(cdp, session, '#comments-visibility', mode)
        for page in [1, 109, 120]:
            result = ev("""(async()=>{
              const app=document.querySelector('iframe').contentWindow.PDFViewerApplication,
                pdf=app.pdfViewer,s=pdf.container,w=s.ownerDocument.defaultView;
              const pause=()=>new Promise(r=>setTimeout(r,180));
              const run=async(inject)=>{
                pdf.endZoomGesture();app.reviewPdfTouchActive=false;
                pdf.currentScale=1;pdf.currentPageNumber=PAGE;
                const p=pdf.getPageView(PAGE-1),r=p.div.getBoundingClientRect();
                s.scrollLeft+=r.left+r.width/2-195;s.scrollTop+=r.top+r.height/2-300;
                await pause();app.reviewPdfTouchActive=true;pdf.beginZoomGesture();
                const positions=[],history=[];
                for(let i=0;i<32;i++){
                  const old=[s.scrollLeft,s.scrollTop];
                  // Zoom out/in repeatedly, including native midpoint-only pans.
                  app.updateZoom(null,i%16<8?.96:1/.96,[195,300],[.25,-.5]);
                  pdf.panBy(.125,.25);
                  positions.push([s.scrollLeft-app.reviewStage.origin,s.scrollTop]);
                  history.push(old);
                  if(inject&&i>1){
                    const stale=history[i-2];s.scrollLeft=stale[0];s.scrollTop=stale[1];
                  }
                }
                // A delayed scroll acknowledgement while fingers are stationary
                // must also reconcile, without waiting for another scale change.
                s.dispatchEvent(new w.Event('scroll'));
                await new Promise(r=>w.requestAnimationFrame(()=>w.requestAnimationFrame(r)));
                positions.push([s.scrollLeft-app.reviewStage.origin,s.scrollTop]);
                if(inject){s.scrollLeft=history[0][0];s.scrollTop=history[0][1];}
                pdf.endZoomGesture();
                positions.push([s.scrollLeft-app.reviewStage.origin,s.scrollTop]);
                app.reviewPdfTouchActive=false;
                await pause();
                positions.push([s.scrollLeft-app.reviewStage.origin,s.scrollTop]);
                // Once released, ordinary browser-owned scrolling must stay free.
                s.scrollTop+=40;const free=s.scrollTop;
                s.dispatchEvent(new w.Event('scroll'));await pause();
                if(Math.abs(s.scrollTop-free)>1)throw new Error('Post-pinch scroll was overridden');
                return positions;
              };
              const clean=await run(false),stale=await run(true);
              return {error:Math.max(...clean.map((p,i)=>Math.hypot(p[0]-stale[i][0],p[1]-stale[i][1]))),clean,stale};
            })()""".replace('PAGE', str(page)))
            worst = max(worst, result['error'])
            assert result['error'] < 2, ('stale scroll compounded into pinch', mode, page, result)
    print(f'PASS injected iPhone scroll rollback: pages 1/109/120, four modes, repeated zoom/pan, release, settled geometry and free scrolling; max difference {worst:.2f}px', flush=True)
