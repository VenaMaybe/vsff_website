// Browser integration only: PDF.js's existing TouchManager owns recognition,
// scale/pan and the midpoint. No second zoom calculation or GestureEvent.scale.
export function installPdfGestures(frame, application) {
  const w = frame.contentWindow, doc = frame.contentDocument;
  const container = application.pdfViewer.container;
  const targets = new Map(), relayed = new WeakSet();
  const contacts = new Set();
  const belongs = target => target?.nodeType === 1 && container.contains(target);
  const reset = () => {
    contacts.clear();
    for (const controller of targets.values()) controller.abort();
    targets.clear();
    application.reviewPdfTouchActive = application.reviewPdfPinching = false;
    application.eventBus.dispatch('pdftouchended', { source: application });
  };
  const track = event => {
    const previous = contacts.size;
    if (event.type === 'touchstart') {
      for (const touch of event.changedTouches) {
        if (!belongs(touch.target)) continue;
        contacts.add(touch.identifier);
        if (targets.has(touch.target)) continue;
        // Touch contacts retain their original targets even after DOM removal.
        // Relay only detached-target events back to the native window listener.
        // Connected events bubble normally and are never duplicated.
        const controller = new w.AbortController();
        targets.set(touch.target, controller);
        for (const type of ['touchmove','touchend','touchcancel']) {
          touch.target.addEventListener(type, original => {
            if (original.target.isConnected || relayed.has(original)) return;
            const forwarded = new w.TouchEvent(original.type, { touches:original.touches,
              targetTouches:original.targetTouches, changedTouches:original.changedTouches,
              cancelable:original.cancelable, bubbles:false });
            relayed.add(original);
            w.dispatchEvent(forwarded);
            if (forwarded.defaultPrevented && original.cancelable) original.preventDefault();
          }, { passive:false, signal:controller.signal });
        }
      }
    } else if (event.type !== 'touchmove') {
      for (const touch of event.changedTouches) contacts.delete(touch.identifier);
    }
    application.reviewPdfTouchActive = contacts.size > 0;
    application.reviewPdfPinching = contacts.size > 1;
    if (previous && !contacts.size) queueMicrotask(() => { if (!contacts.size) reset(); });
  };
  for (const type of ['touchstart','touchend','touchcancel']) w.addEventListener(type, track, { capture:true, passive:true });
  w.addEventListener('blur', reset);
  doc.addEventListener('visibilitychange', () => { if (doc.hidden) reset(); });
  const cancelBrowserGesture = event => {
    if ((belongs(event.target) || contacts.size > 1) && event.cancelable) event.preventDefault();
  };
  for (const type of ['gesturestart','gesturechange']) w.addEventListener(type, cancelBrowserGesture, { passive:false });
  // Safari can route its browser gesture to the embedding frame instead.
  for (const type of ['gesturestart','gesturechange']) frame.parentElement.addEventListener(type, event => {
    if (event.cancelable) event.preventDefault();
  }, { passive:false });
}
