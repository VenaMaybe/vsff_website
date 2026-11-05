import { LeftCard, registerLeftCard } from './left_card.js';

function element(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}

export class CommentFilters {
  constructor(application,opener,save){
    this.save=save;this.mode=null;this.rows=new Map();this.pending=0;
    this.card=new LeftCard('Comment filter',{opener,stateKey:'filters',className:'comment-filter-panel',viewer:{sectionViewer:{frame:document.getElementById('pdf-viewer-frame'),application}}});
    this.modes=element('fieldset');this.modes.className='filter-modes';this.modes.append(element('legend','Show'));
    this.inputs=new Map();
    for(const [value,text] of [['all','All comments'],['mine','Only mine'],['people','Selected reviewers']]){
      const label=element('label'),input=element('input');input.type='radio';input.name='comment-filter-mode';input.value=value;input.disabled=true;
      input.onchange=()=>{if(!input.checked)return;this.mode=value;this.commit({scope:value==='mine'?'mine':'all',hidden_reviewers:value==='all'?[]:[...this.prefs.hidden_reviewers]});};
      label.append(input,document.createTextNode(text));this.modes.append(label);this.inputs.set(value,input);
    }
    this.policy=element('p');this.policy.className='subtle comment-filter-policy';
    this.choices=element('fieldset');this.choices.className='filter-reviewers';
    this.choices.append(element('legend','Show comments from'));
    this.list=element('div');this.choices.append(this.list);
    this.empty=element('p','No reviewers have commented yet.');this.empty.className='subtle';this.choices.append(this.empty);
    this.card.body.append(this.modes,this.policy,this.choices);
    registerLeftCard('filters',()=>this.open());
  }
  open(){this.card.open();this.card.contentReady();return this.card;}
  commit(draft){
    this.draft=draft;this.pending++;this.render();
    this.save(draft).finally(()=>{if(--this.pending===0){this.draft=null;this.render();}});
  }
  update(prefs,people){this.canonical=prefs;this.people=people;this.render();}
  render(){
    if(!this.canonical)return;
    this.prefs={...this.canonical,...(this.draft&&!this.canonical.isolated?{effective_scope:this.draft.scope,hidden_reviewers:this.draft.hidden_reviewers}:{})};
    const prefs=this.prefs;
    this.mode=prefs.isolated||prefs.effective_scope==='mine'?'mine':prefs.hidden_reviewers.length?'people':this.mode==='people'?'people':'all';
    for(const [value,input] of this.inputs){input.checked=this.mode===value;input.disabled=prefs.isolated&&value!=='mine';}
    this.policy.textContent=prefs.isolated?'Isolated review: only your conversations are available.':'';this.policy.hidden=!prefs.isolated;
    this.choices.hidden=this.mode!=='people'||prefs.isolated;this.empty.hidden=this.people.length>0;
    const labels=[];
    for(const person of this.people){
      let row=this.rows.get(person.user_id);
      if(!row){
        const label=element('label'),input=element('input'),text=document.createTextNode('');input.type='checkbox';input.dataset.reviewerId=person.user_id;
        input.onchange=()=>{const hidden=new Set(this.prefs.hidden_reviewers);if(input.checked)hidden.delete(person.user_id);else hidden.add(person.user_id);this.mode='people';this.commit({scope:'all',hidden_reviewers:[...hidden]});};
        label.append(input,text);row={label,input,text};this.rows.set(person.user_id,row);
      }
      row.text.textContent=person.display_name;row.input.setAttribute('aria-label',`Show ${person.display_name}`);
      row.input.checked=!prefs.hidden_reviewers.includes(person.user_id);row.input.disabled=prefs.isolated;labels.push(row.label);
    }
    if(labels.length!==this.list.children.length||labels.some((label,index)=>label!==this.list.children[index]))this.list.replaceChildren(...labels);
  }
}
