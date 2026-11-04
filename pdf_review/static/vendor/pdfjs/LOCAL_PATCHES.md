# Local PDF.js viewer patch

Base: PDF.js **6.4.299**, build **d0991a0d5**. Only `web/viewer.mjs` is modified.
Rendering core, worker, TouchManager, CSS, license and security policy are unchanged.
Pristine module SHA-256:
`3e229a3c44633df56690108b873ff572f642f9d301b70820f01ef535ebeac781`.

`../../../vendor_patches/pdfjs-6.4.299-atomic-zoom.patch` records the exact local
diff, with paths relative to the `vsff_website` repository root. After restoring
the pristine 6.4.299 assets, it can be checked/applied from that root using
`git apply --check pdf_review/vendor_patches/pdfjs-6.4.299-atomic-zoom.patch`
and the same command without `--check`.

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
it; the app's existing blur/visibility/contact cleanup clears it too. This also
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
