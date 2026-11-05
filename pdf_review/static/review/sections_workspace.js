import { confirmAction } from './dialogs.js';
import { jsonRequest } from './thread_api.js';
import { SectionsPanel } from './sections_panel.js';
import { orderSections } from './section_order.js';
import { sectionPageRange } from './section_boundaries.js';
import { boundaryEdge } from './section_boundary_geometry.js';

function node(tag,text,className='') {const e=document.createElement(tag);e.className=className;if(text!==undefined)e.textContent=text;return e;}
function button(text,action){const e=node('button',text);e.type='button';e.onclick=action;return e;}

export class SectionsWorkspace {
  constructor(documentId,{opener,viewer,selectedId}) {
    Object.assign(this,{documentId,viewer,selectedId});this.versionId=viewer?.config.versionId||null;
    this.editor=viewer?.sectionViewer.placementEditor;this.metadata=new Map();
    this.onPlacement=()=>{if(this.list){this.renderList();this.syncPlacement();}};
    this.dialog=new SectionsPanel(opener,visible=>{
      viewer?.sectionViewer.setManagementVisible(visible,this.selectedId);
      if(visible)this.editor?.listeners.add(this.onPlacement);
      else {this.editor?.listeners.delete(this.onPlacement);this.editor?.detach();for(const id of this.metadata.keys())this.flushMetadata(id);}
    },viewer);
  }
  async open(options){this.dialog.open(options);if(!this.sections)this.dialog.body.textContent='Loading...';await this.load();return this;}
  async load(){
    try{
      const data=await jsonRequest(`/documents/${this.documentId}/sections${this.versionId?'?version='+encodeURIComponent(this.versionId):''}`);
      this.sections=data.sections;this.versionId=data.version_id;
      if(!this.sections.some(s=>s.section_id===this.selectedId))this.selectedId=this.sections[0]?.section_id||null;
      this.render();this.dialog.contentReady();
    }catch(error){this.dialog.body.textContent=error.message;}
  }
  select(id,reveal=true,boundaryKind=null){
    if(!this.sections){this.selectedId=id;return;}
    if(!this.sections.some(s=>s.section_id===id))return;
    this.selectedId=id;this.fieldError='';this.renderList();this.renderDetail();
    if(boundaryKind)this.dialog.centerOn(()=>this.viewer.sectionViewer.boundaryCenter(id,boundaryKind));
    else if(reveal)this.dialog.reveal();
  }
  render(){
    const layout=node('div',undefined,'sections-workspace');
    const master=node('nav',undefined,'sections-master');master.setAttribute('aria-label','Sections');
    this.list=node('div',undefined,'section-master-list');
    master.append(this.list,button('+ Add section',()=>this.add()),button('Import outline...',()=>this.importOutline()));
    this.detail=node('div',undefined,'section-detail');layout.append(master,this.detail);
    this.dialog.body.replaceChildren(layout);this.renderList();this.renderDetail();
  }
  renderList(){
    this.viewer?.sectionViewer.setManagementVisible(this.dialog.element.isConnected,this.selectedId);
    this.list.replaceChildren();
    const sections=orderSections(this.sections,s=>this.editor?.get(s.section_id)||s.placement);
    for(const [index,section] of sections.entries()){
      const name=this.metadata.get(section.section_id)?.values.name||section.name;
      const item=button('',()=>{this.select(section.section_id,false);this.name.focus();});
      const title=node('span',`${index+1}  ${name}`,'section-list-name');
      const range=node('span',sectionPageRange(this.editor?.get(section.section_id)||section.placement),'section-list-range');
      if(range.textContent)range.setAttribute('aria-label',`Pages ${range.textContent}`);
      item.append(title,range);
      item.className='section-master-item';item.dataset.sectionId=section.section_id;item.setAttribute('aria-current',String(section.section_id===this.selectedId));
      item.onkeydown=event=>{
        if(!['ArrowUp','ArrowDown','Home','End'].includes(event.key))return;
        event.preventDefault();const target=event.key==='Home'?0:event.key==='End'?sections.length-1:Math.max(0,Math.min(sections.length-1,index+(event.key==='ArrowDown'?1:-1)));
        this.select(sections[target].section_id,false);this.list.children[target].focus();
      };
      this.list.append(item);
    }
  }
  renderDetail(){
    this.fields=null;this.detail.replaceChildren();
    const section=this.sections.find(s=>s.section_id===this.selectedId);
    if(!section){this.detail.append(node('p','Add a section to define its boundaries.','subtle'));return;}
    const id=section.section_id;
    if(!this.metadata.has(id))this.metadata.set(id,{values:{name:section.name,prompt:section.prompt},sequence:0,savedSequence:0,chain:Promise.resolve()});
    const state=this.metadata.get(id);
    const nameLabel=node('label','Name'),promptLabel=node('label','Prompt');
    this.name=node('input');this.name.name='name';this.name.value=state.values.name;this.name.maxLength=200;this.name.required=true;
    const prompt=node('textarea');prompt.name='prompt';prompt.value=state.values.prompt;prompt.rows=1;prompt.maxLength=2000;prompt.placeholder='Optional author prompt';
    const change=(field,input)=>{
      this.dialog.openingCentered=false;state.values[field]=input.value;state.sequence++;state.error=null;
      clearTimeout(state.timer);state.timer=setTimeout(()=>this.flushMetadata(id),350);this.renderList();this.syncStatus();
    };
    this.name.oninput=()=>change('name',this.name);prompt.oninput=()=>change('prompt',prompt);
    this.name.onchange=()=>this.flushMetadata(id);prompt.onchange=()=>this.flushMetadata(id);
    nameLabel.append(this.name);promptLabel.append(prompt);this.detail.append(nameLabel,promptLabel);
    if(this.editor){
      const placement=node('div',undefined,'section-placement');this.fields={};
      for(const kind of ['start','end']){
        const row=node('label',undefined,'section-boundary-fields');const text=node('span',kind==='start'?'Start':'End');
        const page=node('input');page.type='number';page.name=`${kind}_page`;page.min=1;page.max=this.viewer.sectionViewer.application.pdfDocument.numPages;page.placeholder='Page';page.setAttribute('aria-label',`${kind} page`);
        const location=node('span','','section-boundary-location');
        page.onchange=async()=>{this.fieldError='';try{await this.editor.setPage(id,kind,Number(page.value));}catch(error){this.fieldError=error.message;}this.syncPlacement(true);};
        page.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();page.blur();}};
        row.append(text,page,location);placement.append(row);this.fields[kind]={page,location};
      }
      this.detail.append(placement);
    }
    const footer=node('div',undefined,'section-inspector-footer');
    this.status=node('span','','section-save-status');this.status.setAttribute('role','status');
    const remove=button('Delete',event=>this.remove(section,event.currentTarget));remove.className='text-action danger';
    this.retry=button('Retry',()=>{if(state.error)this.flushMetadata(id);else this.editor?.retry(this.editor.lastGroups?.get(id)||[id]);});this.retry.className='text-action';
    footer.append(this.status,this.retry,remove);this.detail.append(footer);this.syncPlacement();
  }
  syncPlacement(force=false){
    if(this.fields){const placement=this.editor.get(this.selectedId);for(const kind of ['start','end']){
      const field=this.fields[kind];if(force||document.activeElement!==field.page)field.page.value=placement?.[`${kind}_page`]||'';
      const edge=boundaryEdge(this.viewer.sectionViewer.application,placement,kind);
      field.location.textContent=!placement?.[`${kind}_view_box`]?'':edge?(edge==='start'?'Start of page':'End of page'):'Inside page';
    }}this.syncStatus();
  }
  syncStatus(){
    if(!this.status)return;
    const metadata=this.metadata.get(this.selectedId),placement=this.editor?.states.get(this.selectedId)||{};
    const error=this.fieldError||metadata?.error||placement.error;
    this.status.textContent=error||((metadata?.saving||metadata?.timer||placement.saving||placement.pending)?'Saving\u2026':'Saved');
    if(!error&&placement.notice)this.status.textContent+=' \u00b7 '+placement.notice;
    this.status.classList.toggle('error',!!error);this.retry.hidden=!metadata?.error&&!(placement.error&&this.editor?.drafts.has(this.selectedId));
  }
  flushMetadata(id){
    const state=this.metadata.get(id);if(!state||state.deleted)return;
    clearTimeout(state.timer);state.timer=null;
    if(state.savedSequence===state.sequence&&!state.error)return state.chain;
    if(!state.values.name.trim()){state.error='Name is required';this.syncStatus();return state.chain;}
    state.error=null;state.saving=true;this.syncStatus();
    const work=async()=>{
      if(state.deleted)return;
      const sequence=state.sequence,values={...state.values};
      try{
        await jsonRequest(`/api/sections/${id}`,{method:'PATCH',body:JSON.stringify(values)});
        state.savedSequence=sequence;state.error=null;
        const section=this.sections.find(s=>s.section_id===id);if(section)Object.assign(section,values);
        await this.viewer?.refresh();
      }catch(error){state.error=error.message;}
      finally{state.saving=state.savedSequence!==state.sequence&&!state.error;this.renderList();this.syncStatus();}
    };
    state.chain=state.chain.then(work,work);return state.chain;
  }
  async add(){
    try{
      const result=await jsonRequest(`/api/documents/${this.documentId}/sections`,{method:'POST',body:JSON.stringify({name:'Untitled section',prompt:''})});
      this.selectedId=result.section_id;await this.load();await this.viewer?.refresh();this.name.focus();this.name.select();
    }catch(error){if(this.status){this.fieldError=error.message;this.syncStatus();}}
  }
  async remove(section,opener){
    if(!await confirmAction('Delete section',`Delete "${section.name}"? Saved placements and feedback will be retained.`,opener))return;
    const state=this.metadata.get(section.section_id);if(state){clearTimeout(state.timer);state.deleted=true;await state.chain;}
    try{
      await jsonRequest(`/api/sections/${section.section_id}`,{method:'PATCH',body:JSON.stringify({archive:true})});
      this.editor?.cancel(section.section_id);this.metadata.delete(section.section_id);await this.load();await this.viewer?.refresh();
    }catch(error){if(state)state.deleted=false;this.fieldError=error.message;this.syncStatus();}
  }
  async importOutline(){if(this.editor&&this.versionId){await this.viewer.sectionViewer.previewOutline();await this.load();}}
}
