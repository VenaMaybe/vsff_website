"""Comment presentation is independent of device-specific composer docking."""
import json
import time
from tests.viewer_acceptance import PDF, viewport, change


def run_composer_modes(cdp, session):
    ev=lambda script:cdp.evaluate(session,script)
    wait=lambda script:cdp.wait(session,script)
    viewport(cdp,session,1440,900)
    ev(PDF+'.currentScale=1;'+PDF+'.currentPageNumber=2')
    wait(PDF+'.getPageView(1).textLayer?.div?.querySelector("span")!=null')
    time.sleep(.25)
    ev("""(async()=>{
      const frame=document.querySelector('iframe'),w=frame.contentWindow,app=w.PDFViewerApplication;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const select=()=>{const text=app.pdfViewer.getPageView(1).textLayer.div.querySelector('span').firstChild;
        const r=w.document.createRange();r.setStart(text,2);r.setEnd(text,16);
        w.getSelection().removeAllRanges();w.getSelection().addRange(r);};
      select();const payload=captureTextSelection(w,app);
      const config=JSON.parse(document.querySelector('#anchor-config').textContent);
      for(let i=0;i<3;i++)await createThread(config.threadsUrl,structuredClone(payload),'Composer neighbor '+i);
      w.getSelection().removeAllRanges();
      window.composerFixture={frame,w,app,payload,select};
    })()""")
    wait("document.querySelectorAll('.thread-card:not(.left-card)').length===3")

    def snapshot():
        return ev("""(async()=>{
          const {anchorGeometry}=await import('/static/review/viewer_shell.js');
          const {app,payload,frame}=composerFixture;
          const box=document.querySelector('#selection-comment-composer'),f=frame.getBoundingClientRect();
          const r=box.getBoundingClientRect(),g=anchorGeometry(app,payload);
          const page=app.pdfViewer.getPageView(1).div.getBoundingClientRect();
          return {rect:{left:r.left,top:r.top,right:r.right,bottom:r.bottom,height:r.height},
            geometry:g,frameTop:f.top,frameLeft:f.left,pageRight:page.right+f.left,
            scroll:app.pdfViewer.container.scrollTop,docked:box.classList.contains('viewport-composer'),
            cards:[...document.querySelectorAll('#thread-list .thread-card,#thread-list .thread-marker')]
              .filter(n=>n.getClientRects().length).map(n=>{const r=n.getBoundingClientRect();
                return {left:r.left,top:r.top,right:r.right,bottom:r.bottom};})};
        })()""")

    for mode in ['expanded','minimized','mobile','hidden']:
        change(cdp,session,'#comments-visibility',mode)
        ev("composerFixture.select()")
        wait("!document.querySelector('#comment-selection-button').hidden")
        ev("document.querySelector('#comment-selection-button').click()")
        wait("!document.querySelector('#selection-comment-composer').hidden")
        time.sleep(.25)
        data=snapshot();r=data['rect'];g=data['geometry']
        assert not data['docked'] and data['scroll']>200,data
        if mode in ['mobile','hidden']:
            assert abs(r['top']-(data['frameTop']+g['bottom']+8))<3,data
        elif mode=='minimized':
            assert abs(r['left']-(data['pageRight']+48))<3,data
        else:
            assert abs(r['left']-(data['pageRight']+6))<3,data
            assert abs(r['top']+r['height']/2-(data['frameTop']+(g['top']+g['bottom'])/2))<3,data
        if mode=='hidden':assert data['cards']==[],data
        for card in data['cards']:
            assert not (r['left']<card['right']-.5 and r['right']>card['left']+.5 and
                        r['top']<card['bottom']-.5 and r['bottom']>card['top']+.5),data
        # Changing style does not discard a draft or replace the composer.
        ev("document.querySelector('#selection-comment-body').value='Keep this draft'")
        next_mode='mobile' if mode!='mobile' else 'minimized'
        change(cdp,session,'#comments-visibility',next_mode)
        assert ev("document.querySelector('#selection-comment-body').value==='Keep this draft'")
        ev("document.querySelector('#cancel-selection-comment').click()")

    # A narrow mouse-driven laptop window remains selection-attached.
    viewport(cdp,session,600,900)
    change(cdp,session,'#comments-visibility','mobile')
    ev("composerFixture.select();document.querySelector('#comment-selection-button').click()")
    wait("!document.querySelector('#selection-comment-composer').hidden")
    time.sleep(.2)
    assert not snapshot()['docked']
    assert ev("document.querySelector('#comments-visibility').value==='mobile'")
    ev("document.querySelector('#cancel-selection-comment').click()")

    # Coarse-pointer tablet: docking works at wide sizes and with any style.
    viewport(cdp,session,1024,768)
    cdp.call('Emulation.setTouchEmulationEnabled',dict(enabled=True,maxTouchPoints=5),session)
    try:
        assert ev("matchMedia('(pointer: coarse)').matches")
        for mode in ['expanded','minimized','mobile','hidden']:
            change(cdp,session,'#comments-visibility',mode)
            ev("composerFixture.select();document.querySelector('#comment-selection-button').click()")
            wait("document.querySelector('#selection-comment-composer').classList.contains('viewport-composer')")
            time.sleep(.15)
            data=snapshot();r=data['rect']
            assert ev("document.querySelector('#selection-comment-composer').parentElement===document.body")
            assert abs(r['right']-(1024-12))<3 and abs(r['bottom']-(768-16))<3,data
            ev("document.querySelector('#cancel-selection-comment').click()")
    finally:
        cdp.call('Emulation.setTouchEmulationEnabled',dict(enabled=False),session)
    viewport(cdp,session,1440,900)
    # Saving a new comment follows the selected presentation, including Hidden.
    for index,mode in enumerate(['expanded','minimized','mobile','hidden'],start=4):
        change(cdp,session,'#comments-visibility',mode)
        ev("composerFixture.select()")
        wait("!document.querySelector('#comment-selection-button').hidden&&!document.querySelector('#comment-selection-button').disabled")
        ev("document.querySelector('#comment-selection-button').click()")
        wait("!document.querySelector('#selection-comment-composer').hidden")
        message='Saved in '+mode
        ev("document.querySelector('#selection-comment-body').value="+json.dumps(message)+";document.querySelector('#selection-comment-form').requestSubmit()")
        wait("document.querySelector('#selection-comment-composer').hidden&&document.querySelectorAll('#thread-list .thread-card').length==="+str(index))
        time.sleep(.2)
        assert ev("document.querySelector('#comments-visibility').value==="+json.dumps(mode))
        if mode=='hidden':
            assert ev("document.querySelector('#thread-list').hidden")
        else:
            wait("document.querySelector('#thread-list .thread-card.active')!==null")
            if mode=='mobile':
                assert ev("document.querySelector('#thread-list .thread-card.active').classList.contains('floating-thread-card')")
    print('PASS composer placement at scroll depth across Expanded/Compact/Pop-up/Hidden, no card collisions, draft retention, narrow laptop and wide touch tablet',flush=True)
