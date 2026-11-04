// Own PDF pinches explicitly: Safari can emit GestureEvents alongside touches.
export function installPdfTouch(frame,application){
  const view=frame.contentWindow,pdf=application.pdfViewer,container=pdf.container;
  // Do not let two gesture recognizers suppress or scale the same gesture.
  application._touchManager?.destroy();application._touchManager=null;
  let pinch=null,nativeGesture=null,ownsTouches=false;
  const options={capture:true,passive:false};
  const enabled=()=>!!application.pdfDocument&&!pdf.isInPresentationMode&&!application.overlayManager?.active;
  const inPdf=target=>container.contains(target)&&!target.closest?.('input,textarea,select,button,.section-management-line');
  const stop=event=>{if(event.cancelable)event.preventDefault();event.stopImmediatePropagation();};
  const reset=()=>{pinch=null;nativeGesture=null;ownsTouches=false;};
  const points=touches=>{
    const [a,b]=touches;
    return {ids:[a.identifier,b.identifier],distance:Math.hypot(b.clientX-a.clientX,b.clientY-a.clientY),origin:[(a.clientX+b.clientX)/2,(a.clientY+b.clientY)/2]};
  };
  const begin=touches=>{const info=points(touches);pinch=info.distance>0?{...info,scale:pdf.currentScale,source:nativeGesture?.used?'gesture':null}:null;};
  const touchStart=event=>{
    if(!enabled()||(!ownsTouches&&!inPdf(event.target))||event.touches.length<2)return;
    ownsTouches=true;stop(event);
    if(event.touches.length===2)begin(event.touches);else pinch=null;
  };
  const touchMove=event=>{
    if(!ownsTouches)return;
    stop(event);
    if(!enabled()||event.touches.length!==2){pinch=null;return;}
    if(!pinch){begin(event.touches);return;}
    // Follow identifiers, not TouchList order; it can change as fingers move.
    const touches=pinch.ids.map(id=>[...event.touches].find(touch=>touch.identifier===id));
    if(touches.some(touch=>!touch)){begin(event.touches);return;}
    const info=points(touches);
    if(info.distance<=0||pinch.source==='gesture')return;
    if(!pinch.source&&Math.abs(info.distance-pinch.distance)<.01&&Math.hypot(info.origin[0]-pinch.origin[0],info.origin[1]-pinch.origin[1])<.01)return;
    pinch.source='touch';
    const target=pinch.scale*info.distance/pinch.distance;
    application.updateZoom(null,target/pdf.currentScale,pinch.origin,[info.origin[0]-pinch.origin[0],info.origin[1]-pinch.origin[1]]);
    pinch.origin=info.origin;
  };
  const touchEnd=event=>{
    if(!ownsTouches)return;
    stop(event);pinch=null;
    if(event.touches.length===2)begin(event.touches);
    if(!event.touches.length)ownsTouches=false;
  };
  view.addEventListener('touchstart',touchStart,options);
  view.addEventListener('touchmove',touchMove,options);
  view.addEventListener('touchend',touchEnd,options);
  view.addEventListener('touchcancel',event=>{if(ownsTouches)stop(event);reset();},options);
  const gestureOrigin=(event,host)=>{
    const rect=frame.getBoundingClientRect();
    return [Number.isFinite(event.clientX)?event.clientX-(host?rect.left:0):container.clientWidth/2,
      Number.isFinite(event.clientY)?event.clientY-(host?rect.top:0):container.clientHeight/2];
  };
  const gestureStart=(event,host)=>{
    const eligible=host?(event.target===frame||event.target.closest?.('.viewer-frame-wrap')||document.elementFromPoint(event.clientX,event.clientY)===frame):inPdf(event.target);
    if(!enabled()||!eligible)return;
    stop(event);
    nativeGesture={scale:pdf.currentScale,start:event.scale>0?event.scale:1,origin:gestureOrigin(event,host),host};
  };
  const gestureChange=(event,host)=>{
    // Some Safari sequences provide touchstart but only gesturechange motion.
    // The first stream that actually moves owns scaling for the whole pinch.
    if(ownsTouches&&pinch?.source==='touch'){stop(event);return;}
    if(!nativeGesture&&pinch)nativeGesture={scale:pinch.scale,start:1,origin:pinch.origin,host};
    if(!nativeGesture||nativeGesture.host!==host)return;
    stop(event);
    if(!enabled()||!(event.scale>0))return;
    const origin=gestureOrigin(event,host),previous=nativeGesture.origin;
    if(!nativeGesture.used&&Math.abs(event.scale-nativeGesture.start)<1e-6&&Math.hypot(origin[0]-previous[0],origin[1]-previous[1])<.01)return;
    nativeGesture.used=true;if(pinch)pinch.source='gesture';
    application.updateZoom(null,nativeGesture.scale*event.scale/nativeGesture.start/pdf.currentScale,previous,[origin[0]-previous[0],origin[1]-previous[1]]);
    nativeGesture.origin=origin;
  };
  for(const [target,host] of [[view,false],[window,true]]){
    target.addEventListener('gesturestart',event=>gestureStart(event,host),options);
    target.addEventListener('gesturechange',event=>gestureChange(event,host),options);
    target.addEventListener('gestureend',event=>{if(ownsTouches||nativeGesture){stop(event);nativeGesture=null;}},options);
    target.addEventListener('blur',reset);
  }
}
