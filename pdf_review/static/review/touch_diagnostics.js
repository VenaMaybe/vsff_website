// Explicit, bounded, in-memory diagnostics. Nothing is uploaded or persisted.
export function installTouchDiagnostics(frame, application, { controls = false, autoStart = true } = {}) {
  application.reviewTouchDiagnostics?.stop();
  const entries = [], pdf = application.pdfViewer, scroller = pdf.container;
  const controllers = [], listeners = [];
  let recording = false, started = 0, ended = null, limitTimer, raf, lastFrame, lastGeometry = 0;
  let activeUntil = 0, contacts = [], panel, status, startButton, stopButton, downloadButton, shareButton;
  let exportUrl, exportTimer, reason = '', stylesheet;
  const describe = node => node?.nodeType === 1 ? {
    tag:node.tagName, id:node.id, classes:String(node.className?.baseVal ?? node.className),
    thread:node.closest?.('[data-thread-id]')?.dataset.threadId, connected:node.isConnected,
  } : null;
  const updateControls = () => {
    if (!panel) return;
    status.textContent = recording ? 'Recording — reproduce the glitch, then tap Stop.'
      : entries.length ? `${entries.length} events saved in this tab. ${reason} Download before reloading.`
      : 'Go to the problem page, then tap Start recording.';
    startButton.disabled = recording;
    startButton.textContent = entries.length ? 'Record again' : 'Start recording';
    stopButton.disabled = !recording;
    downloadButton.disabled = shareButton.disabled = recording || !entries.length;
  };
  const pause = (why = '') => {
    recording = false; ended = performance.now(); reason = why;
    clearTimeout(limitTimer); cancelAnimationFrame(raf); raf = null;
    updateControls();
  };
  const record = (type, data = {}) => {
    if (!recording) return;
    const viewport = window.visualViewport;
    entries.push({ time:performance.now(), type, scale:pdf.currentScale,
      page:pdf.currentPageNumber, scroll:[scroller.scrollLeft,scroller.scrollTop],
      origin:[application.reviewStage?.origin,application.reviewStage?.originY],
      touching:!!application.reviewPdfTouchActive, pinching:!!application.reviewPdfPinching,
      viewport:viewport && {scale:viewport.scale,x:viewport.offsetLeft,y:viewport.offsetTop}, ...data });
    if (entries.length >= 6000) pause('Event limit reached.');
  };
  // At most four pages, never a document-wide scan. Geometry is sampled at 20Hz;
  // frame intervals still expose stalls. No layout reads in touchmove handlers.
  const geometry = () => {
    const ids = new Set([pdf.currentPageNumber-1,pdf.currentPageNumber,pdf.currentPageNumber+1]);
    const midpoint = contacts.length > 1 ? {x:(contacts[0].x+contacts[1].x)/2,y:(contacts[0].y+contacts[1].y)/2} : null;
    if (midpoint) {
      const page = frame.contentDocument.elementFromPoint(midpoint.x,midpoint.y)?.closest('.page');
      if (page) ids.add(Number(page.dataset.pageNumber));
    }
    return {midpoint, contacts:[...contacts], frame:frame.getBoundingClientRect().toJSON(),
      extent:[scroller.clientWidth,scroller.clientHeight,scroller.scrollWidth,scroller.scrollHeight],
      pages:[...ids].filter(id=>id>0&&id<=pdf.pagesCount).map(id=>{
        const view=pdf.getPageView(id-1),div=view.div,box=div.getBoundingClientRect();
        const point=midpoint&&view.viewport.convertToPdfPoint(
          (midpoint.x-box.left-div.clientLeft)*view.viewport.width/div.clientWidth,
          (midpoint.y-box.top-div.clientTop)*view.viewport.height/div.clientHeight);
        return {page:id,box:box.toJSON(),pdfPoint:point,rendering:view.renderingState,
          detailRendering:view.detailView?.renderingState,loading:div.classList.contains('loading')};
      })};
  };
  const tick = now => {
    raf=null;
    if (!recording) return;
    record('frame',{interval:lastFrame==null?null:now-lastFrame}); lastFrame=now;
    if (now-lastGeometry>=50) {lastGeometry=now;record('geometry',geometry());}
    if (recording&&(application.reviewPdfTouchActive||now<activeUntil)) raf=requestAnimationFrame(tick);
    else lastFrame=null;
  };
  const wake = () => {
    if (!recording) return;
    activeUntil=performance.now()+350;
    if (raf==null) raf=requestAnimationFrame(tick);
  };
  const start = () => {
    if (recording) return;
    entries.length=0;contacts=[];lastFrame=null;lastGeometry=0;
    started=performance.now();ended=null;reason='';recording=true;
    record('recording-start');wake();
    limitTimer=setTimeout(()=>pause('Two-minute limit reached.'),120000);updateControls();
  };
  for (const [name,doc] of [['parent',document],['pdf',frame.contentDocument]]) {
    const controller=new doc.defaultView.AbortController();controllers.push(controller);
    const listen=(type,listener)=>doc.addEventListener(type,listener,{capture:true,passive:true,signal:controller.signal});
    for (const type of ['pointerdown','pointerup','pointercancel','click','touchstart','touchend','touchcancel']) {
      listen(type,event=>{
        if (!recording||panel?.contains(event.target)) return;
        if (name==='pdf'&&event.touches) contacts=[...event.touches].map(t=>({id:t.identifier,x:t.clientX,y:t.clientY}));
        const point=event.changedTouches?.[0]||event;
        const hit=Number.isFinite(point.clientX)&&Number.isFinite(point.clientY)?doc.elementFromPoint(point.clientX,point.clientY):null;
        const target=hit?.closest('.thread-marker, .thread-card, .page');
        const style=target&&doc.defaultView.getComputedStyle(target);
        record(type,{document:name,x:point.clientX,y:point.clientY,target:describe(event.target),hit:describe(hit),
          prevented:event.defaultPrevented,pointer:event.pointerType,contacts:[...contacts],box:target?.getBoundingClientRect().toJSON(),
          css:style&&{pointerEvents:style.pointerEvents,scale:style.scale,transform:style.transform},
          listTransform:getComputedStyle(document.getElementById('thread-list')).transform,
          clip:getComputedStyle(document.querySelector('.review-panel')).clipPath});wake();
      });
    }
    listen('touchmove',event=>{
      if (!recording||panel?.contains(event.target)) return;
      const points=[...event.touches].map(t=>({id:t.identifier,x:t.clientX,y:t.clientY}));
      if (name==='pdf') contacts=points;
      record('touchmove',{document:name,contacts:points,prevented:event.defaultPrevented});wake();
    });
    listen('scroll',event=>{if(event.target===scroller){record('scroll');wake();}});
    listen('visibilitychange',()=>{
      if(recording&&doc.hidden){record('recording-hidden');pause('Recording stopped when the page was hidden.');}
    });
  }
  for (const type of ['scalechanging','pdftouchended','reviewlayoutchanged','pagerender','pagerendered','zoomscrollreconciled']) {
    const listener=event=>{record(type,{page:event.pageNumber??pdf.currentPageNumber,detail:event.isDetailView,
      observed:event.observed,intended:event.intended});wake();};
    application.eventBus.on(type,listener);listeners.push([type,listener]);
  }
  const snapshot=()=>({format:'pdf-review-touch-v2',revision:'pinch-camera-1',createdAt:new Date().toISOString(),browser:navigator.userAgent,
    devicePixelRatio:window.devicePixelRatio,pages:pdf.pagesCount,started,ended,reason,geometrySampleMs:50,entries:[...entries]});
  const file=()=>new File([JSON.stringify(snapshot())],'pdf-review-touch-trace.json',{type:'application/json'});
  const download=()=>{
    const blob=file();clearTimeout(exportTimer);if(exportUrl)URL.revokeObjectURL(exportUrl);
    exportUrl=URL.createObjectURL(blob);
    const link=document.createElement('a');link.href=exportUrl;link.download=blob.name;
    document.body.append(link);link.click();link.remove();
    exportTimer=setTimeout(()=>{URL.revokeObjectURL(exportUrl);exportUrl=null;},60000);
  };
  if(controls){
    stylesheet=document.createElement('link');stylesheet.rel='stylesheet';
    stylesheet.href=new URL('./touch_diagnostics.css',import.meta.url).href;document.head.append(stylesheet);
    panel=document.createElement('section');panel.id='touch-diagnostics';panel.setAttribute('aria-label','Zoom diagnostics');
    const title=document.createElement('strong');title.textContent='Zoom diagnostics';
    status=document.createElement('p');status.setAttribute('role','status');
    const actions=document.createElement('div');actions.className='touch-diagnostics-actions';
    const button=(text,action)=>{const node=document.createElement('button');node.type='button';node.textContent=text;
      node.addEventListener('click',action);actions.append(node);return node;};
    startButton=button('Start recording',()=>{
      if(entries.length&&!window.confirm('Replace the previous recording? Download it first if you want to keep it.'))return;
      start();
    });
    stopButton=button('Stop',()=>{record('recording-stop');pause();});
    downloadButton=button('Download trace',download);
    shareButton=button('Share trace',async()=>{
      const attachment=file();
      if(!navigator.canShare?.({files:[attachment]})){download();return;}
      try{await navigator.share({files:[attachment],title:'PDF zoom diagnostics'});}
      catch(error){if(error.name!=='AbortError')status.textContent='Sharing failed. Use Download trace instead.';}
    });
    const note=document.createElement('small');
    note.textContent='Up to 2 minutes. No PDF text, comment text or sign-in tokens. Nothing is uploaded automatically. Attach the downloaded file in this chat.';
    panel.append(title,status,actions,note);document.body.append(panel);
    for(const type of ['click','pointerdown','keydown'])panel.addEventListener(type,event=>event.stopPropagation());
  }
  const api=application.reviewTouchDiagnostics=window.reviewTouchDiagnostics={
    entries,record,start,pause,snapshot,get recording(){return recording;},
    clear(){entries.length=0;updateControls();},
    stop(){
      pause();controllers.forEach(controller=>controller.abort());
      listeners.forEach(([type,listener])=>application.eventBus.off(type,listener));
      clearTimeout(exportTimer);if(exportUrl)URL.revokeObjectURL(exportUrl);
      stylesheet?.remove();panel?.remove();
      delete application.reviewTouchDiagnostics;delete window.reviewTouchDiagnostics;
    },
  };
  if(autoStart)start();else updateControls();
  return api;
}
