// Canonical order scalar: page + fraction down, with page-end == next page-top.
export function boundaryLocation(placement, kind) {
  if (!placement?.[`${kind}_page`]) return null;
  const page=placement[`${kind}_page`],y=placement[`${kind}_y`],box=placement[`${kind}_view_box`];
  // Match the service precision, avoiding false gaps after viewport round trips.
  return page + (y==null ? (kind==='end'?1:0) : Math.round((box[3]-y)/(box[3]-box[1])*1e10)/1e10);
}
export const sameBoundary = (a,b) => a!=null && b!=null && a===b;
// Explicit numeric page edges preserve a deliberate split across two pages.
// Null page edges remain eligible for a shared divider; dragging rejoins them.
function separatePageEdges(a,b) {
  const end=a.kind==='end'?a.placement:b.placement,start=a.kind==='start'?a.placement:b.placement;
  return end.end_page+1===start.start_page && end.end_y===end.end_view_box?.[1] && start.start_y===start.start_view_box?.[3];
}
export function sectionDividers(sections, placementFor = section=>section.placement) {
  const dividers=[];
  for (const section of sections) for(const kind of ['start','end']) {
    const placement=placementFor(section),location=boundaryLocation(placement,kind);
    if(location==null)continue;
    const existing=dividers.find(divider=>sameBoundary(divider.location,location) && !divider.members.some(member=>member.kind===kind) && !divider.members.some(member=>separatePageEdges(member,{kind,placement})));
    const member={section,kind,placement};
    if(existing)existing.members.push(member); else dividers.push({location,members:[member]});
  }
  return dividers;
}

export function sectionPageRange(placement) {
  const start=boundaryLocation(placement,'start'),end=boundaryLocation(placement,'end');
  if(start==null||end==null)return '';
  const first=Math.floor(start),last=Math.max(first,Math.ceil(end)-1);
  return first===last?String(first):`${first}\u2013${last}`;
}
