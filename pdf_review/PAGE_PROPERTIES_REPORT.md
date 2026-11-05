# Page Properties — BETA C2

Historical initial implementation and Firefox follow-up. The card is now
**Version statistics**; Density has been replaced by Comments, Pages/Sections
grouping is available, and tagged vector figures are included in Images.
See [the current report](VERSION_STATISTICS_REPORT.md) for behavior and checks.

Tools > Page properties opens one compact shared left card. The mockup's narrow
vertical histogram has one thin horizontal bar per PDF page, a numeric top axis,
subtle page ticks, always-on gridlines, real section-range brackets and a summary.
Its layout uses the same card typography/pin/close controls as the existing tools.
Section labels pack separately when crowded; bracket endpoints keep the real
page/fraction coordinates. PDFs with no mapped sections use the full chart width.
Long documents grow vertically, preserving the existing content-height card rule.

Hover/focus exposes the precise page/value in the native tooltip and small caption.
Click/Enter navigates with native PDF.js; arrow keys move focus between bars.
Current page/spread highlighting reuses the existing presence page selection.
Metric switches keep the card and SVG page rectangles, updating bar widths, labels,
axis and summary. Pin/drag/reveal/close-all/checkmarks/restoration use LeftCard.
Metric choice is remembered per account and exact version; obsolete gridline
preferences are ignored.

| Metric | Definition and limits |
| --- | --- |
| Words | PDF.js text content, same word segmentation as reading analytics. Total, mean and densest/sparsest pages; no OCR. Blank/image-only text layers count as zero; extraction failure is unavailable. |
| Read time | `max(5 seconds, ceil(words × 60 / 400))`, using the returned reading policy. Estimated page time, never actual reader dwell. Total is the sum of per-page estimates, including page minimums. |
| Images | Raster painting placements from the vendored PDF.js operator list, including supported inline/external/grouped/repeated images and masks. Reused images count per placement. This is not unique assets or semantic illustrations. Vector artwork and annotations are excluded. Tiling/color patterns can contain nested images, so those pages are conservatively unavailable rather than undercounted. Failed extraction and XFA are unavailable. |
| Density | Words per 100 cm² of visible CropBox/view area, normalized to the highest known page = 100%. Different page sizes, crop geometry, rotation and PDF UserUnit are respected. No guessed margins or OCR. All-empty documents stay at 0%. |

Unknown pages have a distinct short outlined mark and are excluded from computed
averages/extrema. Incomplete totals are labeled Subtotal. Ties select the first page.
Section definitions remain authoritative and live placement/name edits update the
brackets; no duplicate section model is stored.

`page_properties_data.js` is shared by the new card and ReadingTracker. Per-page
in-flight work is deduplicated. Opening the card scans text at concurrency two;
image extraction starts only when Images is selected. Work yields between pages;
progress drawing is throttled. Chart rendering never extracts PDF content.

IndexedDB caches only numeric page metadata (word count, physical area and raster
count), keyed by calculation schema + account + immutable version + fingerprint +
page count. It retains at most 12 recent version records. Raw text, PDF bytes,
images, comments and reader history are never copied into this cache. Cached data
is read only after the normal authenticated PDF viewer loads. Quota/disabled-storage
failures use memory caching. Section edits do not invalidate immutable page metrics;
future calculation changes should increment the metadata schema key. Tracking
continues using its existing server validation, caps and leases.

No server routes, database changes, historical migration edits, auth exceptions,
chart libraries or PDF.js/zoom changes were added. New code lives in
`static/review/page_properties_{card,data}.js` and `static/styles/page_properties.css`;
viewer integration changes are limited to `anchors.js`, the template/Tools entry
and ReadingTracker's shared word-count path.

Focused checks:

```powershell
.\.venv\Scripts\python.exe tests/browser_sanity.py --page-properties
.\.venv\Scripts\python.exe tests/browser_sanity.py --reading-ui
.\.venv\Scripts\python.exe tests/browser_sanity.py --tools-menu
```

All passed. The properties fixture contains 138 pages, differing physical sizes,
a blank page, repeated raster images and five chapter ranges. It checks all four
metrics, unknown/grouped image handling, persistent cache reuse without text
extraction, stable SVG nodes, bar navigation/current-page feedback, restored metric and always-on gridlines, no-section PDFs and shared Tools behavior. Existing reading tests
verify timing and UI-state behavior after sharing extraction. Rendered visuals were
inspected in ignored `tests/visual-artifacts/page-properties-{words,images,density}.png`.
These browser checks do not claim physical iPhone validation.

Local testing remains at http://127.0.0.1:5000/; no staging, commit, push or deployment.

Implementation reference: [PDF.js PDFPageProxy API](https://mozilla.github.io/pdf.js/api/draft/module-pdfjsLib-PDFPageProxy.html)
for text, viewport and operator-list extraction; exact grouped/repeated painting
arguments were checked against the vendored `pdf.mjs` CanvasGraphics methods.

## Firefox performance follow-up

The small-PDF page-number tick step previously admitted values below one, causing
fractional page labels (including floating-point artifacts). Page ticks are now
integer-only with a minimum step of one. Word/image counts and count/time axis
labels/summary values display whole numbers. Gridlines are always drawn; the toggle
and persisted gridline setting are removed, including old `grid:false` preferences.

The original metric switch rendered synchronously and again when the cached scan
promise resolved. Every pass rewrote every SVG attribute/title/ARIA label and
rechecked focus for every row. Rendering now has a metadata revision/metric/section
signature, skips identical passes, patches only changed attributes, reuses a number
formatter and touches only the old/new highlighted pages. Cached scans skip finished
pages rather than scheduling one timer for each cached row. Large word counts are
streamed over the segment iterator (no full segment/filter arrays) and yield after
an approximately 8ms budget, checked every 256 segments. IndexedDB pruning uses a
timestamp key cursor rather than cloning all twelve cached documents. Cache schema
values are unchanged; IndexedDB version 2 adds only the eviction timestamp index.

Installed Firefox 159 was checked in a separate headless profile with synthetic
2-page and 138-page documents. The exact user warning was not reproduced, so these
changes remove confirmed inefficiencies without claiming the original physical
session was diagnosed conclusively. Five cached metric switches on 138 pages
produced 11,884 observed chart mutations before and 2,184 afterward (about 82% fewer).
Synchronous switch time stayed in single-digit milliseconds in both runs; this is
not evidence of a measured CPU speedup or a guarantee for all real PDFs/extensions.
The dedicated Firefox check also asserts that selecting the current metric causes
no chart mutations, stable bar nodes survive switching, and ticks are integers.

```powershell
.\.venv\Scripts\python.exe tests/firefox_page_properties.py --small
.\.venv\Scripts\python.exe tests/firefox_page_properties.py
```

Firefox automation uses the built-in Marionette protocol against disposable signed
fixture sessions, never the user's browser profile or private PDFs. Script-warning
limits are not disabled. See [Mozilla's performance guidance](https://firefox-source-docs.mozilla.org/performance/bestpractices.html)
and [Marionette protocol](https://firefox-source-docs.mozilla.org/remote/marionette/Protocol.html).
