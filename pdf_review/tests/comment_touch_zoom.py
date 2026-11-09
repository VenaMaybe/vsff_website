"""CDP touch input and DOM hit testing; this is not physical iOS verification."""
import json
import time
from tests.viewer_acceptance import change


def seed_touch_comment(cdp, session, page):
    ev = lambda script: cdp.evaluate(session, script)
    ev(f"{{const pdf=document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer;pdf.currentScale=1;pdf.currentPageNumber={page}}}")
    cdp.wait(session, f"!!document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.getPageView({page-1}).textLayer?.div.querySelector('span')")
    ev(f"""(async()=>{{
      const w=document.querySelector('iframe').contentWindow,app=w.PDFViewerApplication;
      const range=w.document.createRange();range.selectNodeContents(app.pdfViewer.getPageView({page-1}).textLayer.div.querySelector('span'));
      w.getSelection().removeAllRanges();w.getSelection().addRange(range);
      const {{captureTextSelection}}=await import('/static/review/anchor_selection.js');
      const {{createThread}}=await import('/static/review/thread_api.js');
      const config=JSON.parse(document.querySelector('#anchor-config').textContent);
      await createThread(config.threadsUrl,captureTextSelection(w,app),'Long document touch fixture');
      w.getSelection().removeAllRanges();
    }})()""")
    cdp.wait(session, f"!!document.querySelector('iframe').contentDocument.querySelector('.page[data-page-number=\"{page}\"] .pdf-review-thread-highlight')")


def run_comment_touch_zoom(cdp, session):
    ev = lambda script: cdp.evaluate(session, script)
    cdp.call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=3, mobile=True), session)
    cdp.call('Emulation.setTouchEmulationEnabled', dict(enabled=True, maxTouchPoints=2), session)
    ev("""(async()=>{
      window.tapFrame=document.querySelector('iframe');window.tapApp=tapFrame.contentWindow.PDFViewerApplication;
      window.tapPdf=tapApp.pdfViewer;window.tapScroller=tapPdf.container;
      const {installTouchDiagnostics}=await import('/static/review/touch_diagnostics.js');
      window.tapTrace=installTouchDiagnostics(tapFrame,tapApp);
      window.tapHighlight=[...tapFrame.contentDocument.querySelectorAll('.pdf-review-thread-highlight')].at(-1);
      window.tapId=tapHighlight.dataset.threadId;
      tapPdf.scrollMode=0;tapPdf.spreadMode=0;tapPdf.pagesRotation=0;
      tapFrame.contentWindow.getSelection().removeAllRanges();
      window.tapClear=()=>document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
      window.tapLive=()=>tapFrame.contentDocument.querySelector(`.pdf-review-thread-highlight[data-thread-id="${tapId}"]`);
      window.tapCenter=()=>{const r=tapLive().getBoundingClientRect();
        tapScroller.scrollLeft+=r.left+r.width/2-160;tapScroller.scrollTop+=r.top+r.height/2-260;};
      window.tapPoint=(kind)=>{
        const node=kind==='highlight'?tapLive():document.querySelector(`.${kind}[data-thread-id="${tapId}"]`);
        const r=node.getBoundingClientRect(), f=tapFrame.getBoundingClientRect();
        const x=r.left+Math.min(r.width/2,35),y=r.top+Math.min(r.height/2,12);
        const d=kind==='highlight'?tapFrame.contentDocument:document,hit=d.elementFromPoint(x,y);
        return {x:x+(kind==='highlight'?f.left:0),y:y+(kind==='highlight'?f.top:0),
          hit:kind==='highlight'?!!hit?.closest('.page'):node.contains(hit),box:r.toJSON()};};
    })()""")

    def touch(kind, points):
        cdp.call('Input.dispatchTouchEvent', dict(type=kind, touchPoints=points), session)

    def tap(kind, settle_scroll=0, expected=True):
        point = ev(f'tapPoint({json.dumps(kind)})')
        assert point['hit'], ('visual/hit-test mismatch', kind, point, ev('tapTrace.entries.slice(-8)'))
        assert 0 < point['x'] < 390 and 0 < point['y'] < 844, point
        touch('touchStart', [dict(x=point['x'], y=point['y'], id=7)])
        if settle_scroll:
            # Exact native pan entry point, while the new finger stays still.
            # Isolates late post-zoom scroll adjustment from finger movement.
            ev(f'tapPdf.panBy(0,{settle_scroll})')
        touch('touchEnd', [])
        active = ev("document.querySelector('.thread-card.active')?.dataset.threadId===tapId")
        assert active == expected, (kind, settle_scroll, ev('tapTrace.entries.slice(-16)'))

    def pinch(start, end, center=160):
        f = ev('tapFrame.getBoundingClientRect().toJSON()')
        before = ev('tapPdf.currentScale')
        for step in range(9):
            span = start+(end-start)*step/8
            touch('touchStart' if step == 0 else 'touchMove', [
                dict(x=center-span/2, y=f['top']+260, id=0),
                dict(x=center+span/2, y=f['top']+260, id=1)])
            time.sleep(.016)
        touch('touchEnd', [])
        after = ev('tapPdf.currentScale')
        assert after > before*1.03 if end > start else after < before*.97, (start,end,before,after)

    cases = 0
    change(cdp, session, '#comments-visibility', 'mobile')
    ev('tapClear();tapCenter()')
    time.sleep(.3)
    tap('highlight', settle_scroll=2)
    ev('tapClear()')
    tap('highlight', settle_scroll=25, expected=False)
    for mode in ['expanded', 'minimized', 'mobile', 'hidden']:
        change(cdp, session, '#comments-visibility', mode)
        ev('tapClear();tapPdf.currentScale=.6')
        ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        ev('tapCenter()')
        time.sleep(.3)
        for gesture in [None, (100, 170), (170, 100), (100, 170), (170, 100)]:
            if gesture:
                pinch(*gesture)
            # No render/scroll settle wait between gesture end and this tap.
            tap('highlight', expected=mode != 'hidden')
            ev('tapClear()')
            ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
            time.sleep(.22)
            tap('highlight', expected=mode != 'hidden')
            ev('tapClear()')
            ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
            if mode != 'hidden':
                # Deselecting intentionally animates neighboring cards. Let that
                # preparation finish before choosing a rail tap coordinate.
                time.sleep(.18)
                # Scroll the native PDF surface to make the actual rail reachable.
                kind = 'thread-card' if mode == 'expanded' else 'thread-marker'
                ev(f"{{const railTarget=document.querySelector('.{kind}[data-thread-id=\"'+tapId+'\"]');"
                   "const railRect=railTarget.getBoundingClientRect();tapScroller.scrollLeft+=railRect.left-200;"
                   "tapScroller.scrollTop+=railRect.top-tapFrame.getBoundingClientRect().top-260;}")
                ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                tap(kind)
                ev('tapClear();tapCenter()')
                time.sleep(.22)
            else:
                assert ev("document.querySelector('#thread-list').hidden")
            cases += 1
        if mode != 'hidden':
            # Pinch on uncovered PDF/background beside the visible rail, then
            # tap its actual painted box immediately, without reconciliation.
            for index,(start,end) in enumerate([(110,80),(80,110),(110,80),(80,110)]):
                ev('tapClear()')
                ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                if index == 0:
                    # Start by shrinking from the right document edge, then
                    # reverse without recentering. Native limits cannot keep a
                    # right-edge marker on screen during arbitrary enlargement.
                    ev(f"{{const r=document.querySelector('.{kind}[data-thread-id=\"'+tapId+'\"]').getBoundingClientRect();"
                       "tapScroller.scrollLeft+=r.left-150;tapScroller.scrollTop+=r.top-tapFrame.getBoundingClientRect().top-260;}")
                time.sleep(.22)
                before_rail = ev(f'tapPoint({json.dumps(kind)})')
                assert before_rail['hit'], (mode, before_rail)
                pinch(start,end,center=65)
                tap(kind)
                ev('tapClear()')
                time.sleep(.22)
                tap(kind)
                cases += 1
    change(cdp, session, '#comments-visibility', 'mobile')
    ev('tapClear();tapPdf.currentScale=1')
    ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    ev('tapCenter()')
    time.sleep(.3)
    # A valid stationary tap must survive small native scroll settling, but a
    # real pan must not activate a highlight. Pointercancel/multitouch/selection
    # cancellation have independent coverage in highlight_touch.py.
    tap('highlight', settle_scroll=2)
    ev('tapClear()')
    tap('highlight', settle_scroll=25, expected=False)
    ev('tapTrace.stop()')
    print(f'PASS {cases} comment touch cases across all display modes, repeated native pinches, immediate/settled highlight taps, rail hit tests and native scroll rejection', flush=True)
