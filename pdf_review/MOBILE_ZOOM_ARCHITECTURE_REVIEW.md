# Mobile PDF zoom architecture review

Historical review: the user subsequently requested reverting all custom zoom
changes. The focal wrapper and gesture overrides described below are removed;
the proposed lifecycle refactor has not been implemented. Current behavior uses
unmodified PDF.js defaults.

November 3, 2026. Research and source review following the iPhone SE test of
the native PDF.js integration plus `pdf_zoom_layout.js`.

## Finding

The current integration does too much DOM and layout work during a pinch and
has more than one code path adjusting its final position. Keeping PDF.js is
reasonable. Adding more per-event scroll corrections is a poor next step.

There is a concrete touch-target lifetime hazard in our overlay rendering, plus
several likely contributors to jitter. These are source findings and browser
mechanisms, not a confirmed trace of the particular upward jump on the phone.
The last change improved settled Chrome geometry; it did not establish smooth
continuous Safari behavior. No runtime code was changed for this review.

## What is happening in this application

1. Safari delivers touch events into the full-width PDF.js iframe. Its native
   TouchManager listens on the iframe window (`web/viewer.mjs:20249`). The host
   separately cancels browser-level gesture events over the PDF.
2. PDF.js computes scale/pan and calls `pdfViewer.updateScale`. That changes page
   dimensions, refreshes page views, restores a document location and pans about
   the origin. Canvas redraw is normally deferred with a 400 ms idle timer.
3. Our `pdf_zoom_layout.js` wrapper measures a page, calls that native path,
   changes stage width, measures again and calls `panBy` a second time.
4. `scalechanging`, scroll, rendering and resize notifications schedule app
   highlight rebuilding, section-marker rebuilding and comment/card layout.
   These run in both the iframe and parent documents.
5. Rail layout changes padding, minimum width and overflow sentinels in the PDF
   scroller. Parent-owned cards are positioned by reading iframe page geometry.
   There is no shared pinch lifecycle that limits those changes.

## Specific problems and confidence

| Finding | Source evidence | Implication |
| --- | --- | --- |
| Touched highlight nodes can be removed during a gesture | `anchor_overlay.js:29` schedules rendering on zoom; `:158` replaces the entire existing overlay when dimensions change. | Strong correctness concern: subsequent touch events can remain targeted at the detached node and fail to reach the window listener. |
| Section marker nodes are also replaced | `section_viewer.js:54` removes all existing markers on each render. | The same hazard applies if a gesture begins on a visible marker. |
| Two stages of scroll correction | `pdf_zoom_layout.js:20` invokes native scaling; `:31` pans again using measured geometry. | Extra layout reads/writes and position adjustments. Accurate settled coordinates do not prove the intermediate frames are stable. |
| Card layout affects the PDF scroll extent | `viewer_shell.js:326` changes the overflow key at every scale; its tail can shrink or grow. `left_card.js:112` retains a maximum historical sentinel position. | Near an extent limit, shrinking overflow can clamp scroll position. The asymmetric left tail can retain blank space after zoom-out. This is a plausible source of jumps, especially near the end, not proof of every reported jump. |
| Expensive work runs throughout scaling | Comment layout measures many cards; stage sizing scans page views; highlights and section markers rebuild across pages. | Main-thread work competes with gesture delivery and painting. The source proves the work exists; physical-device profiling would establish its actual cost. |
| Tests measure a quieter interaction | `tests/mobile_pinch.py:24` waits for native canvas/text rendering to settle before another pinch. | They miss quick reversals, a second pinch during redraw, stable-target requirements and transient visual jumps. |

Touch targets are particularly important: browser touch contacts retain their
original target. Removing that element can prevent later events from bubbling to
document/window. This is documented by [MDN's Touch.target reference](https://developer.mozilla.org/en-US/docs/Web/API/Touch/target).
Our window listener plus replacing overlays is therefore an architectural hazard
even without a Safari-specific coordinate error. Native canvas/text refreshes
also need consideration when gestures overlap rendering; not all replacement is
owned by the app.

The wrapper's read/write/read pattern can force synchronous layout, and the rail
adds further measurements and geometric writes. [Browser performance guidance](https://web.dev/articles/avoid-large-complex-layouts-and-layout-thrashing)
explains why that can increase interaction latency. This is a likely contributor,
not a measured Safari performance result.

## What established implementations tell us

PDF.js already has pinch recognition, focal calculations, native panning and
deferred canvas rendering. Our build is 6.4.299 and already contains the earlier
client-coordinate origin fix. Reimplementing distance-to-scale calculations or
blindly adding that patch would duplicate existing behavior.

The native viewer already uses CSS scaling while raster work is delayed; saying
it currently rerenders a fresh full-resolution PDF for every touch event would
be inaccurate. However, it still updates page layout during scaling, and its
400 ms idle redraw is not explicitly tied to lifting both fingers. An idle pause
with fingers still down is different from a completed gesture.

For comparison, [Leaflet's touch-zoom implementation](https://raw.githubusercontent.com/Leaflet/Leaflet/v1.9.4/src/map/handler/Map.TouchZoom.js)
keeps a stable starting coordinate beneath the midpoint, updates through animation
frames, and has an explicit gesture-end phase. This illustrates a useful lifecycle;
it does not establish that a map library is a drop-in PDF viewer.

Safari also has independent issues. [PDF.js #20480](https://github.com/mozilla/pdf.js/issues/20480)
reports jumping in the upstream viewer on iOS. The older
[iframe integration report #16328](https://github.com/mozilla/pdf.js/issues/16328)
shows that browser-level and viewer-level zoom can interact. Neither proves an
iframe must be removed from this app. [MDN's VisualViewport documentation](https://developer.mozilla.org/en-US/docs/Web/API/VisualViewport)
also explains that the top-level visual viewport differs from an iframe's layout
viewport. Treating those measurements as interchangeable is unsafe if site zoom
or browser chrome changes the visible area.

An older [canvas tearing workaround](https://github.com/mozilla/pdf.js/pull/17571)
addresses painting artifacts, and was closed without being merged. It is not an
explanation or general fix for scroll jumps. Similarly, lowering canvas resolution
is not an obvious missing configuration: this build already sets a 5,242,880
pixel canvas cap on iOS/Android. It should not be reduced blindly to compensate
for app layout problems.

## Recommended approach

First make the native integration stable, with one owner of scale and scrolling:

1. Add an explicit pinch lifecycle shared by app presentation code. Observe
   touch start/end/cancel on a durable surface without stealing the native touch
   stream. Keep the phase active until fewer than two tracked contacts remain;
   support interruption, tab hiding and the next gesture starting before cleanup.
2. Keep highlight and boundary DOM nodes alive. Update keyed nodes in place, or
   defer destructive rebuilds until the gesture finishes. Preserve the actual
   targets for the entire active contact sequence, including its first finger.
3. During a pinch, freeze app-owned gutter changes, collision packing, card
   animations and sentinel resizing. Lightweight projection can follow the pages;
   changing the scrollable bounds must wait. Page sizing needed by native zoom
   must still happen, so this is not a blanket freeze of all PDF layout.
4. Establish stage dimensions as part of the native scale transaction, rather
   than reconciling them on another animation frame. After that is stable, remove
   the extra focal pan wrapper instead of stacking corrections on it.
5. On completion, perform one coordinated app layout. If changing rail extents
   requires repositioning, preserve one canonical PDF page/point and account for
   real scroll limits. Avoid cumulative per-event corrections.

This is the smallest architectural improvement and preserves the current iframe,
toolbar, comments, text selection and PDF.js engine. It is preferable to replacing
the renderer or introducing a new gesture library immediately.

If the simplified native path still fails on physical Safari, the next design is
a visual preview phase followed by a committed PDF scale: transform an unchanged
document surface during the gesture, then apply final PDF.js scale and focal
scroll once. Pages, highlights and section lines must share that preview;
unscaled comment/tool cards need a matching position projection. Existing targets
must survive the commit until their contacts end. This is a deliberate zoom
controller refactor, not another fallback beside the existing one.

Embedding PDFViewer directly in the host document could reduce cross-document
coordination later. Mozilla provides a [component viewer example](https://github.com/mozilla/pdf.js/blob/master/examples/components/simpleviewer.mjs),
but it is not a complete replacement for all generic-viewer features. Search,
download policy, shortcuts, text selection, spreads and existing overlay behavior
would all need to be retained. Removing the iframe alone is not a proven fix.

The one focused validation after implementation should be physical-device
continuous zoom/reversal with fingers over both highlights and plain text,
including a page transition and the document end. A short trace should distinguish
lost events, changed scroll limits and delayed redraw. Repeated settled Chrome
coordinate checks cannot substitute for that observation.

## Scope and status

This review changes documentation only. No new gesture handler, library,
dependency, schema change or viewer rewrite was installed, and no browser suite
was rerun. Existing PDF bytes, canonical anchors, Google authentication and
download policy are unaffected. Earlier reports of automated passes describe
their measured cases, not physical Safari correctness.
