# Jump when zooming from several pages into one page

November 4, 2026. Diagnosis followed by the implemented native viewer fix.

## Background and page-boundary correction

The follow-up fix is implemented in the existing native viewer patch. Every
origin-based zoom uses a current page-relative plane. When the midpoint is outside
paper, the viewer chooses the nearest attached page, including offscreen pages,
and extrapolates the PDF coordinates instead of clamping the point to paper or
falling back to an old `_location` snapshot. No attached pages means no automatic
navigation to a stale page.

For touch, native TouchManager start/end callbacks manage a reference whose page
identity remains fixed across the gesture. Current camera coordinates are sampled
against that same page each step, so crossings and actual scroll limits do not
create an accumulating error. End/cancel and document reset clear the reference;
the app's existing contact, blur and visibility cleanup clears it too. The native
pinch recognizer, input distance/scale calculation and atomic final scroll remain.

Verification passes the 80 existing desktop steps and 28 fitting/overflowing
transition cases. The no-visible-page and cross-boundary/reversal regression has
0.49px maximum error in the full run; its no-visible-page zoom stays at scrollLeft
1019 rather than jumping to zero. Actual Chrome two-touch input starts with fingers
on opposite sides of a divider, zooms while translating the midpoint, and keeps
one reference page (1.97px drift). Live highlight, detached-target, fractional pan
and browser-owned one-finger scrolling checks pass. These measurements do not
verify this revision on physical iPhone Safari; reload and repeat the background
and boundary gestures there.

The following investigation describes the previous incomplete implementation.
It is retained as the explanation and reproduction of the defects being fixed.

## Background/boundary investigation before correction

The subsequent physical iPhone report identifies a missing part of the fix:
pinches on background or across page boundaries still snap. The implementation
at that point handled a midpoint on a page without a continuous background/gesture
anchor. That diagnostic follow-up changed no application behavior; the later
correction is described above.

### End-to-end source audit

* Native `TouchManager` (`build/pdf.mjs:4820`) computes finger distance from
  screen coordinates, the midpoint from client coordinates, and incremental pan
  from the midpoint movement. It filters/recognizes the gesture, then calls
  `touchPinchCallback` with distance ratio, previous midpoint and translation.
  It does not classify paper versus background.
* `touchPinchCallback` (`web/viewer.mjs:19433`) accumulates the ratio and calls
  `updateZoom`, then `updateScale`. The latter (`:16267`) computes the new scale
  from the factor/steps, rounding and bounds. Background/page classification does
  not participate in this scale calculation. A positional snap can therefore
  look like accelerated zoom without an excessive scale factor. This does not
  exclude separately uneven input or recognition thresholds on a physical phone.
* Our `pdf_gestures.js` observes contacts, scopes browser-gesture cancellation
  and relays detached-target events. It calculates neither distance nor scale.
  A background touch target normally stays attached, so that relay is not needed
  to explain the background snap. `document_stage.js` preflights native update()
  and freezes origin maintenance during contacts; it adds no pinch-scale math.
* Our patched `#setScaleUpdatePages` (`viewer.mjs:15527`) uses `focalLocation`
  only if the midpoint is inside a visible page's content rectangle. It ignores
  page borders, inter-page gaps, side background and completely offscreen pages
  for this choice. When no rectangle contains the midpoint, it restores native
  `_location` and uses the older origin calculation instead.
* `focalLocation` is a local variable recalculated on every scale update. It is
  not retained for the gesture. In a fast pinch, the moving/resizing page edge
  can pass beneath the midpoint between updates even if the fingers barely
  translate. The path then switches between page anchoring and background
  fallback, or between different pages. Fingers on different pages can have
  their midpoint entirely in the gap.
* Native `update()` (`:15828`) returns immediately when no pages are visible.
  The preflight therefore does **not** always refresh the camera snapshot.
  The background fallback can restore the last visible page's `_location`, which
  may describe a very different scroll position. A separate risk is that stale
  location refresh (`:15513`) then occurs after resize if a page becomes visible.
  That last timing case is supported by the source order, not isolated below.

### Focused trace

The ignored `.mobile-test/background_zoom_probe.py` uses synthetic mixed-size
pages and the same native zoom entry point. No broad suite or physical device
claim is involved. For the all-background case, an arbitrary measured stage bound
provided legitimate horizontal reachability, representing distant cards/layers
or retained space. The stage's contact flag stayed active during each transaction.

| Case | Requested scale | Source behavior | Observed result |
| --- | --- | --- | --- |
| Camera in background; zero visible pages | 35% to 38% | Restored old page-1 `_location` | scrollLeft 950 to 0; page reappeared |
| Midpoint in side background; pages partly visible | 35% to 40% | Native first-visible-location fallback | Confirms fallback executes for the side |
| Midpoint just inside page 1 above divider | 35% to 40% | Page-1 focal destination | final scrollLeft 0 |
| Midpoint in divider/gap | 35% to 40% | First-visible-location fallback | final scrollLeft 0 |
| Midpoint just inside page 2 below divider | 35% to 40% | Page-2 focal destination | final scrollLeft 25 |

For the boundary trace, the origin's X was always 185; only Y changed from 250.5
through 256.5 to 262.5. Each case started at the same scale and camera position.
The pages had different widths and the step crossed a width-fit threshold. The
25px horizontal discrepancy across a 12px vertical border/gap interval exposes
the discontinuity; it does not assert that every equal-page divider has that
size of error. The all-background case demonstrates actual restoration of an
obsolete camera position, not percentage rounding or final edge clamping.

The previous regression cases deliberately placed origins on paper. Even the
real-touch later-page case centered its midpoint inside page 3. They therefore
did not establish background or cross-boundary continuity.

### Direction for the next correction

Use one spatial anchoring policy across paper, borders, gaps and background.
It must define a document-relative reference even when no page contains the
midpoint or no page is visible, rather than restoring stale `_location`.
For touch, anchor identity needs continuity for the gesture, or an explicitly
continuous handoff; selecting a different page at every sampled event is not
enough. Arbitrarily snapping the midpoint to the nearest page edge would merely
introduce another discontinuity.

The atomic final-scroll change remains useful, but does not solve this anchor
selection/lifetime problem. Smoothing or reducing zoom speed would mask symptoms
without resolving it. The synthetic traces confirm concrete defects in these
paths; physical iPhone event timings and any separate distance/scale jump remain
unverified. No further vendor or gesture changes were made during this follow-up.

## Implemented correction

The viewer now captures the PDF point under a gesture origin before page layout
changes, then uses native destination conversion to restore that point. Native
scroll restoration and origin/pan adjustment are combined before assigning the
scroll offsets, so only the final position is clamped. The native fractional pan
cache receives the requested final position. This also handles a gesture over a
later page whose centering differs from the first visible page, and wrapped rows
that reflow at the new scale.

Stage padding to avoid clamping was rejected because it would change geometry
and reachability. An app-owned corrective pan would add a second camera update;
DOM scroll-accessor interception or reproducing destination geometry outside
PDF.js would be brittle. A small, maintained patch inside the native private
scale/scroll implementation keeps those responsibilities together. Its scope,
exact diff and upgrade procedure are in `static/vendor/pdfjs/LOCAL_PATCHES.md`
and `vendor_patches/pdfjs-6.4.299-atomic-zoom.patch`. No rendering-core, worker,
gesture recognizer, database or security changes are involved.

Verification: the focused zoom run passes its existing 80 desktop steps (2.12px
maximum drift), plus 28 fitting/overflowing transitions and reversals across all
card states, rotation, mixed/later pages, spreads and scroll modes (2.50px maximum
nearest-reachable error). Real Chrome touch transition/reversal on a later page
measured 2.95px maximum drift. Fractional pan, live highlights (0.02px error),
detached targets and one-finger browser scrolling pass. Physical iPhone Safari
confirmation remains manual. Tests explicitly check that zoom issues at most one
scroll write per axis; final scroll limits remain enforced.

The sections below record the original diagnosis and disposable isolation.
Vendor line references there refer to the pristine module before the local patch.

The user clarified that this is a larger glitch, specifically while transitioning
from several visible pages to one page or into a page. The earlier emphasis on
whole-percentage rounding was insufficient. The investigation now identifies an
actual position error in the native zoom path with the current layout:
**scroll restoration is clamped before the pinch-origin correction is applied.**

## Source mechanism

1. At low zoom, a page fits horizontally and has automatic centering margins.
   The viewport's top-left can lie outside the PDF page. Native `_updateLocation`
   legitimately records a negative PDF-space left coordinate
   (`static/vendor/pdfjs/web/viewer.mjs:15758`). An out-of-page top coordinate is
   also possible at the document start because of its border/margin.
2. `#setScaleUpdatePages` resizes the pages (`:15511`), then calls
   `scrollPageIntoView` to restore that old viewport location at the new scale
   (`:15557`).
3. `scrollIntoView` assigns scrollLeft and scrollTop directly (`:75`). Even though
   PDF.js passes `allowNegativeOffset: true`, browser scroll offsets still have
   real limits. A negative intermediate request is clamped to zero. That option
   avoids PDF.js's own destination clamp; it cannot suspend the browser's clamp.
4. Only afterward does PDF.js call `panBy` for the pinch midpoint correction
   (`:15565`, `:15483`). It reads the already-clamped offsets. The portion lost
   in step 3 is discarded, so the final position can be wrong even when the
   intended final position is fully inside the valid scroll range.

This differs from an unavoidable final document-edge limit: the *intermediate*
operation hits a limit, although the combined restoration plus midpoint adjustment
would be valid. The fitting/overflowing transition makes this especially relevant.
It does not require a new touch recognizer or a changed current-page policy.

## Focused isolation

After tracing the source, a disposable probe called the exact native `updateZoom`
entry point used by pinch, with two equal 612x792-point synthetic pages and a
375x667 mobile viewport. The PDF scroll viewport was 375x586. The app's contact
flag was held active to keep stage origin maintenance out of the transaction.
No real review data, database, vendor source or application handler was changed.

For a 40% to 85% transaction at origin (185,260), the native visible-page list
changed from [1,2] to [1], matching the reported transition.

| Operation | Requested scrollLeft | Requested scrollTop | Actual result |
| --- | ---: | ---: | --- |
| Restore previous location | -44.125 | -11.25 | Both clamped to 0 |
| Apply midpoint adjustment from clamped position | 208.125 | 292.5 | (208,293) |
| Combine both operations before clamping | 164 | 281.25 | (164,281) |

Both final positions fit inside the measured scroll range. The difference is
not forced by an edge. Measured PDF-point drift at the origin was **44.52 CSS px**.

An isolation override, only in the disposable fixture, carried the requested
restoration offsets into the native pan calculation instead of losing the clamped
amount. It retained the same scales, page layout, native rendering and midpoint:

| Native transaction | Existing drift | With intermediate offset retained |
| --- | ---: | ---: |
| 40% to 65% | 31.19px | 0.85px |
| 40% to 85%, two visible pages to one | 44.52px | 1.09px |
| 85% to 110%, already one visible page | 2.43px | 0.24px |

These deliberately wider transactions isolate the arithmetic; they do not claim
that the phone necessarily emits a 40%-to-85% change in one touch event. An earlier
narrower 42%-to-50% transaction showed 10.41px drift, falling to 0.68px with the same
isolation. Why the phone occasionally delivers a visibly larger transition is not
established by these results.

The ignored probe is `.mobile-test/page_transition_probe.py`. Its override is not
a production implementation. It also traced the next animation frame separately:
the equal-page sweep showed no additional between-frame stage displacement.
Initial mixed-page/last-page traces included real final scroll-limit effects;
those cases were excluded from the causal comparison above.

## Why earlier checks did not establish this

The main desktop focal tests prepare zoom at 280%, and the mobile pinch sequence
starts at 100%. They exercise within-page zoom, live highlights, touch-target
continuity and browser scrolling, but do not systematically cover the centered
small-page to overflowing-page transition. Passing them did not rule this out.

The app's pre-zoom native `update()` snapshot was active in the reproduction.
It prevents the separate stale-location problem but cannot fix the subsequent
loss of an intermediate scroll offset. Removing that snapshot is not a solution.
No card needs to be present for the isolated error.

## Direction selected after the diagnosis

The first correction to evaluate is treating native restoration and origin/pan
adjustment as one scroll transaction, retaining intended offsets until the final
position is clamped. It must preserve genuine final limits, fractional pan state,
spreads and the working desktop path. This direction is now implemented as the
documented native viewer patch above. Finer percentage precision was not needed.

This confirms a defect in this installed integration's native zoom path, not that
every physical Safari jump is explained. The isolated calls are not a physical
Safari verification. The initial investigation changed no viewer behavior; the
later implementation is described at the top of this document.

## Earlier secondary findings: scale quantization

`static/vendor/pdfjs/web/viewer.mjs:19386` routes a touch pinch through
`_accumulateFactor`. At `:20426` that function computes the desired scale, rounds
it using `Math.round(target * 100) / 100`, and carries the unused fraction into
the next event. `PDFViewer.updateScale` at `:16220` rounds to two decimal places
again. These are actual rendering scales, not just toolbar display rounding.

Consequently, slowly changing finger distance can produce several events with
no scale change followed by a whole percentage-point step. At 25% scale, moving
to 26% is a 4% relative enlargement; at 100%, moving to 101% is only 1%. A point
200 CSS pixels away from the midpoint moves 8 pixels in the former step. The
midpoint itself can remain correct throughout. Low-scale, multi-page views make
this mechanism more conspicuous without requiring page navigation to be broken.

Native `TouchManager` also filters small distance changes before invoking the
pinch callback (`static/vendor/pdfjs/build/pdf.mjs:4820`, `:5025`). Its ongoing
distance threshold is `4 / OutputScale.pixelRatio`; initial recognition has a
larger threshold and confirmation phase. Sub-threshold events may pan while
scale waits, then accumulated distance is applied. This is another source of
non-continuous touch updates. Trackpad zoom shares the percentage rounding but
does not pass through this touch-distance filter, so rounding alone does not
establish why the phone feels different from the laptop.

## Other mechanisms worth separating

* PDF.js stretches the existing canvas while delaying a fresh render by the
  configured 400ms (`viewer.mjs:599`, `:14122`, `:15534`). A pause during a pinch
  can therefore replace a stretched bitmap with a sharp render before fingers
  lift. That can look like a small visual snap without moving the viewport.
* Page dimensions are rounded down through CSS `round()` in
  `build/pdf.mjs:1517`. Drawing can change the page rounding quantum when the
  output-scale fraction changes (`viewer.mjs:14420`). Whether that happens in
  this phone's observed zoom range is unconfirmed; an integer device pixel ratio
  without canvas restrictions ordinarily leaves that quantum at 1px.
* Location restoration reads integer DOM offsets (`viewer.mjs:75`), while PDF
  viewport coordinates are floating point. The first visible page used for the
  location snapshot can change (`:15753`, `:15781`). This admits small rounding
  differences around page transitions, but the code does not establish a large
  automatic page-top snap in the current continuous-scroll mode.
* Our updateScale wrapper calls the full native `update()` before zoom to fix
  stale location snapshots (`static/review/document_stage.js:18`). Native zoom
  and its scalechanging handler update again. More visible pages mean more
  visibility/render-queue work, which could cause uneven frame timing. This is a
  performance candidate, not evidence of incorrect midpoint math. Removing the
  pre-update would risk reintroducing the already diagnosed location error.

## App layout review

The shared stage defers origin rebasing and extent shrinking while PDF contacts
are active. It does not calculate scale or pinch displacement. Left cards and
comments no longer change the canvas centering width, and highlights resize with
their page. No additional app scale interpolation or page-navigation handler was
found in the ordinary pinch path. That narrows the investigation but does not
exclude Safari compositing or a missed contact lifecycle in a physical run.

The November 3 investigation used source inspection only. The November 4 follow-up
added the focused disposable trace above, rather than rerunning the broad suite.
Percentage rounding, touch thresholds and delayed redraw are real secondary
mechanisms; none is needed to produce the isolated 44px position error.
