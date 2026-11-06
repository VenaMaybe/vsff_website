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
    // Canonical rectangle arrays are immutable; normalize once per fetched array,
    // rather than repeating line grouping on every zoom or focus update.
    this.rectangleCache = new WeakMap();
    this.selectedThreadId = null;
    this.onThreadSelect = null;
    installStyles(viewerWindow.document);
    this.hitRegions = new WeakMap();
    this.installInteraction();
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

  installInteraction() {
    const document = this.window.document;
    const cancelCursorDelay = () => this.window.clearTimeout(this.cursorDelay);
    document.addEventListener("pointerdown", event => {
      cancelCursorDelay();
      this.hoverPoint = null;
      const highlight = event.button === 0 && event.pointerType !== "touch" ? this.highlightsAt(event)[0] : null;
      if (highlight) this.hoverPoint = { target: event.target, clientX: event.clientX, clientY: event.clientY };
      this.setHoveredHighlight(highlight ?? null);
      // Cursor cosmetics only: native selection still starts on pointer-down.
      // A quick click retains the hand; a hold or actual drag reveals the I-beam.
      if (highlight) this.cursorDelay = this.window.setTimeout(() => {
        this.hoverPoint = null;
        this.setHoveredHighlight(null);
      }, 200);
      if (event.isPrimary === false) {
        if (this.pointerGesture) this.pointerGesture.cancelled = true;
        return;
      }
      const scroller = this.application.pdfViewer.container;
      this.pointerGesture = event.button === 0 ? {
        id: event.pointerId, x: event.clientX, y: event.clientY, moved: false,
        tolerance: event.pointerType === "touch" ? 8 : 4,
        left: scroller.scrollLeft, top: scroller.scrollTop,
      } : null;
    }, true);
    document.addEventListener("pointermove", event => {
      const gesture = this.pointerGesture;
      if (gesture && event.pointerId === gesture.id &&
          Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y) > gesture.tolerance) {
        gesture.moved = true;
        cancelCursorDelay();
        this.hoverPoint = null;
        this.setHoveredHighlight(null);
      }
      // Selection and panning remain wholly native. Only idle hover needs a read.
      if (event.buttons || event.pointerType === "touch") return;
      this.hoverPoint = { target: event.target, clientX: event.clientX, clientY: event.clientY };
      if (this.hoverScheduled) return;
      this.hoverScheduled = true;
      this.window.requestAnimationFrame(() => {
        this.hoverScheduled = false;
        this.setHoveredHighlight(this.highlightsAt(this.hoverPoint)[0] ?? null);
      });
    }, { capture: true, passive: true });
    document.addEventListener("pointerup", () => {
      cancelCursorDelay();
      if (!this.window.getSelection()?.isCollapsed) {
        this.hoverPoint = null;
        this.setHoveredHighlight(null);
      }
    }, true);
    document.addEventListener("pointercancel", () => {
      cancelCursorDelay();
      if (this.pointerGesture) this.pointerGesture.cancelled = true;
      this.hoverPoint = null;
      this.setHoveredHighlight(null);
    }, true);
    document.addEventListener("click", event => {
      // Retain direct programmatic activation used by diagnostics/accessibility.
      const direct = !event.detail && event.target.closest?.(".pdf-review-thread-highlight");
      if (direct) {
        event.preventDefault(); event.stopPropagation();
        this.onThreadSelect?.(direct.dataset.threadId);
        return;
      }
      const gesture = this.pointerGesture;
      this.pointerGesture = null;
      const scroller = this.application.pdfViewer.container;
      if (event.defaultPrevented || event.button !== 0 || event.detail !== 1 ||
          event.ctrlKey || event.metaKey || event.altKey || event.shiftKey ||
          !gesture || gesture.moved || gesture.cancelled ||
          Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y) > gesture.tolerance ||
          scroller.scrollLeft !== gesture.left || scroller.scrollTop !== gesture.top ||
          !this.window.getSelection()?.isCollapsed) return;
      const highlights = this.highlightsAt(event);
      const threads = [...new Set(highlights.map(node => node.dataset.threadId))];
      if (!threads.length) return;
      if (event.pointerType !== "touch") {
        this.hoverPoint = { target: event.target, clientX: event.clientX, clientY: event.clientY };
        this.setHoveredHighlight(highlights[0]);
      }
      event.preventDefault(); event.stopPropagation();
      const current = threads.indexOf(this.selectedThreadId);
      this.onThreadSelect?.(threads[(current + 1) % threads.length]);
    }, true);
    const clearHover = () => { cancelCursorDelay(); this.hoverPoint = null; this.setHoveredHighlight(null); };
    document.addEventListener("scroll", clearHover, { capture: true, passive: true });
    document.addEventListener("pointerleave", clearHover);
    this.window.addEventListener("blur", clearHover);
    this.application.eventBus.on("cursortoolchanged", clearHover);
  }

  highlightsAt(point) {
    if (this.window.document.documentElement.classList.contains("review-comments-hidden") ||
        !point?.target?.isConnected || point.target.closest?.(
      "a, button, input, textarea, select, [contenteditable=true], .annotationLayer, .annotationEditorLayer, .section-management-line"
    )) return [];
    const page = point.target.closest?.(".page");
    const overlay = page?.querySelector(":scope > .pdf-review-anchor-overlay");
    const regions = overlay && !overlay.hidden && this.hitRegions.get(overlay);
    if (!regions?.length) return [];
    // One layout read for this page, using the same percentages as the paint.
    // This follows native zoom immediately without measuring every rectangle.
    const bounds = overlay.getBoundingClientRect();
    const x = (point.clientX - bounds.left) / bounds.width;
    const y = (point.clientY - bounds.top) / bounds.height;
    return regions.filter(region => !region.node.hidden && region.node.dataset.threadId &&
      x >= region.left && x <= region.right && y >= region.top && y <= region.bottom)
      .map(region => region.node);
  }

  setHoveredHighlight(highlight) {
    // Put the cursor on the actual hit-tested text element, not the transparent
    // highlight. A short hold or drag clears it without delaying native selection.
    const cursorTarget = highlight ? this.hoverPoint?.target : null;
    if (cursorTarget !== this.hoverCursorTarget) {
      this.hoverCursorTarget?.classList.remove("review-highlight-cursor");
      this.hoverCursorTarget = cursorTarget;
      cursorTarget?.classList.add("review-highlight-cursor");
    }
    if (highlight === this.hoveredHighlight) return;
    this.hoveredHighlight?.classList.remove("is-hovered");
    this.hoveredHighlight = highlight;
    highlight?.classList.add("is-hovered");
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
    const regions = new Map();
    for (const { anchor, segment, index } of segments) {
      let rectangles = this.rectangleCache.get(segment.rectangles);
      if (!rectangles) {
        rectangles = visibleHighlightRectangles(segment.rectangles, pageView.pdfPage?.rotate ?? 0);
        this.rectangleCache.set(segment.rectangles, rectangles);
      }
      for (const [rectangleIndex, rectangle] of rectangles.entries()) {
        const geometry = pdfRectangleToCss(rectangle, viewport, pageBounds);
        if (!geometry || geometry.width <= 0 || geometry.height <= 0) continue;
        const key = `${anchor.anchor_id}:${index}:${rectangleIndex}`;
        wanted.add(key);
        let highlight = existing.get(key);
        if (!highlight) {
          highlight = this.window.document.createElement("div");
          highlight.className = "pdf-review-anchor-highlight";
          highlight.dataset.rectangleKey = key;
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
        regions.set(highlight, { node: highlight,
          left: geometry.left / pageBounds.width, right: (geometry.left + geometry.width) / pageBounds.width,
          top: geometry.top / pageBounds.height, bottom: (geometry.top + geometry.height) / pageBounds.height });
      }
    }
    // Reverse DOM paint order preserves the former topmost-first click cycle.
    this.hitRegions.set(overlay, [...overlay.children].reverse().flatMap(node => regions.has(node) ? [regions.get(node)] : []));
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
