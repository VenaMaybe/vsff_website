import { jsonRequest } from './thread_api.js';
import { syncMenuValues } from './menus.js';
function element(tag,text) {const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;}
export class ViewerPreferences {
  constructor(config,application,refresh,status) {
    Object.assign(this,{config,application,refresh,status});this.pending=Promise.resolve();
    const menu=document.querySelector('#comments-menu > .toolbar-popover');menu.append(element('hr'));
    for(const [value,label] of [['mine','Mine']]) {
      const button=element('button',label);button.type='button';button.dataset.menuInput='review-scope';button.dataset.menuValue=value;button.setAttribute('role','menuitemradio');menu.append(button);
    }
    this.policy=element('p');this.policy.className='subtle';menu.append(this.policy);
    this.people=element('details');this.people.className='toolbar-menu submenu review-people';this.people.append(element('summary','Everyone'));
    this.choices=element('div');this.choices.className='toolbar-popover';this.choices.setAttribute('role','menu');this.choices.dataset.keepMenuOpen='true';this.people.append(this.choices);menu.insertBefore(this.people,menu.querySelector('[data-menu-value=mine]'));
    const everyone=this.people.firstChild;everyone.dataset.menuInput='review-scope';everyone.dataset.menuValue='all';everyone.setAttribute('role','menuitemradio');
    everyone.setAttribute('aria-haspopup','menu');
    this.people.addEventListener('toggle',()=>{this.people.firstChild.setAttribute('aria-expanded',String(this.people.open));if(!this.people.open)return;const scope=document.getElementById('review-scope');if(scope.value!=='all'){scope.value='all';scope.dispatchEvent(new Event('change'));}this.choices.style.maxHeight=`${innerHeight-16}px`;const b=this.people.getBoundingClientRect();this.choices.style.left=`${Math.max(8,Math.min(innerWidth-this.choices.offsetWidth-8,b.right))}px`;this.choices.style.top=`${Math.max(8,Math.min(innerHeight-this.choices.offsetHeight-8,b.top))}px`;});
    const reset=element('button','Reset to document defaults');reset.type='button';menu.append(element('hr'),reset);reset.onclick=()=>this.save({},true);
    for(const [id,key] of [['review-scope','scope'],['review-spread','spread'],['comments-visibility','display']])document.getElementById(id).addEventListener('change',()=>{
      if(!this.applying){const value=document.getElementById(id).value;this.save({[key]:key==='spread'?Number(value):value});}
    });
    if(config.isOwner){const view=document.querySelector('#review-view-menu > .toolbar-popover');
      const settings=element('button','Review settings');settings.type='button';settings.dataset.reviewSettings=config.documentId;
      const sections=element('button','Manage sections');sections.type='button';sections.dataset.sections=config.documentId;view.append(element('hr'),settings,sections);}
  }
  async initialize(){const {preferences}=await jsonRequest(this.config.preferencesUrl,{method:'POST',body:'{}'});this.apply(preferences);}
  apply(preferences){document.getElementById('pdf-viewer-frame').contentWindow.reviewSetDownloadsAllowed?.(!!preferences.defaults.downloads_allowed);this.applying=true;for(const [id,key] of [['review-scope','effective_scope'],['review-spread','spread'],['comments-visibility','display']]){const input=document.getElementById(id);input.value=preferences[key];input.dispatchEvent(new Event('change'));}this.application.pdfViewer.spreadMode=preferences.spread;this.applying=false;syncMenuValues();}
  save(payload,reset=false){this.pending=this.pending.then(async()=>{const {preferences}=await jsonRequest(this.config.preferencesUrl,{method:reset?'DELETE':'POST',body:JSON.stringify(payload)});if(reset)this.apply(preferences);await this.refresh();}).catch(error=>this.status(error.message,'error'));return this.pending;}
  update(data){const prefs=data.preferences;document.getElementById('pdf-viewer-frame').contentWindow.reviewSetDownloadsAllowed?.(!!prefs.defaults.downloads_allowed);this.policy.textContent=prefs.isolated?'Isolated review · only your conversations':'';document.querySelector('[data-menu-input="review-scope"][data-menu-value="all"]').disabled=prefs.isolated;document.getElementById('review-scope').value=prefs.effective_scope;this.choices.replaceChildren();
    const all=element('button','All');all.type='button';all.onclick=()=>{this.latest.hidden_reviewers=[];this.choices.querySelectorAll('input').forEach(input=>input.checked=true);document.getElementById('review-scope').value='all';syncMenuValues();this.save({scope:'all',hidden_reviewers:[]});};this.choices.append(all);
    for(const person of data.people){const label=element('label'),input=element('input');input.type='checkbox';input.checked=!prefs.hidden_reviewers.includes(person.user_id);input.setAttribute('aria-label',`Show ${person.display_name}`);
      input.onchange=()=>{const hidden=new Set(this.latest.hidden_reviewers);if(input.checked)hidden.delete(person.user_id);else hidden.add(person.user_id);this.latest.hidden_reviewers=[...hidden];this.save({scope:'all',hidden_reviewers:[...hidden]});};label.append(input,document.createTextNode(person.display_name));this.choices.append(label);}
    this.people.hidden=prefs.isolated;this.latest=prefs;syncMenuValues();}
}
