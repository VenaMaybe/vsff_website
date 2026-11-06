import { insertionSlot, packCardSequence } from './card_packing.js';
import { cardScale, cardSize } from './card_scale.js';
import { animateCard, CARD_MOTION_MS } from './card_motion.js';
import { documentStage } from './document_stage.js';

const cards = new Set();
let scheduled = false;
let focusedCard = null;
let placementCard = null;
const openers=new Map();
let storageKey=null, restoring=false, persistTimer=null, savedCards=[];
export function configureLeftCards(config) {
  storageKey=`pdf-review:left-cards:v1:${config.currentUserId}:${config.versionId}`;
  restoring=true;
  try{const data=JSON.parse(localStorage.getItem(storageKey)||'[]');savedCards=Array.isArray(data)?data.slice(0,32):[];}catch{savedCards=[];}
}
export function registerLeftCard(key,open) {openers.set(key,open);}
function syncToolMenuValues() {
  const open = new Set([...cards].map(card => card.stateKey));
  document.querySelectorAll('[data-left-card]').forEach(item => {
    item.setAttribute('aria-checked', String(open.has(item.dataset.leftCard)));
  });
}
document.addEventListener('click', event => {
  if (event.target.closest('[data-close-all-tools]')) {
    for (const card of [...cards]) card.close(false);
    return;
  }
  const tool = event.target.closest('[data-left-card]');
  if (!tool) return;
  const card = [...cards].find(card => card.stateKey === tool.dataset.leftCard);
  const fromToolsCard = !!tool.closest('.tools-panel');
  if (card && (fromToolsCard || card.element.classList.contains('active'))) card.close(false);
  else openers.get(tool.dataset.leftCard)?.({focus: !fromToolsCard});
});
function persistCards() {
  clearTimeout(persistTimer);
  if(!storageKey||restoring)return;
  const state=[];
  for(const card of cards) {
    if(!card.stateKey||!card.anchorPage)continue;
    const page=Number(card.anchorPage.dataset.pageNumber),rect=card.anchorPage.getBoundingClientRect();
    const fraction=(card.element.getBoundingClientRect().top-card.sectionViewer.frame.getBoundingClientRect().top-rect.top)/rect.height;
    if(Number.isFinite(fraction))state.push({key:card.stateKey,page,fraction:Math.round(fraction*1e6)/1e6,pinned:card.pinned});
  }
  try{const value=JSON.stringify(state);if(localStorage.getItem(storageKey)!==value)localStorage.setItem(storageKey,value);}catch{/* Storage can be unavailable; cards remain usable. */}
}
function queuePersist() {if(storageKey&&!restoring){clearTimeout(persistTimer);persistTimer=setTimeout(persistCards,CARD_MOTION_MS+40);}}
window.addEventListener('pagehide',persistCards);
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')persistCards();});
export async function restoreLeftCards(pageCount) {
  const restored=[],seen=new Set();
  try {
    for(const record of savedCards) {
      if(!record||!openers.has(record.key)||seen.has(record.key)||!Number.isInteger(record.page)||record.page<1||record.page>pageCount||!Number.isFinite(record.fraction)||Math.abs(record.fraction)>1e6||typeof record.pinned!=='boolean')continue;
      seen.add(record.key);
      try {
        const card=await openers.get(record.key)();
        if(card?.element.isConnected)restored.push({card,record});
      } catch { /* A failed tool must not prevent the viewer from starting. */ }
    }
    let pinned=false;
    for(const {card,record} of restored) {
      card.openingCentered=false;card.centerRequest=null;
      card.anchorPage=card.sectionViewer.application.pdfViewer.getPageView(record.page-1).div;
      card.anchorFraction=record.fraction;card.anchorCentered=false;card.insertion=null;card.pinned=record.pinned&&!pinned;pinned ||= card.pinned;card.updatePin();
      card.element.classList.remove('active');
    }
    focusedCard=null;placementCard=null;
    if(restored.some(({card})=>card.element.contains(document.activeElement)))document.activeElement.blur();
    layoutCards();
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  } finally {restoring=false;queuePersist();}
}

function layoutCards(animate = false) {
  if (scheduled && !animate) return;
  const run = () => {
    scheduled = false;
    const groups = new Map();
    for (const card of cards) {
      const parent = card.element.parentElement;
      if (!parent) continue;
      if (!groups.has(parent)) groups.set(parent, []);
      groups.get(parent).push(card);
    }
    for (const [parent, group] of groups) {
      const integration=group[0].sectionViewer, pdf=integration.application.pdfViewer;
      const scale=cardScale(integration.application), spacing=8*scale;
      const scaling=group.some(card=>card.lastScale!==undefined&&card.lastScale!==scale);
      // Read geometry once before any card writes. Packing uses only this snapshot.
      const workspace=parent.getBoundingClientRect();
      const frame=integration.frame.getBoundingClientRect();
      const scroller=pdf.container, scrollLeft=scroller.scrollLeft, scrollTop=scroller.scrollTop;
      const pages=new Map(), rails=new Map(), measures=new Map();
      const pageRect=page=>{
        if(!page)return null;
        if(!pages.has(page))pages.set(page,page.getBoundingClientRect());
        return pages.get(page);
      };
      const railLeft=page=>{
        const key=pdf.scrollMode===1?pdf.viewer:page.closest('.spread')||page;
        if(!rails.has(key)){
          const siblings=pdf.scrollMode===1?key.querySelectorAll('.page'):key.matches('.spread')?key.querySelectorAll(':scope > .page'):[page];
          rails.set(key,Math.min(...[...siblings].map(p=>pageRect(p).left)));
        }
        return rails.get(key);
      };
      const firstPage=pageRect(pdf.getPageView(0)?.div);
      const pageTop=firstPage?frame.top+firstPage.top-workspace.top:0;
      const currentPage=pdf.getPageView(pdf.currentPageNumber-1)?.div,current=pageRect(currentPage);
      for(const card of group){
        measures.set(card,{...cardSize(card.element,integration.application),visualTop:card.element.getBoundingClientRect().top});
      }
      for (const card of group) {
        const size=measures.get(card);
        const capture=visualTop=>{
          if(!current)return;
          card.anchorPage=currentPage;card.anchorFraction=(visualTop-frame.top-current.top)/current.height;card.anchorCentered=false;card.insertion=null;
        };
        if (card.centerRequest) {
          const center = card.centerRequest();
          if (!card.pinned && Number.isFinite(center)) capture(workspace.top + Math.max(8, center - workspace.top - size.height / 2));
          card.centerRequest = null;
        }
        const anchor=pageRect(card.anchorPage);
        const centerOffset=card.anchorCentered?Math.min(size.height/2,card.centerOffsetLimit??Infinity):0;
        const documentTop=anchor?frame.top-workspace.top+anchor.top+card.anchorFraction*anchor.height-centerOffset:8;
        card.preferredTop = card.pinned ? Math.max(8,pageTop) : Math.max(pageTop,documentTop);
      }
      // Placement has its own pivot: opening from Tools must not steal focus.
      // Pack upward/downward around that card, spilling upper neighbors below
      // only when the first-page limit prevents making enough room above it.
      for (const card of group) if (card.pinned) card.layoutTop = card.preferredTop;
      const packed=packCardSequence(group.filter(card=>!card.pinned).map(card=>({
        card,preferredTop:card.preferredTop,height:measures.get(card).height,
      })),placementCard,pageTop,spacing,placementCard?.insertion);
      for(const item of packed)item.card.layoutTop=item.top;
      const plans=group.map(card=>{
        const size=measures.get(card),page=card.pinned?currentPage:card.anchorPage;
        if(!page)return null;
        const x=frame.left+railLeft(page)-workspace.left-size.width-12*scale;
        const left=card.pinned?Math.max(8,Math.min(x,workspace.width-size.width-8)):x;
        const offset=card.layoutTop-card.preferredTop;
        const motion=!scaling&&(animate||(card.lastOffset!==undefined&&Math.abs(offset-card.lastOffset)>1));
        card.lastOffset=offset;card.lastScale=scale;
        return {card,left,top:card.layoutTop,height:size.height,width:size.width,visualTop:size.visualTop,motion};
      }).filter(Boolean);
      // No geometry reads below this line: commit positions, then report bounds
      // from the same snapshot instead of forcing layout again for each card.
      for(const plan of plans){
        if(scaling)plan.card.element.getAnimations().forEach(animation=>animation.cancel());
        plan.card.position(plan,workspace.top,frame.top+(firstPage?.top||0));
      }
      documentStage(integration.application).setBounds('left-cards',plans.filter(plan=>!plan.card.pinned).map(plan=>({
        left:plan.left+workspace.left-frame.left+scrollLeft-spacing,
        right:plan.left+workspace.left-frame.left+scrollLeft+plan.width+spacing,
        top:plan.top+scrollTop,bottom:plan.top+plan.height+scrollTop+spacing,
      })));
    }
    queuePersist();
  };
  if (animate) run(); else {
    const card=[...cards][0];
    if(card){scheduled=true;documentStage(card.sectionViewer.application).schedule('left-cards',run);}
  }
}
function clearLeftCardFocus(event) {
  if(event.composedPath().some(node=>node.matches?.('.left-card, #review-tools-menu')))return;
  if(![...cards].some(card=>card.element.classList.contains('active')))return;
  // Freeze all document-card positions before dropping packing priority.
  for(const card of cards)if(!card.pinned)card.captureAnchor(card.element.getBoundingClientRect().top);
  for(const card of cards) {
    if(!card.element.classList.contains('active'))continue;
    card.element.classList.remove('active');
    if(card.element.contains(document.activeElement))document.activeElement.blur();
  }
  focusedCard=null;placementCard=null;
}
let nextId = 0;

// Reusable simultaneous utility cards. Callers own content; the shell owns
// viewport packing, document anchors, pinning, animation and focus.
export class LeftCard {
  constructor(title, { opener, viewer, className = '', onVisibility, stateKey=null } = {}) {
    Object.assign(this, { viewer, onVisibility, title, stateKey });
    this.opener = opener?.getClientRects().length ? opener : opener?.closest('.toolbar-menu')?.querySelector('summary');
    this.pinned = false;
    this.element = document.createElement('section');
    this.element.className = `left-card thread-card ${className}`;
    this.element.setAttribute('role', 'region');
    const header = document.createElement('header'); header.className = 'dialog-header';
    const heading = document.createElement('h2'); heading.id = `left-card-${++nextId}`; heading.textContent = title;
    this.element.setAttribute('aria-labelledby', heading.id);
    this.closeButton = document.createElement('button'); this.closeButton.type = 'button';
    this.closeButton.textContent = '\u00d7'; this.closeButton.setAttribute('aria-label', `Close ${title}`);
    this.closeButton.onclick = () => this.close();
    this.pin = document.createElement('button'); this.pin.type = 'button'; this.pin.className = 'left-card-pin sections-pin';
    this.pin.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l-1 7 4 4v2H6v-2l4-4zM12 16v6"/></svg>';
    this.pin.onclick = () => this.setPinned(!this.pinned);
    header.addEventListener('pointerdown', event => this.startHeaderDrag(event));
    this.updatePin(); header.append(heading, this.pin, this.closeButton);
    this.body = document.createElement('div'); this.body.className = 'left-card-body sections-panel-body';
    this.element.append(header, this.body);
    this.schedule = () => layoutCards();
    this.openingCentered = true;
    this.element.addEventListener('pointerdown', () => { this.stopEntrance(); this.openingCentered=false; this.activate(); });
    this.element.addEventListener('focusin', () => this.activate());
    this.element.addEventListener('keydown', event => {
      if (event.key === 'Escape' && this.cancelHeaderDrag) { event.preventDefault(); event.stopPropagation(); this.cancelHeaderDrag(); return; }
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); this.close(); }
    });
    this.element.addEventListener('wheel', event => {
      if (!this.scroller || event.ctrlKey || event.target.closest('textarea, select')) return;
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? this.scroller.clientHeight : 1;
      this.scroller.scrollBy(event.deltaX * unit, event.deltaY * unit); event.preventDefault();
    }, { passive: false });
  }
  get height() { return cardSize(this.element, this.sectionViewer.application).height; }
  get width() { return cardSize(this.element, this.sectionViewer.application).width; }
  get sectionViewer() { return this.viewer?.sectionViewer; }
  open({focus = true} = {}) {
    if (this.element.isConnected) { this.reveal({focus}); return true; }
    // Reused cards can retain their old active class after closing.
    if (!focus) this.element.classList.remove('active');
    this.openingCentered=true;
    this.openingEntrance=true;
    // Use the displayed neighbor positions as the insertion's starting layout.
    // Keep this snapshot stable while asynchronously loaded content changes size.
    const workspace = document.querySelector('.viewer-workspace');
    const center=(workspace?.getBoundingClientRect().top||0)+(workspace?.clientHeight||innerHeight)/2;
    const neighbors=[...cards].filter(card=>!card.pinned).map(card=>({
      card,top:card.element.getBoundingClientRect().top,height:card.height,
      parentTop:card.element.parentElement.getBoundingClientRect().top,animations:card.element.getAnimations(),
    }));
    for(const {card,top} of neighbors)card.captureAnchor(top);
    for(const {card,top,parentTop,animations} of neighbors)if(animations.length){
      animations.forEach(animation=>animation.cancel());card.element.style.top=`${top-parentTop}px`;
    }
    const insertion=insertionSlot(neighbors,center);
    cards.add(this);placementCard=this;
    (workspace || document.body).append(this.element);
    syncToolMenuValues();
    const integration = this.sectionViewer;
    this.scroller = integration?.application.pdfViewer.container;
    this.root = integration?.frame.contentDocument.documentElement;
    this.focusEvents=new AbortController();
    const outside=event=>clearLeftCardFocus(event);
    for(const doc of [document,integration?.frame.contentDocument].filter(Boolean))for(const type of ['pointerdown','click']) {
      doc.addEventListener(type,outside,{capture:true,signal:this.focusEvents.signal});
    }
    this.bus = integration?.application.eventBus;
    this.bus?.dispatch('leftcardchanged', { source: this });
    this.captureAnchor((workspace?.getBoundingClientRect().top || 0) + (workspace?.clientHeight || innerHeight)/2);
    // Oversized new cards start with their header visible, including after load.
    // This offset attaches to the document anchor; it is not a sticky viewport cap.
    this.centerOffsetLimit=Math.max(0,(workspace?.clientHeight || innerHeight)/2-8);
    this.anchorCentered=true;this.insertion=insertion;
    this.onScroll = () => this.schedule();
    this.scroller?.addEventListener('scroll', this.onScroll, { passive: true });
    this.resize = new ResizeObserver(this.schedule);
    this.resize.observe(workspace || document.body); this.resize.observe(this.element);
    for (const event of ['scalechanging', 'rotationchanging', 'spreadmodechanged', 'scrollmodechanged', 'pagerendered', 'reviewlayoutchanged', 'documentoriginchanged']) this.bus?.on(event, this.schedule);
    layoutCards(true);
    this.onVisibility?.(true); if (focus) this.closeButton.focus({ preventScroll: true });
    const animation = this.openingAnimation = animateCard(this.element, 4, true);
    const finished = () => {
      if (this.openingAnimation !== animation) return;
      this.openingAnimation = null; this.openingEntrance = false;
    };
    if (animation) animation.finished.then(finished, finished);
    else finished();
    return true;
  }
  stopEntrance() {
    const animation = this.openingAnimation;
    this.openingAnimation = null; this.openingEntrance = false;
    animation?.cancel();
  }
  contentReady() {
    if(!this.openingCentered)return;
    layoutCards(true);
    requestAnimationFrame(()=>requestAnimationFrame(()=>{this.openingCentered=false;}));
  }
  activate() {
    const changed = !this.pinned && (focusedCard !== this || !this.element.classList.contains('active'));
    if(changed && this.element.isConnected && !this.openingCentered && !this.openingEntrance) {
      // Collision displacement becomes the anchor before changing focus priority.
      // Preserve neighbors too so focusing one card cannot undo their packing.
      for(const card of cards)if(!card.pinned && card.element.parentElement===this.element.parentElement) {
        const top=card.element.getBoundingClientRect().top;
        card.captureAnchor(top);
        const animations=card.element.getAnimations();
        if(animations.length){
          animations.forEach(animation=>animation.cancel());
          card.element.style.top=`${top-card.element.parentElement.getBoundingClientRect().top}px`;
        }
      }
    }
    if (!this.pinned) {focusedCard = this;if(changed)placementCard=this;}
    for (const card of cards) card.element.classList.toggle('active', card === this);
    if (changed) layoutCards(true);
  }
  startHeaderDrag(event) {
    if (event.button !== 0 || event.target.closest('button') || this.busy) return;
    this.stopEntrance();
    event.preventDefault(); this.openingCentered = false;
    const header = event.currentTarget, initial = this.element.getBoundingClientRect().top, start = event.clientY;
    const listeners = new AbortController(); let moved = false;
    header.setPointerCapture(event.pointerId);
    const finish = cancel => {
      listeners.abort(); this.cancelHeaderDrag = null;
      if (header.hasPointerCapture(event.pointerId)) header.releasePointerCapture(event.pointerId);
      if (cancel) { this.captureAnchor(initial); layoutCards(true); }
    };
    this.cancelHeaderDrag = () => finish(true);
    document.addEventListener('pointermove', move => {
      if (move.pointerId !== event.pointerId || (!moved && Math.abs(move.clientY-start)<3)) return;
      if (!moved) { if (this.pinned) this.setPinned(false, false); this.activate(); placementCard=this; moved = true; }
      this.captureAnchor(initial + move.clientY-start); layoutCards();
    }, {capture:true, signal:listeners.signal});
    document.addEventListener('pointerup', up => { if(up.pointerId===event.pointerId)finish(false); }, {capture:true,signal:listeners.signal});
    document.addEventListener('pointercancel', cancel => { if(cancel.pointerId===event.pointerId)finish(true); }, {capture:true,signal:listeners.signal});
  }
  setPinned(value, animate = true) {
    this.openingCentered = false;
    const parent = this.element.parentElement;
    if (!parent) { this.pinned = value; this.updatePin(); return; }
    const top = this.element.getBoundingClientRect().top;
    if (value) {
      // Removing a card from document flow must leave the existing neighbors
      // exactly where they are, including any previous collision offsets.
      for (const other of cards) if (other !== this && !other.pinned && other.element.parentElement === parent) other.captureAnchor(other.element.getBoundingClientRect().top);
      if (focusedCard === this) focusedCard = null;
      for (const other of cards) if (other !== this && other.pinned && other.element.parentElement === parent) {
        other.pinned = false;
        other.captureAnchor(Math.max(other.element.getBoundingClientRect().top, parent.getBoundingClientRect().top + 40));
        other.updatePin(); focusedCard = other;
      }
    } else {
      this.captureAnchor(Math.max(top, parent.getBoundingClientRect().top + 40));
      focusedCard = this;
    }
    this.pinned = value; this.centerRequest = null; this.updatePin();
    if(!value)placementCard=this;else if(placementCard===this)placementCard=null;
    layoutCards(animate);
  }
  documentTop() {
    if (!this.anchorPage) return 8;
    const page = this.anchorPage.getBoundingClientRect();
    return this.sectionViewer.frame.getBoundingClientRect().top - this.element.parentElement.getBoundingClientRect().top + page.top + this.anchorFraction * page.height - (this.anchorCentered?Math.min(this.height/2,this.centerOffsetLimit??Infinity):0);
  }
  centerOn(getCenter) {
    this.openingCentered = false;
    this.centerRequest = getCenter; this.activate(); placementCard=this; layoutCards(true);
    this.closeButton.focus({ preventScroll:true });
  }
  reveal({focus = true} = {}) {
    if (focus) {this.activate();placementCard=this;}
    const rect = this.element.getBoundingClientRect(), parent = this.element.parentElement.getBoundingClientRect();
    if (rect.top < parent.top || rect.bottom > parent.bottom) {
      if (!this.pinned) this.captureAnchor(parent.top + 8);

      layoutCards(true);
    }
    if (focus) this.closeButton.focus({ preventScroll: true });
  }
  updatePin() {
    this.pin.setAttribute('aria-pressed', String(this.pinned));
    this.element.dataset.pinned = String(this.pinned);
    const label = this.pinned ? `Unpin ${this.title} from the viewport` : `Pin ${this.title} to the viewport`;
    this.pin.setAttribute('aria-label', label); this.pin.title = label;
  }
  captureAnchor(visualTop) {
    this.anchorCentered=false;this.insertion=null;
    const integration = this.sectionViewer, pdf = integration?.application.pdfViewer;
    this.anchorPage = pdf?.getPageView(pdf.currentPageNumber - 1)?.div;
    if (!this.anchorPage) return;
    const page = this.anchorPage.getBoundingClientRect();
    // Negative fractions are intentional: the card may be above the current page.
    // Capture the actual rendered card position, never a clamped page boundary.
    this.anchorFraction = (visualTop - integration.frame.getBoundingClientRect().top - page.top) / page.height;
  }
  position({left,top,visualTop,motion},parentTop,firstPageTop) {
    if(!this.openingCentered&&!this.openingEntrance&&visualTop<firstPageTop){this.element.getAnimations().forEach(animation=>animation.cancel());visualTop=firstPageTop;}
    const x=`${left}px`,y=`${top}px`;
    if(this.element.style.left!==x)this.element.style.left=x;
    if(this.element.style.top!==y)this.element.style.top=y;
    this.lastTop=top;
    // Initial placement (including content-ready layouts) is not a move from
    // the default CSS position. Keep open()'s single short entrance intact.
    if(motion&&!this.openingCentered&&!this.openingEntrance&&Math.abs(visualTop-parentTop-top)>.5)animateCard(this.element,visualTop-parentTop-top);
  }

  close(restoreFocus = true) {
    if (this.busy) return false;
    this.stopEntrance();
    this.cancelHeaderDrag?.();this.focusEvents?.abort();
    this.scroller?.removeEventListener('scroll', this.onScroll); this.resize?.disconnect();
    for (const event of ['scalechanging', 'rotationchanging', 'spreadmodechanged', 'scrollmodechanged', 'pagerendered', 'reviewlayoutchanged', 'documentoriginchanged']) this.bus?.off(event, this.schedule);
    this.element.getAnimations().forEach(animation => animation.cancel());
    const parent = this.element.parentElement;
    this.element.remove();
    cards.delete(this);
    syncToolMenuValues();
    if (focusedCard === this) focusedCard = null;
    if (placementCard === this) placementCard = focusedCard;
    if (![...cards].some(card => card.root === this.root)) documentStage(this.sectionViewer.application).setBounds('left-cards', []);
    this.bus?.dispatch('leftcardchanged', { source: this }); layoutCards(true);
    this.onVisibility?.(false);
    if (restoreFocus && this.opener?.isConnected) this.opener.focus({ preventScroll: true });
    return true;
  }
  setBusy(value) {
    this.busy = value; this.element.setAttribute('aria-busy', String(value)); this.body.inert = value;
    this.closeButton.disabled = value; this.pin.disabled = value;
  }
}
