// Register before the iframe starts. PDF.js explicitly exposes this pre-run hook.
document.addEventListener("webviewerloaded", (event) => {
  const viewer = event.detail?.source;
  if (viewer !== document.getElementById("pdf-viewer-frame")?.contentWindow) return;
  viewer.PDFViewerApplicationOptions.setAll({
    // Stored native editor preferences must not re-enable a second annotation model.
    disablePreferences: true,
    annotationEditorMode: -1,
    enableComment: false,
    enableSignatureEditor: false,
    enableHighlightFloatingButton: false,
    enableUpdatedAddImage: false,
  });
  const sheet = viewer.document.createElement("link");
  sheet.rel = "stylesheet";
  // Use the script URL rather than assuming an application mount prefix.
  sheet.href = new URL("../styles/pdfjs.css", bootstrapSource).href;
  viewer.document.head.append(sheet);
});
const bootstrapSource = document.currentScript.src;
