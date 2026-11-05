import { jsonRequest } from './thread_api.js';
import { viewingPages } from './presence.js';
import { ReadingClock } from './reading_clock.js';
import { pagePropertiesFor } from './page_properties_data.js';

export class ReadingTracker extends EventTarget {
  constructor(application,frame,config,connected) {
    super();Object.assign(this,{application,frame,config,connected});
    this.url=`/api/versions/${encodeURIComponent(config.versionId)}/reading`;
    this.clock=new ReadingClock();this.words=new Map();
    this.properties=pagePropertiesFor(application.pdfDocument,config,frame.contentWindow.pdfjsLib?.OPS);
    this.tracking={status:'off'};this.policy={idle_seconds:60,batch_seconds:15,lease_seconds:25};
    this.lastInput=performance.now();this.lastScroll=0;this.lastFlush=0;this.granted=false;
    const input=()=>{this.lastInput=performance.now();};
    for(const doc of [document,frame.contentDocument]) {
      for(const event of ['pointerdown','pointermove','keydown','touchstart','wheel'])doc.addEventListener(event,input,{passive:true});
    }
    application.pdfViewer.container.addEventListener('scroll',()=>{
      input();this.lastScroll=performance.now();this.clock.reset();
    },{passive:true});
    for(const event of ['pagechanging','spreadmodechanged','scrollmodechanged'])application.eventBus.on(event,()=>{this.clock.reset();input();});
    document.addEventListener('visibilitychange',()=>{this.tick();if(document.hidden)this.flush(true);});
    window.addEventListener('blur',()=>{this.clock.reset();queueMicrotask(()=>this.tick());});
    window.addEventListener('focus',()=>{input();this.clock.reset();});
    window.addEventListener('offline',()=>{this.granted=false;this.clock.clear();});
    window.addEventListener('pagehide',()=>{this.clock.reset();this.flush(true);});
    window.addEventListener('pageshow',()=>{this.clock.reset();input();});
    this.timer=setInterval(()=>this.tick(),1000);
  }
  emit() { this.dispatchEvent(new Event('change')); }
  async initialize() { await this.refresh();if(this.tracking.status==='active')await this.flush(); }
  async refresh(offset=0) {
    const data=await jsonRequest(this.url+(offset?`?offset=${offset}`:''));
    const changed=this.tracking.generation!==data.tracking.generation;
    this.tracking=data.tracking;this.policy=data.policy;
    this.summary=offset?{...data,readers:[...(this.summary?.readers||[]),...data.readers]}:data;
    if(changed||this.tracking.status!=='active'){this.session=null;this.granted=false;this.clock.clear();}
    this.emit();return data;
  }
  active(now=performance.now()) {
    return this.tracking.status==='active' && !document.hidden && document.hasFocus() &&
      navigator.onLine && this.connected() && now-this.lastInput<this.policy.idle_seconds*1000;
  }
  pages() {
    const pdf=this.application.pdfViewer,{page,pages}=viewingPages(this.application);
    const bounds=pdf.container.getBoundingClientRect();
    // Use the same page/pair as live presence. Split one elapsed-time budget by
    // visible area; an offscreen spread partner gets zero, never another full tick.
    const visible=pages.map(number=>{
      const rect=pdf.getPageView(number-1)?.div.getBoundingClientRect();
      const weight=rect?Math.max(0,Math.min(rect.right,bounds.right)-Math.max(rect.left,bounds.left))*
        Math.max(0,Math.min(rect.bottom,bounds.bottom)-Math.max(rect.top,bounds.top)):0;
      return {page:number,weight};
    }).filter(p=>p.weight>0);
    return {page,pages:visible};
  }
  async wordCount(page) {
    const words=await this.properties.wordCount(page);
    if(words!==null)this.words.set(page,Math.min(100000,words));
    return words;
  }
  tick() {
    if(this.tracking.status!=='active'){this.clock.clear();return;}
    const now=performance.now(),active=this.active(now),view=this.pages();
    const eligible=active && this.granted && now<this.leaseUntil && now-this.lastScroll>=600;
    this.clock.sample(now,eligible,view.pages);
    if(eligible)for(const page of view.pages)this.wordCount(page.page);
    if(this.tracking.status==='active' && (active || this.granted) &&
       (now-this.lastFlush>=this.policy.batch_seconds*1000 || (!this.session&&active&&now-this.lastFlush>=1000) || (!active&&this.granted)))this.flush(!active);
  }
  async flush(release=false) {
    if(this.sending || this.tracking.status!=='active')return;
    if(!navigator.onLine || !this.connected()) {this.granted=false;this.clock.clear();return;}
    this.sending=true;const started=performance.now();
    try {
      if(!this.session) {
        if(release)return;
        this.session=await jsonRequest(this.url+'/sessions',{method:'POST',body:JSON.stringify({generation:this.tracking.generation,page_count:this.application.pdfDocument.numPages})});
      }
      const pages=this.granted?this.clock.drain(this.words):[];
      const active=!release&&this.active(),current=this.pages().page;
      const result=await jsonRequest(this.url+'/batches',{method:'POST',keepalive:release,
        body:JSON.stringify({session_id:this.session.session_id,sequence:this.session.sequence+1,active,current_page:current,pages})});
      this.session.sequence=result.sequence;this.granted=result.granted;
      this.leaseUntil=started+this.policy.lease_seconds*1000;
      if(!result.granted)this.clock.clear();
      this.connectionState=result.granted?'Tracking active':active?'Another tab or device is tracking':'Waiting for activity';
      this.emit();
    } catch(error) {
      // No persistent outbox or reconnect catch-up. A lost acknowledgment may
      // lose the tail of a visit, but cannot replay time into another session.
      this.session=null;this.granted=false;this.clock.clear();
      this.connectionState='Updates interrupted; timing paused';this.emit();
      if(error.status===422)await this.refresh().catch(()=>{});
    } finally {this.lastFlush=performance.now();this.sending=false;}
  }
}
