import { pdfRectangleToCss } from './anchor_geometry.js';

// Navigation uses authorized/filter-visible threads and canonical geometry,
// including offscreen pages and every segment of a multi-page highlight.
export class CommentNavigation {
  constructor(frame,application,state,select){
    Object.assign(this,{frame,application,state,select});
    this.lastId=null;
    for(const doc of [document,frame.contentDocument])doc.addEventListener('keydown',event=>{
      if(event.defaultPrevented||event.isComposing||!event.shiftKey||event.ctrlKey||event.metaKey||event.altKey||
          !['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key))return;
      const target=event.target;
      if(target.closest?.('input,textarea,select,summary,a,[contenteditable]:not([contenteditable=false]),[role=textbox],.toolbar-menu,dialog[open],[role=dialog]')||
          (target.closest?.('button')&&!target.closest('.thread-marker'))||
          document.querySelector('dialog[open]')||application.overlayManager?.active||
          (doc.getSelection()&&!doc.getSelection().isCollapsed))return;
      const direction=['ArrowDown','ArrowRight'].includes(event.key)?1:-1;
      const entry=this.next(direction);
      if(!entry)return;
      event.preventDefault();event.stopImmediatePropagation();
      this.select(entry.thread.thread_id,entry.anchor);
    },true);
  }
  remember(id){this.lastId=id;}
  ordered(){
    if(this.threadSource===this.state.threads&&this.filter===this.state.filter)return this.entries;
    this.threadSource=this.state.threads;this.filter=this.state.filter;
    this.entries=this.state.visibleThreads().flatMap(thread=>{
      const anchor=thread.targets[0]?.anchor,segment=anchor?.segments?.[0],rect=segment?.rectangles?.[0];
      return rect?[{thread,anchor,page:segment.page_number,offset:Number.isInteger(segment.text_start)?segment.text_start:Infinity,
        top:-rect[3],left:rect[0]}]:[];
    }).sort((a,b)=>a.page-b.page||(a.offset===b.offset?0:a.offset-b.offset)||a.top-b.top||a.left-b.left||a.thread.thread_id.localeCompare(b.thread.thread_id));
    return this.entries;
  }
  next(direction){
    const entries=this.ordered();if(!entries.length)return null;
    const viewer=this.application.pdfViewer,scroller=viewer.container;
    const box=scroller.getBoundingClientRect();
    const left=box.left+scroller.clientLeft,top=box.top+scroller.clientTop;
    const bounds={left:Math.max(0,left),top:Math.max(0,top),
      right:Math.min(left+scroller.clientWidth,this.frame.contentWindow.innerWidth),
      bottom:Math.min(top+scroller.clientHeight,this.frame.contentWindow.innerHeight)};
    if(bounds.right<=bounds.left||bounds.bottom<=bounds.top)return null;
    const pages=new Map();
    const regions=entry=>entry.anchor.segments.flatMap(segment=>{
      if(!pages.has(segment.page_number)){
        const view=viewer.getPageView(segment.page_number-1),div=view?.div;
        if(!div?.isConnected||!view.viewport){pages.set(segment.page_number,null);}
        else{
          const rect=div.getBoundingClientRect();
          pages.set(segment.page_number,{view,content:{left:rect.left+div.clientLeft,top:rect.top+div.clientTop,width:div.clientWidth,height:div.clientHeight}});
        }
      }
      const page=pages.get(segment.page_number);if(!page)return [];
      return segment.rectangles.flatMap(rect=>{
        const result=pdfRectangleToCss(rect,page.view.viewport,page.content);if(!result)return [];
        const left=page.content.left+result.left,top=page.content.top+result.top;
        return [{left,top,right:left+result.width,bottom:top+result.height}];
      });
    });
    const current=entries.findIndex(entry=>entry.thread.thread_id===this.lastId);
    if(current>=0&&regions(entries[current]).some(r=>r.right>bounds.left&&r.left<bounds.right&&r.bottom>bounds.top&&r.top<bounds.bottom)){
      return entries[(current+direction+entries.length)%entries.length];
    }
    const x=(bounds.left+bounds.right)/2,y=(bounds.top+bounds.bottom)/2;
    let nearest=null,distance=Infinity;
    for(const entry of entries)for(const rect of regions(entry)){
      const value=Math.hypot(Math.max(rect.left-x,0,x-rect.right),Math.max(rect.top-y,0,y-rect.bottom));
      if(value<distance){nearest=entry;distance=value;}
    }
    return nearest;
  }
}
