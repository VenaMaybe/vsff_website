// Choose one gap in the displayed stack. Keep it through loading and resizing.
export function insertionSlot(items, center) {
  const ordered=[...items].sort((a,b)=>a.top-b.top);
  let slot=0,distance=Infinity;
  // If the midpoint is inside a stack, split an internal gap. The outer edge
  // of a tall last card must not win and send the entire stack upward.
  const inside=ordered.length>1&&center>ordered[0].top&&center<ordered.at(-1).top+ordered.at(-1).height;
  const first=inside?1:0,last=inside?ordered.length-1:ordered.length;
  for(let i=first;i<=last;i++){
    const start=i?ordered[i-1].top+ordered[i-1].height:-Infinity;
    const end=i<ordered.length?ordered[i].top:Infinity;
    const point=Math.max(start,Math.min(center,end)),candidate=Math.abs(point-center);
    if(candidate<distance){distance=candidate;slot=i;}
  }
  return {above:ordered.slice(0,slot).map(item=>item.card),below:ordered.slice(slot).map(item=>item.card)};
}

// Pack around a requested insertion point, moving each neighbor only as needed.
// Items contain screen-space preferredTop/height and an opaque card identity.
export function packCardSequence(items, pivotCard, minimum, gap, insertion = null) {
  const ordered=items.map(item=>({...item})).sort((a,b)=>a.preferredTop-b.preferredTop);
  const pivot=ordered.find(item=>item.card===pivotCard);
  if(!pivot){
    let bottom=minimum;
    for(const item of ordered){item.top=Math.max(minimum,item.preferredTop,bottom);bottom=item.top+item.height+gap;}
    return ordered;
  }
  pivot.top=Math.max(minimum,pivot.preferredTop);
  const center=pivot.top+pivot.height/2,above=[],below=[];
  if(insertion){
    const remaining=new Map(ordered.filter(item=>item!==pivot).map(item=>[item.card,item]));
    for(const [keys,side] of [[insertion.above,above],[insertion.below,below]])for(const key of keys){
      const item=remaining.get(key);if(item){side.push(item);remaining.delete(key);}
    }
    below.push(...remaining.values());
  }else for(const item of ordered){
    if(item===pivot)continue;
    (item.preferredTop+item.height/2<center?above:below).push(item);
  }
  let required=above.reduce((sum,item)=>sum+item.height+gap,0);
  // Spill the nearest upper cars below the insertion before violating page 1.
  // Prepending retains their original order when more than one must move.
  while(above.length&&required>pivot.top-minimum){
    const item=above.pop();required-=item.height+gap;below.unshift(item);
  }
  const limits=[];let lower=minimum;
  for(const item of above){limits.push(lower);lower+=item.height+gap;}
  let top=pivot.top;
  for(let i=above.length-1;i>=0;i--){
    const item=above[i];item.top=Math.max(limits[i],Math.min(item.preferredTop,top-item.height-gap));top=item.top;
  }
  let bottom=pivot.top+pivot.height+gap;
  for(const item of below){item.top=Math.max(item.preferredTop,bottom);bottom=item.top+item.height+gap;}
  return [...above,pivot,...below];
}
