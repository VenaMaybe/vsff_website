// Register before the iframe starts. PDF.js explicitly exposes this pre-run hook.
document.addEventListener("webviewerloaded", (event) => {
  const viewer = event.detail?.source;
  if (viewer !== document.getElementById("pdf-viewer-frame")?.contentWindow) return;
  viewer.document.documentElement.dataset.uiTheme=document.documentElement.dataset.uiTheme;
  viewer.document.documentElement.dataset.pdfTheme=document.documentElement.dataset.pdfTheme;
  syncPdfColors(viewer.document.documentElement);
  viewer.PDFViewerApplicationOptions.setAll({
    viewerCssTheme: document.documentElement.dataset.uiTheme==='dark'?2:1,
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

function syncPdfColors(root=document.getElementById('pdf-viewer-frame')?.contentDocument?.documentElement){
  const source=document.documentElement;
  if(root){
    for(const key of ['pdfTheme','pdfColorAmount','pdfWhitePoint'])root.dataset[key]=source.dataset[key];
    root.style.setProperty('--pdf-grayscale',String(1-Number(source.dataset.pdfColorAmount)/100));
    // invert(.9) maps original black to .9. This multiplier sets its exact
    // grayscale white point while retaining a small dark-paper floor.
    root.style.setProperty('--pdf-dark-brightness',String(Number(source.dataset.pdfWhitePoint)/90));
  }
  const colors=document.getElementById('review-pdf-colors');
  if(colors)colors.hidden=source.dataset.pdfTheme!=='dark';
}

document.addEventListener('DOMContentLoaded',()=>{
  for(const kind of ['pdf','ui']){
    const button=document.getElementById(`review-${kind}-dark`),key=`${kind}Theme`;
    button?.addEventListener('click',()=>{
      const mode=document.documentElement.dataset[key]==='dark'?'light':'dark';
      document.documentElement.dataset[key]=mode;
      const root=document.getElementById('pdf-viewer-frame')?.contentDocument?.documentElement;
      if(root){root.dataset[key]=mode;if(kind==='ui')root.style.colorScheme=mode;}
      if(kind==='pdf')syncPdfColors(root);
      button.setAttribute('aria-checked',String(mode==='dark'));
    });
  }
  for(const [id,key] of [['review-pdf-color','pdfColorAmount'],['review-pdf-white-point','pdfWhitePoint']]){
    document.getElementById(id)?.addEventListener('input',event=>{
      document.documentElement.dataset[key]=event.target.value;
      document.querySelector(`#review-pdf-colors output[for="${id}"]`).textContent=`${event.target.value}%`;syncPdfColors();
    });
  }
});

function blockRestrictedShortcut(event) {
  if(document.body?.dataset.downloadsAllowed!=='false')return;
  if((event.ctrlKey||event.metaKey)&&['s','p'].includes(event.key.toLowerCase())){
    event.preventDefault();event.stopImmediatePropagation();
  }
}
document.addEventListener('keydown',blockRestrictedShortcut,true);
const originalPrint=window.print;
window.print=function(...args){if(document.body?.dataset.downloadsAllowed!=='false')return originalPrint.apply(this,args);};
