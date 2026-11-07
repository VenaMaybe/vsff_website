import { cardScale, cardSize } from './card_scale.js';
import { animateCard, CARD_MOTION_MS } from './card_motion.js';
import { bindMenuDismissal, syncMenuValues } from "./menus.js";
import { pdfRectangleToCss } from "./anchor_geometry.js";
import { sectionGeometry } from './section_viewer.js';
import { LeftCard, registerLeftCard } from './left_card.js';
import { documentStage } from './document_stage.js';
import { installPdfGestures } from './pdf_gestures.js';
import { usesViewportComposer } from './comment_composer.js';

function installSearch(frame, application) {
  const doc = frame.contentDocument;
  const find = application.findBar;
  const row = doc.createElement("div");
  row.className = "review-find-row";
  const options = doc.createElement("div");
  options.className = "review-find-options";
  options.setAttribute('role','group');options.setAttribute('aria-label','Search options');
  for (const id of ["findbarOptionsOneContainer", "findbarOptionsTwoContainer"]) {
    options.append(...doc.getElementById(id).children);
  }
  find.findField.placeholder = "Search document...";
  find.findField.setAttribute("aria-label", "Search document");
  row.append(find.findField, find.findPreviousButton, find.findNextButton);
  find.bar.replaceChildren(row,find.findResultsCount,options,find.findMsg);
  const opener=document.querySelector('[data-pdf-control="viewFindButton"]');
  const nativeOpen=find.open.bind(find),nativeClose=find.close.bind(find);
  const focus=find.findField.focus.bind(find.findField),select=find.findField.select.bind(find.findField);
  let focusSearch=true;
  find.findField.focus=(options={})=>{if(focusSearch)focus({...options,preventScroll:true});};
  find.findField.select=()=>{if(focusSearch)select();};
  const card=new LeftCard('Search',{opener,viewer:{sectionViewer:{frame,application}},className:'search-panel',stateKey:'search',onVisibility:visible=>{if(!visible)nativeClose();}});
  card.body.append(find.bar);
  // Native localization observes the iframe; adopted controls use app-owned text.
  const count=find.updateResultsCount.bind(find),ui=find.updateUIState.bind(find);
  find.updateResultsCount=(matches={})=>{count(matches);const {current=0,total=0}=matches;find.findResultsCount.textContent=total?`${current} of ${total}`:'';};
  find.updateUIState=(state,previous,matches)=>{ui(state,previous,matches);const id=find.findMsg.getAttribute('data-l10n-id');find.findMsg.textContent=id==='pdfjs-find-not-found'?'No matches':id==='pdfjs-find-reached-top'?'Reached top; continuing from bottom':id==='pdfjs-find-reached-bottom'?'Reached bottom; continuing from top':'';};
  find.open=(options={})=>{
    card.open(options);
    // Native find.open also selects/focuses the field; keep Tools launches passive.
    focusSearch=options.focus!==false;
    try{nativeOpen();card.contentReady();find.findField.focus({preventScroll:true});}
    finally{focusSearch=true;}
    return card;
  };
  find.close=()=>{nativeClose();card.close();};
  registerLeftCard('search',options=>find.open(options));
  const shortcut = (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
      event.preventDefault(); event.stopImmediatePropagation();
      const search = find.open();
      if (!search.pinned) search.setPinned(true);
    }
    if (event.key === "Escape" && find.opened) { find.close(); }
  };
  document.addEventListener("keydown", shortcut);
  doc.addEventListener("keydown", shortcut, true);
}

function installToolsCard(frame,application){
  const menu=document.getElementById('review-tools-menu'),summary=menu.querySelector(':scope > summary');
  // Both surfaces share markup and delegated actions; each keeps its own focus.
  const content=menu.querySelector(':scope > .toolbar-popover').cloneNode(true);
  content.removeAttribute('style');
  const card=new LeftCard('Tools',{opener:summary,viewer:{sectionViewer:{frame,application}},stateKey:'tools',className:'tools-panel',onVisibility:visible=>{
    if(visible)card.contentReady();
  }});
  card.body.append(content);
  const open=()=>{menu.open=false;card.open();return card;};
  registerLeftCard('tools',open);
  summary.title='Tools (double-click or Shift+Enter to open as a card)';
  summary.addEventListener('dblclick',event=>{event.preventDefault();open();});
  const shortcut=event=>{
    if(event.key!=='Enter'||!event.shiftKey||event.ctrlKey||event.metaKey||event.altKey||
        event.isComposing||event.defaultPrevented)return;
    const target=event.target;
    // Keep editor newlines, Search's previous-match shortcut and other controls.
    if(target.isContentEditable||target.closest('input,textarea,select,[contenteditable="true"],[role="textbox"]'))return;
    if(!menu.contains(target)&&!card.element.contains(target)&&
        target.closest('button,a,summary,[role="button"],[role="dialog"],.toolbar-menu'))return;
    event.preventDefault();event.stopImmediatePropagation();
    if(!event.repeat)open();
  };
  document.addEventListener('keydown',shortcut,true);
  frame.contentDocument.addEventListener('keydown',shortcut,true);
}

export function installViewerControls(frame, application) {
  documentStage(application);
  installPdfGestures(frame, application);
  const pdf = application.pdfViewer;
  const native = frame.contentDocument;
  const page = document.getElementById("review-page-number");
  const scale = document.getElementById("review-scale");
  document.getElementById("review-page-count").textContent = `/ ${application.pdfDocument.numPages}`;
  page.max = application.pdfDocument.numPages;
  document.querySelectorAll("[data-pdf-control]").forEach(button=>{
    button.title ||= button.getAttribute("aria-label") || button.textContent.trim();
  });
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-pdf-control]');
    if(!button||button.disabled||button.hasAttribute('data-left-card'))return;
    native.getElementById(button.dataset.pdfControl)?.click();
    if(!button.closest('[data-keep-menu-open]'))button.closest("details")?.removeAttribute("open");
  });
  const syncCursorTools=({tool=application.pdfCursorTools?.activeTool??0,disabled}={})=>{
    for(const button of document.querySelectorAll('[data-pdf-control="cursorSelectTool"], [data-pdf-control="cursorHandTool"]')){
      const selected=button.dataset.pdfControl==='cursorSelectTool'?0:1;
      button.setAttribute('aria-pressed',String(tool===selected));
      button.disabled=disabled??native.getElementById(button.dataset.pdfControl)?.disabled??false;
    }
  };
  application.eventBus.on('cursortoolchanged',syncCursorTools);
  syncCursorTools();
  const commitPage = () => {
    const value = Number(page.value);
    if (Number.isInteger(value) && value >= 1 && value <= application.pdfDocument.numPages) pdf.currentPageNumber = value;
    page.value = pdf.currentPageNumber;
    if (matchMedia('(width < 750px), (pointer: coarse)').matches) page.blur();
  };
  page.addEventListener("change", commitPage);
  page.addEventListener("keydown", (event) => {
    if (event.key === 'Enter') { event.preventDefault(); commitPage(); }
  });
  scale.addEventListener("change", () => { if (scale.value !== "custom") pdf.currentScaleValue = scale.value; });
  const syncScale = () => {
    const value = String(pdf.currentScaleValue);
    const custom = document.getElementById("review-custom-scale");
    if ([...scale.options].some((option) => option.value === value)) scale.value = value;
    else { custom.textContent = `${Math.round(pdf.currentScale * 100)}%`; custom.hidden = false; scale.value = "custom"; }
    document.getElementById("review-scale-label").textContent = scale.selectedOptions[0].textContent;
    syncMenuValues();
  };
  application.eventBus.on("pagechanging", ({ pageNumber }) => { page.value = pageNumber; });
  application.eventBus.on("scalechanging", syncScale);
  for (const [id, property, event] of [["review-scroll", "scrollMode", "scrollmodechanged"], ["review-spread", "spreadMode", "spreadmodechanged"]]) {
    const control = document.getElementById(id);
    control.value = pdf[property];
    control.addEventListener("change", () => { pdf[property] = Number(control.value); });
    application.eventBus.on(event, ({ mode }) => { control.value = mode; syncMenuValues(); });
  }
  syncScale();
  const header = document.querySelector(".viewer-shell-bar");
  new ResizeObserver(() => document.documentElement.style.setProperty('--toolbar-height', `${header.offsetHeight}px`)).observe(header);
  syncMenuValues();
  installSearch(frame, application);
  installToolsCard(frame,application);
  bindMenuDismissal(native);

}

// Canonical payloads/anchors share segments. Never retain a DOM Range for layout.
export function anchorGeometry(application, anchor, { end = false } = {}) {
  const segment = end ? anchor?.segments?.at(-1) : anchor?.segments?.[0];
  const view = segment && application.pdfViewer.getPageView(segment.page_number - 1);
  if (!view?.div?.isConnected || !view.viewport) return null;
  const page = view.div.getBoundingClientRect();
  const content = { left: page.left + view.div.clientLeft, top: page.top + view.div.clientTop,
    width: view.div.clientWidth, height: view.div.clientHeight };
  const rectangles = end ? segment.rectangles.slice(-1) : segment.rectangles;
  const rects = rectangles.map((rectangle) => pdfRectangleToCss(rectangle, view.viewport, content)).filter(Boolean);
  if (!rects.length) return null;
  return { page, pageNumber: segment.page_number,
    top: content.top + Math.min(...rects.map((rect) => rect.top)),
    bottom: content.top + Math.max(...rects.map((rect) => rect.top + rect.height)),
    left: content.left + Math.min(...rects.map((rect) => rect.left)),
    right: content.left + Math.max(...rects.map((rect) => rect.left + rect.width)) };
}

export class CommentRail {
  constructor(frame, application, state, composer, selectionLayout) {
    Object.assign(this, { frame, application, state, composer, selectionLayout });
    composer.position = () => { this.composerPlacement = null; this.positionComposer(); };
    this.panel = document.querySelector(".review-panel");
    this.list = document.getElementById("thread-list");
    this.visibility = document.getElementById("comments-visibility");
    this.scroller = application.pdfViewer.container;
    this.stage = documentStage(application);
    application.eventBus.on('documentoriginchanged', ({dx,dy}) => {
      // Parent overlay coordinates must rebase in the same transaction as the
      // native scroll origin, before a scroll event can translate the list.
      for (const card of this.list.children) {
        if (card.style.left) card.style.left = `${parseFloat(card.style.left)+dx}px`;
        if (card.style.top) card.style.top = `${parseFloat(card.style.top)+dy}px`;
      }
      // Animation snapshots use the same document coordinates as card.top.
      // Rebasing moves content and scroll together; it is not card movement.
      for (const position of this.commentPositions?.values() || []) position.top += dy;
      if (this.composerPlacement) { this.composerPlacement.left += dx; this.composerPlacement.top += dy; }
      this.translate();
    });
    this.mobileQuery = matchMedia("(width < 750px)");
    this.mode = this.visibility.value;
    this.visibility.value = this.mode;
    this.mobileQuery.addEventListener("change", () => this.schedule());
    this.scheduled = false;
    this.observed = new Set();
    this.observer = new ResizeObserver(() => this.schedule());
    this.scroller.addEventListener("scroll", () => { this.translate(); this.selectionLayout(); if (this.mode === "mobile") this.schedule(); }, { passive: true });
    // The cards live in the parent overlay, but wheel scrolling belongs to the
    // same document surface as the PDF beneath them.
    this.panel.addEventListener("wheel", (event) => {
      if (event.ctrlKey || event.target.closest("textarea, .migration-panel, .anchor-debug-section")) return;
      const popup = event.target.closest(".thread-card.active, .selection-comment-composer");
      if (popup && (this.mode === "mobile" || popup.scrollHeight > popup.clientHeight)) return;
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? this.scroller.clientHeight : 1;
      this.scroller.scrollBy(event.deltaX * unit, event.deltaY * unit);
      event.preventDefault();
    }, { passive: false });
    new ResizeObserver(() => this.schedule()).observe(document.querySelector(".viewer-workspace"));
    new ResizeObserver(() => this.schedule()).observe(this.scroller);
    window.visualViewport?.addEventListener('resize', () => this.positionComposer());
    window.visualViewport?.addEventListener('scroll', () => this.positionComposer());
    application.eventBus.on("updateviewarea", () => {
      // Scrolling alone changes no content-space geometry. Check one current page.
      const page = application.pdfViewer.getPageView(application.pdfViewer.currentPageNumber - 1)?.div?.getBoundingClientRect();
      const signature = page && [Math.round(page.left + this.scroller.scrollLeft), Math.round(page.width), Math.round(page.height), application.pdfViewer.spreadMode].join(":");
      if (signature !== this.geometrySignature) { this.geometrySignature = signature; this.schedule(); }
    });
    for (const event of ["scalechanging", "rotationchanging", "pagerendered", "textlayerrendered", "scrollmodechanged", "spreadmodechanged", "pagesinit", "leftcardchanged"]) application.eventBus.on(event, () => this.schedule());
    this.visibility.addEventListener("change", () => {
      this.mode = this.visibility.value;
      this.schedule();
      const hidden = this.mode === "hidden";
      frame.contentDocument.documentElement.classList.toggle("review-comments-hidden", hidden);
    });
    document.querySelector(".anchor-debug-section").hidden = new URLSearchParams(location.search).get("debug") !== "anchors";
    if (document.getElementById("migration-panel")) this.panel.classList.add("migration-active");
  }
  schedule() {
    this.stage.schedule('comments', () => this.layout());
  }
  translate() {
    this.list.style.transform = `translate(${-this.scroller.scrollLeft}px, ${-this.scroller.scrollTop}px)`;
    this.positionComposer();
    this.positionFloating();
  }
  showThread() {
    if (this.mode === "hidden") {
      this.mode = this.mobileQuery.matches ? "mobile" : "expanded";
      this.visibility.value = this.mode;
      this.frame.contentDocument.documentElement.classList.remove("review-comments-hidden");
      syncMenuValues();
    }
    this.schedule();
  }
  layout() {
    this.positionComposer();
    const composing = !this.composer.container.hidden;
    const viewportComposer = this.composer.container.classList.contains('viewport-composer');
    const visible = this.mode !== "hidden";
    const cards = [...this.list.querySelectorAll(".thread-card")];
    for (const old of this.observed) {
      if (!old.isConnected) { this.observer.unobserve(old); this.observed.delete(old); }
    }
    this.panel.classList.toggle("has-comments", cards.length > 0 && visible);
    this.panel.classList.toggle("composing", composing);
    const mobile = this.mode === "mobile";
    const minimized = this.mode === "minimized" || mobile;
    this.panel.classList.toggle("mobile-comments", mobile);
    // Comments remain beside their page/spread at every viewport and zoom. When
    // the pair is wider than the viewport, the native scrollbar reaches both.
    const root = this.frame.contentDocument.documentElement;
    root.classList.toggle("review-comments-hidden", !visible);
    this.list.hidden = !visible;
    this.list.dataset.layout = "right-rail";
    const items = [];
    this.floating = null;
    const markers = new Map([...this.list.querySelectorAll(".thread-marker")].map((item) => [item.dataset.threadId, item]));
    for (const card of cards) {
      const thread = this.state.thread(card.dataset.threadId);
      const geometry = thread?.section ? sectionGeometry(this.application,thread.section) : anchorGeometry(this.application, thread?.targets[0]?.anchor);
      const marker = markers.get(thread.thread_id);
      const active = thread.thread_id === this.state.selectedThreadId;
      if (!visible) { marker.hidden = true; card.hidden = true; continue; }
      marker.hidden = !minimized;
      card.hidden = minimized && !active;
      card.classList.toggle("floating-thread-card", minimized && active);
      card.style.removeProperty("width");
      card.style.removeProperty("max-height");
      const item = minimized ? marker : card;
      card.setAttribute("aria-label", `Review thread, page ${geometry?.pageNumber || "unknown"}`);
      if (!this.observed.has(item)) { this.observer.observe(item); this.observed.add(item); }
      if (active && !this.observed.has(card)) { this.observer.observe(card); this.observed.add(card); }
      if (!geometry) { item.hidden = true; card.hidden = true; continue; }
      const railLeft = this.spreadRight(geometry.pageNumber) + 6*cardScale(this.application);
      const x = (mobile && !thread.section ? Math.min(railLeft, this.scroller.clientWidth - 42*cardScale(this.application)) : railLeft) + this.scroller.scrollLeft;
      items.push({ card: item, page: geometry.pageNumber, sectionId:thread.section?.section_id, bottomAligned:!!thread.section, y: geometry.top + this.scroller.scrollTop - (thread.section&&!minimized?cardSize(item, this.application).height:0),
        center: (geometry.top + geometry.bottom) / 2 + this.scroller.scrollTop,
        active: active && !minimized, x, height: cardSize(item, this.application).height });
      if (active && minimized) this.floating = { card, geometry, railLeft };
    }
    const gap = (minimized ? 3 : 6) * cardScale(this.application);
    const composerGeometry = composing && anchorGeometry(this.application, this.composer.payload);
    // An active card (or composer) is the fixed point. Pack neighbors backwards
    // and forwards around it, without touching either PDF scroll coordinate.
    if (composerGeometry && !minimized && !viewportComposer) items.push({ card: this.composer.container,
      page: composerGeometry.pageNumber, y: composerGeometry.top + this.scroller.scrollTop,
      center: (composerGeometry.top + composerGeometry.bottom) / 2 + this.scroller.scrollTop,
      active: true, x: this.spreadRight(composerGeometry.pageNumber) + 6*cardScale(this.application) + this.scroller.scrollLeft,
      height: cardSize(this.composer.container, this.application).height });
    const compare=(a,b)=>a.page-b.page || a.y-b.y || (a.card.dataset.threadId||'').localeCompare(b.card.dataset.threadId||'');
    items.sort(compare);
    const sections=minimized?[]:items.filter(item=>item.bottomAligned);
    const normal=sections.length?items.filter(item=>!item.bottomAligned):items;
    const pivot = normal.findIndex((item) => item.active);
    if (pivot >= 0) {
      const selected = normal[pivot];
      selected.top = selected.bottomAligned ? selected.y : Math.max(this.scroller.scrollTop + 8, selected.center - selected.height / 2);
      let top = selected.top;
      for (let i = pivot - 1; i >= 0; i--) {
        normal[i].top = Math.min(normal[i].y, top - normal[i].height - gap);
        top = normal[i].top;
      }
    }
    let bottom = pivot >= 0 ? normal[pivot].top + normal[pivot].height + gap : 8;
    for (let i = pivot + 1; i < normal.length; i++) {
      const item = normal[i];
      item.top = Math.max(item.y, bottom);
      bottom = item.top + item.height + gap;
    }
    if(sections.length){
      // Keep the ordinary list intact. Insert each section response group at the
      // list boundary that puts its bottom closest to the section endpoint.
      const groups=[];
      for(const item of [...sections].sort((a,b)=>a.page-b.page||a.center-b.center||compare(a,b))){
        const last=groups.at(-1);
        if(last?.[0].sectionId===item.sectionId)last.push(item);else groups.push([item]);
      }
      const list=[...normal];
      let firstSlot=0;
      for(const group of groups){
        const height=group.reduce((sum,item)=>sum+item.height,0)+gap*(group.length-1);
        const target=group[0].center,preferred=target-height;
        let best=null;
        for(let index=firstSlot;index<=list.length;index++){
          const before=list[index-1],after=list[index];
          const lower=before?before.top+before.height+gap:Math.min(8,list[0]?.top??-Infinity);
          const upper=after?after.top-gap-height:Infinity;
          // Use an existing natural gap when it fits. In a dense run, insert
          // directly after the preceding card and push the remaining list down.
          const top=upper>=lower?Math.max(lower,Math.min(preferred,upper)):lower;
          const distance=Math.abs(top+height-target);
          const shift=after?Math.max(0,top+height+gap-after.top):0;
          if(!best||distance<best.distance||(distance===best.distance&&shift<best.shift))best={index,top,distance,shift};
        }
        let top=best.top;
        for(const item of group){item.top=top;top+=item.height+gap;}
        list.splice(best.index,0,...group);
        firstSlot=best.index+group.length;
        for(let index=firstSlot;index<list.length;index++){
          const before=list[index-1],item=list[index];
          item.top=Math.max(item.top,before.top+before.height+gap);
        }
      }
      bottom=Math.max(...items.map(item=>item.top+item.height+gap));
    }
    for (const item of items) {
      const composer = item.card === this.composer.container;
      if (composer) this.composerPlacement = { payload: this.composer.payload, left: item.x, top: item.top };
      item.card.style.left = `${item.x - (composer ? this.scroller.scrollLeft : 0)}px`;
      item.card.style.top = `${item.top - (composer ? this.scroller.scrollTop : 0)}px`;
    }
    this.positionFloating();
    // Floating cards and composers do not belong to the marker-height list.
    // Reserve only their actual painted area, without expanded-card-sized gaps.
    const obstacles = [this.floating?.card, composing ? this.composer.container : null]
      .filter(Boolean).map(node => node.getBoundingClientRect()).sort((a,b)=>a.top-b.top);
    if (minimized && obstacles.length) {
      let previous = -Infinity;
      const frameTop = this.frame.getBoundingClientRect().top;
      for (const item of items) {
        const rect = item.card.getBoundingClientRect();
        let top = Math.max(item.top, previous);
        for (const obstacle of obstacles) {
          const screenTop = frameTop + top - this.scroller.scrollTop;
          if (rect.left < obstacle.right && rect.right > obstacle.left &&
              screenTop < obstacle.bottom && screenTop + item.height > obstacle.top) {
            top = obstacle.bottom - frameTop + this.scroller.scrollTop + gap;
          }
        }
        item.top = top; item.card.style.top = `${top}px`;
        previous = top + item.height + gap;
      }
    }
    const frame = this.frame.getBoundingClientRect();
    const reachable = new Set(items.map(item => item.card));
    if (this.floating) reachable.add(this.floating.card);
    if (composing && !viewportComposer) reachable.add(this.composer.container);
    this.stage.setBounds('comments', [...reachable].filter(card => card.getClientRects().length).map(card => {
      const rect = card.getBoundingClientRect();
      const visualTop = rect.top-frame.top+this.scroller.scrollTop;
      const targetTop = card.parentElement === this.list ? card.offsetTop : visualTop;
      return {left:rect.left-frame.left+this.scroller.scrollLeft,
        right:rect.right-frame.left+this.scroller.scrollLeft+10,
        top:Math.min(visualTop,targetTop),
        bottom:Math.max(visualTop,targetTop)+cardSize(card, this.application).height+gap};
    }));
    // Parent-owned cards must never cover the iframe's native scrollbars.
    this.panel.style.clipPath = `inset(0 ${this.scroller.offsetWidth - this.scroller.clientWidth}px ${this.scroller.offsetHeight - this.scroller.clientHeight}px 0)`;
    this.animateComments(items, composing);
    this.translate();
    this.selectionLayout();
    this.application.eventBus.dispatch("reviewlayoutchanged",{source:this});
  }
  animateComments(items, composing) {
    const focus = `${this.mode}:${this.state.selectedThreadId || ""}:${composing}`;
    const changed = this.commentFocus !== undefined && this.commentFocus !== focus;
    const previous = this.commentPositions || new Map();
    const next = new Map();
    const now = performance.now();
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const nodes = items.map(({ card }) => card).filter((card) => card !== this.composer.container);
    if (this.floating) nodes.push(this.floating.card);
    for (const node of nodes) {
      const key = `${node.classList.contains("thread-marker") ? "marker" : "card"}:${node.dataset.threadId}`;
      const top = parseFloat(node.style.top);
      const old = previous.get(key);
      let motion = old?.motion;
      if (changed && !reduced) {
        const opening = node.classList.contains("active") && !old;
        const remaining = old?.motion ? Math.max(0, 1 - (now - old.motion.started) / CARD_MOTION_MS) : 0;
        const visualTop = old ? old.top + (old.motion?.delta || 0) * remaining ** 3 : top + 4;
        motion = { started: now, delta: visualTop - top, opening };
      }
      if (!reduced && motion && (changed || old?.node !== node)) {
        const remaining = Math.max(0, 1 - (now - motion.started) / CARD_MOTION_MS);
        if (remaining > 0 && (Math.abs(motion.delta) > .5 || motion.opening)) {
          animateCard(node, motion.delta * remaining ** 3, motion.opening, CARD_MOTION_MS * remaining);
        }
      }
      next.set(key, { node, top, motion });
    }
    this.commentPositions = next;
    this.commentFocus = focus;
  }
  spreadRight(pageNumber) {
    const page = this.application.pdfViewer.getPageView(pageNumber - 1).div;
    const pdf = this.application.pdfViewer;
    const siblings = pdf.scrollMode === 1 ? pdf.viewer.querySelectorAll(".page, .dummyPage")
      : page.closest(".spread")?.querySelectorAll(".page, .dummyPage") || [page];
    return Math.max(...[...siblings].map((item) => item.getBoundingClientRect().right));
  }
  popupPosition(box, geometry) {
    const width = Math.min(280, this.scroller.clientWidth - 40);
    box.style.width = `${width}px`;
    const left = Math.max(8, Math.min(geometry.left, this.scroller.clientWidth - cardSize(box, this.application).width - 8));
    const top = geometry.bottom + 8;
    box.style.maxHeight = `${Math.max(120, this.scroller.clientHeight * 0.65)}px`;
    return { left, top };
  }
  positionFloating() {
    if (!this.floating) return;
    const { card } = this.floating;
    const thread = this.state.thread(card.dataset.threadId);
    const geometry = thread?.section ? sectionGeometry(this.application,thread.section) : anchorGeometry(this.application, thread?.targets[0]?.anchor);
    if (!geometry) return;
    const mobile = this.mode === "mobile" && !thread.section;
    card.style.removeProperty("width");
    card.style.removeProperty("max-height");
    const position = mobile ? this.popupPosition(card, geometry) : {
      left: this.spreadRight(geometry.pageNumber) + 48*cardScale(this.application),
      top: thread.section ? geometry.top-cardSize(card, this.application).height : Math.max(8, (geometry.top + geometry.bottom - cardSize(card, this.application).height) / 2) };
    card.style.left = `${position.left + this.scroller.scrollLeft}px`;
    card.style.top = `${position.top + this.scroller.scrollTop}px`;
  }
  positionComposer() {
    const box = this.composer.container;
    if (box.hidden) return;
    if (usesViewportComposer()) {
      this.composer.setViewportDocked(true);
      const viewport = window.visualViewport;
      const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
      const right = left + (viewport?.width || innerWidth);
      const bottom = top + (viewport?.height || innerHeight);
      // Safari may pan the visual viewport independently of the PDF frame.
      // Size to the visible screen, never to their potentially tiny overlap.
      box.style.width = `${Math.max(0, Math.min(280, right - left - 24))}px`;
      box.style.maxHeight = `${Math.max(0, bottom - top - 28)}px`;
      box.style.left = `${Math.max(left + 12, right - cardSize(box, this.application).width - 12)}px`;
      box.style.top = `${Math.max(top + 12, bottom - cardSize(box, this.application).height - 16)}px`;
      return;
    }
    this.composer.setViewportDocked(false);
    const geometry = anchorGeometry(this.application, this.composer.payload);
    if (!geometry) return;
    box.style.removeProperty("width");
    box.style.removeProperty("max-height");
    if (this.mode === 'mobile' || this.mode === 'hidden') {
      const position = this.popupPosition(box, geometry);
      box.style.left = `${position.left}px`; box.style.top = `${position.top}px`;
      return;
    }
    if (this.mode === 'expanded' && this.composerPlacement?.payload === this.composer.payload) {
      box.style.left = `${this.composerPlacement.left - this.scroller.scrollLeft}px`;
      box.style.top = `${this.composerPlacement.top - this.scroller.scrollTop}px`;
      return;
    }
    box.style.left = `${this.spreadRight(geometry.pageNumber) + (this.mode === "minimized" ? 48 : 6)*cardScale(this.application)}px`;
    box.style.top = `${Math.max(8, (geometry.top + geometry.bottom - cardSize(box, this.application).height) / 2)}px`;
  }
}
