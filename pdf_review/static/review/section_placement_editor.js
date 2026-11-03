import { boundaryLocation, sectionDividers } from './section_boundaries.js';
import { jsonRequest } from './thread_api.js';
import { PAGE_EDGE_SNAP, pageAxisLength } from './section_boundary_geometry.js';

// Owner-only transient drafts shared by page entry and cross-page PDF dragging.
// Autosave commits use revision-checked services; shared dividers save atomically.
export class SectionPlacementEditor {
  constructor(viewer) {
    this.viewer = viewer; this.drafts = new Map(); this.listeners = new Set(); this.states = new Map(); this.tokens = new Map(); this.queue = Promise.resolve(); this.lastGroups=new Map(); this.localRevisions=new Map(); this.lastSplit=new Map();
    const doc = viewer.frame.contentDocument;
    doc.addEventListener('click', event => this.click(event), true);
    doc.addEventListener('dblclick', event => {
      const marker=event.target.closest('.section-management-line[data-shared=true]');
      if(marker){event.preventDefault();event.stopImmediatePropagation();if(performance.now()>(this.suppressSplitUntil||0))this.splitDivider(marker);}
    },true);
    doc.addEventListener('pointerdown', event => this.startDrag(event), true);
    for (const target of [document, doc]) target.addEventListener('keydown', event => {
      if (event.key === 'Escape' && this.cancelDrag) {
        event.preventDefault(); event.stopImmediatePropagation();
        this.cancelDrag?.();
      }
    }, true);
  }
  get(id) { return this.drafts.get(id) || this.viewer.sections.find(s => s.section_id === id)?.placement || null; }
  changed(id) {
    this.viewer.schedule();
    for (const listener of this.listeners) listener(id);
  }
  partner(id, kind) {
    const divider=sectionDividers(this.viewer.sections,s=>this.get(s.section_id)).find(d=>d.members.some(m=>m.section.section_id===id&&m.kind===kind));
    return divider?.members.find(m=>m.section.section_id!==id)?.section.section_id||null;
  }
  valueAt(location, kind) {
    const count=this.viewer.application.pdfDocument.numPages;
    const integer=Math.abs(location-Math.round(location))<1e-8;
    let page=integer ? Math.round(location)-(kind==='end'?1:0) : Math.floor(location);
    page=Math.max(1,Math.min(count,page));
    const box=[...this.viewer.application.pdfViewer.getPageView(page-1).viewport.viewBox];
    const fraction=location-page;
    return {page,y:integer && ((kind==='start'&&fraction===0)||(kind==='end'&&fraction===1))?null:box[3]-Math.max(0,Math.min(1,fraction))*(box[3]-box[1]),box};
  }
  setBoundary(id, kind, page, y, box, partner = this.partner(id,kind)) {
    if (!this.viewer.config.isOwner) return [];
    const draft=structuredClone(this.get(id) || {expected_revision:0});
    const opposite=kind==='end'?'start':'end';
    if (!draft[`${opposite}_page`]) {
      draft[`${opposite}_page`]=page;draft[`${opposite}_y`]=null;draft[`${opposite}_view_box`]=[...box];
    }
    draft[`${kind}_page`]=page;draft[`${kind}_y`]=y;draft[`${kind}_view_box`]=[...box];
    let candidate=page+(y==null?(kind==='end'?1:0):(box[3]-y)/(box[3]-box[1]));
    const zone=PAGE_EDGE_SNAP/pageAxisLength(this.viewer.application.pdfViewer.getPageView(page-1));
    if(Math.abs(candidate-Math.round(candidate))<=zone)candidate=Math.round(candidate);
    const ownStart=boundaryLocation(draft,'start'),ownEnd=boundaryLocation(draft,'end');
    let low=kind==='end'?ownStart+1e-5:1, high=kind==='start'?ownEnd-1e-5:this.viewer.application.pdfDocument.numPages+1;
    if (partner) {
      const other=this.get(partner);
      const start=boundaryLocation(other,'start'),end=boundaryLocation(other,'end');
      // Preserve a positive range; sub-page neighboring sections are allowed.
      if(kind==='end')high=end-1e-5;
      else low=start+1e-5;
    } else for(const section of this.viewer.sections) {
      if(section.section_id===id)continue;
      const placement=this.get(section.section_id),start=boundaryLocation(placement,'start'),end=boundaryLocation(placement,'end');
      if(start==null||end==null)continue;
      if(kind==='end' && start>=ownStart)high=Math.min(high,start);
      if(kind==='start' && end<=ownEnd)low=Math.max(low,end);
      // Check the fixed opposite edge, not the pointer's provisional range.
      // Crossing our own edge should clamp, not look like a new overlapping range.
      if((kind==='end' && start<=ownStart && end>ownStart) || (kind==='start' && start<ownEnd && end>=ownEnd)) { this.states.set(id,{error:'Sections cannot overlap'});this.changed(id);return []; }
    }
    if(low>high){this.states.set(id,{error:'Sections cannot overlap'});this.changed(id);return [];}
    let location=Math.max(low,Math.min(high,candidate));
    const tolerance=6/pageAxisLength(this.viewer.application.pdfViewer.getPageView(page-1));
    if(!partner) {
      if(kind==='end' && high>low && Math.abs(candidate-high)<tolerance)location=high;
      if(kind==='start' && high>low && Math.abs(candidate-low)<tolerance)location=low;
    }
    const ids=[id]; if(partner)ids.push(partner);
    const constrained=Math.abs(location-candidate)>1e-8;
    const neighbor=partner&&this.viewer.sections.find(s=>s.section_id===partner);
    const moved=Math.abs(location-boundaryLocation(this.viewer.sections.find(s=>s.section_id===id)?.placement,kind))>1e-8;
    const notice=partner ? [constrained?'Section end must follow its start.':'',moved?`Moved ${opposite} of ${neighbor?.name||'neighboring section'}.`:''].filter(Boolean).join(' ') : constrained?'Sections cannot overlap':'';
    const apply=(target,edge,base)=>{
      const value=this.valueAt(location,edge);
      base[`${edge}_page`]=value.page;base[`${edge}_y`]=value.y;base[`${edge}_view_box`]=value.box;
      this.drafts.set(target,base);this.tokens.set(target,(this.tokens.get(target)||0)+1);
      this.states.set(target,{pending:true,notice,clamped:constrained});
    };
    apply(id,kind,draft);
    if(partner)apply(partner,opposite,structuredClone(this.get(partner)));
    for(const target of ids)this.changed(target);
    return ids;
  }
  async setPage(id, kind, page) {
    const count=this.viewer.application.pdfDocument.numPages;
    if(!Number.isInteger(page)||page<1||page>count)throw new Error(`Enter a page from 1 to ${count}.`);
    const pdfPage=await this.viewer.application.pdfDocument.getPage(page);
    const ids=this.setBoundary(id,kind,page,null,pdfPage.view);
    if(ids.length)return this.commit(ids);
  }
  payload(draft) {
    const payload={page_count:this.viewer.application.pdfDocument.numPages,expected_revision:draft.revision??draft.expected_revision??0};
    for(const kind of ['start','end'])for(const suffix of ['page','y','view_box'])payload[`${kind}_${suffix}`]=draft[`${kind}_${suffix}`];
    return payload;
  }
  splitDivider(marker) {
    if(!this.viewer.config.isOwner||!this.viewer.managementVisible)return;
    this.suppressSplitUntil=performance.now()+500;
    const members=JSON.parse(marker.dataset.members||'[]'),left=members.find(m=>m.kind==='end'),right=members.find(m=>m.kind==='start');
    if(!left||!right)return;
    const a=structuredClone(this.get(left.id)),b=structuredClone(this.get(right.id));
    const at=boundaryLocation(a,'end'),start=boundaryLocation(a,'start'),end=boundaryLocation(b,'end');
    // About six rendered pixels to either side, bounded by the pair's outer edges.
    const axis=page=>pageAxisLength(this.viewer.application.pdfViewer.getPageView(page-1));
    const shift=(placement,kind)=>6/axis(placement[`${kind}_page`]);
    const locations=[Math.max(start+(at-start)/2,at-shift(a,'end')),Math.min(end-(end-at)/2,at+shift(b,'start'))];
    const edge=Math.round(at),count=this.viewer.application.pdfDocument.numPages;
    // Explicit exact PDF edges keep an across-page split stable at every zoom.
    const across=edge>1 && edge<=count && edge>start && edge<end && Math.abs(at-edge)<=PAGE_EDGE_SNAP/axis(a.end_page);
    for(const [index,member] of [left,right].entries()){
      const draft=index?b:a,value=this.valueAt(across?edge:locations[index],member.kind);
      if(across)value.y=value.box[index?3:1];
      draft[`${member.kind}_page`]=value.page;draft[`${member.kind}_y`]=value.y;draft[`${member.kind}_view_box`]=value.box;
      this.drafts.set(member.id,draft);this.tokens.set(member.id,(this.tokens.get(member.id)||0)+1);
      this.states.set(member.id,{pending:true});this.changed(member.id);
    }
    return this.commit([left.id,right.id],true);
  }
  retry(ids) { return this.commit(ids,this.lastSplit.get(ids[0])||false); }
  commit(ids, split=false) {
    if(!ids.length)return Promise.resolve();
    for(const id of ids){this.lastGroups.set(id,ids);this.lastSplit.set(id,split);this.states.set(id,{...this.states.get(id),error:null,saving:true});this.changed(id);}
    // Capture at gesture completion: a later drag must not change an earlier request.
    const active=ids.filter(id=>this.drafts.has(id)); if(!active.length)return Promise.resolve();
    const drafts=active.map(id=>structuredClone(this.drafts.get(id))), tokens=active.map(id=>this.tokens.get(id));
    const bases=active.map(id=>this.localRevisions.get(id));
    const work=async()=>{
      drafts.forEach((draft,index)=>{
        const revision=this.localRevisions.get(active[index]);
        if(revision!=null && revision!==bases[index])draft.revision=revision;
      });
      try {
        if(active.length===2) {
          const before=boundaryLocation(drafts[0],'start')<boundaryLocation(drafts[1],'start')?0:1, after=1-before;
          await jsonRequest(`/api/versions/${this.viewer.config.versionId}/sections/shared-boundary`,{method:'POST',body:JSON.stringify({before_id:active[before],after_id:active[after],before:this.payload(drafts[before]),after:this.payload(drafts[after]),...(split?{split:true}:{edited_id:active[0]})})});
        } else await jsonRequest(`/api/versions/${this.viewer.config.versionId}/sections/${active[0]}/placement`,{method:'POST',body:JSON.stringify(this.payload(drafts[0]))});
        await this.viewer.refresh();
        active.forEach((id,index)=>{
          // Only rebase onto our acknowledged write, never an intervening owner's edit.
          const revision=this.payload(drafts[index]).expected_revision+1;
          this.localRevisions.set(id,revision);
          if(this.tokens.get(id)===tokens[index])this.drafts.delete(id);
          else {
            const pending=this.drafts.get(id);
            if(pending)pending.revision=revision;
          }
          this.states.set(id,{...this.states.get(id),saving:this.drafts.has(id),pending:this.drafts.has(id),saved:true,error:null});this.changed(id);
        });
      } catch(error) {
        for(const id of active){this.states.set(id,{error:error.message});this.changed(id);}
      }
    };
    this.queue=this.queue.then(work,work);return this.queue;
  }
  point(event, view, kind) {
    const rect = view.div.getBoundingClientRect(), box = view.viewport.viewBox;
    const point = view.viewport.convertToPdfPoint(
      (event.clientX - rect.left - view.div.clientLeft) * view.viewport.width / view.div.clientWidth,
      (event.clientY - rect.top - view.div.clientTop) * view.viewport.height / view.div.clientHeight);
    const y = Math.max(box[1], Math.min(box[3], point[1]));
    return y;
  }
  click(event) {
    if (performance.now() < (this.suppressClickUntil || 0)) { event.preventDefault(); event.stopImmediatePropagation(); return; }
    const marker = event.target.closest('[data-section-id].section-structure-marker');
    if (marker && this.viewer.config.isOwner) {
      event.preventDefault(); event.stopImmediatePropagation();
      this.viewer.onActivateSection?.(marker.dataset.sectionId, marker.dataset.kind || 'end');
    }
  }
  startDrag(event) {
    const marker = event.target.closest('.section-management-line');
    if (!marker || !this.viewer.config.isOwner || !this.viewer.managementVisible || event.button !== 0) return;
    event.preventDefault(); event.stopImmediatePropagation();
    const id = marker.dataset.sectionId, kind = marker.dataset.kind;
    this.viewer.onActivateSection?.(id, kind);
    const capture = this.viewer.application.pdfViewer.container;
    const members=JSON.parse(marker.dataset.members||'[]');
    const partner=members.find(member=>member.id!==id&&member.kind!==kind)?.id||null, affected=[id,...(partner?[partner]:[])];
    const key=members.map(m=>m.id+':'+m.kind).sort().join('|'),last=this.lastDividerClick;
    if(partner&&last?.key===key&&performance.now()-last.time<450&&Math.hypot(event.clientX-last.x,event.clientY-last.y)<5){
      this.lastDividerClick=null;this.splitDivider(marker);return;
    }
    const original=new Map(affected.map(target=>[target,this.drafts.has(target)?structuredClone(this.drafts.get(target)):null]));
    let changedIds=[];
    const startX = event.clientX, startY = event.clientY;
    let moved = false;
    this.cancelDrag?.();
    const listeners = new AbortController(), doc = this.viewer.frame.contentDocument;
    capture.setPointerCapture(event.pointerId);
    doc.documentElement.classList.add('section-dragging');
    let pointer = event, frame = null;
    const update = () => {
      const view = this.pageAtPoint(pointer, kind);
      if (view) changedIds=this.setBoundary(id, kind, Number(view.div.dataset.pageNumber), this.point(pointer, view, kind), view.viewport.viewBox, partner);
    };
    const scroll = () => {
      if (!moved) return;
      const rect = capture.getBoundingClientRect();
      const distance = pointer.clientY < rect.top + 36 ? pointer.clientY - rect.top - 36 : pointer.clientY > rect.bottom - 36 ? pointer.clientY - rect.bottom + 36 : 0;
      if (distance) { capture.scrollBy(0, Math.max(-18, Math.min(18, distance / 2))); update(); }
      frame = requestAnimationFrame(scroll);
    };
    doc.addEventListener('pointermove', move => {
      if (move.pointerId !== event.pointerId) return;
      if (!moved && Math.hypot(move.clientX - startX, move.clientY - startY) < 3) return;
      pointer = move; move.preventDefault();
      if (!moved) { moved = true; frame = requestAnimationFrame(scroll); }
      update();
    }, { capture: true, signal: listeners.signal });
    const finish = cancel => {
      listeners.abort(); this.cancelDrag = null; cancelAnimationFrame(frame); doc.documentElement.classList.remove('section-dragging');
      if (capture.hasPointerCapture(event.pointerId)) capture.releasePointerCapture(event.pointerId);
      if (cancel) for(const target of affected){if(original.get(target))this.drafts.set(target,original.get(target));else this.drafts.delete(target);this.states.delete(target);this.changed(target);}
      else if(moved)this.commit(changedIds);
      else this.lastDividerClick={key:members.map(m=>m.id+':'+m.kind).sort().join('|'),time:performance.now(),x:event.clientX,y:event.clientY};
      if (moved) this.suppressClickUntil = performance.now() + 150;
    };
    this.cancelDrag = () => finish(true);
    doc.addEventListener('pointerup', up => { if (up.pointerId === event.pointerId) finish(false); }, { capture: true, signal: listeners.signal });
    doc.addEventListener('pointercancel', cancel => { if (cancel.pointerId === event.pointerId) finish(true); }, { capture: true, signal: listeners.signal });
  }
  pageAtPoint(event, kind) {
    const pdf = this.viewer.application.pdfViewer, doc = this.viewer.frame.contentDocument;
    const hit = doc.elementFromPoint(event.clientX, event.clientY)?.closest('.page');
    if (hit) return pdf.getPageView(Number(hit.dataset.pageNumber)-1);
    const pages = Array.from({length:this.viewer.application.pdfDocument.numPages}, (_,i)=>pdf.getPageView(i)).filter(view=>view?.div.isConnected);
    const candidates = pages.map(view=>({view, rect:view.div.getBoundingClientRect()}));
    const column = candidates.filter(({rect})=>event.clientX>=rect.left && event.clientX<=rect.right);
    const above = column.filter(({rect})=>rect.bottom<=event.clientY).sort((a,b)=>b.rect.bottom-a.rect.bottom)[0];
    const below = column.filter(({rect})=>rect.top>=event.clientY).sort((a,b)=>a.rect.top-b.rect.top)[0];
    if (above && below) return (kind==='end'?above:below).view;
    const distance = ({rect}) => Math.max(rect.left-event.clientX,0,event.clientX-rect.right)**2 + Math.max(rect.top-event.clientY,0,event.clientY-rect.bottom)**2;
    return candidates.sort((a,b)=>distance(a)-distance(b))[0]?.view;
  }
  cancel(id) {
    this.cancelDrag?.(); this.drafts.delete(id); this.changed(id);
  }
  detach() { this.cancelDrag?.(); }
}
