import { jsonRequest } from './thread_api.js';
import { syncMenuValues } from './menus.js';
function element(tag,text) {const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;}
export class ViewerPreferences {
  constructor(config,application,refresh,status) {
    Object.assign(this,{config,application,refresh,status});this.pending=Promise.resolve();
    const menu=document.querySelector('#comments-menu > .toolbar-popover');menu.append(element('hr'));
    for(const [value,label] of [['all','Everyone'],['mine','Mine']]) {
      const button=element('button',label);button.type='button';button.dataset.menuInput='review-scope';button.dataset.menuValue=value;button.setAttribute('role','menuitemradio');menu.append(button);
    }
    this.policy=element('p');this.policy.className='subtle';menu.append(this.policy);
    this.people=element('details');this.people.className='toolbar-menu submenu review-people';this.people.append(element('summary','People…'));
    this.choices=element('div');this.choices.className='toolbar-popover';this.choices.setAttribute('role','menu');this.people.append(this.choices);menu.append(this.people);
    this.people.firstChild.setAttribute('aria-haspopup','menu');
    this.people.addEventListener('toggle',()=>{this.people.firstChild.setAttribute('aria-expanded',String(this.people.open));if(!this.people.open)return;const b=this.people.getBoundingClientRect();this.choices.style.left=`${Math.max(8,Math.min(innerWidth-this.choices.offsetWidth-8,b.right))}px`;this.choices.style.top=`${Math.max(8,Math.min(innerHeight-this.choices.offsetHeight-8,b.top))}px`;});
    const reset=element('button','Reset to document defaults');reset.type='button';menu.append(reset);reset.onclick=()=>this.save({},true);
    for(const [id,key] of [['review-scope','scope'],['review-spread','spread'],['comments-visibility','display']])document.getElementById(id).addEventListener('change',()=>{
      if(!this.applying){const value=document.getElementById(id).value;this.save({[key]:key==='spread'?Number(value):value});}
    });
    if(config.isOwner){const view=document.querySelector('#review-view-menu > .toolbar-popover');
      const settings=element('button','Review settings');settings.type='button';settings.dataset.reviewSettings=config.documentId;
      const sections=element('button','Manage sections');sections.type='button';sections.dataset.sections=config.documentId;view.append(element('hr'),settings,sections);}
  }
  async initialize(){const {preferences}=await jsonRequest(this.config.preferencesUrl,{method:'POST',body:'{}'});this.apply(preferences);}
  apply(preferences){this.applying=true;for(const [id,key] of [['review-scope','effective_scope'],['review-spread','spread'],['comments-visibility','display']]){const input=document.getElementById(id);input.value=preferences[key];input.dispatchEvent(new Event('change'));}this.application.pdfViewer.spreadMode=preferences.spread;this.applying=false;syncMenuValues();}
  save(payload,reset=false){this.pending=this.pending.then(async()=>{const {preferences}=await jsonRequest(this.config.preferencesUrl,{method:reset?'DELETE':'POST',body:JSON.stringify(payload)});if(reset)this.apply(preferences);await this.refresh();}).catch(error=>this.status(error.message,'error'));return this.pending;}
  update(data){const prefs=data.preferences;this.policy.textContent=prefs.isolated?'Isolated review · only your conversations':'';document.querySelector('[data-menu-input="review-scope"][data-menu-value="all"]').disabled=prefs.isolated;document.getElementById('review-scope').value=prefs.effective_scope;this.choices.replaceChildren();
    for(const person of data.people){const label=element('label'),input=element('input');input.type='checkbox';input.checked=!prefs.hidden_reviewers.includes(person.user_id);input.setAttribute('aria-label',`Show ${person.display_name}`);
      input.onchange=()=>{const hidden=new Set(this.latest.hidden_reviewers);if(input.checked)hidden.delete(person.user_id);else hidden.add(person.user_id);this.latest.hidden_reviewers=[...hidden];this.save({hidden_reviewers:[...hidden]});};label.append(input,document.createTextNode(person.display_name));this.choices.append(label);}
    this.people.hidden=prefs.isolated;this.latest=prefs;syncMenuValues();}
}
