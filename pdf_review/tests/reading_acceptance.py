"""Default-on clock/UI acceptance using only the disposable browser fixture."""
import time
from tests.viewer_acceptance import PDF, viewport, change, screenshot
from tests.beta_c2_acceptance import request


def seed_reading(app,document,version,users):
    from review import reading,sections
    database=app.config['DATABASE']
    for name,start,end in [('Chapter 1',1,2),('Chapter 2',3,7),('Chapter 3',8,8)]:
        sid=sections.create_section(database,document,users[0]['user_id'],{'name':name})
        sections.save_placement(database,sid,version,users[0]['user_id'],dict(start_page=start,end_page=end,
            start_y=None,end_y=None,start_view_box=[0,0,612,792],end_view_box=[0,0,792,612],page_count=8,expected_revision=0))
    for index,user in enumerate(users[1:]):
        uid=user['user_id']
        sid=reading.start_session(database,version,uid,1,8)['session_id']
        clock=time.time()-1000
        reading.record_batch(database,version,uid,dict(session_id=sid,sequence=1,active=True,current_page=1,pages=[]),clock=clock)
        for sequence,page in enumerate([1,3,3,5,5,5,5,5,5],2):
            clock+=20
            reading.record_batch(database,version,uid,dict(session_id=sid,sequence=sequence,active=True,current_page=page,
                pages=[dict(page=page,ms=20000,words=200+index*40,visit=page)]),clock=clock)


def run_reading(cdp,a,b,fixture,base):
    ev=lambda script:cdp.evaluate(a,script)
    wait=lambda script:cdp.wait(a,script)
    viewport(cdp,a,1280,1000)
    # Deterministic clock cases complement real foreground timing below.
    result=ev("""(async()=>{const {ReadingClock}=await import('/static/review/reading_clock.js');
      const c=new ReadingClock(),p=[{page:1,weight:1},{page:2,weight:3}];
      c.sample(0,true,p);c.sample(1000,true,p);c.sample(2000,false,p);c.sample(3000,true,p);
      c.sample(13000,true,p);c.sample(14000,true,p);return c.drain(new Map([[1,10],[2,20]]));})()""")
    assert sum(r['ms'] for r in result)==2000,result
    assert sum(r['ms'] for r in result if r['page']==1)==500,result
    assert sum(r['ms'] for r in result if r['page']==2)==1500,result
    gates=ev("""(async()=>{const {ReadingTracker}=await import('/static/review/reading_tracker.js');
      const t={tracking:{status:'active'},policy:{idle_seconds:60},lastInput:100,connected:()=>true};
      const hidden=Object.getOwnPropertyDescriptor(document,'hidden'),focused=Object.getOwnPropertyDescriptor(document,'hasFocus');
      const set=(name,value)=>Object.defineProperty(document,name,{configurable:true,value});
      try{set('hidden',false);set('hasFocus',()=>true);const check=()=>ReadingTracker.prototype.active.call(t,1000),r=[check()];
        set('hidden',true);r.push(check());set('hidden',false);set('hasFocus',()=>false);r.push(check());
        set('hasFocus',()=>true);t.lastInput=-61000;r.push(check());t.lastInput=100;t.connected=()=>false;r.push(check());
        t.connected=()=>true;t.tracking.status='paused';r.push(check());return r;
      }finally{for(const [name,descriptor] of [['hidden',hidden],['hasFocus',focused]]){if(descriptor)Object.defineProperty(document,name,descriptor);else delete document[name];}}
    })()""")
    assert gates==[True,False,False,False,False,False],gates
    url=f"/api/versions/{fixture['versions'][0]}/reading"
    assert request(cdp,a,url)['data']['tracking']['status']=='active'
    ev("document.querySelector('[data-left-card=reading]').click();document.querySelector('[data-left-card=analytics]').click()")
    wait("!!document.querySelector('.reading-spine-card')&&!!document.querySelector('.reader-analytics-card')")
    assert ev("document.querySelectorAll('.reading-spine-card,.reader-analytics-card').length===2")
    assert ev("document.querySelector('.reading-consent').textContent.includes('Authors manage tracking')")
    # Focus this real page and choose p.5, where readers cluster.
    cdp.call('Page.bringToFront',{},a)
    ev(PDF+'.currentScale=.65')
    time.sleep(.3)
    ev(PDF+'.currentPageNumber=5')
    time.sleep(18)
    result=request(cdp,a,url+'/consent','POST',{'action':'pause','page_count':8})
    assert result['status']==200,result
    wait("document.querySelector('.reading-spine-card .reading-consent').textContent.includes('paused by')")
    data=request(cdp,a,url)['data']
    own=next(r for r in data['readers'] if r['user_id']==fixture['users'][0]['user_id'])
    assert own['active_ms']>=3000,own
    # Shared spread selection remains the same source as live presence.
    change(cdp,a,'#review-spread',1)
    assert ev("(async()=>{const {viewingPages}=await import('/static/review/presence.js'),a=document.querySelector('iframe').contentWindow.PDFViewerApplication;await new Promise(r=>requestAnimationFrame(r));const p=viewingPages(a);return p.pages.includes(p.page)&&p.pages.length<=2;})()")
    change(cdp,a,'#review-spread',0)
    ev("document.querySelector('[data-left-card=reading]').click()")
    wait("document.querySelectorAll('.reading-reader-dot').length===3")
    assert ev("(()=>{const labels=[...document.querySelectorAll('.reading-spine-label')].map(e=>e.getBoundingClientRect()).sort((a,b)=>a.top-b.top);return labels.every((r,i)=>!i||r.top>=labels[i-1].bottom+2);})()")
    assert ev("(()=>{const d=[...document.querySelectorAll('.reading-reader-dot')].map(e=>parseFloat(e.style.top));return d.some((a,i)=>d.some((b,j)=>i!==j&&Math.abs(a-b)<2));})()")
    # A reader click selects the existing analytics card rather than duplicating it.
    ev("[...document.querySelectorAll('.reading-spine-label.reader')].find(e=>e.textContent.startsWith('Alice')).click()")
    wait("document.querySelector('.reader-analytics-card h2').textContent==='Alice'")
    wait("document.querySelector('.reading-section-stat')!==null")
    assert ev("document.querySelectorAll('.reader-analytics-card').length===1")
    # Pin each tool for a narrow, readable screenshot; this uses normal card APIs.
    ev("document.querySelector('.reading-spine-card .left-card-pin').click()")
    wait("(()=>{const e=document.querySelector('.reading-spine-card'),r=e.getBoundingClientRect();return r.left>=8&&r.top>=40&&r.top<65&&e.getAnimations().length===0;})()")
    screenshot(cdp,a,'reading-progress-spine')
    ev("document.querySelector('.reader-analytics-card .left-card-pin').click()")
    wait("(()=>{const e=document.querySelector('.reader-analytics-card'),r=e.getBoundingClientRect();return r.left>=8&&r.top>=40&&r.top<65&&e.getAnimations().length===0;})()")
    screenshot(cdp,a,'reader-analytics-sections')
    ev("[...document.querySelectorAll('.reading-tabs button')].find(e=>e.textContent==='Pages').click();document.querySelector('.reading-page-group').open=true")
    wait("document.querySelector('.reading-page')!==null")
    assert ev("[...document.querySelectorAll('.reading-page')].every(e=>e.querySelector('.reading-page-words')?.textContent.match(/^[0-9,]+ words$/)&&e.querySelector('.reading-page-ert')?.textContent.match(/^ERT [0-9]+s$/))")
    assert ev("getComputedStyle(document.querySelector('.reading-page-group:last-child')).borderBottomWidth==='0px'")
    assert ev("document.querySelector('.reading-legend > small').textContent.startsWith('Considered read')")
    # Legend completion is cumulative, not the current page number.
    assert ev("(async()=>{const c=JSON.parse(document.querySelector('#anchor-config').textContent),response=await fetch('/api/versions/'+c.versionId+'/reading'),data=await response.json();return data.readers.every(r=>[...document.querySelectorAll('.reading-legend-row')].some(e=>e.firstElementChild.textContent===r.display_name&&e.children[1].textContent===r.pages_read+' / 8'));})()")
    # Multiple expanded groups survive live refresh while missing metrics resolve.
    ev("document.querySelector('.reading-page-group:last-child').open=true")
    wait("document.querySelectorAll('.reading-page').length===10")
    ev("""(()=>{
      window.readingStable={group:document.querySelector('.reading-page-group'),row:document.querySelector('.reading-page'),removed:0,fetches:0};
      const state=window.readingStable;
      state.observer=new MutationObserver(records=>{state.removed+=records.reduce((sum,r)=>sum+[...r.removedNodes].filter(n=>n.nodeType===1).length,0);});
      state.observer.observe(document.querySelector('.reading-section-views'),{childList:true,subtree:true});
      const original=window.fetch;window.fetch=async(...args)=>{const result=await original(...args);if(String(args[0]).includes('pages_only=1'))state.fetches++;return result;};
    })()""")
    # A committed policy notification causes the same canonical refresh as a timed batch.
    assert request(cdp,a,url+'/consent','POST',{'action':'pause','page_count':8})['status']==200
    wait("window.readingStable.fetches>=2")
    assert ev("window.readingStable.group===document.querySelector('.reading-page-group')&&window.readingStable.row===document.querySelector('.reading-page')&&window.readingStable.removed===0")
    ev("window.readingStable.observer.disconnect()")
    assert ev("[...document.querySelectorAll('.reading-page')].every(e=>getComputedStyle(e).boxShadow==='none')")
    assert ev("getComputedStyle(document.querySelector('.reading-page-group[data-section-id=all] .reading-page:last-child')).paddingBottom==='0px'&&getComputedStyle(document.querySelector('.reading-page-group:not([data-section-id=all]) .reading-page:last-child')).paddingBottom==='0px'&&getComputedStyle(document.querySelector('.reading-page-group[open]:not(:last-child)')).paddingBottom==='10px'")
    ev("document.querySelector('.reading-page-group:last-child').open=false")
    screenshot(cdp,a,'reader-analytics-pages')
    ev("document.querySelector('.reading-page').click()")
    wait(PDF+'.currentPageNumber===1')
    # Reopen/reveal, close all, and restore all six tool states (old limit was 4).
    ev("document.querySelector('[data-left-card=search]').click();document.querySelector('[data-left-card=filters]').click();document.querySelector('[data-left-card=settings]').click();document.querySelector('[data-left-card=sections]').click()")
    wait("document.querySelectorAll('.left-card').length===6")
    wait("JSON.parse(localStorage.getItem('pdf-review:left-cards:v1:'+JSON.parse(document.querySelector('#anchor-config').textContent).currentUserId+':'+JSON.parse(document.querySelector('#anchor-config').textContent).versionId)||'[]').length===6")
    cdp.call('Page.reload',{},a)
    wait("document.querySelector('#realtime-status')?.textContent==='Live'")
    wait("document.querySelectorAll('.left-card').length===6")
    wait("document.querySelector('.reader-analytics-card h2')?.textContent==='Alice'")
    wait("document.querySelector('.reading-tabs [aria-pressed=true]')?.textContent==='Pages'")
    wait("document.querySelector('.reading-page-group')?.open&&document.querySelector('.reading-page')!==null")
    assert ev("!document.querySelector('.reading-page-group:last-child').open")
    assert ev("[...document.querySelectorAll('[data-left-card]')].every(e=>e.getAttribute('aria-checked')==='true')")
    ev("document.querySelector('[data-close-all-tools]').click()")
    wait("document.querySelectorAll('.left-card').length===0")
    print('PASS default-on reading, real active timing/author pause, inactive/suspended clock, weighted spreads, clustered spine, reader selection/pages and six-card restoration',flush=True)
