"""Live socket timing, including same-page scrolling and stable analytics rows."""
import json
from tests.viewer_acceptance import PDF, viewport
from tests.beta_c2_acceptance import request


def run_reading_live(cdp,a,b,fixture):
    version=fixture['versions'][0];uid=fixture['users'][1]['user_id']
    url=f'/api/versions/{version}/reading'
    def ev(code,session=a):return cdp.evaluate(session,code)
    def wait(code,session=a):return cdp.wait(session,code)
    viewport(cdp,a,1400,1000)
    # Observe application messages without changing tracking behavior.
    ev("""(async()=>{
      const {ReadingCards}=await import('/static/review/reading_cards.js');
      const apply=ReadingCards.prototype.applyActivity;
      window.liveReading={events:0,gets:0};
      ReadingCards.prototype.applyActivity=function(data){
        window.liveReading.card=this;liveReading.events++;return apply.call(this,data);
      };
      const original=window.fetch;
      window.fetch=(url,...args)=>{if(String(url).includes('/reading')&&!(args[0]?.method))liveReading.gets++;return original(url,...args);};
    })()""")
    cdp.call('Page.bringToFront',{},b)
    ev(PDF+'.currentScale=1;'+PDF+'.currentPageNumber=1',b)
    ev("document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))",b)
    wait('liveReading.events>=2')
    assert request(cdp,b,url)['data']['policy']['idle_seconds']==300
    ev("document.querySelector('[data-left-card=analytics]').click()")
    wait("[...document.querySelector('#reading-reader-select').options].some(o=>o.value==="+json.dumps(uid)+")")
    ev("document.querySelector('#reading-reader-select').value="+json.dumps(uid)+";document.querySelector('#reading-reader-select').dispatchEvent(new Event('change'))")
    wait("liveReading.card.detail?.reader_id==="+json.dumps(uid))
    ev("[...document.querySelectorAll('.reading-tabs button')].find(b=>b.textContent==='Pages').click();document.querySelector('.reading-page-group').open=true")
    wait("document.querySelector('.reading-page')!=null")
    ev("liveReading.row=document.querySelector('.reading-page');liveReading.startEvents=liveReading.events;liveReading.gets=0;liveReading.removed=0;new MutationObserver(rows=>{liveReading.removed+=rows.reduce((n,r)=>n+[...r.removedNodes].filter(n=>n.nodeType===1).length,0);}).observe(document.querySelector('.reading-section-views'),{childList:true,subtree:true})")
    before=next(r for r in request(cdp,b,url)['data']['readers'] if r['user_id']==uid)['active_ms']
    # The old 600ms scroll guard would discard this entire interval.
    ev("""(async()=>{const pdf=document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer;
      const timer=setInterval(()=>pdf.container.dispatchEvent(new Event('scroll')),100);
      try{await new Promise(r=>setTimeout(r,4500));}finally{clearInterval(timer);}})()""",b)
    after=next(r for r in request(cdp,b,url)['data']['readers'] if r['user_id']==uid)['active_ms']
    assert 3000<=after-before<=6000,(before,after)
    wait('liveReading.events>=liveReading.startEvents+3')
    assert ev("liveReading.row===document.querySelector('.reading-page')&&liveReading.removed===0&&liveReading.gets<=1"),ev('({removed:liveReading.removed,gets:liveReading.gets})')
    assert ev("liveReading.card.detail.totals.active_ms>="+str(before+2500))
    assert ev("liveReading.card.windows.values().next().value.pages[0].active_ms>="+str(before+2500))
    # A second real tab shares B's account and must take ownership immediately;
    # returning to B takes it back without waiting for the 25-second lease.
    hook="""(async()=>{const {ReadingTracker}=await import('/static/review/reading_tracker.js');
      const original=ReadingTracker.prototype.emit;
      ReadingTracker.prototype.emit=function(){window.testTracker=this;return original.call(this);};})()"""
    ev(hook,b)
    info=cdp.call('Target.getTargetInfo',{},b)['targetInfo']
    target=cdp.call('Target.createTarget',dict(url='about:blank',browserContextId=info['browserContextId']))['targetId']
    session=cdp.call('Target.attachToTarget',dict(targetId=target,flatten=True))['sessionId']
    try:
        cdp.call('Runtime.enable',{},session)
        base=ev('location.origin',b)
        cdp.call('Page.navigate',dict(url=base+f'/versions/{version}/view'),session)
        wait("document.querySelector('#realtime-status')?.textContent==='Live'",session)
        ev(hook,session)
        cdp.call('Page.bringToFront',{},session)
        ev("document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))",session)
        wait('window.testTracker?.granted===true',session)
        wait('window.testTracker?.granted===false',b)
        cdp.call('Page.bringToFront',{},b)
        ev("document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))",b)
        wait('window.testTracker?.granted===true',b)
        wait('window.testTracker?.granted===false',session)
    finally:
        cdp.call('Target.closeTarget',dict(targetId=target))
    print('PASS live acknowledged socket time reaches author, continuous same-page scrolling counts, page rows retained without per-tick HTTP reloads',flush=True)
