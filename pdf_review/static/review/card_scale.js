// Card content keeps its normal layout, shrinking uniformly below the preferred zoom.
// Positions remain in screen CSS pixels, shared with PDF.js and documentStage.
export function cardScale(application) {
  const scale = application.pdfViewer.currentScale;
  const threshold = application.reviewCardZoomThreshold || 100;
  return Number.isFinite(scale) && scale > 0 ? Math.min(1, scale * 100 / threshold) : 1;
}
export function cardSize(node, application) {
  // The mobile keyboard composer is a viewport control, outside the document rail.
  const scale = node.classList.contains('viewport-composer') ? 1 : cardScale(application);
  return { width: node.offsetWidth * scale, height: node.offsetHeight * scale };
}
