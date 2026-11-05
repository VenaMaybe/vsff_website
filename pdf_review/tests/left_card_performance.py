"""Exercise all utility cards and report browser layout work, without timing gates."""
import json
import time
from tests.viewer_acceptance import viewport, ARTIFACTS


def run_left_card_performance(cdp,session):
    ev=lambda script:cdp.evaluate(session,script)
    wait=lambda script:cdp.wait(session,script)
    viewport(cdp,session,1600,1000)
    ev("document.querySelector('#review-tools-menu > summary').dispatchEvent(new MouseEvent('dblclick',{bubbles:true}))")
    for tool in ['search','filters','reading','analytics','properties','settings','sections']:
        ev(f"document.querySelector('.tools-panel [data-left-card={tool}]').click()")
    wait("document.querySelectorAll('.left-card').length===8&&document.querySelector('.settings-panel form')!==null&&document.querySelector('.sections-workspace')!==null")
    time.sleep(1)
    cdp.call('Performance.enable',{},session)
    def metrics():
        return {item['name']:item['value'] for item in cdp.call('Performance.getMetrics',{},session)['metrics']}
    initial=metrics()
    result=ev("""(async()=>{
      const app=document.querySelector('iframe').contentWindow.PDFViewerApplication,pdf=app.pdfViewer,stage=app.reviewStage;
      const counts={runs:0,cardRects:0,cardSizes:0};
      const original=Element.prototype.getBoundingClientRect,scheduled=stage.schedule;
      const height=Object.getOwnPropertyDescriptor(HTMLElement.prototype,'offsetHeight');
      const width=Object.getOwnPropertyDescriptor(HTMLElement.prototype,'offsetWidth');
      Element.prototype.getBoundingClientRect=function(){if(this.classList.contains('left-card'))counts.cardRects++;return original.call(this);};
      for(const [key,descriptor] of [['offsetHeight',height],['offsetWidth',width]])Object.defineProperty(HTMLElement.prototype,key,{configurable:true,get(){if(this.classList.contains('left-card'))counts.cardSizes++;return descriptor.get.call(this);}});
      stage.schedule=function(key,job){if(key==='left-cards'&&job){const run=job;job=()=>{counts.runs++;run();};}return scheduled.call(this,key,job);};
      const pause=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      try{
        for(let i=0;i<24;i++){app.eventBus.dispatch('reviewlayoutchanged',{source:app});await pause();}
        const unchanged={...counts};
        for(let i=0;i<24;i++){pdf.currentScale=.6+(i%2)*.04;pdf.container.scrollTop+=i%2?12:-12;await pause();}
        await pause();
        const cards=[...document.querySelectorAll('.left-card')].filter(n=>n.dataset.pinned!=='true').map(n=>original.call(n)).sort((a,b)=>a.top-b.top);
        return {unchanged,total:counts,nonoverlap:cards.every((r,i)=>!i||r.top>=cards[i-1].bottom-.5),count:cards.length};
      }finally{Element.prototype.getBoundingClientRect=original;Object.defineProperty(HTMLElement.prototype,'offsetHeight',height);Object.defineProperty(HTMLElement.prototype,'offsetWidth',width);stage.schedule=scheduled;}
    })()""")
    final=metrics()
    result['browser']={key:round(final[key]-initial[key],5) for key in ['LayoutCount','RecalcStyleCount','LayoutDuration','RecalcStyleDuration','TaskDuration']}
    assert result['count']==8 and result['nonoverlap'],result
    ARTIFACTS.mkdir(exist_ok=True)
    (ARTIFACTS/'left-card-performance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('PASS all-eight-card packing during zoom/scroll; profile '+json.dumps(result),flush=True)
    # Many dividers must finish page measurements before any marker mutations.
    section=ev("""(async()=>{
      const {SectionViewer}=await import('/static/review/section_viewer.js');
      const frame=document.querySelector('iframe'),application=frame.contentWindow.PDFViewerApplication;
      const w=frame.contentWindow,pdf=application.pdfViewer;
      const harness={frame,application,managementVisible:true,managementSectionId:'perf0',sections:[],onActivateSection:(id,kind)=>{harness.activated=[id,kind];}};
      for(let i=0;i<64;i++){
        const page=Math.floor(i/32)+1,box=pdf.getPageView(page-1).viewport.viewBox,j=i%32;
        harness.sections.push({section_id:'perf'+i,name:'Performance section '+i,placement:{start_page:page,end_page:page,start_y:box[3]-j/32*(box[3]-box[1]),end_y:box[3]-(j+1)/32*(box[3]-box[1]),start_view_box:box,end_view_box:box}});
      }
      const observer=new w.MutationObserver(()=>{});observer.observe(pdf.viewer,{subtree:true,attributes:true,childList:true,characterData:true});
      let readsAfterWrites=0,wrote=false;
      const descriptors=['clientWidth','clientHeight'].map(key=>[key,Object.getOwnPropertyDescriptor(w.Element.prototype,key)]);
      for(const [key,descriptor] of descriptors)Object.defineProperty(w.Element.prototype,key,{configurable:true,get(){
        if(this.classList.contains('page')){wrote ||= observer.takeRecords().length>0;if(wrote)readsAfterWrites++;}
        return descriptor.get.call(this);
      }});
      try{
        SectionViewer.prototype.render.call(harness);observer.takeRecords();
        const lines=[...pdf.viewer.querySelectorAll('.section-structure-marker')],label=lines[0].firstElementChild;
        SectionViewer.prototype.render.call(harness);
        const mutations=observer.takeRecords().length;
        lines[0].dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
        harness.managementVisible=false;SectionViewer.prototype.render.call(harness);
        return {readsAfterWrites,mutations,count:lines.length,stable:label===lines[0].firstElementChild,activated:harness.activated};
      }finally{observer.disconnect();for(const [key,descriptor] of descriptors)Object.defineProperty(w.Element.prototype,key,descriptor);}
    })()""")
    assert section['readsAfterWrites']==0 and section['mutations']==0 and section['count']>=64 and section['stable'] and section['activated'][0].startswith('perf'),section
    assert result['total']['cardSizes']<=result['total']['runs']*16+32,result
    print('PASS 64-section divider read/write batching, unchanged-node retention and keyboard activation '+json.dumps(section),flush=True)

