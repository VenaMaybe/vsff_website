# Trackpad zoom diagnosis

November 3, 2026. Original diagnosis followed by the implemented architectural fix.
The diagnosis below describes the former layout; see the implementation status at the end.

## Confirmed cause

The app changes the PDF stage's minimum width after PDF.js finishes its native
cursor-centered zoom calculation. PDF.js centers pages using automatic horizontal
margins. The later width change therefore moves the pages again, without a
corresponding native focal-scroll adjustment.

The card-dependent minimum width is the key difference between the working
no-card view and the failing card view. This was isolated in a disposable Chrome
fixture, retaining the right comment gutter while disabling only that minimum
width in the fixture DOM. The post-zoom displacement disappeared. There is no
need to invoke Safari touch handling to reproduce this trackpad problem.

## Code path

1. Vendored `static/vendor/pdfjs/web/viewer.mjs:20692` handles the trackpad wheel
   event. At `:20706` it takes `[evt.clientX, evt.clientY]` as the zoom origin and
   passes it to native zoom at `:20714`.
2. Native `#setScaleUpdatePages` at `:15511` changes page dimensions, restores its
   document location and applies the origin correction through `panBy`. Only
   afterward does it emit `scalechanging` at `:15574`.
3. `static/review/viewer_shell.js:157` listens for that event. Its `schedule`
   method at `:172` defers app rail layout to an animation frame.
4. The rail computes `stageWidth` from the newly scaled page widths at `:216`.
   At `:217`, it sets `--review-stage-width` to that width if either a right
   gutter or left gutter exists, otherwise to zero. A left card sets a 284px
   gutter in `static/review/left_card.js:190`.
5. `static/styles/pdfjs.css:15` uses that variable as `#viewer`'s minimum content
   width, alongside the fixed gutter padding. This changes the actual width
   available for centering the pages.
6. Native `static/vendor/pdfjs/web/viewer.css:6243` defines horizontal page margins
   as `auto`; `.page` applies them at `:6362`. The browser recenters the page
   when the app updates its stage width, after the native correction is over.

## Measured isolation

Synthetic two-page PDF, desktop viewport 1440px wide, a right comment gutter,
cursor X=700, and native zoom from 253% to 234%. The experiment calls the same
native `updateZoom` routine that the trackpad path invokes, without injecting a
new gesture algorithm. Measurements are taken immediately before/after native
zoom and again after app layout.

| Measurement | Existing minimum width | Only minimum-width rule disabled |
| --- | ---: | ---: |
| Initial PDF point under cursor, X | 322.387 | 323.494 |
| PDF point immediately after native zoom, X | 322.444 | 323.642 |
| PDF point after app layout, X | 347.307 | 323.642 |
| Extra page displacement after native zoom | 77.516 CSS px left | 0 CSS px |
| Total cursor-point drift, converted to CSS px | approximately 78 | approximately 0.46 |

The gutter and comment remain present in both cases. Their initial page points
differ because disabling minimum width changes centering before the experiment.
The meaningful comparison is each case's own before/after displacement.

In the failing case, the stage's outer width decreases from 2373px to 2218px on
the app's later layout. Half that decrease is 77.5px, matching the measured extra
page shift. ScrollLeft stays at 396 during that later shift, so this particular
reproduction is page recentering, not a scroll-clamp event.

The probe also reproduced the extra displacement with only a left card and with
both gutters. With no cards, the minimum-width variable stays zero and the app
does not introduce this second width change.

## Why zoom-out looks worse

During zoom-out the page becomes narrower while its parent temporarily retains
the previous larger minimum width. Automatic margins center the smaller page in
that old width. Native zoom calculates scrolling for that intermediate layout.
The app then shrinks the parent, removing roughly half the width difference from
the page's horizontal position. The page slides left, so the cursor is now over
a point farther right in the document. Repeated updates accumulate the error.

During zoom-in, a larger page initially overflows the previous smaller stage,
which collapses its automatic horizontal margins. The subsequent stage update
restores a small centering margin. In the recorded case this added approximately
3.7px of rightward page movement after native zoom, much smaller than the
zoom-out displacement. Fitted views also have genuine scroll limits, so exact
cursor retention is not possible in every low-scale configuration.

## Scope of conclusion

This identifies a specific integration cause for the card-dependent horizontal
trackpad behavior. It does not establish that all physical mobile glitches have
the same cause. Touch-target replacement from the earlier architecture review
is a separate concern, not needed to explain this reproduction.

The correction belongs in document/gutter layout coordination: stop changing
page centering after native zoom's focal calculation. Removing minimum width
globally was an isolation experiment, not a proposed finished fix; existing
comment reachability, spreads, left tools and scroll extent must still work.
No custom pinch handler, vendor patch or production change was made. The probe
lives in ignored `.mobile-test/zoom_probe.py` and uses disposable synthetic data.

## Implemented architectural fix

`document_stage.js` now owns scroll reachability, independent of native PDF
canvas width. Cards report measured rectangles; their union with native document
bounds drives one extent element. There are no card-width/page-count/spread
formulas in canvas sizing. Content left/above zero rebases canvas and scroll
origins equally, with parent card coordinates updated atomically. Closing or
resizing cards preserves the current viewport rather than forcing scroll clamps.
Native page centering no longer changes on a later card-layout frame.

A separate mixed-page touch reproduction exposed native view-snapshot ordering:
a stale location could be refreshed after page resizing. A preflight native
update() before updateScale refreshes that snapshot using the old geometry.
Native scale/pan/focal math remains intact. No corrective pan wrapper or vendor
patch is installed. Scoped PDF gesture handling and original touch-target
continuity address the browser-input concerns independently of stage sizing.

Focused verification: 80 native zoom steps over all four rail states, an 8-page
mixed-size document, odd/even spreads, vertical/horizontal/wrapped layouts,
opening/closing/resizing/pinning tools, dynamic right-card width, arbitrary distant
bounds in both axes, a fitted-page/tall-card scrollbar check, actual trackpad wheel input and atomic overlay rebasing.
Maximum measured desktop focal drift was 2.12 CSS px. Chrome two-touch input in
both directions, immediate reversal and delayed drawing had maximum measured
focal drift 2.37 CSS px; detached-target continuity, one-finger scrolling and
scoped Safari-event cancellation passed. The existing six-refinement viewer
check also passed. Physical iPhone Safari remains unverified; MOBILE_TESTING.md
lists the exact device steps. Native document-edge limits still apply.

Run the focused check with
`.\.venv\Scripts\python.exe tests/browser_sanity.py --zoom-layout`.
