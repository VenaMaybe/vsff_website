import { animateCard, CARD_MOTION_MS } from './card_motion.js';
import { bindMenuDismissal, syncMenuValues } from "./menus.js";
import { pdfRectangleToCss } from "./anchor_geometry.js";
import { sectionGeometry } from './section_viewer.js';
import { LeftCard, registerLeftCard } from './left_card.js';

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
  const focus=find.findField.focus.bind(find.findField);
  find.findField.focus=(options={})=>focus({...options,preventScroll:true});
  const card=new LeftCard('Search document',{opener,viewer:{sectionViewer:{frame,application}},className:'search-panel',stateKey:'search',onVisibility:visible=>{if(!visible)nativeClose();}});
  card.body.append(find.bar);
  // Native localization observes the iframe; adopted controls use app-owned text.
  const count=find.updateResultsCount.bind(find),ui=find.updateUIState.bind(find);
  find.updateResultsCount=(matches={})=>{count(matches);const {current=0,total=0}=matches;find.findResultsCount.textContent=total?`${current} of ${total}`:'';};
  find.updateUIState=(state,previous,matches)=>{ui(state,previous,matches);const id=find.findMsg.getAttribute('data-l10n-id');find.findMsg.textContent=id==='pdfjs-find-not-found'?'No matches':id==='pdfjs-find-reached-top'?'Reached top; continuing from bottom':id==='pdfjs-find-reached-bottom'?'Reached bottom; continuing from top':'';};
  find.open=()=>{const opening=!card.element.isConnected;card.open();if(opening&&innerWidth<750)application.pdfViewer.container.scrollLeft=0;nativeOpen();card.contentReady();find.findField.focus({preventScroll:true});return card;};
  find.close=()=>{nativeClose();card.close();};
  registerLeftCard('search',()=>find.open());
  const shortcut = (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
      event.preventDefault(); event.stopImmediatePropagation(); find.open();
    }
    if (event.key === "Escape" && find.opened) { find.close(); }
  };
  document.addEventListener("keydown", shortcut);
  doc.addEventListener("keydown", shortcut, true);
}

export function installViewerControls(frame, application) {
  const pdf = application.pdfViewer;
  const native = frame.contentDocument;
  const page = document.getElementById("review-page-number");
  const scale = document.getElementById("review-scale");
  document.getElementById("review-page-count").textContent = `/ ${application.pdfDocument.numPages}`;
  page.max = application.pdfDocument.numPages;
  document.querySelectorAll("[data-pdf-control]").forEach((button) => {
    button.title ||= button.getAttribute("aria-label") || button.textContent.trim();
    button.addEventListener("click", () => {
      native.getElementById(button.dataset.pdfControl)?.click();
      button.closest("details")?.removeAttribute("open");
    });
  });
  page.addEventListener("change", () => {
    const value = Number(page.value);
    if (Number.isInteger(value) && value >= 1 && value <= application.pdfDocument.numPages) pdf.currentPageNumber = value;
    page.value = pdf.currentPageNumber;
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
  bindMenuDismissal(native);

}

// Canonical payloads/anchors share segments. Never retain a DOM Range for layout.
export function anchorGeometry(application, anchor) {
  const segment = anchor?.segments?.[0];
  const view = segment && application.pdfViewer.getPageView(segment.page_number - 1);
  if (!view?.div?.isConnected || !view.viewport) return null;
  const page = view.div.getBoundingClientRect();
  const content = { left: page.left + view.div.clientLeft, top: page.top + view.div.clientTop,
    width: view.div.clientWidth, height: view.div.clientHeight };
  const rects = segment.rectangles.map((rectangle) => pdfRectangleToCss(rectangle, view.viewport, content)).filter(Boolean);
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
    this.panel = document.querySelector(".review-panel");
    this.list = document.getElementById("thread-list");
    this.visibility = document.getElementById("comments-visibility");
    this.scroller = application.pdfViewer.container;
    this.mobileQuery = matchMedia("(width < 750px)");
    this.desktopMode = "expanded";
    this.mode = this.mobileQuery.matches ? "mobile" : this.visibility.value;
    this.visibility.value = this.mode;
    this.mobileQuery.addEventListener("change", ({ matches }) => {
      if (matches) {
        if (this.mode !== "mobile") this.desktopMode = this.mode;
        this.mode = "mobile";
      } else if (this.mode === "mobile") this.mode = this.desktopMode;
      this.visibility.value = this.mode;
      this.application.pdfViewer.viewer.style.removeProperty("width");
      this.schedule();
      syncMenuValues();
    });
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
    let workspaceWidth = this.panel.clientWidth;
    new ResizeObserver(() => {
      if (workspaceWidth !== this.panel.clientWidth) {
        workspaceWidth = this.panel.clientWidth;
        this.application.pdfViewer.viewer.style.removeProperty("width");
      }
      this.schedule();
    }).observe(document.querySelector(".viewer-workspace"));
    new ResizeObserver(() => this.schedule()).observe(this.scroller);
    application.eventBus.on("updateviewarea", () => {
      // Scrolling alone changes no content-space geometry. Check one current page.
      const page = application.pdfViewer.getPageView(application.pdfViewer.currentPageNumber - 1)?.div?.getBoundingClientRect();
      const signature = page && [Math.round(page.left + this.scroller.scrollLeft), Math.round(page.width), Math.round(page.height), application.pdfViewer.spreadMode].join(":");
      if (signature !== this.geometrySignature) { this.geometrySignature = signature; this.schedule(); }
    });
    for (const event of ["scalechanging", "rotationchanging", "pagerendered", "textlayerrendered", "scrollmodechanged", "spreadmodechanged", "pagesinit", "leftcardchanged"]) application.eventBus.on(event, () => this.schedule());
    this.visibility.addEventListener("change", () => {
      this.mode = this.visibility.value;
      if (this.mode !== "mobile") this.desktopMode = this.mode;
      this.application.pdfViewer.viewer.style.removeProperty("width");
      this.schedule();
      const hidden = this.mode === "hidden";
      frame.contentDocument.documentElement.classList.toggle("review-comments-hidden", hidden);
    });
    document.querySelector(".anchor-debug-section").hidden = new URLSearchParams(location.search).get("debug") !== "anchors";
    if (document.getElementById("migration-panel")) this.panel.classList.add("migration-active");
  }
  schedule() {
    if (this.scheduled) return;
    this.scheduled = true;
    requestAnimationFrame(() => { this.scheduled = false; this.layout(); });
  }
  translate() {
    this.list.style.transform = `translate(${-this.scroller.scrollLeft}px, ${-this.scroller.scrollTop}px)`;
    this.positionComposer();
    this.positionFloating();
  }
  freezePageWidth() {
    const viewer = this.application.pdfViewer.viewer;
    if (!viewer.style.width) viewer.style.width = this.frame.contentWindow.getComputedStyle(viewer).width;
  }
  showThread() {
    this.freezePageWidth();
    if (this.mode === "hidden") {
      this.mode = this.mobileQuery.matches ? "mobile" : "expanded";
      this.visibility.value = this.mode;
      this.frame.contentDocument.documentElement.classList.remove("review-comments-hidden");
      syncMenuValues();
    }
    this.schedule();
  }
  layout() {
    const composing = !this.composer.container.hidden;
    const visible = this.mode !== "hidden";
    const cards = [...this.list.querySelectorAll(".thread-card")];
    for (const old of this.observed) {
      if (!old.isConnected) { this.observer.unobserve(old); this.observed.delete(old); }
    }
    this.panel.classList.toggle("has-comments", cards.length > 0 && visible);
    this.panel.classList.toggle("composing", composing);
    const pdf = this.application.pdfViewer;
    const mobile = this.mode === "mobile";
    const minimized = this.mode === "minimized" || mobile;
    this.panel.classList.toggle("mobile-comments", mobile);
    const styles = getComputedStyle(document.documentElement);
    const cardWidth = parseFloat(styles.getPropertyValue("--comment-width"));
    const railWidth = minimized ? parseFloat(styles.getPropertyValue("--comment-marker-width")) : cardWidth + 20;
    // Comments remain beside their page/spread at every viewport and zoom. When
    // the pair is wider than the viewport, the native scrollbar reaches both.
    const reserve = ((cards.length && visible) || composing) ? (minimized ? railWidth : cardWidth + 20) : 0;
    const root = this.frame.contentDocument.documentElement;
    root.classList.toggle("review-comments-hidden", !visible);
    root.style.setProperty("--review-rail-right", `${reserve}px`);
    const pages = Array.from({ length: this.application.pdfDocument.numPages }, (_, i) => pdf.getPageView(i));
    const stageWidth = Math.max(...pages.map((view) => (view?.viewport?.width || 0) + 18)) * (pdf.spreadMode ? 2 : 1) + 7;
    root.style.setProperty("--review-stage-width", (reserve || parseFloat(root.style.getPropertyValue("--review-rail-left"))) ? `${stageWidth}px` : "0px");
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
      const railLeft = this.spreadRight(geometry.pageNumber) + 6;
      const x = (mobile && !thread.section ? Math.min(railLeft, this.scroller.clientWidth - 42) : railLeft) + this.scroller.scrollLeft;
      items.push({ card: item, page: geometry.pageNumber, bottomAligned:!!thread.section, y: geometry.top + this.scroller.scrollTop - (thread.section&&!minimized?item.offsetHeight:0),
        center: (geometry.top + geometry.bottom) / 2 + this.scroller.scrollTop,
        active: active && !minimized, x, height: item.offsetHeight });
      if (active && minimized) this.floating = { card, geometry, railLeft };
    }
    const gap = minimized ? 3 : 6;
    const composerGeometry = composing && anchorGeometry(this.application, this.composer.payload);
    // An active card (or composer) is the fixed point. Pack neighbors backwards
    // and forwards around it, without touching either PDF scroll coordinate.
    if (composerGeometry && !minimized) items.push({ card: this.composer.container,
      page: composerGeometry.pageNumber, y: composerGeometry.top + this.scroller.scrollTop,
      center: (composerGeometry.top + composerGeometry.bottom) / 2 + this.scroller.scrollTop,
      active: true, x: this.spreadRight(composerGeometry.pageNumber) + 6 + this.scroller.scrollLeft,
      height: this.composer.container.offsetHeight });
    items.sort((a, b) => a.page - b.page || a.y - b.y || (a.card.dataset.threadId || "").localeCompare(b.card.dataset.threadId || ""));
    const pivot = items.findIndex((item) => item.active);
    if (pivot >= 0) {
      const selected = items[pivot];
      selected.top = selected.bottomAligned ? selected.y : Math.max(this.scroller.scrollTop + 8, selected.center - selected.height / 2);
      let top = selected.top;
      for (let i = pivot - 1; i >= 0; i--) {
        items[i].top = Math.min(items[i].y, top - items[i].height - gap);
        top = items[i].top;
      }
    }
    let bottom = pivot >= 0 ? items[pivot].top + items[pivot].height + gap : 8;
    for (let i = pivot + 1; i < items.length; i++) {
      const item = items[i];
      item.top = Math.max(item.y, bottom);
      bottom = item.top + item.height + gap;
    }
    for (const item of items) {
      item.card.style.left = `${item.x}px`;
      item.card.style.top = `${item.top}px`;
    }
    // Make collision overflow reachable using the PDF's primary scrollbar.
    if (!this.tail) { this.tail = this.frame.contentDocument.createElement("div"); this.tail.className = "review-rail-tail"; this.scroller.append(this.tail); }
    const viewer = this.application.pdfViewer.viewer;
    const needed = !visible ? 0 : Math.max(0, bottom - viewer.offsetHeight);
    const overflowKey = [pdf.currentScale, pdf.pagesRotation, pdf.scrollMode, pdf.spreadMode, this.mode].join(":");
    this.overflowHeight = Math.max(this.overflowKey === overflowKey ? this.overflowHeight || 0 : 0, needed);
    this.overflowKey = overflowKey;
    this.tail.style.height = `${Math.ceil(this.overflowHeight)}px`;
    this.positionFloating();
    const floatingRight = this.floating ? this.floating.card.offsetLeft + this.floating.card.offsetWidth + 10 : 0;
    this.tail.style.width = `${Math.ceil(Math.max(this.scroller.clientWidth, floatingRight, ...items.map((item) => item.x + item.card.offsetWidth + 10)))}px`;
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
    const left = Math.max(8, Math.min(geometry.left, this.scroller.clientWidth - width - 8));
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
      left: this.spreadRight(geometry.pageNumber) + 48,
      top: thread.section ? geometry.top-card.offsetHeight : Math.max(8, (geometry.top + geometry.bottom - card.offsetHeight) / 2) };
    card.style.left = `${position.left + this.scroller.scrollLeft}px`;
    card.style.top = `${position.top + this.scroller.scrollTop}px`;
  }
  positionComposer() {
    const box = this.composer.container;
    if (box.hidden) return;
    const geometry = anchorGeometry(this.application, this.composer.payload);
    if (!geometry) return;
    box.style.removeProperty("width");
    box.style.removeProperty("max-height");
    if (this.mode === "mobile") {
      const position = this.popupPosition(box, geometry);
      box.style.left = `${position.left}px`;
      box.style.top = `${position.top}px`;
    } else {
      box.style.left = `${this.spreadRight(geometry.pageNumber) + (this.mode === "minimized" ? 48 : 6)}px`;
      box.style.top = `${Math.max(8, (geometry.top + geometry.bottom - box.offsetHeight) / 2)}px`;
    }
  }
}
