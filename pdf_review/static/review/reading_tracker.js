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
    this.tracking={status:'off'};this.policy={idle_seconds:300,batch_seconds:1,lease_seconds:25};
    this.lastInput=performance.now();this.lastFlush=0;this.granted=false;
    this.claimRequested=true;
    const input=()=>{
      const resuming=!this.active();this.lastInput=performance.now();
      if(resuming||!this.granted){this.claimRequested=true;this.flush();}
    };
    for(const doc of [document,frame.contentDocument]) {
      for(const event of ['pointerdown','pointermove','keydown','touchstart','wheel'])doc.addEventListener(event,input,{passive:true});
    }
    application.pdfViewer.container.addEventListener('scroll',()=>{
      this.tick();
    },{passive:true});
    for(const event of ['pagechanging','spreadmodechanged','scrollmodechanged'])application.eventBus.on(event,()=>this.tick());
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)input();this.tick();if(document.hidden)this.flush(true);});
    window.addEventListener('blur',()=>{this.clock.reset();queueMicrotask(()=>this.tick());});
    window.addEventListener('focus',()=>{this.claimRequested=true;input();this.tick();});
    window.addEventListener('offline',()=>{this.granted=false;this.clock.clear();});
    window.addEventListener('pagehide',()=>{this.clock.reset();this.flush(true);});
    window.addEventListener('pageshow',()=>{this.clock.reset();input();});
    this.timer=setInterval(()=>this.tick(),250);
  }
  attachRealtime(socket) {
    this.socket=socket;
    socket.on('reading.owner',event=>{
      if(!event||event.claimed_at<this.ownerAt)return;
      this.ownerAt=event.claimed_at;
      this.ownerSession=event?.session_id;
      if(this.session&&this.ownerSession!==this.session.session_id){
        this.granted=false;this.clock.clear();this.connectionState='Another tab or device is tracking';this.emit();
      }
    });
    socket.on('disconnect',()=>{this.session=null;this.granted=false;this.clock.clear();});
    socket.on('connect',()=>{this.claimRequested=true;});
  }
  request(kind,data) {
    return new Promise((resolve,reject)=>{
      if(!this.socket?.connected)return reject(Error('Reading connection unavailable.'));
      this.socket.timeout(5000).emit(`reading.${kind}`,{version_id:this.config.versionId,
        csrf_token:document.querySelector('meta[name="csrf-token"]').content,data},(error,response)=>{
        if(error||!response?.ok){
          const failure=Error(response?.error||'Reading update interrupted.');
          if(response&&!response.ok)failure.status=422;
          reject(failure);
        }else resolve(response.result);
      });
    });
  }
  emit() { this.dispatchEvent(new Event('change')); }
  async initialize() { await this.refresh();if(this.tracking.status==='active')await this.flush(); }
  async refresh(offset=0) {
    const data=await jsonRequest(this.url+(offset?`?offset=${offset}`:''));
    const changed=this.tracking.generation!==data.tracking.generation;
    this.tracking=data.tracking;this.policy=data.policy;
    for(const reader of data.readers){
      const live=this.summary?.readers.find(r=>r.user_id===reader.user_id);
      if(live&&live.active_ms>reader.active_ms)Object.assign(reader,live);
    }
    this.summary=offset?{...data,readers:[...(this.summary?.readers||[]),...data.readers]}:data;
    if(changed||this.tracking.status!=='active'){
      this.session=null;this.granted=false;this.clock.clear();this.claimRequested=this.active();
    }
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
    const now=performance.now(),active=this.active(now);
    const eligible=active && this.granted && now<this.leaseUntil;
    // Hidden, idle and superseded tabs need no recurring page geometry reads.
    const view=eligible?this.pages():{pages:[]};
    this.clock.sample(now,eligible,view.pages);
    if(eligible)for(const page of view.pages)if(!this.words.has(page.page))this.wordCount(page.page);
    if(this.tracking.status==='active' && (this.granted || this.claimRequested) && (active || this.granted) &&
       (this.claimRequested&&active || now-this.lastFlush>=this.policy.batch_seconds*1000 || (!active&&this.granted)))this.flush(!active);
  }
  async flush(release=false) {
    if(this.sending || this.tracking.status!=='active')return;
    if(!release&&performance.now()<(this.retryAfter||0))return;
    if(!navigator.onLine || !this.connected()) {this.granted=false;this.clock.clear();return;}
    if(!release&&!this.socket?.connected)return;
    this.sending=true;const started=performance.now();
    try {
      if(!this.session) {
        if(release)return;
        this.session=await this.request('session',{generation:this.tracking.generation,page_count:this.application.pdfDocument.numPages});
      }
      if(!release&&this.active()&&this.claimRequested){
        this.claimRequested=false;
        await this.request('claim',{session_id:this.session.session_id});
        this.granted=this.ownerSession===this.session.session_id;
        this.leaseUntil=performance.now()+this.policy.lease_seconds*1000;
        // Seed timing immediately on grant, rather than waiting for two ticks.
        this.clock.sample(performance.now(),this.granted,this.pages().pages);
      }
      const pages=this.granted?this.clock.drain(this.words):[];
      const active=!release&&this.active(),current=this.pages().page;
      const data={session_id:this.session.session_id,sequence:this.session.sequence+1,active,current_page:current,pages};
      const result=release?await jsonRequest(this.url+'/batches',{method:'POST',keepalive:true,body:JSON.stringify(data)}):await this.request('batch',data);
      this.session.sequence=result.sequence;this.granted=result.granted;
      this.leaseUntil=started+this.policy.lease_seconds*1000;
      if(!result.granted)this.clock.clear();
      this.connectionState=result.granted?'Tracking active':active?'Another tab or device is tracking':'Waiting for activity';
      this.emit();
    } catch(error) {
      // No persistent outbox or reconnect catch-up. A lost acknowledgment may
      // lose the tail of a visit, but cannot replay time into another session.
      this.session=null;this.granted=false;this.clock.clear();this.claimRequested=this.active();
      this.retryAfter=performance.now()+1000;
      this.connectionState='Updates interrupted; timing paused';this.emit();
      if(error.status===422)await this.refresh().catch(()=>{});
    } finally {this.lastFlush=started;this.sending=false;}
  }
}
