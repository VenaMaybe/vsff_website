import {
  ANCHOR_SCHEMA_VERSION,
  CAPTURE_ERROR,
  TEXT_CONTEXT_LENGTH,
  TEXT_SELECTOR_VERSION,
} from "./anchor_constants.js";
import {
  clientRectToPdfRectangle,
  deduplicateRectangles,
} from "./anchor_geometry.js";

export class SelectionCaptureError extends Error {}

function fail() {
  throw new SelectionCaptureError(CAPTURE_ERROR);
}

function codePoints(value) {
  return Array.from(value);
}

function textLayerForNode(node) {
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  return element?.closest?.(".textLayer") || null;
}

function pageNumberForLayer(textLayer) {
  const value = Number(textLayer.closest(".page")?.dataset.pageNumber);
  return Number.isInteger(value) && value > 0 ? value : null;
}

function logicalPageText(document, textLayer) {
  const walker = document.createTreeWalker(textLayer, NodeFilter.SHOW_TEXT);
  let text = "";
  while (walker.nextNode()) {
    if (!walker.currentNode.parentElement?.closest(".pdf-review-anchor-overlay")) {
      text += walker.currentNode.data;
    }
  }
  return text;
}

function boundaryOffset(document, textLayer, container, offset) {
  if (!textLayer.contains(container)) {
    fail();
  }
  const prefixRange = document.createRange();
  prefixRange.setStart(textLayer, 0);
  prefixRange.setEnd(container, offset);
  return codePoints(prefixRange.toString()).length;
}

function normalizedRotation(rotation) {
  return ((rotation % 360) + 360) % 360;
}

export function captureTextSelection(viewerWindow, viewerApplication) {
  const document = viewerWindow.document;
  const selection = viewerWindow.getSelection();
  if (!selection || selection.rangeCount !== 1 || selection.isCollapsed) {
    fail();
  }
  const range = selection.getRangeAt(0);
  if (range.collapsed) {
    fail();
  }
  const startLayer = textLayerForNode(range.startContainer);
  const endLayer = textLayerForNode(range.endContainer);
  if (!startLayer || !endLayer) {
    fail();
  }
  const startPage = pageNumberForLayer(startLayer);
  const endPage = pageNumberForLayer(endLayer);
  if (!startPage || !endPage || endPage < startPage) {
    fail();
  }
  const overallText = selection.toString();
  if (!overallText.trim()) {
    fail();
  }

  const clientRectangles = Array.from(range.getClientRects()).filter(
    (rectangle) => rectangle.width > 0 && rectangle.height > 0
  );
  if (!clientRectangles.length) {
    fail();
  }

  const segments = [];
  for (let pageNumber = startPage; pageNumber <= endPage; pageNumber += 1) {
    const pageView = viewerApplication.pdfViewer.getPageView(pageNumber - 1);
    const textLayer = pageView?.textLayer?.div;
    const viewport = pageView?.viewport;
    if (!textLayer?.isConnected || !viewport || !range.intersectsNode(textLayer)) {
      fail();
    }
    const textLayerRect = textLayer.getBoundingClientRect();
    if (textLayerRect.width <= 0 || textLayerRect.height <= 0) {
      fail();
    }
    const pageText = logicalPageText(document, textLayer);
    const pageCodePoints = codePoints(pageText);
    const textStart = pageNumber === startPage
      ? boundaryOffset(document, textLayer, range.startContainer, range.startOffset)
      : 0;
    const textEnd = pageNumber === endPage
      ? boundaryOffset(document, textLayer, range.endContainer, range.endOffset)
      : pageCodePoints.length;
    if (textStart < 0 || textEnd <= textStart || textEnd > pageCodePoints.length) {
      fail();
    }
    const exactText = pageCodePoints.slice(textStart, textEnd).join("");
    if (!exactText.trim()) {
      fail();
    }
    const rectangles = deduplicateRectangles(
      clientRectangles
        .map((rectangle) => clientRectToPdfRectangle(rectangle, textLayerRect, viewport))
        .filter(Boolean)
    );
    if (!rectangles.length) {
      fail();
    }
    segments.push({
      segment_index: segments.length,
      page_number: pageNumber,
      rectangles,
      pdf_view_box: Array.from(viewport.viewBox, Number),
      capture_viewport: {
        width: viewport.width,
        height: viewport.height,
        rotation: normalizedRotation(viewport.rotation),
      },
      exact_text: exactText,
      prefix: pageCodePoints.slice(Math.max(0, textStart - TEXT_CONTEXT_LENGTH), textStart).join(""),
      suffix: pageCodePoints.slice(textEnd, textEnd + TEXT_CONTEXT_LENGTH).join(""),
      text_start: textStart,
      text_end: textEnd,
      page_text: pageText,
    });
  }

  if (!segments.length || segments[0].page_number !== startPage ||
      segments.at(-1).page_number !== endPage) {
    fail();
  }
  return {
    anchor_kind: "text",
    selection_text: overallText,
    selector_version: TEXT_SELECTOR_VERSION,
    anchor_schema_version: ANCHOR_SCHEMA_VERSION,
    page_count: viewerApplication.pdfDocument.numPages,
    segments,
  };
}
