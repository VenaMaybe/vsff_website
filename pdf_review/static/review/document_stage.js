import { cardScale } from './card_scale.js';

// PDF layout and UI reachability are independent. Only this coordinator writes
// the scroll extent/origin; providers report measured document-space boxes.
export function documentStage(application) {
  return application.reviewStage ||= new DocumentStage(application);
}

class DocumentStage {
  constructor(application) {
    this.application = application;
    this.pdf = application.pdfViewer;
    this.scroller = this.pdf.container;
    const syncCardScale = () => document.querySelector('.viewer-workspace')?.style.setProperty('--review-card-scale', cardScale(application));
    syncCardScale();
    application.eventBus.on('scalechanging', syncCardScale);
    application.eventBus.on('reviewcardscalechanged', () => { syncCardScale(); this.schedule(); });
    this.origin = 0;
    this.originY = 0;
    this.bounds = new Map();
    this.jobs = new Map();
    this.extent = this.scroller.ownerDocument.createElement('div');
    this.extent.className = 'review-document-extent';
    this.extent.setAttribute('aria-hidden', 'true');
    this.scroller.append(this.extent);
    const nativeUpdateScale = this.pdf.updateScale;
    this.pdf.updateScale = function(options) {
      // Native pan can mark its location stale. PDF.js otherwise refreshes that
      // snapshot after resizing pages, mixing old scroll pixels with new page
      // dimensions. Snapshot the current native view BEFORE the transaction.
      // All scale, midpoint, pan and rendering calculations remain native.
      if (this.pdfDocument) this.update();
      return nativeUpdateScale.call(this, options);
    };
    this.scroller.addEventListener('scroll', () => {
      this.scrolling = true;
      clearTimeout(this.scrollIdle);
      this.scrollIdle = setTimeout(() => { this.scrolling = false; this.schedule(); }, 150);
      this.schedule();
    }, { passive: true });
    application.eventBus.on('pdftouchended', () => this.schedule());
    for (const event of ['scalechanging','rotationchanging','spreadmodechanged','scrollmodechanged','pagesinit','pagerendered']) {
      application.eventBus.on(event, () => this.schedule());
    }
    this.resize = new ResizeObserver(() => this.schedule());
    this.resize.observe(this.scroller);
    this.schedule();
  }
  schedule(key, job) {
    if (job) this.jobs.set(key, job);
    if (this.pending) return;
    this.pending = requestAnimationFrame(() => {
      this.pending = null;
      const jobs = [...this.jobs.values()];
      this.jobs.clear();
      this.flushing=true;
      try{for (const run of jobs) run();}
      finally{this.flushing=false;}
      this.commit();
    });
  }
  setBounds(key, boxes) {
    this.bounds.set(key, boxes.filter(box => [box.left,box.right,box.top,box.bottom].every(Number.isFinite)));
    // Current frame jobs are followed by commit already; bounds need no extra frame.
    if(!this.flushing)this.schedule();
  }
  commit() {
    const s = this.scroller, viewer = this.pdf.viewer;
    const scrollLeft = s.scrollLeft, scrollTop = s.scrollTop;
    const rect = viewer.getBoundingClientRect(), surface = s.getBoundingClientRect();
    const left = rect.left - surface.left - s.clientLeft + scrollLeft;
    const top = rect.top - surface.top - s.clientTop + scrollTop;
    let minimum = left, minimumY = top;
    let right = left + Math.max(viewer.clientWidth,viewer.scrollWidth);
    let bottom = top + Math.max(viewer.clientHeight,viewer.scrollHeight);
    for (const group of this.bounds.values()) for (const box of group) {
      minimum = Math.min(minimum, box.left); minimumY = Math.min(minimumY, box.top);
      right = Math.max(right, box.right); bottom = Math.max(bottom, box.bottom);
    }
    // Reclaim origin space only as it scrolls away; otherwise a negative
    // scrollLeft would be needed to keep the document in the same screen place.
    // Native touch scrolling (including momentum after lift) owns the camera.
    // Rebase/reclaim only when idle; programmatic scroll writes while Safari is
    // tracking a finger can interfere with its asynchronous scroll trajectory.
    const scrolling = this.scrolling || this.application.reviewPdfTouchActive;
    const origin = scrolling ? this.origin : Math.ceil(Math.max(0, this.origin - minimum, this.origin - scrollLeft));
    const delta = origin - this.origin;
    const originY = scrolling ? this.originY : Math.ceil(Math.max(0, this.originY - minimumY, this.originY - scrollTop));
    const deltaY = originY - this.originY;
    right += delta; bottom += deltaY;
    // Keep the current viewport reachable when content closes or shrinks. This
    // prevents browser clamping without resizing/recentering the PDF canvas.
    this.extent.style.width = `${Math.ceil(Math.max(s.clientWidth, right, scrollLeft + delta + s.clientWidth,
      scrolling ? parseFloat(this.extent.style.width) || 0 : 0))}px`;
    this.extent.style.height = `${Math.ceil(Math.max(s.clientHeight, bottom, scrollTop + deltaY + s.clientHeight,
      scrolling ? parseFloat(this.extent.style.height) || 0 : 0))}px`;
    if (delta || deltaY) {
      viewer.style.marginLeft = `${origin}px`;
      viewer.style.marginTop = `${originY}px`;
      this.origin = origin;
      this.originY = originY;
      for (const group of this.bounds.values()) for (const box of group) {
        box.left += delta; box.right += delta;
        box.top += deltaY; box.bottom += deltaY;
      }
      // An origin rebase moves content and viewport equally. No scale, gesture
      // distance or focal-point correction is calculated by the app.
      s.scrollLeft = scrollLeft + delta;
      s.scrollTop = scrollTop + deltaY;
      this.application.eventBus.dispatch('documentoriginchanged', { source: this, dx:delta, dy:deltaY });
    }
  }
}
