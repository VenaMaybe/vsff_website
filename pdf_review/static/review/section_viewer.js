import { sectionDividers } from './section_boundaries.js';
import { boundaryGeometry } from './section_boundary_geometry.js';
import { SectionPlacementEditor } from './section_placement_editor.js';
import { jsonRequest } from './thread_api.js';
import { AppDialog } from './dialogs.js';

function node(tag,text,className='') { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; e.className=className; return e; }

function dividerAnchor(divider) {
  const ending=divider.members.find(m=>m.kind==='end'),starting=divider.members.find(m=>m.kind==='start');
  return ending && starting && ending.placement.end_page<starting.placement.start_page ? starting : ending||divider.members[0];
}

export function sectionGeometry(application,section) {
  const point=boundaryGeometry(application,section?.placement,'end');
  if(!point?.view.div.isConnected) return null;
  const rect=point.view.div.getBoundingClientRect(), y=rect.top+point.view.div.clientTop+point.top+point.dy/2;
  return {page:rect,pageNumber:section.placement.end_page,top:y,bottom:y,left:rect.left,right:rect.right};
}

export class SectionViewer {
  constructor(frame,application,config,state,refresh,status) {
    Object.assign(this,{frame,application,config,state,refresh,status});
    this.sections=[];
    const link=frame.contentDocument.createElement('link'); link.rel='stylesheet'; link.href=new URL('../styles/sections.css',import.meta.url).href;
    frame.contentDocument.head.append(link);
    for(const event of ['pagerendered','scalechanging','rotationchanging','spreadmodechanged','scrollmodechanged']) application.eventBus.on(event,()=>this.schedule());
    application.eventBus.on('pdftouchended',()=>this.schedule());
    if (config.isOwner) this.placementEditor = new SectionPlacementEditor(this);
  }
  update(data) {
    this.sections=data.sections;
    this.state.sectionThreads=[];
    for(const section of data.sections.filter(s=>s.placement)) {
      const responses=data.responses.filter(r=>r.section_id===section.section_id);
      if(!responses.some(r=>r.author_id===this.config.currentUserId) && this.config.canMutate) responses.push({response_id:null,author_id:this.config.currentUserId,comments:[]});
      for(const response of responses) this.state.sectionThreads.push({
        thread_id:`section:${section.section_id}:${response.response_id??'new'}`,
        response_id:response.response_id,section,targets:[],status:'open',review_color:response.review_color,
        comments:response.comments.map(c=>({...c,section:true,thread_id:`section:${section.section_id}:${response.response_id}`,
          author:{user_id:c.author_id,display_name:c.display_name},is_deleted:!!c.deleted_at})),
      });
    }
    this.placementEditor?.changed();
    this.schedule();
  }
  schedule() { if(this.scheduled)return; this.scheduled=true; requestAnimationFrame(()=>{this.scheduled=false;this.render();}); }
  setManagementVisible(visible, selectedId = null) {
    this.managementVisible = visible;
    this.managementSectionId = selectedId;
    this.schedule();
  }
  render() {
    const doc=this.frame.contentDocument;
    const old=new Map([...doc.querySelectorAll('.section-structure-marker')].map(line=>[line.dataset.markerKey,line]));
    const wanted=new Set();
    for (const divider of this.managementVisible ? sectionDividers(this.sections, section=>this.placementEditor?.get(section.section_id)||section.placement) : []) {
      const ending=divider.members.find(m=>m.kind==='end'),starting=divider.members.find(m=>m.kind==='start');
      const pageTransition=ending && starting && ending.placement.end_page<starting.placement.start_page;
      const member=(pageTransition?starting:null) || divider.members.find(m=>m.section.section_id===this.managementSectionId) || ending || divider.members[0];
      const {section,kind}=member;
      // A linked page transition is drawn at the following page's start.
      const physical=dividerAnchor(divider);
      const geometry=boundaryGeometry(this.application,physical.placement,physical.kind);
      if(!geometry)continue;
      const {view,x,top,dx,dy}=geometry;
      const key=JSON.stringify(divider.members.map(m=>[m.section.section_id,m.kind]));
      wanted.add(key);
      const line=old.get(key)||doc.createElement('span');line.className='section-structure-marker section-management-line';
      line.dataset.markerKey=key;line.hidden=false;
      line.dataset.sectionId=section.section_id;line.dataset.kind=kind;
      line.dataset.members=JSON.stringify(divider.members.map(m=>({id:m.section.section_id,kind:m.kind})));
      line.dataset.shared=String(divider.members.length>1);
      line.dataset.edge=String(!!geometry.edge);
      line.dataset.pageEdge=geometry.edge||'';
      line.dataset.pending=String(divider.members.some(m=>this.placementEditor?.drafts.has(m.section.section_id)));
      line.dataset.clamped=String(divider.members.some(m=>this.placementEditor?.states.get(m.section.section_id)?.clamped));
      line.dataset.selected=String(divider.members.some(m=>m.section.section_id===this.managementSectionId));
      line.tabIndex=0;line.setAttribute('role','button');
      line.onkeydown=event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();this.onActivateSection?.(section.section_id,kind);}};
      line.style.left=`${x}px`;line.style.top=`${top}px`;line.style.width=`${Math.hypot(dx,dy)}px`;line.style.transform=`rotate(${Math.atan2(dy,dx)}rad)`;
      const label=line.firstElementChild||doc.createElement('span');label.className='section-management-label';
      label.textContent=divider.members.length>1 ? divider.members.map(m=>m.section.name).join(' / ') : `${kind==='start'?'Start':'End'}: ${section.name}`;
      line.title=label.textContent+(divider.members.length>1?' ? Double-click to separate':'');line.setAttribute('aria-label',label.textContent);
      if(!label.parentElement)line.append(label);
      if(line.parentElement!==view.div)view.div.append(line);
    }
    for(const [key,line] of old)if(!wanted.has(key)) {
      if(this.application.reviewPdfTouchActive)line.hidden=true;
      else line.remove();
    }
  }

  boundaryCenter(id, kind) {
    const divider=sectionDividers(this.sections,s=>this.placementEditor?.get(s.section_id)||s.placement).find(d=>d.members.some(m=>m.section.section_id===id&&m.kind===kind));
    const member=divider&&dividerAnchor(divider);
    const geometry = member && boundaryGeometry(this.application,member.placement,member.kind);
    if (!geometry) return null;
    return this.frame.getBoundingClientRect().top + geometry.view.div.getBoundingClientRect().top + geometry.view.div.clientTop + geometry.top + geometry.dy/2;
  }
  async action(operation) {
    try { await operation(); await this.refresh(); return true; }
    catch(error) { this.status(error.message,'error'); await this.refresh(); return {error}; }
  }
  reply(thread,body) {
    const url=thread.response_id?`/api/section-responses/${thread.response_id}/comments`:
      `/api/versions/${this.config.versionId}/sections/${thread.section.section_id}/responses`;
    return this.action(()=>jsonRequest(url,{method:'POST',body:JSON.stringify({body})}));
  }
  edit(comment,body) { return this.action(()=>jsonRequest(`/api/section-comments/${comment.comment_id}`,{method:'PATCH',body:JSON.stringify({body,expected_revision:comment.current_revision})})); }
  remove(comment) { return this.action(()=>jsonRequest(`/api/section-comments/${comment.comment_id}`,{method:'DELETE'})); }
  async previewOutline() {
    const outline=await this.application.pdfDocument.getOutline();
    if(!outline?.length) {this.status('This PDF has no outline. Define sections manually.');return;}
    const shell=new AppDialog('Import PDF outline',{size:'medium'}),dialog=shell.element,form=node('form'),list=node('div');
    const closed=new Promise(resolve=>{shell.onClose=resolve;});
    const candidates=[];
    const walk=async(items,depth=0)=>{
      for(const item of items) {
        const dest=typeof item.dest==='string'?await this.application.pdfDocument.getDestination(item.dest):item.dest;
        if(dest?.length) {
          const page=Number.isInteger(dest[0])?dest[0]+1:await this.application.pdfDocument.getPageIndex(dest[0])+1;
          const row=node('label',undefined,'outline-candidate'),check=node('input'),name=node('input'),position=node('input');
          row.style.paddingLeft=`${Math.min(depth,6)*12}px`;
          check.type='checkbox';check.checked=depth===0;check.setAttribute('aria-label',`Include ${item.title}`);
          name.value=item.title;name.maxLength=200;name.setAttribute('aria-label','Section name');
          position.type='number';position.min=1;position.max=this.application.pdfDocument.numPages;position.value=page;position.setAttribute('aria-label','Start page');
          row.append(check,name,position);list.append(row);candidates.push({check,name,position});
        }
        if(item.items?.length)await walk(item.items,depth+1);
      }
    };
    await walk(outline);
    const message=node('p','Choose outline items and edit their names/start pages. Selected starts define adjacent ranges; the final section ends at the PDF end. Nothing is created until confirmation.');
    const error=node('p',''),submit=node('button','Create selected sections'),cancel=node('button','Cancel');
    submit.type='submit';cancel.type='button';cancel.onclick=()=>shell.close();
    form.append(message,list,error,submit,cancel);shell.body.append(form);shell.open();
    form.onsubmit=async event=>{
      event.preventDefault();shell.setBusy(true);
      try {
        const selected=candidates.filter(c=>c.check.checked).sort((a,b)=>Number(a.position.value)-Number(b.position.value));
        const payload=[];
        for(let i=0;i<selected.length;i++) {
          const start=Number(selected[i].position.value),end=i+1<selected.length?Number(selected[i+1].position.value)-1:this.application.pdfDocument.numPages;
          const startPage=await this.application.pdfDocument.getPage(start),endPage=await this.application.pdfDocument.getPage(end);
          payload.push({name:selected[i].name.value,prompt:'',placement:{start_page:start,start_y:null,end_page:end,end_y:null,
            start_view_box:startPage.view,end_view_box:endPage.view,page_count:this.application.pdfDocument.numPages,expected_revision:0}});
        }
        await jsonRequest(`/api/versions/${this.config.versionId}/sections/outline`,{method:'POST',body:JSON.stringify({candidates:payload})});
        await this.refresh();shell.setBusy(false);shell.close();
      } catch(e){error.textContent=e.message;} finally {shell.setBusy(false);}
    };
    return closed;
  }
}
