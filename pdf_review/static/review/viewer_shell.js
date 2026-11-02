import { bindMenuDismissal, syncMenuValues } from "./menus.js";
import { pdfRectangleToCss } from "./anchor_geometry.js";

function installSearch(frame, application) {
  const doc = frame.contentDocument;
  const find = application.findBar;
  const row = doc.createElement("div");
  row.className = "review-find-row";
  const options = doc.createElement("details");
  options.className = "review-find-options";
  const summary = doc.createElement("summary");
  summary.textContent = "Options";
  options.append(summary);
  for (const id of ["findbarOptionsOneContainer", "findbarOptionsTwoContainer"]) options.append(doc.getElementById(id));
  const close = doc.createElement("button");
  close.type = "button";
  close.className = "review-find-close";
  close.setAttribute("aria-label", "Close document search");
  close.title = "Close document search (Escape)";
  close.textContent = "\u00d7";
  close.addEventListener("click", () => { find.close(); document.querySelector('[data-pdf-control="viewFindButton"]').focus(); });
  find.findField.placeholder = "Search document\u2026";
  find.findField.setAttribute("aria-label", "Search document");
  row.append(find.findField, find.findResultsCount, find.findPreviousButton, find.findNextButton, close);
  find.bar.replaceChildren(row, options, find.findMsg);
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
  new ResizeObserver(() => document.documentElement.style.setProperty("--toolbar-height", `${header.offsetHeight}px`)).observe(header);
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
    this.mode = "expanded";
    this.scheduled = false;
    this.observed = new Set();
    this.observer = new ResizeObserver(() => this.schedule());
    this.scroller.addEventListener("scroll", () => { this.translate(); this.selectionLayout(); }, { passive: true });
    // The cards live in the parent overlay, but wheel scrolling belongs to the
    // same document surface as the PDF beneath them.
    this.panel.addEventListener("wheel", (event) => {
      if (event.ctrlKey || event.target.closest("textarea, .migration-panel, .anchor-debug-section")) return;
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? this.scroller.clientHeight : 1;
      this.scroller.scrollBy(event.deltaX * unit, event.deltaY * unit);
      event.preventDefault();
    }, { passive: false });
    new ResizeObserver(() => this.schedule()).observe(document.querySelector(".viewer-workspace"));
    new ResizeObserver(() => this.schedule()).observe(this.scroller);
    application.eventBus.on("updateviewarea", () => {
      // Scrolling alone changes no content-space geometry. Check one current page.
      const page = application.pdfViewer.getPageView(application.pdfViewer.currentPageNumber - 1)?.div?.getBoundingClientRect();
      const signature = page && [Math.round(page.left + this.scroller.scrollLeft), Math.round(page.width), Math.round(page.height), application.pdfViewer.spreadMode].join(":");
      if (signature !== this.geometrySignature) { this.geometrySignature = signature; this.schedule(); }
    });
    for (const event of ["scalechanging", "rotationchanging", "pagerendered", "textlayerrendered", "scrollmodechanged", "spreadmodechanged", "pagesinit"]) application.eventBus.on(event, () => this.schedule());
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
    if (this.scheduled) return;
    this.scheduled = true;
    requestAnimationFrame(() => { this.scheduled = false; this.layout(); });
  }
  translate() {
    this.list.style.transform = `translate(${-this.scroller.scrollLeft}px, ${-this.scroller.scrollTop}px)`;
    this.positionComposer();
  }
  showThread(threadId) {
    if (this.mode === "hidden") {
      this.mode = "expanded";
      this.visibility.value = "expanded";
      this.frame.contentDocument.documentElement.classList.remove("review-comments-hidden");
      syncMenuValues();
    }
    this.schedule();
    // Overlay navigation centers the PDF destination over two frames. Reveal the
    // card afterwards when dense collisions displaced it beyond that viewport.
    requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(() => {
      const card = [...this.list.querySelectorAll(".thread-card")].find((item) => item.dataset.threadId === threadId);
      if (!card) return;
      const bounds = card.getBoundingClientRect();
      const workspace = this.panel.getBoundingClientRect();
      if (bounds.top < workspace.top + 36 || bounds.top > workspace.bottom - 60) this.scroller.scrollTop += bounds.top - workspace.top - 44;
      const right = workspace.left + this.scroller.clientWidth - 8;
      if (bounds.right > right) this.scroller.scrollLeft += bounds.right - right;
      else if (bounds.left < workspace.left + 8) this.scroller.scrollLeft += bounds.left - workspace.left - 8;
    })));
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
    const minimized = this.mode === "minimized";
    const styles = getComputedStyle(document.documentElement);
    const cardWidth = parseFloat(styles.getPropertyValue("--comment-width"));
    const railWidth = minimized ? parseFloat(styles.getPropertyValue("--comment-marker-width")) : cardWidth + 20;
    // Comments remain beside their page/spread at every viewport and zoom. When
    // the pair is wider than the viewport, the native scrollbar reaches both.
    const reserve = ((cards.length && visible) || composing) ? (composing ? cardWidth + 20 : railWidth) : 0;
    const root = this.frame.contentDocument.documentElement;
    const oldReserve = root.style.getPropertyValue("--review-rail-right");
    root.style.setProperty("--review-rail-right", `${reserve}px`);
    const pages = Array.from({ length: this.application.pdfDocument.numPages }, (_, i) => pdf.getPageView(i));
    const stageWidth = Math.max(...pages.map((view) => (view?.viewport?.width || 0) + 18)) * (pdf.spreadMode ? 2 : 1) + 7;
    root.style.setProperty("--review-stage-width", reserve ? `${stageWidth}px` : "0px");
    this.list.hidden = !visible;
    this.list.dataset.layout = "right-rail";
    const items = [];
    const markers = new Map([...this.list.querySelectorAll(".thread-marker")].map((item) => [item.dataset.threadId, item]));
    for (const card of cards) {
      const thread = this.state.thread(card.dataset.threadId);
      const geometry = anchorGeometry(this.application, thread?.targets[0]?.anchor);
      const marker = markers.get(thread.thread_id);
      const isMarker = minimized && thread.thread_id !== this.state.selectedThreadId;
      marker.hidden = !isMarker;
      card.hidden = isMarker;
      const item = isMarker ? marker : card;
      card.setAttribute("aria-label", `Review thread, page ${geometry?.pageNumber || "unknown"}`);
      if (!this.observed.has(item)) { this.observer.observe(item); this.observed.add(item); }
      if (!geometry) { item.hidden = true; continue; }
      const railLeft = this.spreadRight(geometry.pageNumber) + 6;
      const x = railLeft + this.scroller.scrollLeft - (minimized && !isMarker ? cardWidth - 34 : 0);
      items.push({ card: item, page: geometry.pageNumber, y: geometry.top + this.scroller.scrollTop,
        x, height: item.offsetHeight });
    }
    items.sort((a, b) => a.page - b.page || a.y - b.y || a.card.dataset.threadId.localeCompare(b.card.dataset.threadId));
    let bottom = 8;
    const gap = minimized ? 3 : 6;
    const composerGeometry = composing && anchorGeometry(this.application, this.composer.payload);
    const composerTop = composerGeometry ? composerGeometry.top + this.scroller.scrollTop : -Infinity;
    const composerBottom = composerTop + this.composer.container.offsetHeight + 6;
    for (const item of items) {
      let top = Math.max(item.y, bottom);
      if (composing && top + item.height > composerTop && top < composerBottom) top = composerBottom;
      item.card.style.left = `${item.x}px`;
      item.card.style.top = `${top}px`;
      bottom = top + item.height + gap;
    }
    // Make collision overflow reachable using the PDF's primary scrollbar.
    if (!this.tail) { this.tail = this.frame.contentDocument.createElement("div"); this.tail.className = "review-rail-tail"; this.scroller.append(this.tail); }
    const viewer = this.application.pdfViewer.viewer;
    const needed = !visible ? 0 : Math.max(0, bottom - viewer.offsetHeight);
    this.tail.style.height = `${Math.ceil(needed)}px`;
    this.tail.style.width = `${Math.ceil(Math.max(this.scroller.clientWidth, ...items.map((item) => item.x + item.card.offsetWidth + 10)))}px`;
    // Parent-owned cards must never cover the iframe's native scrollbars.
    this.panel.style.clipPath = `inset(0 ${this.scroller.offsetWidth - this.scroller.clientWidth}px ${this.scroller.offsetHeight - this.scroller.clientHeight}px 0)`;
    this.translate();
    this.selectionLayout();
    if (oldReserve !== `${reserve}px`) { this.application.eventBus.dispatch("resize", { source: this }); this.schedule(); }
  }
  spreadRight(pageNumber) {
    const page = this.application.pdfViewer.getPageView(pageNumber - 1).div;
    const pdf = this.application.pdfViewer;
    const siblings = pdf.scrollMode === 1 ? pdf.viewer.querySelectorAll(".page, .dummyPage")
      : page.closest(".spread")?.querySelectorAll(".page, .dummyPage") || [page];
    return Math.max(...[...siblings].map((item) => item.getBoundingClientRect().right));
  }
  positionComposer() {
    const box = this.composer.container;
    if (box.hidden) return;
    const geometry = anchorGeometry(this.application, this.composer.payload);
    if (!geometry) { box.style.removeProperty("left"); box.style.removeProperty("top"); return; }
    box.style.left = `${this.spreadRight(geometry.pageNumber) + 6}px`;
    box.style.top = `${geometry.top}px`;
  }
}
