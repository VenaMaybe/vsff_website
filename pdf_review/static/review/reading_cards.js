import { LeftCard, registerLeftCard } from './left_card.js';
import { ReadingTracker } from './reading_tracker.js';
import { jsonRequest } from './thread_api.js';

function node(tag,text,cls='') {const e=document.createElement(tag);if(text!==undefined)e.textContent=text;e.className=cls;return e;}
function button(text,fn,cls='') {const b=node('button',text,cls);b.type='button';b.onclick=fn;return b;}
function duration(ms) {const seconds=Math.floor(ms/1000),minutes=Math.floor(seconds/60);return minutes>=60?`${Math.floor(minutes/60)}h ${minutes%60}m`:minutes?`${minutes}m`: `${seconds}s`;}
function when(value) {return value?new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'No recorded activity';}
function color(reader) {return /^#[0-9a-f]{6}$/i.test(reader?.review_color)?reader.review_color:'#4e79a7';}
function percent(reader) {return reader?.page_count?Math.round(reader.pages_read/reader.page_count*100):0;}
function setText(element,value){if(element.textContent!==value)element.textContent=value;}
function setStyle(element,key,value){if(element.style[key]!==value)element.style[key]=value;}
function setAttribute(element,key,value){if(element.getAttribute(key)!==String(value))element.setAttribute(key,value);}
function orderChildren(parent,children){let previous=null;for(const child of children){const next=previous?previous.nextSibling:parent.firstChild;if(child!==next)parent.insertBefore(child,next);previous=child;}}

export class ReadingCards {
  constructor(application,frame,config,connected) {
    Object.assign(this,{application,frame,config});
    this.tracker=new ReadingTracker(application,frame,config,connected);
    const viewer={sectionViewer:{application,frame}};
    this.spine=new LeftCard('Manuscript',{viewer,opener:document.querySelector('[data-left-card=reading]'),stateKey:'reading',className:'reading-spine-card'});
    this.analytics=new LeftCard('Time tracker',{viewer,opener:document.querySelector('[data-left-card=analytics]'),stateKey:'analytics',className:'reader-analytics-card'});
    this.selected=config.currentUserId;this.view='sections';this.windows=new Map();this.expanded=new Set();
    this.viewStateKey=`pdf-review:reading-view:v1:${config.currentUserId}:${config.versionId}`;
    try {
      const saved=JSON.parse(localStorage.getItem(this.viewStateKey)||'null');
      if(saved?.view==='pages'||saved?.view==='sections')this.view=saved.view;
      if(typeof saved?.reader==='string'&&saved.reader.length<=128)this.selected=saved.reader;
      if(Array.isArray(saved?.expanded))this.expanded=new Set(saved.expanded.filter(k=>typeof k==='string'&&k.length<=128).slice(0,1000));
    } catch { /* Storage is optional; use the normal defaults. */ }
    this.selector=node('select');this.selector.id='reading-reader-select';this.selector.setAttribute('aria-label','Reader');
    this.selector.onchange=()=>{this.selected=this.selector.value;this.windows.clear();this.saveViewState();this.loadDetail();};
    this.stats=node('div',undefined,'reading-stats');this.sectionViews=node('div',undefined,'reading-section-views');
    const label=node('label','Reader');label.htmlFor=this.selector.id;
    this.analyticsControls=node('div',undefined,'reading-consent');
    this.analytics.body.append(node('p','Time tracker','reading-subtitle'),label,this.selector,this.stats,this.sectionViews,this.analyticsControls);
    this.spineControls=node('div',undefined,'reading-consent');this.spineContent=node('div');
    this.spine.body.append(node('p','Reading progress','reading-subtitle'),this.spineContent,this.spineControls);
    this.spineError=node('p','', 'reading-error');this.analyticsError=node('p','', 'reading-error');
    this.spine.body.append(this.spineError);this.analytics.body.append(this.analyticsError);
    registerLeftCard('reading',()=>this.openSpine());registerLeftCard('analytics',()=>this.openAnalytics());
    this.tracker.addEventListener('change',()=>this.scheduleRender());
    this.poll=setInterval(()=>{
      if(document.hidden||(!this.spine.element.isConnected&&!this.analytics.element.isConnected))return;
      this.requestRefresh();
    },30000);
  }
  saveViewState() {
    try {localStorage.setItem(this.viewStateKey,JSON.stringify({view:this.view,reader:this.selected,expanded:[...this.expanded]}));}
    catch { /* Card controls remain usable with storage disabled. */ }
  }
  sectionsChanged(sections) {
    const signature=JSON.stringify(sections.map(s=>({name:s.name,placement:s.placement})));
    if(this.sectionSignature && this.sectionSignature!==signature &&
       (this.spine.element.isConnected||this.analytics.element.isConnected))this.requestRefresh();
    this.sectionSignature=signature;
  }
  async initialize() {await this.tracker.initialize();this.render();}
  error(error) {this.spineError.textContent=this.analyticsError.textContent=error.message;}
  async refresh() {
    await this.tracker.refresh();
    if(this.analytics.element.isConnected)await this.loadDetail();
  }
  openSpine() {this.spine.open();this.render();this.requestRefresh();return this.spine;}
  openAnalytics(reader=null) {
    if(reader){this.selected=reader;this.saveViewState();}
    this.analytics.open();this.render();this.loadDetail().catch(e=>this.error(e));return this.analytics;
  }
  navigate(page) {this.application.pdfViewer.currentPageNumber=Math.max(1,Math.min(this.application.pdfDocument.numPages,page));}
  navigateSection(section) {
    const page=section.start_page,view=this.application.pdfViewer.getPageView(page-1);
    if(!view?.viewport)return this.navigate(page);
    const box=view.viewport.viewBox,fraction=section.start-(page-1);
    this.application.pdfViewer.scrollPageIntoView({pageNumber:page,ignoreDestinationZoom:true,
      destArray:[null,{name:'XYZ'},box[0],box[3]-fraction*(box[3]-box[1]),null]});
  }
  readers() {
    const rows=[...(this.tracker.summary?.readers||[])];
    if(!rows.some(r=>r.user_id===this.config.currentUserId))rows.unshift({user_id:this.config.currentUserId,
      display_name:this.config.currentDisplayName||'You',review_color:this.config.currentReviewColor,page_count:this.application.pdfDocument.numPages,
      active_ms:0,pages_read:0,furthest_page:0,status:this.tracker.tracking.status});
    return rows;
  }
  renderControls(container) {
    const status=this.tracker.tracking.status;
    if(container.dataset.status===status)return;
    container.dataset.status=status;
    container.replaceChildren(node('small',status==='active'
      ? 'Reading activity is recorded while this document is actively viewed. Authors manage tracking in Settings.'
      : status==='paused'?'Reading tracking is paused by the document author.'
      : 'Reading tracking is off for this document. Existing history is retained.','reading-note'));
  }
  requestRefresh() {
    this.refreshDirty=true;
    if(this.refreshRunning)return this.refreshRunning;
    this.refreshRunning=(async()=>{
      while(this.refreshDirty){this.refreshDirty=false;await this.refresh();}
    })().catch(e=>this.error(e)).finally(()=>{this.refreshRunning=null;});
    return this.refreshRunning;
  }
  attachRealtime(socket) {
    socket.on('reading.changed',event=>{
      if(event?.schema_version===1&&event.version_id===this.config.versionId)this.requestRefresh();
    });
    socket.on('review.presence',event=>{
      if(event?.version_id!==this.config.versionId||!this.tracker.summary)return;
      const positions=this.positions=new Map(event.reviewers.map(r=>[r.user_id,r.page]));
      for(const reader of this.tracker.summary.readers){
        reader.online=reader.status==='active'&&positions.has(reader.user_id)&&positions.get(reader.user_id)!=null;
        reader.current_page=reader.online?positions.get(reader.user_id):null;
      }
      this.scheduleRender();
    });
    socket.on('connect',()=>{this.positions=null;this.requestRefresh();});
    socket.on('disconnect',()=>{this.positions=new Map();this.scheduleRender();});
  }
  scheduleRender(){
    if(this.renderPending||(!this.spine.element.isConnected&&!this.analytics.element.isConnected))return;
    this.renderPending=requestAnimationFrame(()=>{this.renderPending=null;this.render();});
  }
  render() {
    if(!this.spine.element.isConnected&&!this.analytics.element.isConnected)return;
    if(this.positions)for(const reader of this.tracker.summary?.readers||[]){
      reader.online=reader.status==='active'&&this.positions.get(reader.user_id)!=null;
      reader.current_page=reader.online?this.positions.get(reader.user_id):null;
    }
    if(this.spine.element.isConnected){this.renderControls(this.spineControls);this.renderSpine();this.spine.contentReady();}
    // Closing analytics must also stop its expanded page groups from extracting
    // text in the background whenever presence/tracking refreshes the other card.
    if(!this.analytics.element.isConnected)return;
    this.renderControls(this.analyticsControls);
    const readers=this.readers();
    if(this.tracker.summary&&!readers.some(r=>r.user_id===this.selected)){this.selected=this.config.currentUserId;this.saveViewState();}
    const signature=readers.map(r=>`${r.user_id}:${r.display_name}`).join('|');
    if(this.selector.dataset.signature!==signature) {
      this.selector.replaceChildren(...readers.map(reader=>{const option=node('option',reader.display_name);option.value=reader.user_id;return option;}));
      this.selector.dataset.signature=signature;
    }
    this.selector.value=this.selected;
    const reader=readers.find(r=>r.user_id===this.selected);
    this.analytics.element.style.setProperty('--reader-color',color(reader));
    this.analytics.element.querySelector('h2').textContent=reader?.display_name||'Time tracker';
    this.renderStats(reader);this.renderSections();
    this.analytics.contentReady();
  }
  renderSpine() {
    const count=this.application.pdfDocument.numPages,summary=this.tracker.summary;
    const readers=summary?.readers||[],sections=summary?.sections||[];
    const signature=JSON.stringify([count,summary?.next_offset,
      sections.map(section=>[section.section_id,section.name,section.start,section.start_page,section.end_page]),
      readers.map(reader=>[reader.user_id,reader.display_name,color(reader),reader.current_page,reader.last_page,reader.furthest_page,reader.pages_read,reader.page_count,reader.online])]);
    if(signature===this.spineSignature)return;
    this.spineSignature=signature;
    const rows=sections.map(s=>({type:'section',section:s,name:s.name,page:s.start_page,range:s.start_page===s.end_page?`p. ${s.start_page}`:`pp. ${s.start_page}–${s.end_page}`,position:s.start/count}));
    rows.push({type:'section',name:'End',page:count,range:`p. ${count}`,position:1});
    for(const reader of readers) {
      const page=reader.current_page||reader.last_page;
      if(page)rows.push({type:'reader',reader,page,position:(page-.5)/count});
    }
    const height=Math.max(340,rows.reduce((h,r)=>h+(r.type==='section'?36:26),0)+20);
    rows.sort((a,b)=>a.position-b.position||(a.type===b.type
      ? (a.reader?.display_name||a.name).localeCompare(b.reader?.display_name||b.name)
      : a.type==='section'?-1:1));
    let bottom=-4;
    const clusters=new Map();
    for(const row of rows) {
      row.height=row.type==='section'?32:22;row.anchor=Math.min(height-8,Math.max(8,row.position*(height-16)+8));
      row.top=Math.max(row.anchor-row.height/2,bottom+4);bottom=row.top+row.height;
    }
    bottom=height;
    for(const row of [...rows].reverse()){row.top=Math.min(row.top,bottom-row.height);bottom=row.top-4;}
    if(!this.spineCanvas){
      this.spineCanvas=node('div',undefined,'reading-spine');
      this.spineLine=node('span',undefined,'reading-spine-line');
      this.spineLeaders=document.createElementNS('http://www.w3.org/2000/svg','svg');
      this.spineLeaders.setAttribute('class','reading-leaders');this.spineLeaders.setAttribute('preserveAspectRatio','none');this.spineLeaders.setAttribute('aria-hidden','true');
      this.spineLegend=node('div',undefined,'reading-legend');this.legendHeading=node('small','Considered read ? Estimated completion','reading-note');
      this.spineEntries=new Map();this.legendEntries=new Map();
      this.spineContent.append(this.spineCanvas,this.spineLegend);
    }
    const canvas=this.spineCanvas,svg=this.spineLeaders,legend=this.spineLegend;
    setStyle(canvas,'height',`${height}px`);setAttribute(svg,'viewBox',`0 0 230 ${height}`);
    const active=new Set(),children=[this.spineLine,svg],leaders=[];
    for(const row of rows){
      const key=row.type==='reader'?`reader:${row.reader.user_id}`:row.section?`section:${row.section.section_id}`:'end';active.add(key);
      let entry=this.spineEntries.get(key);
      if(!entry){
        entry={point:node('span',undefined,row.type==='reader'?'reading-reader-dot':'reading-section-dot')};
        entry.label=button('',()=>{
          const current=entry.row;
          if(current.type==='reader')this.openAnalytics(current.reader.user_id);
          else if(current.section)this.navigateSection(current.section);else this.navigate(current.page);
        },`reading-spine-label ${row.type}`);
        entry.name=node('span');entry.label.append(entry.name);
        if(row.type==='section'){entry.range=node('small');entry.label.append(entry.range);}
        entry.leader=document.createElementNS(svg.namespaceURI,'path');this.spineEntries.set(key,entry);
      }
      entry.row=row;const {point,label,leader}=entry;
      setStyle(point,'top',`${row.anchor}px`);setStyle(label,'top',`${row.top}px`);setStyle(label,'height',`${row.height}px`);
      setText(entry.name,row.type==='reader'?`${row.reader.display_name} ? p. ${row.page}`:row.name);
      if(row.type==='reader'){
        const cluster=Math.round(row.anchor/5),peers=clusters.get(cluster)||0;clusters.set(cluster,peers+1);
        setStyle(point,'left',`${10+(peers%3)*6}px`);
        if(label.style.getPropertyValue('--reader-color')!==color(row.reader))label.style.setProperty('--reader-color',color(row.reader));
        setStyle(point,'backgroundColor',color(row.reader));setAttribute(point,'data-online',String(row.reader.online));
        const title=`${row.reader.online?'Currently viewing':'Last recorded position'} ? p. ${row.page}. Furthest p. ${row.reader.furthest_page}; ${percent(row.reader)}% considered read.`;
        if(label.title!==title)label.title=title;
      }else setText(entry.range,row.range);
      setAttribute(leader,'d',`M${row.type==='reader'?parseFloat(point.style.left)+3.5:14} ${row.anchor} L32 ${row.top+row.height/2}`);
      children.push(point,label);leaders.push(leader);
    }
    for(const [key,entry] of this.spineEntries)if(!active.has(key)){entry.point.remove();entry.label.remove();entry.leader.remove();this.spineEntries.delete(key);}
    orderChildren(canvas,children);orderChildren(svg,leaders);
    const legendChildren=[this.legendHeading],readerIds=new Set();
    for(const reader of readers){
      readerIds.add(reader.user_id);let entry=this.legendEntries.get(reader.user_id);
      if(!entry){
        entry={row:button('',()=>this.openAnalytics(reader.user_id),'reading-legend-row'),name:node('span'),read:node('span'),percentage:node('span')};
        entry.row.append(entry.name,entry.read,entry.percentage);this.legendEntries.set(reader.user_id,entry);
      }
      setText(entry.name,reader.display_name);
      if(entry.name.style.getPropertyValue('--reader-color')!==color(reader))entry.name.style.setProperty('--reader-color',color(reader));
      setText(entry.read,`${reader.pages_read||0} / ${count}`);setText(entry.percentage,`${percent(reader)}%`);
      const title=`${reader.pages_read||0} of ${count} pages considered read. ${reader.online?'Currently viewing':'Last recorded position'}: p. ${reader.current_page||reader.last_page||'?'}.`;
      if(entry.row.title!==title)entry.row.title=title;legendChildren.push(entry.row);
    }
    for(const [key,entry] of this.legendEntries)if(!readerIds.has(key)){entry.row.remove();this.legendEntries.delete(key);}
    if(!readers.length){this.emptyLegend ||= node('p','No reading activity yet.','reading-note');legendChildren.push(this.emptyLegend);}else this.emptyLegend?.remove();
    if(summary?.next_offset!=null){
      this.moreReaders ||= button('More readers',async()=>{try{await this.tracker.refresh(this.tracker.summary.next_offset);}catch(e){this.error(e);}},'quiet-control');legendChildren.push(this.moreReaders);
    }else this.moreReaders?.remove();
    orderChildren(legend,legendChildren);
  }

  renderStats(reader) {
    const detail=this.detail?.reader_id===this.selected?this.detail:null;
    const totals=detail?.totals||reader||{},count=detail?.page_count||reader?.page_count||this.application.pdfDocument.numPages;
    const current=reader?.current_page||totals.last_page||reader?.last_page;
    let index=0;
    for(const [label,value] of [
      [reader?.online?'Currently viewing':'Last recorded page',current?`p. ${current}`:'–'],
      ['Furthest reached',totals.furthest_page?`p. ${totals.furthest_page}`:'–'],
      ['Active viewing time',duration(totals.active_ms||0)],
      ['Considered read',`${totals.pages_read||0} / ${count} (${Math.round((totals.pages_read||0)/count*100)}%)`],
      ['Last activity',when(totals.last_activity)],
    ]) {
      let row=this.stats.children[index++];
      if(!row){row=node('div',undefined,'reading-stat');row.append(node('span'),node('strong'));this.stats.append(row);}
      if(row.children[0].textContent!==label)row.children[0].textContent=label;
      if(row.children[1].textContent!==value)row.children[1].textContent=value;
    }
  }
  async loadDetail() {
    const selected=this.selected;
    if(!this.tracker.summary?.readers.some(r=>r.user_id===selected)) {
      this.detail=null;this.render();return;
    }
    try {
      const result=await jsonRequest(`${this.tracker.url}/readers/${encodeURIComponent(selected)}`);
      if(this.selected!==selected)return;
      this.detail=result;
      for(const data of this.windows.values())data.stale=true;
      this.analyticsError.textContent='';this.render();
    } catch(error) {
      if(this.selected!==selected)return;
      this.detail=null;this.windows.clear();this.error(error);this.render();
    }
  }
  renderSections() {
    const detail=this.detail?.reader_id===this.selected?this.detail:null;
    // Rebuild only when the selected reader/view or actual document structure changes.
    const signature=JSON.stringify([this.selected,this.view,detail?.page_count,
      detail?.sections.map(s=>[s.section_id,s.name,s.start,s.end,s.start_page,s.end_page])]);
    if(this.sectionViews.dataset.signature!==signature){
      this.sectionViews.dataset.signature=signature;this.sectionViews.replaceChildren();
      const tabs=node('div',undefined,'reading-tabs');tabs.setAttribute('role','group');tabs.setAttribute('aria-label','Reading detail view');
      for(const [value,label] of [['sections','Sections'],['pages','Pages']]) {
        const tab=button(label,()=>{this.view=value;this.saveViewState();this.renderSections();this.analytics.contentReady();},'quiet-control');
        tab.setAttribute('aria-pressed',String(this.view===value));tabs.append(tab);
      }
      this.sectionViews.append(tabs);
      if(!detail){this.sectionViews.append(node('p','No recorded reading activity yet.','reading-note'));return;}
      if(this.view==='sections') {
        this.sectionViews.append(node('h3','Dwell time by section'));
        for(const section of detail.sections) {
          const row=node('div',undefined,'reading-section-stat'),heading=button(section.name,()=>this.navigateSection(section),'reading-section-link');
          row.dataset.sectionId=section.section_id;
          const bar=node('span',undefined,'reading-time-track');bar.append(node('span'));
          row.append(heading,node('span',undefined,'reading-section-time'),bar,node('small'));
          this.sectionViews.append(row);
        }
        if(!detail.sections.length)this.sectionViews.append(node('p','No mapped sections. Use Pages for the whole document.','reading-note'));
        this.sectionViews.append(node('p','Bars compare active viewing time. A section is considered read only when more than 90% of its pages are considered read. Viewing time does not establish comprehension.','reading-note'));
      } else {
        for(const section of this.pageGroups(detail)) {
          const group=node('details',undefined,'reading-page-group');group.dataset.sectionId=section.section_id;
          group.append(node('summary',`${section.name} \u00b7 ${section.start_page}\u2013${section.end_page}`));
          const body=node('div',undefined,'reading-pages');group.append(body);
          group.open=this.expanded.has(section.section_id);
          group.addEventListener('toggle',()=>{
            if(group.open){this.expanded.add(section.section_id);this.paintPages(body,section);}
            else this.expanded.delete(section.section_id);
            this.saveViewState();
          });
          this.sectionViews.append(group);
        }
      }
    }
    if(!detail)return;
    if(this.view==='sections') {
      const maximum=Math.max(1,...detail.sections.map(s=>s.active_ms));
      for(const row of this.sectionViews.querySelectorAll('.reading-section-stat')) {
        const section=detail.sections.find(s=>s.section_id===row.dataset.sectionId);
        const time=row.querySelector('.reading-section-time'),read=row.querySelector('small');
        if(time.textContent!==duration(section.active_ms))time.textContent=duration(section.active_ms);
        row.dataset.state=section.is_read?'read':section.pages_read?'partial':'unread';
        const status=section.is_read?'Considered read':section.pages_read?'In progress':'Not yet read';
        const progress=`${status} · ${section.pages_read}/${section.page_count} pages (${section.percentage}%)`;
        if(read.textContent!==progress)read.textContent=progress;
        row.querySelector('.reading-time-track > span').style.width=`${section.active_ms/maximum*100}%`;
      }
    } else {
      const sections=new Map(this.pageGroups(detail).map(s=>[s.section_id,s]));
      for(const group of this.sectionViews.querySelectorAll('.reading-page-group[open]'))this.paintPages(group.querySelector('.reading-pages'),sections.get(group.dataset.sectionId));
    }
  }
  pageGroups(detail) {return [...detail.sections,{section_id:'all',name:'All pages',start_page:1,end_page:detail.page_count}];}
  async paintPages(body,section,more=false) {
    if(!this.analytics.element.isConnected)return;
    const selected=this.selected,key=`${selected}:${section.section_id}`;
    let data=this.windows.get(key);
    if(!data){data={pages:[],stale:true,next:null};this.windows.set(key,data);}
    if(data.loading)return;
    if(data.stale||more) {
      const start=more?data.next:section.start_page;
      if(start==null||start>section.end_page)return;
      const count=more?50:Math.max(50,data.pages.length);
      data.loading=true;data.stale=false;
      if(!data.pages.length&&!body.children.length)body.append(node('small','Loading\u2026','reading-page-loading'));
      try {
        const pages=[];
        for(let offset=0;offset<count&&start+offset<=section.end_page;offset+=50){
          const result=await jsonRequest(`${this.tracker.url}/readers/${encodeURIComponent(selected)}?start=${start+offset}&limit=${Math.min(50,count-offset,section.end_page-start-offset+1)}&pages_only=1`);
          pages.push(...result.pages);
        }
        if(this.windows.get(key)!==data)return;
        data.pages=more?[...data.pages,...pages]:pages;
        const last=data.pages.at(-1)?.page_number;
        data.next=last<section.end_page?last+1:null;
      } catch(error){
        data.stale=true;
        if(!data.pages.length){const message=body.querySelector('.reading-page-loading');if(message)message.textContent=error.message;return;}
        this.error(error);
      } finally {data.loading=false;}
    }
    if(!this.analytics.element.isConnected||selected!==this.selected||this.windows.get(key)!==data)return;
    const pages=data.pages,metrics=new Map();
    // Bound concurrent PDF text extraction, including for pages not viewed yet.
    let cursor=0;
    await Promise.all(Array.from({length:Math.min(4,pages.length)},async()=>{
      while(cursor<pages.length){
        if(!this.analytics.element.isConnected||selected!==this.selected||this.windows.get(key)!==data)return;
        const page=pages[cursor++];
        const words=page.word_count??await this.tracker.wordCount(page.page_number);
        const policy=this.tracker.policy;
        const threshold=page.threshold_ms??(words==null?null:Math.max(policy.minimum_page_seconds*1000,Math.ceil(words*60000/policy.words_per_minute)));
        metrics.set(page.page_number,{words,threshold});
      }
    }));
    if(!this.analytics.element.isConnected||selected!==this.selected||this.windows.get(key)!==data)return;
    if(!body.isConnected){
      const group=[...this.sectionViews.querySelectorAll('.reading-page-group')].find(e=>e.dataset.sectionId===section.section_id);
      const replacement=group?.open?group.querySelector('.reading-pages'):null;
      // A closed card still contains its expanded groups. Retrying the same
      // detached body creates an endless chain of already-resolved promises.
      if(replacement?.isConnected&&replacement!==body)this.paintPages(replacement,section);
      return;
    }
    if(data.pages!==pages){this.paintPages(body,section);return;}
    body.querySelectorAll('.reading-page-loading').forEach(e=>e.remove());
    const existing=new Map([...body.querySelectorAll('.reading-page')].map(e=>[Number(e.dataset.pageNumber),e]));
    const setText=(element,value)=>{if(element.textContent!==value)element.textContent=value;};
    let previous=null;
    for(const page of pages) {
      let item=existing.get(page.page_number);
      if(!item){
        item=button('',()=>this.navigate(page.page_number),'reading-page');item.dataset.pageNumber=page.page_number;
        const thumb=node('span',String(page.page_number),'reading-page-thumb');
        const text=node('span',undefined,'reading-page-text');text.append(node('strong'),node('small'));
        const estimates=node('span',undefined,'reading-page-estimates');
        estimates.append(node('small',undefined,'reading-page-words'),node('small',undefined,'reading-page-ert'));
        item.append(thumb,text,estimates);
      }
      existing.delete(page.page_number);item.dataset.state=page.state;
      const metric=metrics.get(page.page_number),text=item.querySelector('.reading-page-text');
      setText(text.children[0],`${page.state==='read'?'Considered read':page.state==='partial'?'Partially viewed':'Not yet viewed'} \u00b7 ${duration(page.active_ms)}`);
      setText(text.children[1],page.last_visited?`Last visit ${when(page.last_visited)}`:'No recorded visit');
      setText(item.querySelector('.reading-page-words'),metric.words==null?'Words unavailable':`${metric.words.toLocaleString()} words`);
      setText(item.querySelector('.reading-page-ert'),metric.threshold==null?'ERT unavailable':`ERT ${Math.ceil(metric.threshold/1000)}s`);
      item.title=`${page.visit_count} active viewing visits.`;
      const expected=previous?previous.nextElementSibling:body.firstElementChild;
      if(item!==expected)body.insertBefore(item,expected);
      previous=item;
    }
    for(const item of existing.values())item.remove();
    let moreButton=body.querySelector('.reading-more-pages');
    if(data.next&&!moreButton){moreButton=button('More pages',()=>this.paintPages(body,section,true),'quiet-control reading-more-pages');body.append(moreButton);}
    if(!data.next)moreButton?.remove();
    this.analytics.contentReady();
  }
}
