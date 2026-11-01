import { pdfRectangleToCss } from "./anchor_geometry.js";

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
    this.window.requestAnimationFrame(() => this.renderAll());
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
          element.remove();
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
      anchor.segments
        .filter((segment) => segment.page_number === pageNumber)
        .map((segment) => ({ anchor, segment }))
    );
    if (!segments.length) {
      pageDiv.querySelector(":scope > .pdf-review-anchor-overlay")?.remove();
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
      width: pageBounds.width,
      height: pageBounds.height,
      rotation: viewport.rotation,
      rectangles: segments.map(({ anchor, segment }) => [
        anchor.anchor_id,
        segment.rectangles,
        this.threadStates.get(anchor.anchor_id)?.status ?? null,
        this.threadStates.get(anchor.anchor_id)?.threadId === this.selectedThreadId,
      ]),
    });
    const existingOverlay = pageDiv.querySelector(":scope > .pdf-review-anchor-overlay");
    if (existingOverlay?.dataset.renderKey === renderKey) {
      return;
    }
    const overlay = this.window.document.createElement("div");
    overlay.className = "pdf-review-anchor-overlay";
    overlay.dataset.renderKey = renderKey;
    for (const { anchor, segment } of segments) {
      for (const rectangle of segment.rectangles) {
        const geometry = pdfRectangleToCss(rectangle, viewport, pageBounds);
        if (!geometry || geometry.width <= 0 || geometry.height <= 0) {
          continue;
        }
        const highlight = this.window.document.createElement("div");
        highlight.className = "pdf-review-anchor-highlight";
        highlight.dataset.anchorId = anchor.anchor_id;
        const threadState = this.threadStates.get(anchor.anchor_id);
        if (threadState) {
          highlight.dataset.threadId = threadState.threadId;
          highlight.classList.add("pdf-review-thread-highlight");
          highlight.classList.toggle("is-active", threadState.threadId === this.selectedThreadId);
          highlight.classList.toggle("is-resolved", threadState.status === "resolved");
          highlight.title = "Open review thread";
          highlight.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            this.onThreadSelect?.(threadState.threadId);
          });
        }
        highlight.style.left = `${geometry.left}px`;
        highlight.style.top = `${geometry.top}px`;
        highlight.style.width = `${geometry.width}px`;
        highlight.style.height = `${geometry.height}px`;
        overlay.append(highlight);
      }
    }
    if (overlay.childElementCount) {
      if (existingOverlay) {
        existingOverlay.replaceWith(overlay);
      } else {
        pageDiv.append(overlay);
      }
    }
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
