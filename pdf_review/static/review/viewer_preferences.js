import { CommentFilters } from './comment_filters.js';
import { jsonRequest } from './thread_api.js';
import { syncMenuValues } from './menus.js';
function element(tag,text) {const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;}
export class ViewerPreferences {
  constructor(config,application,refresh,status) {
    Object.assign(this,{config,application,refresh,status});this.pending=Promise.resolve();
    this.cardZoom=document.getElementById('review-card-zoom');
    this.setCardZoom(Number(this.cardZoom.value));
    this.cardZoom.addEventListener('input',()=>this.setCardZoom(Number(this.cardZoom.value)));
    this.cardZoom.addEventListener('change',()=>this.save({card_zoom_threshold:Number(this.cardZoom.value)}));
    const menu=document.querySelector('#comments-menu > .toolbar-popover');
    const filters=document.querySelector('[data-comment-filters]');
    this.filters=new CommentFilters(application,filters,payload=>this.save(payload));
    const reset=element('button','Reset to document defaults');reset.type='button';menu.append(element('hr'),reset);reset.onclick=()=>this.save({},true);
    for(const [id,key] of [['review-scope','scope'],['review-spread','spread'],['comments-visibility','display']])document.getElementById(id).addEventListener('change',()=>{
      if(!this.applying){const value=document.getElementById(id).value;this.save({[key]:key==='spread'?Number(value):value});}
    });
  }
  async initialize(){const {preferences}=await jsonRequest(this.config.preferencesUrl,{method:'POST',body:'{}'});this.apply(preferences);}
  setCardZoom(value){
    this.cardZoom.value=value;
    document.querySelector('output[for="review-card-zoom"]').textContent=`${value}%`;
    if(this.application.reviewCardZoomThreshold===value)return;
    this.application.reviewCardZoomThreshold=value;
    this.application.eventBus.dispatch('reviewcardscalechanged',{source:this});
  }
  apply(preferences){this.setCardZoom(preferences.card_zoom_threshold);this.filters.mode=null;document.getElementById('pdf-viewer-frame').contentWindow.reviewSetDownloadsAllowed?.(!!preferences.defaults.downloads_allowed);this.applying=true;for(const [id,key] of [['review-scope','effective_scope'],['review-spread','spread'],['comments-visibility','display']]){const input=document.getElementById(id);input.value=preferences[key];input.dispatchEvent(new Event('change'));}this.application.pdfViewer.spreadMode=preferences.spread;this.applying=false;syncMenuValues();}
  save(payload,reset=false){this.pending=this.pending.then(async()=>{const {preferences}=await jsonRequest(this.config.preferencesUrl,{method:reset?'DELETE':'POST',body:JSON.stringify(payload)});if(reset)this.apply(preferences);await this.refresh();}).catch(error=>this.status(error.message,'error'));return this.pending;}
  update(data){const prefs=data.preferences;document.getElementById('pdf-viewer-frame').contentWindow.reviewSetDownloadsAllowed?.(!!prefs.defaults.downloads_allowed);document.getElementById('review-scope').value=prefs.effective_scope;this.filters.update(prefs,data.people);syncMenuValues();}
}
