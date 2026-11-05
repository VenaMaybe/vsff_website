"""Card scaling uses PDF zoom without changing card wrapping or document coordinates."""
import time
from tests.viewer_acceptance import PDF, SELECT, viewport, change, screenshot


def run_card_scaling(cdp, session):
    ev=lambda script:cdp.evaluate(session,script)
    wait=lambda script:cdp.wait(session,script)
    viewport(cdp,session,1600,1000)
    ev(PDF+'.currentScale=1')
    ev(SELECT)
    ev("""(async()=>{
      const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const config=JSON.parse(document.querySelector('#anchor-config').textContent);
      const anchor=captureTextSelection(w,w.PDFViewerApplication);
      for(let i=0;i<3;i++)await createThread(config.threadsUrl,anchor,'Card scaling comment '+i);
      w.getSelection().removeAllRanges();
    })()""")
    wait("document.querySelectorAll('#thread-list .thread-card').length===3")
    change(cdp,session,'#comments-visibility','expanded')
    ev("document.querySelector('[data-left-card=filters]').click();document.querySelector('[data-left-card=settings]').click()")
    wait("document.querySelector('.settings-panel form')!==null")
    ev("document.querySelector('.settings-panel .left-card-pin').click()")
    time.sleep(.3)
    measure="""(()=>{
      const pdf=PDF,frame=document.querySelector('iframe').getBoundingClientRect();
      const nodes=[...document.querySelectorAll('.left-card,#thread-list .thread-card')].filter(n=>!n.hidden);
      const rects=nodes.map(n=>{const r=n.getBoundingClientRect();return {w:r.width,h:r.height,x:r.left,y:r.top,
        layoutW:n.offsetWidth,layoutH:n.offsetHeight,left:n.classList.contains('left-card'),pinned:n.dataset.pinned==='true'};});
      const comments=rects.filter(n=>!n.left).sort((a,b)=>a.y-b.y);
      const filter=document.querySelector('.comment-filter-panel'),r=filter.getBoundingClientRect();
      const first=pdf.getPageView(0).div.getBoundingClientRect();
      return {rects,nonoverlap:comments.every((r,i)=>!i||r.y>=comments[i-1].y+comments[i-1].h-.3),
        leftGap:frame.left+first.left-r.right,toolbar:getComputedStyle(document.querySelector('.viewer-shell-bar')).fontSize};
    })()""".replace('PDF',PDF)
    baseline=ev(measure)
    for zoom in [.75,.5,.25,1,1.5,.5]:
        ev(PDF+f'.currentScale={zoom}')
        time.sleep(.25)
        state=ev(measure)
        factor=min(1,zoom)
        assert state['nonoverlap'],(zoom,state)
        assert abs(state['leftGap']-12*factor)<1.5,(zoom,state)
        assert state['toolbar']==baseline['toolbar']
        for original,actual in zip(baseline['rects'],state['rects']):
            assert actual['layoutW']==original['layoutW'],(zoom,original,actual)
            assert abs(actual['w']-original['w']*factor)<1,(zoom,original,actual)
            assert abs(actual['h']-actual['layoutH']*factor)<1,(zoom,actual)
    # A scaled header still follows the pointer in screen pixels.
    header=ev("(()=>{const r=document.querySelector('.settings-panel .dialog-header').getBoundingClientRect();return {x:r.left+20,y:r.top+5};})()")
    top=ev("document.querySelector('.settings-panel').getBoundingClientRect().top")
    for kind,y,extra in [('mousePressed',header['y'],{'button':'left','clickCount':1}),('mouseMoved',header['y']+60,{'buttons':1}),('mouseReleased',header['y']+60,{'button':'left','clickCount':1})]:
        cdp.call('Input.dispatchMouseEvent',dict(type=kind,x=header['x'],y=y,**extra),session)
    time.sleep(.25)
    actual=ev("document.querySelector('.settings-panel').getBoundingClientRect().top")
    assert abs(actual-top-60)<2,(top,actual)
    screenshot(cdp,session,'cards-at-half-zoom')
    change(cdp,session,'#comments-visibility','minimized')
    time.sleep(.25)
    assert ev("[...document.querySelectorAll('#thread-list .thread-marker')].every(n=>Math.abs(n.getBoundingClientRect().width-n.offsetWidth*.5)<1)")
    print('PASS proportional card/marker scaling below 100%, fixed size above, scaled packing/gutters, pinned cards and screen-space header dragging',flush=True)
