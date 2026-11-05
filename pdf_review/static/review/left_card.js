import { animateCard, CARD_MOTION_MS } from './card_motion.js';
import { documentStage } from './document_stage.js';

const cards = new Set();
let scheduled = false;
let focusedCard = null;
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
      card.anchorFraction=record.fraction;card.pinned=record.pinned&&!pinned;pinned ||= card.pinned;card.updatePin();
      card.element.classList.remove('active');
    }
    focusedCard=null;
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
      const integration=group[0].sectionViewer;
      const firstPage=integration.application.pdfViewer.getPageView(0)?.div;
      const pageTop=firstPage ? integration.frame.getBoundingClientRect().top+firstPage.getBoundingClientRect().top-parent.getBoundingClientRect().top : 0;
      for (const card of group) {
        if (card.openingCentered && !card.pinned) card.captureAnchor(parent.getBoundingClientRect().top + Math.max(8, (parent.clientHeight-card.element.offsetHeight)/2));
        if (card.centerRequest) {
          const center = card.centerRequest();
          if (!card.pinned && Number.isFinite(center)) card.captureAnchor(parent.getBoundingClientRect().top + Math.max(8, center - parent.getBoundingClientRect().top - card.element.offsetHeight / 2));
          card.centerRequest = null;
        }
        card.preferredTop = card.pinned ? Math.max(8,pageTop) : Math.max(pageTop,card.documentTop());
      }
      // Pinned cards are an independent overlay. Only document-attached cards
      // take part in collision packing and choose a fixed point.
      const occupied = [];
      for (const card of group) if (card.pinned) card.layoutTop = card.preferredTop;
      const order = group.filter(card => !card.pinned).sort((a,b) => (b === focusedCard)-(a === focusedCard));
      for (const card of order) {
        const gaps = [];
        const min = pageTop, max = Infinity;
        let start = min;
        for (const box of occupied.sort((a,b) => a.top-b.top)) {
          if (box.bottom + 8 <= min || box.top - 8 >= max) continue;
          gaps.push({ start, end: Math.min(max, box.top - 8) });
          start = Math.max(start, box.bottom + 8);
        }
        gaps.push({ start, end:max });
        const fitting = gaps.filter(gap => gap.end - gap.start >= card.element.offsetHeight);
        const choices = fitting.map(gap => Math.max(gap.start, Math.min(card.preferredTop, gap.end - card.element.offsetHeight)));
        card.layoutTop = choices.length ? choices.reduce((a,b) => Math.abs(b-card.preferredTop) < Math.abs(a-card.preferredTop) ? b : a) : card.preferredTop;
        occupied.push({top:card.layoutTop, bottom:card.layoutTop+card.element.offsetHeight});
      }
      for (const card of group) {
        const offset = card.layoutTop-card.preferredTop;
        card.position(animate || (card.lastOffset !== undefined && Math.abs(offset-card.lastOffset)>1));
        card.lastOffset = offset;
      }
      const scroller=integration.application.pdfViewer.container, frame=integration.frame.getBoundingClientRect();
      documentStage(integration.application).setBounds('left-cards', group.filter(card=>!card.pinned).map(card=>{
        const rect=card.element.getBoundingClientRect();
        return {left:rect.left-frame.left+scroller.scrollLeft-8, right:rect.right-frame.left+scroller.scrollLeft+8,
          top:card.layoutTop+scroller.scrollTop, bottom:card.layoutTop+card.element.offsetHeight+scroller.scrollTop+8};
      }));
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
  focusedCard=null;
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
    this.element.addEventListener('pointerdown', () => { this.openingCentered=false; this.activate(); });
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
  get sectionViewer() { return this.viewer?.sectionViewer; }
  open({focus = true} = {}) {
    if (this.element.isConnected) { this.reveal({focus}); return true; }
    // Reused cards can retain their old active class after closing.
    if (!focus) this.element.classList.remove('active');
    cards.add(this);
    const workspace = document.querySelector('.viewer-workspace');
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
    this.captureAnchor((workspace?.getBoundingClientRect().top || 0) + Math.max(8, ((workspace?.clientHeight || innerHeight)-this.element.offsetHeight)/2));
    this.onScroll = () => this.schedule();
    this.scroller?.addEventListener('scroll', this.onScroll, { passive: true });
    this.resize = new ResizeObserver(this.schedule);
    this.resize.observe(workspace || document.body); this.resize.observe(this.element);
    for (const event of ['scalechanging', 'rotationchanging', 'spreadmodechanged', 'scrollmodechanged', 'pagerendered', 'reviewlayoutchanged', 'documentoriginchanged']) this.bus?.on(event, this.schedule);
    layoutCards(true); animateCard(this.element, 4, true);
    this.onVisibility?.(true); if (focus) this.closeButton.focus({ preventScroll: true });
    return true;
  }
  contentReady() {
    if(!this.openingCentered)return;
    layoutCards(true);
    requestAnimationFrame(()=>requestAnimationFrame(()=>{this.openingCentered=false;}));
  }
  activate() {
    const changed = !this.pinned && (focusedCard !== this || !this.element.classList.contains('active'));
    if(changed && this.element.isConnected && !this.openingCentered) {
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
    if (!this.pinned) focusedCard = this;
    for (const card of cards) card.element.classList.toggle('active', card === this);
    if (changed) layoutCards(true);
  }
  startHeaderDrag(event) {
    if (event.button !== 0 || event.target.closest('button') || this.busy) return;
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
      if (!moved) { if (this.pinned) this.setPinned(false, false); this.activate(); moved = true; }
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
    layoutCards(animate);
  }
  documentTop() {
    if (!this.anchorPage) return 8;
    const page = this.anchorPage.getBoundingClientRect();
    return this.sectionViewer.frame.getBoundingClientRect().top - this.element.parentElement.getBoundingClientRect().top + page.top + this.anchorFraction * page.height;
  }
  centerOn(getCenter) {
    this.openingCentered = false;
    this.centerRequest = getCenter; this.activate(); layoutCards(true);
    this.closeButton.focus({ preventScroll:true });
  }
  reveal({focus = true} = {}) {
    if (focus) this.activate();
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
    const integration = this.sectionViewer, pdf = integration?.application.pdfViewer;
    this.anchorPage = pdf?.getPageView(pdf.currentPageNumber - 1)?.div;
    if (!this.anchorPage) return;
    const page = this.anchorPage.getBoundingClientRect();
    // Negative fractions are intentional: the card may be above the current page.
    // Capture the actual rendered card position, never a clamped page boundary.
    this.anchorFraction = (visualTop - integration.frame.getBoundingClientRect().top - page.top) / page.height;
  }
  position(animate = false, visualTop = this.element.getBoundingClientRect().top) {
    const integration = this.sectionViewer;
    if (!integration) return;
    const pdf = integration.application.pdfViewer;
    const page = !this.pinned ? this.anchorPage : pdf.getPageView(pdf.currentPageNumber - 1)?.div;
    if (!page) return;
    const rect = page.getBoundingClientRect(), frame = integration.frame.getBoundingClientRect();
    const firstPageTop=frame.top+pdf.getPageView(0).div.getBoundingClientRect().top;
    if(visualTop<firstPageTop){this.element.getAnimations().forEach(animation=>animation.cancel());visualTop=firstPageTop;}
    const workspace = this.element.parentElement.getBoundingClientRect();
    const siblings = pdf.scrollMode === 1 ? pdf.viewer.querySelectorAll('.page') : page.closest('.spread')?.querySelectorAll(':scope > .page') || [page];
    const left = Math.min(...[...siblings].map(p => p.getBoundingClientRect().left));
    const x = frame.left + left - workspace.left - this.element.offsetWidth - 12;
    // Unpinned tools belong to the document rail at every viewport size.
    // The shared stage provides scrollable space to their left on mobile too.
    const overlay = this.pinned;
    this.element.style.left = `${overlay ? Math.max(8, Math.min(x, workspace.width - this.element.offsetWidth - 8)) : x}px`;
    const top = this.layoutTop ?? 8;
    this.element.style.top = `${top}px`; this.lastTop = top;
    if (animate && Math.abs(visualTop - workspace.top - top) > .5) animateCard(this.element, visualTop - workspace.top - top);
  }
  close(restoreFocus = true) {
    if (this.busy) return false;
    this.cancelHeaderDrag?.();this.focusEvents?.abort();
    this.scroller?.removeEventListener('scroll', this.onScroll); this.resize?.disconnect();
    for (const event of ['scalechanging', 'rotationchanging', 'spreadmodechanged', 'scrollmodechanged', 'pagerendered', 'reviewlayoutchanged', 'documentoriginchanged']) this.bus?.off(event, this.schedule);
    this.element.getAnimations().forEach(animation => animation.cancel());
    const parent = this.element.parentElement;
    this.element.remove();
    cards.delete(this);
    syncToolMenuValues();
    if (focusedCard === this) focusedCard = null;
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
