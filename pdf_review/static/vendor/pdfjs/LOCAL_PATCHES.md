# Local PDF.js viewer patches

Base: PDF.js **6.4.299**, build **d0991a0d5**. Only `web/viewer.mjs` is modified.
Rendering core, worker, TouchManager, CSS, license and security policy are unchanged.
Pristine module SHA-256:
`3e229a3c44633df56690108b873ff572f642f9d301b70820f01ef535ebeac781`.

`../../../vendor_patches/pdfjs-6.4.299-atomic-zoom.patch` records the exact local
diff, with paths relative to the `vsff_website` repository root. After restoring
the pristine 6.4.299 assets, it can be checked/applied from that root using
`git apply --check pdf_review/vendor_patches/pdfjs-6.4.299-atomic-zoom.patch`
and the same command without `--check`.

After the atomic-zoom patch, apply
`../../../vendor_patches/pdfjs-6.4.299-detail-loading.patch` (also relative to the
repository root). It separates loading-indicator ownership from detail rendering.
Then apply `../../../vendor_patches/pdfjs-6.4.299-pinch-camera.patch`.
All three patches modify only `web/viewer.mjs`.

## Physical iPhone stale scroll rollback (November 8, 2026)

The supplied 191-page Safari trace contains 116 scroll events during pinch that
return to an exact earlier scale transaction's position, differing from the
latest transaction by more than 100px (maximum 9,329px). At 8893ms the scale is
0.88 and scrollTop is 78,851; at 8895ms it reverts to 83,190, the position from
scale 0.93. The previous patch then resampled that stale camera at the current
scale. This amplified the rollback across later zoom steps and distant pages.

An active native gesture now retains its last requested camera, clamped to real
scroll limits. Both zoom and midpoint-only pan use it. Native scroll updates
reconcile delayed positions while that gesture owns the camera; gesture end
reconciles once and discards ownership. Ordinary scrolling after release is
unmodified. `zoomscrollreconciled` records observed/intended offsets for opt-in
diagnostics. There is no CSS workaround, new recognizer, or delayed scroll lock.

Run `--zoom-rollback` to inject the observed ordering on pages 1/109/120 in all
four display modes, with repeated zoom/pan, stationary-contact reconciliation,
gesture release and free post-release scrolling. This tests the failure
mechanism in Chrome, not the iOS scrolling process. Physical Safari must verify
whether any late rollback after ownership ends still requires follow-up.

## Detail redraw loading indicator (November 8, 2026)

`PDFPageDetailView` shares its base page's `div` and inherits the base rendering
state setter. Every detail redraw consequently added `loadingIcon`/`loading` to
an already rendered page. Native panning changes the visible detail area and
restarts that lifecycle. The mobile 5,242,880-pixel canvas cap and high DPR make
this path more common. Six native detail redraws in the regression fixture all
set the indicator while the base page was FINISHED.

`loadingIconDiv` now identifies the indicator owner. Base pages retain their
indicator; detail views return null and cannot set or clear the base indicator.
Canvas creation, detail sharpness, cancellation, timing, render queues, memory
limits and gesture calculations are unchanged. No CSS hides initial loading.
Verify with `tests/browser_sanity.py --detail-loading` or `--zoom-layout`.

## Why this lives in the viewer

The native scale transaction previously restored scroll offsets and then applied
the gesture-origin pan. Browsers could clamp the intermediate restoration and
discard up to tens of pixels before the final, otherwise valid pan. Both native
`#setScaleUpdatePages` and fractional `#panPosition` are private; an app-level
replacement would need duplicate geometry, DOM scroll-accessor interception or
a second corrective scroll. This patch keeps the transaction in its native owner.

Before page dimensions change, current page geometry identifies a PDF-space
reference for the supplied origin. An on-paper origin selects its page;
background, borders and gaps use the nearest attached page, including offscreen
pages. Coordinates extrapolate outside that page without snapping to an edge.
Native destination conversion restores the point at the new scale. The scroll helper combines restoration and native pan
before assigning each scroll axis once. The requested final floating-point
position updates native fractional pan state, including when the real final
position is clamped by the browser. Subsequent pure panning still uses `panBy`.

The native application's TouchManager callbacks begin/end a gesture reference.
The reference page stays fixed until the gesture ends, even if page edges pass
under the midpoint; each step samples the actual camera in that same plane so
final scroll limits cannot accumulate error. End/cancel and document reset clear
it; the app's existing blur/visibility/contact cleanup clears it too. Since the
pinch-camera follow-up, the sampled camera is the gesture's clamped requested
position rather than a potentially stale browser scroll offset. This also
prevents reuse of stale visible-page location when all pages are offscreen.
Origins without any attached page retain camera position rather than navigating
to an old page. Non-origin navigation and toolbar zoom,
same-scale panning, rendering/scale limits and genuine final scroll limits retain
their native paths. No page counts, card dimensions or assumed row widths enter
the calculation. Cards continue to report bounds to the independent app stage.

The upstream source map is retained as an upstream asset, but its directive is
removed from this modified module so debugging uses the actual local code.

## Upgrading

Treat the patch as version-specific. Compare the replacement viewer's native
zoom/scroll implementation and remove the patch if upstream already provides
equivalent behavior. Otherwise port the source-level changes deliberately; do
not blindly carry a generated bundle diff onto another release. Recreate the
patch and run `tests/browser_sanity.py --zoom-layout` with the project Python.
That check includes the small-page/overflow transition, mixed page sizes, later
pages, rotation, wrapped rows, spreads, card states, reversals, entirely offscreen
background, gap crossing, gesture reset and browser touch across a divider.
Physical iPhone Safari validation remains separate from Chrome automation.
