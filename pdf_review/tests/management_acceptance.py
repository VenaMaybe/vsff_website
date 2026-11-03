"""Focused autosaving inspector, shared divider, spread and left-card checks."""
import json
import time
from tests.viewer_acceptance import screenshot,viewport,PDF


def run_management(cdp,a,fixture,base):
    doc=fixture['document_id'];version=fixture['versions'][0]
    viewport(cdp,a,1440,1000)
    def ev(script):return cdp.evaluate(a,script)
    def wait(script):return cdp.wait(a,script)
    def idle():
        wait("![...document.querySelectorAll('.left-card')].some(c=>c.getAnimations().length)")
        time.sleep(.08)
    def context():return ev(f"fetch('/api/versions/{version}/review-context').then(r=>r.json())")
    def placement(id):return next(s['placement'] for s in context()['sections'] if s['section_id']==id)
    def field(name,value):
        ev(f"{{const input=document.querySelector('.sections-panel [name={name}]');input.value={json.dumps(str(value))};input.dispatchEvent(new Event('input',{{bubbles:true}}));input.dispatchEvent(new Event('change',{{bubbles:true}}));}}")
    def saved(id):
        wait("document.querySelector('.section-save-status')?.textContent.startsWith('Saved')")
        wait(f"fetch('/api/versions/{version}/review-context').then(r=>r.json()).then(d=>d.sections.some(s=>s.section_id==={json.dumps(id)}&&s.placement))")
    def add(name):
        count=ev("document.querySelectorAll('.section-master-item').length")
        ev("[...document.querySelectorAll('.sections-panel button')].find(b=>b.textContent==='+ Add section').click()")
        wait(f"document.querySelectorAll('.section-master-item').length==={count+1}")
        id=ev("document.querySelector('.section-master-item[aria-current=true]').dataset.sectionId")
        field('name',name)
        wait(f"fetch('/documents/{doc}/sections?version={version}').then(r=>r.json()).then(d=>d.sections.some(s=>s.section_id==={json.dumps(id)}&&s.name==={json.dumps(name)}))")
        return id
    def line(id,kind):
        return "[...document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line')].find(l=>JSON.parse(l.dataset.members).some(m=>m.id==="+json.dumps(id)+"&&m.kind==="+json.dumps(kind)+"))"
    def drag(id,kind,page,percent):
        ev(PDF+'.container.scrollTop=0');time.sleep(.12)
        p=ev(f"(()=>{{const line={line(id,kind)},r=line.getBoundingClientRect(),f=document.querySelector('iframe').getBoundingClientRect();return {{x:f.left+r.left+100,y:f.top+r.top+(line.dataset.kind==='start'?4:-3)}};}})()")
        target=ev(f"(()=>{{const p={PDF}.getPageView({page-1}).div,r=p.getBoundingClientRect(),f=document.querySelector('iframe').getBoundingClientRect();return f.top+r.top+p.clientTop+p.clientHeight*{percent}/100;}})()")
        cdp.call('Input.dispatchMouseEvent',{'type':'mousePressed','x':p['x'],'y':p['y'],'button':'left','clickCount':1},a)
        for step in range(1,9):
            cdp.call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':p['x'],'y':p['y']+(target-p['y'])*step/8,'buttons':1},a)
        cdp.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':p['x'],'y':target,'button':'left','clickCount':1},a)
        time.sleep(.18)
        wait("!document.querySelector('.section-save-status').textContent.startsWith('Saving')")
    ev(PDF+'.currentScale=.35')
    ev("document.querySelector('[data-sections]').click()")
    wait("document.querySelector('.sections-workspace')!==null");idle();time.sleep(.15)
    assert ev("document.querySelector('.sections-panel').dataset.pinned==='false'")
    assert ev("(()=>{const r=document.querySelector('.sections-panel').getBoundingClientRect(),w=document.querySelector('.viewer-workspace').getBoundingClientRect();return Math.abs((r.top+r.bottom)/2-(w.top+w.bottom)/2)<10;})()")
    # Dragging the header changes only the vertical document anchor.
    header=ev("(()=>{const r=document.querySelector('.sections-panel .dialog-header').getBoundingClientRect();return {x:r.left+55,y:r.top+r.height/2,top:document.querySelector('.sections-panel').getBoundingClientRect().top,left:document.querySelector('.sections-panel').getBoundingClientRect().left};})()")
    cdp.call('Input.dispatchMouseEvent',{'type':'mousePressed','x':header['x'],'y':header['y'],'button':'left','clickCount':1},a)
    cdp.call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':header['x']+30,'y':header['y']+90,'buttons':1},a)
    cdp.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':header['x']+30,'y':header['y']+90,'button':'left','clickCount':1},a)
    idle()
    assert abs(ev("document.querySelector('.sections-panel').getBoundingClientRect().top")-header['top']-90)<2
    assert abs(ev("document.querySelector('.sections-panel').getBoundingClientRect().left")-header['left'])<1
    ev("window.pagePositions=Array.from({length:2},(_,i)=>{const p="+PDF+".getPageView(i).div,r=p.getBoundingClientRect();return r.top+"+PDF+".container.scrollTop;})")
    left=add('First section');field('prompt','What changed?');field('start_page',1);saved(left)
    assert placement(left)['end_page']==1
    right=add('Second section');field('start_page',2);saved(right)
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line').length===3")
    assert ev(line(left,'end')+".dataset.shared==='true'")
    assert ev("(()=>{const rows=[...document.querySelectorAll('.section-master-item')];return rows[0].querySelector('.section-list-range').textContent==='1'&&rows[1].querySelector('.section-list-range').textContent==='2';})()")
    assert ev("Array.from({length:2},(_,i)=>{const r="+PDF+".getPageView(i).div.getBoundingClientRect();return Math.abs(r.top+"+PDF+".container.scrollTop-window.pagePositions[i])<1;}).every(Boolean)")
    assert ev("!document.querySelector('iframe').contentDocument.querySelector('.section-gap-before,.section-gap-after')")

    assert ev("![...document.querySelectorAll('.sections-panel button')].some(b=>['Save boundaries','Cancel changes','Save section'].includes(b.textContent))")
    assert ev("!document.querySelector('#section-editor')")
    # Failed autosaves keep the edited value and expose a compact Retry action.
    ev("window.originalFetch=window.fetch;window.failMetadata=true;window.fetch=(url,options)=>{if(window.failMetadata&&String(url).startsWith('/api/sections/')){window.failMetadata=false;return Promise.resolve(new Response(JSON.stringify({error:{message:'Synthetic save failure'}}),{status:503,headers:{'Content-Type':'application/json'}}));}return window.originalFetch(url,options);}")
    field('prompt','Retry this prompt')
    wait("document.querySelector('.section-save-status').textContent.includes('Synthetic save failure')")
    assert ev("document.querySelector('[name=prompt]').value==='Retry this prompt'")
    ev("window.fetch=window.originalFetch;[...document.querySelectorAll('.section-inspector-footer button')].find(b=>b.textContent==='Retry').click()")
    wait("document.querySelector('.section-save-status').textContent.startsWith('Saved')")
    assert next(s for s in context()['sections'] if s['section_id']==right)['prompt']=='Retry this prompt'
    # Even with the lower section selected, the page-border divider selects the following section.
    assert ev(line(left,'end')+".dataset.sectionId==="+json.dumps(right))
    ev(line(left,'end')+".click()")
    wait("document.querySelector('.section-master-item[aria-current=true]').dataset.sectionId==="+json.dumps(right))
    # Shared divider moves both endpoints and persists one atomic pair edit.
    old_left,old_right=placement(left),placement(right)
    drag(left,'end',1,65)
    wait(f"fetch('/api/versions/{version}/review-context').then(r=>r.json()).then(d=>d.sections.find(s=>s.section_id==={json.dumps(right)}).placement.start_page===1)")
    first,second=placement(left),placement(right)
    assert first['end_page']==second['start_page']==1
    assert abs(first['end_y']-second['start_y'])<1e-7
    assert first['revision']==old_left['revision']+1 and second['revision']==old_right['revision']+1
    assert first['start_y']==old_left['start_y'] and second['end_y']==old_right['end_y']
    # Seed an intentional gap through the existing single-placement API.
    payload={k:v for k,v in first.items() if k!='revision'};payload.update(end_y=500,expected_revision=first['revision'],page_count=2)
    ev(f"fetch('/api/versions/{version}/sections/{left}/placement',{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name=csrf-token]').content}},body:JSON.stringify({json.dumps(payload)})}})")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line').length===4")
    unchanged=placement(right)
    # An independent end cannot run through the next section; it clamps/snaps to it.
    drag(left,'end',2,25)
    assert placement(right)==unchanged
    assert abs(placement(left)['end_y']-unchanged['start_y'])<1e-6
    assert ev("document.querySelector('.section-save-status').textContent.includes('cannot overlap')")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line').length===3")
    assert ev(line(left,'end')+".dataset.shared==='true'")
    # Page entry moves the linked start and reports which endpoint changed.
    ev("document.querySelector('.section-master-item[data-section-id=\""+left+"\"]').click()")
    field('end_page',1)
    wait("document.querySelector('.section-save-status').textContent.includes('Saved')")
    assert placement(right)['start_page']==2 and placement(right)['start_y'] is None
    assert placement(right)['revision']==unchanged['revision']+1
    assert ev("document.querySelector('.section-save-status').textContent.includes('Moved start of Second section')")
    # A linked neighbor may now shrink to a fraction of a page.
    field('end_page',2)
    wait("document.querySelector('.section-save-status').textContent.startsWith('Saved')")
    tail=placement(right)
    assert tail['start_page']==2 and 0<tail['start_y']<792
    field('end_page',1)
    wait("document.querySelector('.section-save-status').textContent.startsWith('Saved')")
    assert ev("(()=>{const l="+line(left,'end')+";return l.dataset.sectionId==="+json.dumps(right)+"&&l.dataset.kind==='start'&&l.closest('.page').dataset.pageNumber==='2';})()")
    # Outside interactions blur left cards without closing them or moving their layout.
    for target in ["document.querySelector('iframe').contentDocument.body","document.querySelector('iframe').contentDocument.querySelector('.page')","document.querySelector('.section-feedback-card')"]:
        ev("document.querySelector('.sections-panel [name=name]').focus()")
        assert ev("document.querySelector('.sections-panel').classList.contains('active')")
        ev(target+".click()")
        assert ev("!document.querySelector('.left-card.active')&&document.querySelector('.sections-panel').isConnected")
    ev("document.querySelector('.sections-panel [name=name]').focus();document.querySelector('.sections-panel [name=name]').click()")
    assert ev("document.querySelector('.sections-panel.active')!==null")
    # Closing Sections removes every PDF boundary overlay; reopening restores them.
    ev("document.querySelector('.sections-panel .dialog-header button:last-child').click()")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.section-structure-marker').length===0")
    ev("document.querySelector('[data-sections]').click()")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line').length===3")
    # Opening another utility card does not pin either or change content height.
    ev("document.querySelector('[data-review-settings]').click()")
    wait("document.querySelector('.settings-form')!==null");idle()
    assert ev("[...document.querySelectorAll('.left-card')].every(c=>c.dataset.pinned==='false'&&c.scrollHeight<=c.clientHeight+1)")
    assert ev("(()=>{const a=document.querySelector('.sections-panel').getBoundingClientRect(),b=document.querySelector('.settings-panel').getBoundingClientRect();return a.bottom+4<=b.top||b.bottom+4<=a.top;})()")
    # Closing one card must not remove the remaining card's click-away listeners.
    ev("document.querySelector('.sections-panel .dialog-header button:last-child').click();document.querySelector('.settings-panel select').focus()")
    assert ev("document.querySelector('.settings-panel.active')!==null")
    ev("document.querySelector('iframe').contentDocument.querySelector('.page').click()")
    assert ev("!document.querySelector('.left-card.active')")
    ev("document.querySelector('[data-sections]').click()")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line').length===3")
    ev("document.querySelector('.settings-panel .dialog-header button:last-child').click()")
    # Section overlays leave PDF.js spread membership and vertical alignment unchanged.
    ev(PDF+'.spreadMode=1');time.sleep(.25)
    assert ev(PDF+".getPageView(0).div.closest('.spread')==="+PDF+".getPageView(1).div.closest('.spread')")
    assert ev("Math.abs("+PDF+".getPageView(0).div.getBoundingClientRect().top-"+PDF+".getPageView(1).div.getBoundingClientRect().top)<1")
    # Enter either edge zone: both map to the same canonical inter-page location.
    ev(PDF+'.spreadMode=0');time.sleep(.15)
    drag(left,'end',1,98)
    assert placement(left)['end_y'] is None and placement(right)['start_page']==2 and placement(right)['start_y'] is None
    drag(left,'end',2,1)
    assert placement(left)['end_page']==1 and placement(left)['end_y'] is None
    ev(PDF+'.spreadMode=1');time.sleep(.25)
    assert ev("Math.abs("+PDF+".getPageView(0).div.getBoundingClientRect().top-"+PDF+".getPageView(1).div.getBoundingClientRect().top)<1")
    assert ev(line(left,'end')+".dataset.shared==='true'")
    assert ev("parseFloat(document.querySelector('iframe').contentWindow.getComputedStyle("+line(left,'end')+").borderTopWidth)===2")
    # No structural rail/backing should sit under a management divider.
    assert ev("document.querySelector('iframe').contentDocument.querySelectorAll('.section-row-rail').length===0")
    assert ev("document.querySelector('iframe').contentWindow.getComputedStyle("+line(left,'end')+").backgroundColor==='rgba(0, 0, 0, 0)'")
    assert ev("(()=>{const l="+line(left,'end')+",p=l.closest('.page'),r=l.getBoundingClientRect(),b=p.getBoundingClientRect();return p.dataset.pageNumber==='2'&&Math.abs(r.top-b.top-p.clientTop-12)<2&&Math.abs(r.width-p.clientWidth)<1;})()")
    screenshot(cdp,a,'autosave-shared-divider-spread-1440')
    ev(PDF+'.spreadMode=0');time.sleep(.2)
    ev(PDF+'.container.scrollTop=0');time.sleep(.15)
    before_split=[placement(left),placement(right)]
    point=ev(f"(()=>{{const l={line(left,'end')},r=l.getBoundingClientRect(),f=document.querySelector('iframe').getBoundingClientRect();return {{x:f.left+r.left+100,y:f.top+r.top+(l.dataset.kind==='start'?4:-3)}};}})()")
    for count in [1,2]:
        cdp.call('Input.dispatchMouseEvent',{'type':'mousePressed','x':point['x'],'y':point['y'],'button':'left','clickCount':count},a)
        cdp.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':point['x'],'y':point['y'],'button':'left','clickCount':count},a)
        time.sleep(.05)
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line').length===4")
    wait("document.querySelector('.section-save-status').textContent.startsWith('Saved')")
    after_split=[placement(left),placement(right)]
    assert after_split[0]['end_page']==1 and after_split[1]['start_page']==2
    assert after_split[0]['end_y']==0 and after_split[1]['start_y']==792
    assert ev("document.querySelector('[name=start_page]').value==='2'&&document.querySelector('.section-boundary-fields:first-child .section-boundary-location').textContent==='Start of page'")
    assert after_split[0]['revision']==before_split[0]['revision']+1
    assert after_split[1]['revision']==before_split[1]['revision']+1
    assert after_split[0]['start_y']==before_split[0]['start_y'] and after_split[1]['end_y']==before_split[1]['end_y']
    # Rejoin, then move the shared line again: no false shared-boundary error.
    drag(left,'end',2,20)
    wait("document.querySelector('.section-save-status').textContent.includes('Saved')")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line').length===3")
    drag(left,'end',1,75)
    wait("document.querySelector('.section-save-status').textContent.startsWith('Saved')")

    # A shared border close to the edge also splits onto different pages.
    first,second=placement(left),placement(right)
    def payload(p,**values):
        data={k:v for k,v in p.items() if k!='revision'}
        data.update(expected_revision=p['revision'],page_count=2,**values)
        return data
    pair={'before_id':left,'after_id':right,'before':payload(first,end_page=1,end_y=20),'after':payload(second,start_page=1,start_y=20)}
    assert ev(f"fetch('/api/versions/{version}/sections/shared-boundary',{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name=csrf-token]').content}},body:JSON.stringify({json.dumps(pair)})}}).then(r=>r.ok)")
    wait(line(left,'end')+"?.dataset.pageEdge==='end'")
    ev(PDF+'.container.scrollTop=0');time.sleep(.15)
    point=ev(f"(()=>{{const l={line(left,'end')},r=l.getBoundingClientRect(),f=document.querySelector('iframe').getBoundingClientRect();return {{x:f.left+r.left+100,y:f.top+r.top-3}};}})()")
    for count in [1,2]:
        cdp.call('Input.dispatchMouseEvent',{'type':'mousePressed','x':point['x'],'y':point['y'],'button':'left','clickCount':count},a)
        cdp.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':point['x'],'y':point['y'],'button':'left','clickCount':count},a)
        time.sleep(.05)
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line').length===4")
    wait("document.querySelector('.section-save-status').textContent.startsWith('Saved')")
    assert placement(left)['end_page']==1 and placement(right)['start_page']==2
    assert ev("Array.from({length:2},(_,i)=>{const r="+PDF+".getPageView(i).div.getBoundingClientRect();return Math.abs(r.top+"+PDF+".container.scrollTop-window.pagePositions[i])<1;}).every(Boolean)")
    # Explicit page-edge splits stay separate and inset by 12px across zooms.
    for scale in [.5,1]:
        ev(PDF+f'.currentScale={scale}');time.sleep(.2)
        assert ev("document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line').length===4")
        assert ev("(()=>{const l="+line(left,'end')+",r=l.getBoundingClientRect(),p=l.closest('.page'),b=p.getBoundingClientRect();return Math.abs(b.bottom-p.clientTop-r.top-12)<2;})()")
    ev(PDF+'.currentScale=.35');time.sleep(.2)
    screenshot(cdp,a,'page-edge-split-1440')
    ev(PDF+'.spreadMode=0');viewport(cdp,a,768,1024);idle();screenshot(cdp,a,'autosave-inspector-768')
    # Hold the save queue while a snapped independent edge becomes a shared drag.
    # Each request must retain its own geometry, then rebase only its own revisions.
    assert ev("""(async()=>{
      const {SectionPlacementEditor}=await import('/static/review/section_placement_editor.js');
      const {sectionPageRange}=await import('/static/review/section_boundaries.js');
      const box=[0,0,612,792],placement=(start,end)=>({start_page:1,end_page:1,start_y:start,end_y:end,start_view_box:box,end_view_box:box,revision:1});
      const model=[{section_id:'left',placement:placement(null,400)},{section_id:'right',placement:placement(300,null)}];
      const viewer={config:{isOwner:true,versionId:'queue-fixture'},sections:model,schedule(){},refresh:async()=>{},
        frame:{contentDocument:document.implementation.createHTMLDocument()},
        application:{pdfDocument:{numPages:2},pdfViewer:{getPageView:()=>({viewport:{viewBox:box},div:{clientHeight:792}})}}};
      if(sectionPageRange(null)!==''||sectionPageRange({...model[0].placement,end_page:2,end_y:null})!=='1\u20132'||sectionPageRange({...model[0].placement,end_page:2,end_y:792})!=='1')throw Error('page range edge handling');
      const editor=new SectionPlacementEditor(viewer),requests=[],originalFetch=window.fetch;
      let release;editor.queue=new Promise(resolve=>release=resolve);
      window.fetch=(url,options)=>{
        if(!String(url).includes('/queue-fixture/'))return originalFetch(url,options);
        const body=JSON.parse(options.body);requests.push(body);
        const write=(id,p)=>{const section=model.find(s=>s.section_id===id);if(p.expected_revision!==section.placement.revision)throw Error('stale queued revision');section.placement={...p,revision:p.expected_revision+1};};
        if(body.before_id){
          const scalar=y=>Math.round((792-y)/792*1e10);
          if(scalar(model[0].placement.end_y)!==scalar(model[1].placement.start_y))throw Error('queued pair no longer adjacent');
          write(body.before_id,body.before);write(body.after_id,body.after);
        }else write('left',body);
        return Promise.resolve(new Response(JSON.stringify({ok:true}),{headers:{'Content-Type':'application/json'}}));
      };
      try{
        editor.setBoundary('left','end',1,200,box,null);editor.commit(['left']);
        editor.setBoundary('left','end',1,250,box,'right');editor.commit(['left','right']);
        release();await editor.queue;
        if(requests.length!==2||Math.abs(requests[0].end_y-300)>1e-6||requests[1].before.expected_revision!==2||requests[1].after.expected_revision!==1)throw Error('queued snapshots changed');
        if([...editor.states.values()].some(s=>s.error))throw Error('queued save failed');
        // Moving an independent end above its own start must clamp, preserving neighbors.
        const other=JSON.stringify(model[0].placement);
        const changed=editor.setBoundary('right','end',1,700,box,null);
        if(!changed.length||JSON.stringify(model[0].placement)!==other||!editor.states.get('right').notice)throw Error('self-edge clamp failed');
        return true;
      }finally{window.fetch=originalFetch;}
    })()""")
    # Delete remains explicit and cancellable.
    ev("[...document.querySelectorAll('.sections-panel button')].find(b=>b.textContent==='Delete').click()")
    wait("document.querySelector('dialog[open]')!==null")
    ev("[...document.querySelectorAll('dialog button')].find(b=>b.textContent==='Cancel').click()")
    assert len(context()['sections'])==2
    print('PASS centered unpinned cards, header drag, autosave inspector, atomic shared divider, gap preservation, overlap clamp/snap, page synchronization, in-page edge zones, unchanged page spacing, live page ranges, across-page split/rejoin, delayed save snapshots, self-edge clamp, spread alignment and explicit Delete',flush=True)
