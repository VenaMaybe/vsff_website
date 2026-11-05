// Pure aggregation; no network calls or durable cache of review conversations.
export function mappedSections(sections,pageCount){
  return (sections||[]).filter(s=>s.placement).map(section=>{
    const p=section.placement,coordinate=kind=>{
      const box=p[kind+'_view_box'],fraction=p[kind+'_y']==null?Number(kind==='end'):(box[3]-p[kind+'_y'])/(box[3]-box[1]);
      return Math.max(0,Math.min(pageCount,p[kind+'_page']-1+Math.max(0,Math.min(1,fraction))));
    };
    return {id:section.section_id,name:section.name,start:coordinate('start'),end:coordinate('end')};
  }).filter(s=>Number.isFinite(s.start)&&Number.isFinite(s.end)&&s.end>s.start).sort((a,b)=>a.start-b.start);
}
export function sectionAt(sections,point){
  let low=0,high=sections.length;
  while(low<high){const mid=(low+high)>>1;if(sections[mid].start<=point)low=mid+1;else high=mid;}
  const section=sections[low-1];return section&&point<section.end?section:null;
}
const color=value=>/^#[0-9a-f]{6}$/i.test(value||'')?value:'#808080';
export function commentStatistics(threads,responses,sections,pageCount){
  const records=[],authors=new Map(),seen=new Set();
  const add=(comment,point,sectionId=null)=>{
    if(comment.is_deleted||comment.deleted_at||seen.has(comment.comment_id)||!Number.isFinite(point))return;
    seen.add(comment.comment_id);
    const source=comment.author||{user_id:comment.author_id,display_name:comment.display_name,review_color:comment.review_color};
    if(!source.user_id)return;
    authors.set(source.user_id,{id:source.user_id,name:source.display_name||'Reviewer',color:color(source.review_color)});
    records.push({point:Math.max(0,Math.min(pageCount-.000001,point)),sectionId,author:source.user_id});
  };
  for(const thread of threads||[]){
    const segment=thread.targets?.[0]?.anchor?.segments?.[0];if(!segment)continue;
    const box=segment.pdf_view_box,rect=segment.rectangles?.[0];
    const fraction=box&&rect?(box[3]-(rect[1]+rect[3])/2)/(box[3]-box[1]):.5;
    const point=segment.page_number-1+Math.max(0,Math.min(.999999,fraction));
    for(const comment of thread.comments||[])add(comment,point);
  }
  for(const response of responses||[]){
    const section=sections.find(s=>s.id===response.section_id);if(!section)continue;
    // At a linked border, feedback belongs to the section ending there.
    for(const comment of response.comments||[])add(comment,Math.max(section.start,section.end-.000001),section.id);
  }
  return {records,authors:[...authors.values()].sort((a,b)=>a.name.localeCompare(b.name)||a.id.localeCompare(b.id))};
}
function blank(key,name,start,end){return {key,name,start,end,page:Math.floor(start)+1,words:0,time:0,images:0,comments:0,people:new Map()};}
export function statisticsUnits(rows,sections,grouping,comments,policy){
  const units=grouping==='pages'?rows.map(row=>blank(`p${row.page}`,`Page ${row.page}`,row.page-1,row.page)):
    sections.map(s=>({...blank(s.id,s.name,s.start,s.end),section:true}));
  let unsectioned;
  if(grouping==='sections'){
    const covered=sections.reduce((n,s)=>n+s.end-s.start,0);
    if(covered<rows.length-1e-7){
      let first=0;for(const s of sections){if(s.start>first+1e-7)break;first=s.end;}
      unsectioned=blank('unsectioned','Unsectioned',first,rows.length);unsectioned.unsectioned=true;units.push(unsectioned);
    }
  }
  const byId=new Map(units.map(u=>[u.key,u]));
  const pageSections=new Map();
  if(grouping==='sections')for(const unit of units.filter(u=>u.section))for(let page=Math.floor(unit.start)+1;page<=Math.ceil(unit.end);page++){
    const list=pageSections.get(page)||[];list.push([unit,Math.min(unit.end,page)-Math.max(unit.start,page-1)]);pageSections.set(page,list);
  }
  const at=point=>grouping==='pages'?units[Math.floor(point)]:byId.get(sectionAt(sections,point)?.id)||unsectioned;
  for(const row of rows){
    const pageUnit=grouping==='pages'?units[row.page-1]:null;
    if(pageUnit){
      pageUnit.words=row.words;pageUnit.images=row.images;
      pageUnit.time=row.words==null?null:Math.max(policy.minimum_page_seconds,Math.ceil(row.words*60/policy.words_per_minute));continue;
    }
    const overlaps=[...(pageSections.get(row.page)||[])];
    const uncovered=1-overlaps.reduce((n,r)=>n+r[1],0);if(!pageUnit&&unsectioned&&uncovered>1e-7)overlaps.push([unsectioned,uncovered]);
    for(const metric of ['words','images']){
      if(row[metric]==null){for(const [unit] of overlaps)unit[metric]=null;continue;}
      for(const [fraction,count] of row[metric==='words'?'wordRuns':'imageRuns']||[]){const unit=at(row.page-1+fraction);if(unit&&unit[metric]!=null)unit[metric]+=count;}
    }
    if(row.words==null){for(const [unit] of overlaps)unit.time=null;continue;}
    const seconds=Math.max(policy.minimum_page_seconds,Math.ceil(row.words*60/policy.words_per_minute));
    // Preserve the same per-page ERT budget when a page spans several sections.
    const weights=new Map(overlaps.map(([unit,area])=>[unit,row.words?0:area]));
    if(row.words)for(const [fraction,count] of row.wordRuns||[]){const unit=at(row.page-1+fraction);if(unit)weights.set(unit,(weights.get(unit)||0)+count/row.words);}
    const allocation=[...weights].map(([unit,weight])=>({unit,exact:seconds*weight,value:Math.floor(seconds*weight)}));
    let remainder=seconds-allocation.reduce((n,a)=>n+a.value,0);
    allocation.sort((a,b)=>(b.exact-b.value)-(a.exact-a.value));
    for(const a of allocation){if(remainder-->0)a.value++;if(a.unit.time!=null)a.unit.time+=a.value;}
  }
  for(const comment of comments.records){
    const unit=grouping==='sections'&&comment.sectionId?byId.get(comment.sectionId):at(comment.point);if(!unit)continue;
    unit.comments++;unit.people.set(comment.author,(unit.people.get(comment.author)||0)+1);
  }
  return units;
}
