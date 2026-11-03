// Edge zones change overlay geometry only; PDF.js owns page and spread spacing.
export const PAGE_EDGE_INSET = 12;
export const PAGE_EDGE_SNAP = 18;

export function pageAxisLength(view) {
  const viewport=view.viewport,box=viewport.viewBox;
  if(!viewport.convertToViewportPoint)return Math.max(1,view.div.clientHeight);
  const a=viewport.convertToViewportPoint(box[0],box[1]),b=viewport.convertToViewportPoint(box[0],box[3]);
  return Math.max(1,Math.hypot((b[0]-a[0])*view.div.clientWidth/viewport.width,(b[1]-a[1])*view.div.clientHeight/viewport.height));
}

export function boundaryEdge(application,placement,kind) {
  const page=placement?.[`${kind}_page`],box=placement?.[`${kind}_view_box`];
  const view=page && application.pdfViewer.getPageView(page-1);
  if(!view?.viewport||!box)return null;
  const y=placement[`${kind}_y`];
  if(y==null)return kind;
  const fraction=(box[3]-y)/(box[3]-box[1]),zone=PAGE_EDGE_SNAP/pageAxisLength(view);
  return fraction<=zone?'start':fraction>=1-zone?'end':null;
}

export function boundaryGeometry(application, placement, kind) {
  const view=placement && application.pdfViewer.getPageView(placement[`${kind}_page`]-1),box=placement?.[`${kind}_view_box`];
  if(!view?.viewport||!box)return null;
  const edge=boundaryEdge(application,placement,kind);
  const inset=Math.min(.25,PAGE_EDGE_INSET/pageAxisLength(view));
  const y=edge ? box[3]-(edge==='start'?inset:1-inset)*(box[3]-box[1]) : placement[`${kind}_y`];
  const a=view.viewport.convertToViewportPoint(box[0],y),b=view.viewport.convertToViewportPoint(box[2],y);
  const sx=view.div.clientWidth/view.viewport.width,sy=view.div.clientHeight/view.viewport.height;
  return {view,x:a[0]*sx,top:a[1]*sy,dx:(b[0]-a[0])*sx,dy:(b[1]-a[1])*sy,edge};
}
