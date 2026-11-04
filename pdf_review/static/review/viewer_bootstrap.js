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
  // Wrap before PDF.js binds its event bus so native actions share the policy.
  const application=viewer.PDFViewerApplication;
  const allowed=()=>document.body.dataset.downloadsAllowed!=='false';
  const guard=(target,name)=>{
    const original=target?.[name];
    if(typeof original==='function')target[name]=function(...args){if(allowed())return original.apply(this,args);};
  };
  for(const name of ['download','save','downloadOrSave','triggerPrinting','beforePrint'])guard(application,name);
  guard(viewer,'print');
  viewer.document.addEventListener('keydown',blockRestrictedShortcut,true);
  viewer.reviewSetDownloadsAllowed=value=>{
    document.body.dataset.downloadsAllowed=String(value);
    viewer.document.documentElement.dataset.downloadsAllowed=String(value);
    for(const button of document.querySelectorAll('[data-pdf-control="printButton"],[data-pdf-control="downloadButton"]')){
      button.hidden=!value;button.disabled=!value;
    }
    if(!value&&application.printService)application.afterPrint();
  };
  viewer.reviewSetDownloadsAllowed(allowed());
  application.initializedPromise.then(()=>{
    // Also cover attachment exports and callers that bypass the toolbar.
    for(const name of ['download','downloadData','openOrDownloadData','_triggerDownload'])guard(application.downloadManager,name);
  });
  const sheet = viewer.document.createElement("link");
  sheet.rel = "stylesheet";
  // Use the script URL rather than assuming an application mount prefix.
  sheet.href = new URL("../styles/pdfjs.css", bootstrapSource).href;
  viewer.document.head.append(sheet);
});
const bootstrapSource = document.currentScript.src;

function blockRestrictedShortcut(event) {
  if(document.body?.dataset.downloadsAllowed!=='false')return;
  if((event.ctrlKey||event.metaKey)&&['s','p'].includes(event.key.toLowerCase())){
    event.preventDefault();event.stopImmediatePropagation();
  }
}
document.addEventListener('keydown',blockRestrictedShortcut,true);
const originalPrint=window.print;
window.print=function(...args){if(document.body?.dataset.downloadsAllowed!=='false')return originalPrint.apply(this,args);};
