// Card content keeps its normal layout, shrinking uniformly with PDF zoom below 100%.
// Positions remain in screen CSS pixels, shared with PDF.js and documentStage.
export function cardScale(application) {
  const scale = application.pdfViewer.currentScale;
  return Number.isFinite(scale) && scale > 0 ? Math.min(1, scale) : 1;
}
export function cardSize(node, application) {
  // The mobile keyboard composer is a viewport control, outside the document rail.
  const scale = node.classList.contains('viewport-composer') ? 1 : cardScale(application);
  return { width: node.offsetWidth * scale, height: node.offsetHeight * scale };
}
