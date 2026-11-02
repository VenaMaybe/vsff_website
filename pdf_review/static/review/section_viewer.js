import { jsonRequest } from './thread_api.js';

function node(tag,text,className='') { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; e.className=className; return e; }

export function sectionGeometry(application,section) {
  const p=section?.placement;
  const view=p && application.pdfViewer.getPageView(p.end_page-1);
  if(!view?.viewport || !view.div.isConnected) return null;
  const box=view.div.getBoundingClientRect();
  const [x0,y0,x1,y1]=p.end_view_box;
  const point=view.viewport.convertToViewportPoint((x0+x1)/2,p.end_y??y0);
  const y=p.end_y===null ? box.bottom : box.top+view.div.clientTop+point[1]*view.div.clientHeight/view.viewport.height;
  return {page:box,pageNumber:p.end_page,top:y,bottom:y,left:box.left,right:box.right};
}

export class SectionViewer {
  constructor(frame,application,config,state,refresh,status) {
    Object.assign(this,{frame,application,config,state,refresh,status});
    this.sections=[];
    const link=frame.contentDocument.createElement('link'); link.rel='stylesheet'; link.href=new URL('../styles/sections.css',import.meta.url).href;
    frame.contentDocument.head.append(link);
    for(const event of ['pagerendered','scalechanging','rotationchanging','spreadmodechanged','scrollmodechanged']) application.eventBus.on(event,()=>this.schedule());
    this.editor=document.getElementById('section-editor');
    if(this.editor) this.installEditor();
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
    if(this.editor) {
      const select=document.getElementById('section-choice'),current=select.value;
      select.replaceChildren(...data.sections.map(s=>{const o=node('option',s.name); o.value=s.section_id; return o;}));
      if(data.sections.some(s=>s.section_id===current)) select.value=current;
    }
    this.schedule();
  }
  schedule() { if(this.scheduled)return; this.scheduled=true; requestAnimationFrame(()=>{this.scheduled=false;this.render();}); }
  render() {
    const doc=this.frame.contentDocument,pdf=this.application.pdfViewer;
    doc.querySelectorAll('.section-structure-marker').forEach(e=>e.remove());
    for(const section of this.sections.filter(s=>s.placement)) {
      const p=section.placement,view=pdf.getPageView(p.end_page-1);
      if(!view?.viewport)continue;
      const spread=view.div.closest('.spread');
      const siblings=spread?[...spread.querySelectorAll(':scope > .page')]:[view.div];
      const intra=p.end_y===null && siblings.at(-1)!==view.div;
      const rail=p.end_y===null && !intra && pdf.scrollMode!==1;
      const marker=doc.createElement('span');
      marker.className=`section-structure-marker ${rail?'section-row-rail':'section-edge-tick'}`;
      marker.tabIndex=0; marker.setAttribute('role','note');
      const label=`End of ${section.name}${section.prompt?`. Author prompt: ${section.prompt}`:''}`;
      marker.setAttribute('aria-label',label); marker.title=label;
      if(rail) { marker.textContent=`End of ${section.name}`; marker.style.top=`${view.div.clientHeight+1}px`; }
      else {
        const g=sectionGeometry(this.application,section),b=view.div.getBoundingClientRect();
        marker.style.top=`${Math.max(0,Math.min(view.div.clientHeight-2,g.top-b.top-view.div.clientTop))}px`;
      }
      view.div.append(marker);
    }
    if(this.draft && this.editor && !this.editor.hidden)for(const kind of ['start','end']) {
      const page=this.draft[`${kind}_page`],view=page && pdf.getPageView(page-1);if(!view?.viewport)continue;
      const box=this.draft[`${kind}_view_box`],y=this.draft[`${kind}_y`];
      const marker=doc.createElement('span');marker.className='section-structure-marker section-draft-marker';marker.textContent=`${kind} preview`;
      const point=view.viewport.convertToViewportPoint((box[0]+box[2])/2,y??(kind==='start'?box[3]:box[1]));
      marker.style.top=`${point[1]*view.div.clientHeight/view.viewport.height}px`;view.div.append(marker);
    }
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
  installEditor() {
    document.getElementById('section-editor-close').onclick=()=>{this.editor.hidden=true;this.target=null;this.draft=null;this.schedule();this.frame.contentDocument.documentElement.classList.remove('section-editing');};
    for(const kind of ['start','end']) document.getElementById(`section-set-${kind}`).onclick=()=>{
      this.target=kind; this.frame.contentDocument.documentElement.classList.add('section-editing');
      this.status(`Click the ${kind} location on a PDF page. Click near its edge for an exact page boundary.`);
      document.getElementById('section-boundary-preview').textContent=`Click PDF to set ${kind}`;
    };
    document.getElementById('section-choice').onchange=()=>{this.draft=null; document.getElementById('section-boundary-preview').textContent='Choose Set start or Set end.';};
    this.frame.contentDocument.addEventListener('click',event=>{
      if(!this.target || this.editor.hidden)return;
      const page=event.target.closest('.page'); if(!page)return;
      event.preventDefault();event.stopImmediatePropagation();
      const section=this.sections.find(s=>s.section_id===document.getElementById('section-choice').value); if(!section)return;
      const number=Number(page.dataset.pageNumber),view=this.application.pdfViewer.getPageView(number-1),b=page.getBoundingClientRect();
      const point=view.viewport.convertToPdfPoint((event.clientX-b.left-page.clientLeft)*view.viewport.width/page.clientWidth,(event.clientY-b.top-page.clientTop)*view.viewport.height/page.clientHeight);
      this.draft??=section.placement?{...section.placement}:{expected_revision:0};
      this.draft[`${this.target}_page`]=number;
      this.draft[`${this.target}_y`]=event.clientY-b.top<8 || b.bottom-event.clientY<8 ? null : Math.max(view.viewport.viewBox[1],Math.min(view.viewport.viewBox[3],point[1]));
      this.draft[`${this.target}_view_box`]=[...view.viewport.viewBox];
      document.getElementById('section-boundary-preview').textContent=`Start: p.${this.draft.start_page??'?'} Y ${this.draft.start_y??'edge'} · End: p.${this.draft.end_page??'?'} Y ${this.draft.end_y??'edge'}`;
      this.target=null;this.frame.contentDocument.documentElement.classList.remove('section-editing');
      this.schedule();
    },true);
    document.getElementById('section-save-placement').onclick=()=>this.action(async()=>{
      if(!this.draft?.start_page || !this.draft?.end_page)throw new Error('Set both start and end before saving.');
      const section=this.sections.find(s=>s.section_id===document.getElementById('section-choice').value);
      const {revision,...placement}=this.draft;
      placement.expected_revision=revision??placement.expected_revision??0;
      placement.page_count=this.application.pdfDocument.numPages;
      await jsonRequest(`/api/versions/${this.config.versionId}/sections/${section.section_id}/placement`,{method:'POST',body:JSON.stringify(placement)});
      this.draft=null;document.getElementById('section-boundary-preview').textContent='Boundaries saved.';
    });
    document.getElementById('section-outline').onclick=()=>this.previewOutline().catch(error=>this.status(error.message,'error'));
    if(new URLSearchParams(location.search).get('sections')==='edit')this.editor.hidden=false;
  }
  async previewOutline() {
    const outline=await this.application.pdfDocument.getOutline();
    if(!outline?.length) {this.status('This PDF has no outline. Define sections manually.');return;}
    const dialog=node('dialog',undefined,'outline-dialog'),form=node('form'),list=node('div');
    const candidates=[];
    const walk=async(items,depth=0)=>{
      for(const item of items) {
        const dest=typeof item.dest==='string'?await this.application.pdfDocument.getDestination(item.dest):item.dest;
        if(dest?.length) {
          const page=Number.isInteger(dest[0])?dest[0]+1:await this.application.pdfDocument.getPageIndex(dest[0])+1;
          const row=node('label',undefined,'outline-candidate'),check=node('input'),name=node('input'),position=node('input');
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
    submit.type='submit';cancel.type='button';cancel.onclick=()=>dialog.close();
    form.append(node('h2','Import PDF outline'),message,list,error,submit,cancel);dialog.append(form);document.body.append(dialog);
    dialog.addEventListener('close',()=>dialog.remove());dialog.showModal();
    form.onsubmit=async event=>{
      event.preventDefault();submit.disabled=true;
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
        await this.refresh();dialog.close();
      } catch(e){error.textContent=e.message;} finally {submit.disabled=false;}
    };
  }
}
