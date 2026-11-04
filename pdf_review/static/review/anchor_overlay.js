import { pdfRectangleToCss, visibleHighlightRectangles } from "./anchor_geometry.js";

const STYLE_ID = "pdf-review-anchor-styles";
const STYLESHEET_URL = new URL("./anchor_overlay.css", import.meta.url).href;

function installStyles(document) {
  if (document.getElementById(STYLE_ID)) {
    return;
  }
  const stylesheet = document.createElement("link");
  stylesheet.id = STYLE_ID;
  stylesheet.rel = "stylesheet";
  stylesheet.href = STYLESHEET_URL;
  document.head.append(stylesheet);
}

export class AnchorOverlay {
  constructor(viewerWindow, viewerApplication) {
    this.window = viewerWindow;
    this.application = viewerApplication;
    this.anchors = [];
    this.threadStates = new Map();
    this.selectedThreadId = null;
    this.onThreadSelect = null;
    installStyles(viewerWindow.document);
    const renderEvent = ({ pageNumber }) => this.renderPage(pageNumber);
    viewerApplication.eventBus.on("textlayerrendered", renderEvent);
    viewerApplication.eventBus.on("pagerendered", renderEvent);
    viewerApplication.eventBus.on("scalechanging", () => this.scheduleRenderAll());
    viewerApplication.eventBus.on("rotationchanging", () => this.scheduleRenderAll());
    viewerApplication.eventBus.on("pagesinit", () => this.scheduleRenderAll());
    viewerApplication.eventBus.on('pdftouchended', () => this.scheduleRenderAll());
    viewerApplication.eventBus.on("updateviewarea", ({ location }) => {
      const pageNumber = location?.pageNumber;
      if (Number.isInteger(pageNumber)) {
        this.window.requestAnimationFrame(() => this.renderPage(pageNumber));
      }
    });
  }

  setAnchors(anchors) {
    this.anchors = anchors;
    this.scheduleRenderAll();
  }

  setThreadStates(states, selectedThreadId = null, onThreadSelect = null) {
    this.threadStates = new Map(states.map((state) => [state.anchorId, state]));
    this.selectedThreadId = selectedThreadId;
    this.onThreadSelect = onThreadSelect;
    this.scheduleRenderAll();
  }

  scheduleRenderAll() {
    if (this.renderScheduled) return;
    this.renderScheduled = true;
    this.window.requestAnimationFrame(() => {
      this.renderScheduled = false;
      this.renderAll();
    });
  }

  renderAll() {
    const pages = new Set(
      this.anchors.flatMap((anchor) => anchor.segments.map((segment) => segment.page_number))
    );
    this.window.document
      .querySelectorAll(".pdf-review-anchor-overlay")
      .forEach((element) => {
        const pageNumber = Number(element.closest(".page")?.dataset.pageNumber);
        if (!pages.has(pageNumber)) {
          if (this.application.reviewPdfTouchActive) element.hidden = true;
          else element.remove();
        }
      });
    pages.forEach((pageNumber) => this.renderPage(pageNumber));
  }

  renderPage(pageNumber) {
    if (!Number.isInteger(pageNumber) || pageNumber < 1) {
      return;
    }
    const pageView = this.application.pdfViewer.getPageView(pageNumber - 1);
    const pageDiv = pageView?.div;
    const viewport = pageView?.viewport;
    if (!pageDiv || !viewport) {
      return;
    }
    const segments = this.anchors.flatMap((anchor) =>
      anchor.segments.flatMap((segment, index) => segment.page_number === pageNumber
        ? [{ anchor, segment, index }] : [])
    );
    if (!segments.length) {
      const old = pageDiv.querySelector(":scope > .pdf-review-anchor-overlay");
      if (old && this.application.reviewPdfTouchActive) old.hidden = true;
      else old?.remove();
      return;
    }
    const pageBounds = {
      width: pageDiv.clientWidth,
      height: pageDiv.clientHeight,
    };
    if (!pageBounds.width || !pageBounds.height) {
      return;
    }
    const renderKey = JSON.stringify({
      rotation: viewport.rotation,
      rectangles: segments.map(({ anchor, segment }) => [
        anchor.anchor_id,
        segment.rectangles,
        this.threadStates.get(anchor.anchor_id)?.threadId ?? null,
        this.threadStates.get(anchor.anchor_id)?.status ?? null,
        this.threadStates.get(anchor.anchor_id)?.color ?? null,
        this.threadStates.get(anchor.anchor_id)?.threadId === this.selectedThreadId,
      ]),
    });
    const existingOverlay = pageDiv.querySelector(":scope > .pdf-review-anchor-overlay");
    if (existingOverlay?.dataset.renderKey === renderKey && !existingOverlay.hidden &&
        !existingOverlay.querySelector('[hidden]')) {
      return;
    }
    // Percentage geometry follows native page resizing immediately, even while
    // touches are down. Keep DOM targets; only reconcile their data and styles.
    const overlay = existingOverlay || this.window.document.createElement("div");
    overlay.className = "pdf-review-anchor-overlay";
    overlay.hidden = false;
    overlay.dataset.renderKey = renderKey;
    const existing = new Map([...overlay.children].map(node => [node.dataset.rectangleKey, node]));
    const wanted = new Set();
    for (const { anchor, segment, index } of segments) {
      for (const [rectangleIndex, rectangle] of visibleHighlightRectangles(segment.rectangles).entries()) {
        const geometry = pdfRectangleToCss(rectangle, viewport, pageBounds);
        if (!geometry || geometry.width <= 0 || geometry.height <= 0) continue;
        const key = `${anchor.anchor_id}:${index}:${rectangleIndex}`;
        wanted.add(key);
        let highlight = existing.get(key);
        if (!highlight) {
          highlight = this.window.document.createElement("div");
          highlight.className = "pdf-review-anchor-highlight";
          highlight.dataset.rectangleKey = key;
          highlight.addEventListener("click", event => {
            if (!highlight.dataset.threadId) return;
            event.preventDefault(); event.stopPropagation();
            const hits = event.detail ? this.window.document.elementsFromPoint(event.clientX,event.clientY) : [];
            const threads = [...new Set(hits.filter(node => node.classList?.contains('pdf-review-thread-highlight') &&
              node.closest('.pdf-review-anchor-overlay') === overlay).map(node => node.dataset.threadId))];
            const current = threads.indexOf(this.selectedThreadId);
            this.onThreadSelect?.(threads.length ? threads[(current+1)%threads.length] : highlight.dataset.threadId);
          });
          overlay.append(highlight);
        }
        highlight.hidden = false;
        highlight.dataset.anchorId = anchor.anchor_id;
        const state = this.threadStates.get(anchor.anchor_id);
        highlight.classList.toggle('pdf-review-thread-highlight', !!state);
        highlight.classList.toggle('is-active', !!state && state.threadId === this.selectedThreadId);
        highlight.classList.toggle('is-resolved', state?.status === 'resolved');
        if (state) {
          highlight.dataset.threadId = state.threadId;
          highlight.title = 'Open review thread; click again to cycle overlapping comments';
        } else {
          delete highlight.dataset.threadId;
          highlight.removeAttribute('title');
        }
        if (/^#[0-9a-f]{6}$/.test(state?.color)) highlight.style.setProperty('--review-color', state.color);
        else highlight.style.removeProperty('--review-color');
        highlight.style.left = `${geometry.left / pageBounds.width * 100}%`;
        highlight.style.top = `${geometry.top / pageBounds.height * 100}%`;
        highlight.style.width = `${geometry.width / pageBounds.width * 100}%`;
        highlight.style.height = `${geometry.height / pageBounds.height * 100}%`;
      }
    }
    for (const [key,node] of existing) if (!wanted.has(key)) {
      if (this.application.reviewPdfTouchActive) node.hidden = true;
      else node.remove();
    }
    if (!existingOverlay) pageDiv.append(overlay);
  }

  navigateTo(anchor) {
    const firstSegment = anchor.segments[0];
    const pageNumber = firstSegment?.page_number;
    const firstRectangle = firstSegment?.rectangles?.[0];
    if (pageNumber && firstRectangle) {
      const [left, , , top] = firstRectangle;
      this.application.pdfViewer.scrollPageIntoView({
        pageNumber,
        destArray: [null, { name: "XYZ" }, left, top, null],
        ignoreDestinationZoom: true,
        center: "vertical",
      });
      this.window.requestAnimationFrame(() => {
        this.renderPage(pageNumber);
        this.window.requestAnimationFrame(() => {
          const pageView = this.application.pdfViewer.getPageView(pageNumber - 1);
          const highlight = Array.from(
            pageView?.div?.querySelectorAll(".pdf-review-anchor-highlight") ?? []
          ).find((element) => element.dataset.anchorId === anchor.anchor_id);
          highlight?.scrollIntoView({ block: "center", inline: "nearest" });
        });
      });
    }
  }

  currentViewportDetails(pageNumber) {
    const pageView = this.application.pdfViewer.getPageView(pageNumber - 1);
    const viewport = pageView?.viewport;
    const textLayerRect = pageView?.textLayer?.div?.getBoundingClientRect();
    if (!viewport) {
      return null;
    }
    return {
      viewport_width: viewport.width,
      viewport_height: viewport.height,
      rotation: viewport.rotation,
      scale: viewport.scale,
      rendered_text_layer_width: textLayerRect?.width ?? null,
      rendered_text_layer_height: textLayerRect?.height ?? null,
    };
  }
}
