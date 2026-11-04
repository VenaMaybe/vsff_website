import { CommentFilters } from './comment_filters.js';
import { jsonRequest } from './thread_api.js';
import { syncMenuValues } from './menus.js';
function element(tag,text) {const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;}
export class ViewerPreferences {
  constructor(config,application,refresh,status) {
    Object.assign(this,{config,application,refresh,status});this.pending=Promise.resolve();
    const menu=document.querySelector('#comments-menu > .toolbar-popover');menu.append(element('hr'));
    const filters=element('button','Filter comments...');filters.type='button';filters.dataset.commentFilters='';menu.append(filters);
    this.filters=new CommentFilters(application,filters,payload=>this.save(payload));
    filters.onclick=()=>{document.getElementById('comments-menu').open=false;this.filters.open();};
    const reset=element('button','Reset to document defaults');reset.type='button';menu.append(element('hr'),reset);reset.onclick=()=>this.save({},true);
    for(const [id,key] of [['review-scope','scope'],['review-spread','spread'],['comments-visibility','display']])document.getElementById(id).addEventListener('change',()=>{
      if(!this.applying){const value=document.getElementById(id).value;this.save({[key]:key==='spread'?Number(value):value});}
    });
    if(config.isOwner){const view=document.querySelector('#review-view-menu > .toolbar-popover');
      const settings=element('button','Review settings');settings.type='button';settings.dataset.reviewSettings=config.documentId;
      const sections=element('button','Manage sections');sections.type='button';sections.dataset.sections=config.documentId;view.append(element('hr'),settings,sections);}
  }
  async initialize(){const {preferences}=await jsonRequest(this.config.preferencesUrl,{method:'POST',body:'{}'});this.apply(preferences);}
  apply(preferences){this.filters.mode=null;document.getElementById('pdf-viewer-frame').contentWindow.reviewSetDownloadsAllowed?.(!!preferences.defaults.downloads_allowed);this.applying=true;for(const [id,key] of [['review-scope','effective_scope'],['review-spread','spread'],['comments-visibility','display']]){const input=document.getElementById(id);input.value=preferences[key];input.dispatchEvent(new Event('change'));}this.application.pdfViewer.spreadMode=preferences.spread;this.applying=false;syncMenuValues();}
  save(payload,reset=false){this.pending=this.pending.then(async()=>{const {preferences}=await jsonRequest(this.config.preferencesUrl,{method:reset?'DELETE':'POST',body:JSON.stringify(payload)});if(reset)this.apply(preferences);await this.refresh();}).catch(error=>this.status(error.message,'error'));return this.pending;}
  update(data){const prefs=data.preferences;document.getElementById('pdf-viewer-frame').contentWindow.reviewSetDownloadsAllowed?.(!!prefs.defaults.downloads_allowed);document.getElementById('review-scope').value=prefs.effective_scope;this.filters.update(prefs,data.people);syncMenuValues();}
}
