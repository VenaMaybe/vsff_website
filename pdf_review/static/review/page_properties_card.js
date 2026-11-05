import { LeftCard, registerLeftCard } from './left_card.js';
import { pagePropertiesFor } from './page_properties_data.js';
import { viewingPages } from './presence.js';
import { mappedSections, sectionAt, commentStatistics, statisticsUnits } from './version_statistics.js';
const SVG='http://www.w3.org/2000/svg';
const METRICS={words:'Words',time:'Read time',images:'Images',comments:'Comments'};
const integers=new Intl.NumberFormat(undefined,{maximumFractionDigits:0});
const node=(tag,text,cls='')=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;e.className=cls;return e;};
function svg(tag,attrs={}){const e=document.createElementNS(SVG,tag);for(const [key,value] of Object.entries(attrs))e.setAttribute(key,value);return e;}
function setText(e,value){if(e.textContent!==value)e.textContent=value;}
function attribute(e,key,value){const text=String(value);if(e.getAttribute(key)!==text)e.setAttribute(key,text);}
function niceStep(value){if(value<=0)return 1;const base=10**Math.floor(Math.log10(value)),n=value/base;return (n<=1?1:n<=2?2:n<=5?5:10)*base;}
export class PagePropertiesCard {
  constructor(application,frame,config,policy) {
    Object.assign(this,{application,frame,config});this.policy={words_per_minute:400,minimum_page_seconds:5,...policy};this.metric='words';this.grouping='pages';this.sections=[];this.comments={records:[],authors:[]};
    this.preferenceKey=`pdf-review:page-properties-ui:v1:${config.currentUserId}:${config.versionId}`;
    try{const saved=JSON.parse(localStorage.getItem(this.preferenceKey)||'null');if(Object.hasOwn(METRICS,saved?.metric))this.metric=saved.metric;if(saved?.grouping==='sections')this.grouping='sections';}catch{/* Use Words when storage is unavailable. */}
    this.data=pagePropertiesFor(application.pdfDocument,config,frame.contentWindow.pdfjsLib?.OPS);
    this.card=new LeftCard('Statistics',{viewer:{sectionViewer:{application,frame}},opener:document.querySelector('[data-left-card=properties]'),stateKey:'properties',className:'page-properties-card'});
    this.groups=node('div',undefined,'properties-tabs properties-groups');this.groups.setAttribute('role','group');this.groups.setAttribute('aria-label','Group version statistics');
    for(const key of ['pages','sections']){const b=node('button',key==='pages'?'Pages':'Sections');b.type='button';b.dataset.grouping=key;b.onclick=()=>{this.grouping=key;this.save();this.start();};this.groups.append(b);}
    this.tabs=node('div',undefined,'properties-tabs');this.tabs.setAttribute('role','group');this.tabs.setAttribute('aria-label','Version metric');
    for(const [key,label] of Object.entries(METRICS)){
      const b=node('button',label);b.type='button';b.dataset.metric=key;b.onclick=()=>{this.metric=key;this.save();this.start();};this.tabs.append(b);
    }
    this.info=node('div',undefined,'properties-info');this.label=node('span');this.total=node('strong');this.info.append(this.label,this.total);
    this.chart=svg('svg',{class:'properties-chart',role:'group','aria-label':'Statistics histogram'});
    this.axis=svg('g');this.gridLines=svg('g');this.tickLabels=svg('g');this.bars=svg('g');this.brackets=svg('g');
    this.chart.append(this.axis,this.gridLines,this.tickLabels,this.bars,this.brackets);
    this.rows=[];
    this.legend=node('div',undefined,'properties-legend');
    this.hover=node('p','Hover a bar for details.','properties-hover');this.hover.setAttribute('aria-live','polite');
    this.summary=node('div',undefined,'properties-summary');this.summary.append(node('h3','Summary'));
    this.summaryRows=Array.from({length:4},()=>{const row=node('div');row.append(node('span'),node('strong'));this.summary.append(row);return row;});
    this.status=node('p','', 'properties-status');this.card.body.append(this.groups,this.tabs,this.info,this.chart,this.legend,this.hover,this.summary,this.status);
    registerLeftCard('properties',options=>this.open(options));
    this.data.addEventListener('change',()=>this.schedule());
    for(const event of ['pagechanging','spreadmodechanged'])application.eventBus.on(event,()=>this.currentPages());
    this.render();
  }
  createRows(){
    this.bars.replaceChildren();this.currentSignature=null;
    this.rows=this.units.map((unit,index)=>{
      const rect=svg('rect',{class:'properties-bar',tabindex:index===0?'0':'-1',role:'button','data-page':unit.page});
      const title=svg('title');rect.append(title);rect.onclick=()=>this.navigate(unit.page);
      rect.onpointerenter=rect.onfocus=()=>{this.hoveredIndex=index;setText(this.hover,this.description(index));};
      rect.onkeydown=event=>{
        if(event.key==='Enter'||event.key===' '){event.preventDefault();this.navigate(unit.page);}
        const delta=event.key==='ArrowDown'?1:event.key==='ArrowUp'?-1:0;
        if(delta){event.preventDefault();const next=this.rows[index+delta];if(next){attribute(rect,'tabindex','-1');attribute(next,'tabindex','0');next.focus();}}
      };
      rect.stack=svg('g',{'pointer-events':'none'});rect.segments=new Map();this.bars.append(rect,rect.stack);return rect;
    });
  }
  save(){try{localStorage.setItem(this.preferenceKey,JSON.stringify({metric:this.metric,grouping:this.grouping}));}catch{}}
  open(options){this.card.open(options);this.start();return this.card;}
  async start(){
    this.render();if(this.metric!=='comments')await this.data.scan(this.metric==='images'?'images':'text');
    clearTimeout(this.renderTimer);this.scheduled=false;this.render();
  }
  schedule(){if(this.scheduled||!this.card.element.isConnected)return;this.scheduled=true;this.renderTimer=setTimeout(()=>{this.scheduled=false;this.render();},100);}
  update(sections,threads=[],responses=[]){
    const mapped=mappedSections(sections,this.data.rows.length),comments=commentStatistics(threads,responses,mapped,this.data.rows.length);
    const sectionSignature=JSON.stringify(mapped),commentSignature=JSON.stringify(comments);
    if(sectionSignature===this.sectionSignature&&commentSignature===this.commentSignature)return;
    Object.assign(this,{sections:mapped,comments,sectionSignature,commentSignature});this.render();
  }
  navigate(page){this.application.pdfViewer.currentPageNumber=page;}
  values(){return this.units.map(row=>row[this.metric]);}
  format(value){return value==null?'Unavailable':this.metric==='time'?`${Math.ceil(value)}s`:integers.format(value);}
  description(index){
    const unit=this.units[index],label={time:'estimated read time',images:'images / figures',comments:'comments',words:'words'}[this.metric];
    const people=this.metric==='comments'?this.comments.authors.filter(a=>unit.people.has(a.id)).map(a=>`${a.name}: ${unit.people.get(a.id)}`).join(', '):'';
    return `${unit.name}: ${this.format(this.valuesCache[index])} ${label}${people?` (${people})`:''}`;
  }
  currentPages(){
    if(!this.rows.length||!this.card.element.isConnected)return;
    const {page,pages}=viewingPages(this.application),focused=this.card.element.contains(document.activeElement);
    const signature=`${page}:${pages.join(',')}:${focused}`;if(signature===this.currentSignature)return;this.currentSignature=signature;
    let first=-1;
    this.units.forEach((unit,i)=>{
      const current=pages.some(p=>unit.unsectioned?!sectionAt(this.sections,p-.5):unit.start<p&&unit.end>p-1);
      attribute(this.rows[i],'data-current',current);if(current&&first<0)first=i;
    });
    if(!focused){const old=this.chart.querySelector('[tabindex="0"]');if(old)attribute(old,'tabindex','-1');if(first>=0)attribute(this.rows[first],'tabindex','0');}
  }
  renderSegments(rect,unit,{left,y,height,width,axisMax}){
    const active=new Set();let offset=0;
    if(this.metric==='comments')for(const author of this.comments.authors){
      const count=unit.people.get(author.id)||0;if(!count)continue;active.add(author.id);
      let segment=rect.segments.get(author.id);if(!segment){segment=svg('rect',{'data-author':author.id});rect.segments.set(author.id,segment);rect.stack.append(segment);}
      const length=count/axisMax*width;attribute(segment,'x',left+offset);attribute(segment,'y',y);attribute(segment,'height',height);attribute(segment,'width',length);attribute(segment,'fill',author.color);offset+=length;
    }
    for(const [id,segment] of rect.segments)if(!active.has(id)){segment.remove();rect.segments.delete(id);}
  }
  render(){
    if(!this.card.element.isConnected)return;
    const renderSignature=JSON.stringify([this.metric,this.grouping,this.metric==='comments'?0:this.data.revision,this.sectionSignature,this.metric==='comments'?this.commentSignature:'']);
    if(renderSignature===this.renderSignature){this.currentPages();return;}
    this.renderSignature=renderSignature;
    this.units=statisticsUnits(this.data.rows,this.sections,this.grouping,this.comments,this.policy);
    const rowSignature=JSON.stringify([this.grouping,this.units.map(u=>[u.key,u.page])]);if(rowSignature!==this.rowSignature){this.rowSignature=rowSignature;this.createRows();this.hoveredIndex=null;}
    const values=this.valuesCache=this.values(),known=values.filter(v=>v!=null),count=values.length;
    const noun=this.grouping==='pages'?'page':'section';
    const labels={words:'Words',time:'Estimated seconds',images:'Images',comments:'Comments'};
    for(const b of this.groups.children)attribute(b,'aria-pressed',b.dataset.grouping===this.grouping);
    for(const b of this.tabs.children)attribute(b,'aria-pressed',b.dataset.metric===this.metric);
    setText(this.label,`${labels[this.metric]} per ${noun}`);
    const total=known.reduce((sum,n)=>sum+n,0),complete=known.length===count;
    setText(this.total,`${complete?'Total':'Subtotal'}: ${this.format(total)}`);
    const maximum=known.reduce((max,n)=>Math.max(max,n),0),step=Math.max(1,niceStep(maximum/4)),axisMax=Math.max(step,Math.ceil(maximum/step)*step);
    this.axisMax=axisMax;
    const perSection=this.grouping==='sections',showBrackets=!perSection&&this.sections.length>0;
    const height=Math.max(112,count*(perSection?28:4),showBrackets?this.sections.length*38:0),top=27,bottom=top+height;
    const left=perSection?76:26,right=showBrackets?154:228,width=right-left;
    attribute(this.chart,'data-metric',this.metric);
    attribute(this.chart,'viewBox',`0 0 244 ${bottom+4}`);if(this.chart.style.height!==`${bottom+4}px`)this.chart.style.height=`${bottom+4}px`;
    const axisSignature=JSON.stringify([this.metric,this.grouping,this.rowSignature,perSection?this.sectionSignature:'',axisMax,step,left,right,height]);
    if(this.axisSignature!==axisSignature){
      this.axisSignature=axisSignature;this.axis.replaceChildren();this.gridLines.replaceChildren();
      this.axis.append(svg('path',{d:`M${left} ${top-5}V${bottom}`,class:'properties-axis-line'}));
      for(let value=0;value<=axisMax;value+=step){
        const x=left+value/axisMax*width,label=svg('text',{x,y:top-10,'text-anchor':value===axisMax?'end':value===0?'start':'middle'});
        label.textContent=integers.format(value);this.axis.append(label);
        this.gridLines.append(svg('path',{d:`M${x} ${top}V${bottom}`,class:'properties-grid'}));
      }
      this.tickLabels.replaceChildren();
      if(perSection){
        this.units.forEach((unit,i)=>{const label=svg('text',{x:left-7,y:top+(i+.5)/count*height+2,'text-anchor':'end',class:'properties-section-label'});label.textContent=unit.name.length>13?unit.name.slice(0,12)+'…':unit.name;const title=svg('title');title.textContent=unit.name;label.append(title);label.onclick=()=>this.navigate(unit.page);this.tickLabels.append(label);});
      }else{
        const interval=Math.max(1,Math.ceil(niceStep(count/14))),ticks=new Set([1,count]);for(let page=interval;page<count;page+=interval)if(page>1&&count-page>interval*.35)ticks.add(page);
        for(const page of [...ticks].sort((a,b)=>a-b)){const label=svg('text',{x:left-7,y:top+(page-.5)/count*height+2,'text-anchor':'end'});label.textContent=page;this.tickLabels.append(label);}
        const p=svg('text',{x:5,y:top-10});p.textContent='p.';this.tickLabels.append(p);
      }
    }
    for(let i=0;i<count;i++){
      const rect=this.rows[i],value=values[i],y=top+(i+.5)/count*height;
      const barHeight=Math.min(perSection?6:2.5,height/count*.65),barY=y-barHeight/2;
      attribute(rect,'x',left);attribute(rect,'y',barY);attribute(rect,'height',barHeight);
      attribute(rect,'width',value==null?3:Math.max(1,value/axisMax*width));attribute(rect,'data-unknown',value==null);attribute(rect,'data-zero',value===0);
      this.renderSegments(rect,this.units[i],{left,y:barY,height:barHeight,width,axisMax});
      const description=this.description(i);setText(rect.firstElementChild,description);attribute(rect,'aria-label',description);
    }
    const bracketSignature=JSON.stringify([this.grouping,this.sectionSignature,height,right]);
    if(this.bracketSignature!==bracketSignature){
      this.bracketSignature=bracketSignature;this.brackets.replaceChildren();let labelBottom=top-18;
      const labels=(showBrackets?this.sections:[]).map(section=>{
        const y=Math.max(top+section.start/count*height+9,labelBottom+27);labelBottom=y;return {section,y};
      });
      let nextLabel=bottom+9;
      for(const label of [...labels].reverse()){label.y=Math.min(label.y,nextLabel-27);nextLabel=label.y;}
      for(const {section,y} of labels){
        const a=top+Math.max(0,Math.min(count,section.start))/count*height,b=top+Math.max(0,Math.min(count,section.end))/count*height;
        const x=right+6;this.brackets.append(svg('path',{d:`M${x} ${a}h3V${b}h-3`,class:'properties-bracket'}));
        if(Math.abs(y-(a+9))>5)this.brackets.append(svg('path',{d:`M${x+3} ${(a+b)/2}L${x+8} ${y-2}`,class:'properties-bracket'}));
        const label=svg('text',{x:x+9,y,class:'properties-section-label'});label.textContent=section.name.length>12?section.name.slice(0,11)+'…':section.name;
        const title=svg('title');title.textContent=`${section.name} · pp. ${(Math.floor(section.start)+1)}–${Math.ceil(section.end)}`;label.append(title);
        const range=svg('text',{x:x+9,y:y+11,class:'properties-section-range'});range.textContent=`pp. ${(Math.floor(section.start)+1)}–${Math.ceil(section.end)}`;
        label.onclick=range.onclick=()=>this.navigate((Math.floor(section.start)+1));this.brackets.append(label,range);
      }
    }
    let densest=null,sparsest=null;
    values.forEach((value,i)=>{if(value==null)return;if(densest==null||value>values[densest])densest=i;if(sparsest==null||value<values[sparsest])sparsest=i;});
    const average=known.length?total/known.length:null;
    const name=i=>this.grouping==='pages'?`p. ${i+1}`:this.units[i].name;
    const summary=[
      [perSection?'Total groups':'Total pages',String(count)],
      [`Average ${this.metric==='time'?'read time':this.metric} / ${noun}`,this.format(average)],
      [this.metric==='time'?'Longest read':this.metric==='images'?'Most images':this.metric==='comments'?'Most comments':'Most words',densest==null?'—':`${name(densest)} (${this.format(values[densest])})`],
      [this.metric==='time'?'Shortest read':this.metric==='images'?'Fewest images':this.metric==='comments'?'Fewest comments':'Fewest words',sparsest==null?'—':`${name(sparsest)} (${this.format(values[sparsest])})`]
    ];
    summary.forEach(([label,value],i)=>{setText(this.summaryRows[i].children[0],label);setText(this.summaryRows[i].children[1],value);});
    const kind=this.metric==='images'?'images':'text',done=this.metric==='comments'?this.data.rows.length:this.data.rows.filter(r=>r[kind+'Done']).length,pageCount=this.data.rows.length;
    const partial=perSection&&this.sections.some(s=>s.start%1||s.end%1);
    const detail=this.metric==='images'?'Raster placements + tagged figures (including vector art), counted once per illustration. Untagged vector decoration is excluded; unsupported extraction is unavailable.':
      this.metric==='time'?`${this.policy.words_per_minute} words/minute, ${this.policy.minimum_page_seconds}s minimum per page. Estimates, not tracked time.`:
      this.metric==='comments'?'Visible-to-you messages + replies, excluding deleted messages. Includes resolved conversations and section thoughts. Multi-page highlights count once at their first location.':
      known.length<count?'Some page text could not be extracted. Totals include known pages only.':'PDF text words; no OCR. Blank or image-only pages have zero words.';
    setText(this.status,done<pageCount?`Calculating ${done} / ${pageCount} pages…`:detail+(partial&&this.metric!=='comments'?' Partial pages use text-run / illustration centers; page ERT is shared proportionally.':''));
    const legendSignature=JSON.stringify(this.metric==='comments'?this.comments.authors:[]);
    if(legendSignature!==this.legendSignature){this.legendSignature=legendSignature;this.legend.replaceChildren();if(this.metric==='comments')for(const author of this.comments.authors){const item=node('span',author.name),dot=node('i');dot.style.backgroundColor=author.color;item.prepend(dot);this.legend.append(item);}}
    if(this.hoveredIndex!=null&&this.units[this.hoveredIndex])setText(this.hover,this.description(this.hoveredIndex));
    this.currentPages();this.card.contentReady();
  }
}
