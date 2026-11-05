# Version statistics — BETA C2

The tool is now named **Statistics** (previously Version statistics). Its comment
bar segments match PDF highlight opacity: 28% normally, 38% on hover and 44% for
the current or keyboard-focused bar, while retaining each author's own color.

Tools > Statistics reuses the existing `properties` LeftCard identity so
saved card positions, open/pinned state, Tools checkmarks and close behavior survive
the rename. Pages/Sections and metric choices are remembered per account/version.
Density is replaced by Comments. The four metrics are Words, Read time, Images
and Comments; integer axes and always-on gridlines remain.

Pages retains the narrow histogram, actual section brackets, page ticks, native
navigation and current-page/spread highlighting. Sections displays one bar per
mapped section, with Unsectioned for uncovered content (including PDFs with no
mapped sections). Switching metrics patches the existing SVG bars; grouping
changes only the row layer. Section definitions remain the existing placements.

## Comment counts and colors

Counts include non-deleted messages and replies in accessible conversations,
including resolved threads and exact-version section thoughts. Each message uses
its actual author's review color, not the root conversation author's color.
Bar width is the total count and colored segment widths are proportional to each
author's count. Tooltips/captions give totals and author breakdowns; a small legend
identifies colors. A current-page outline preserves reviewer colors.

Multi-page highlighted conversations count once at the first segment/location.
Section conversations attach to their own section and its end page, including
linked page borders. Deleted-message tombstones and empty response placeholders
do not count. Existing canonical thread/review-context refreshes supply counts:
privacy, isolated review, document access and reviewer filters are still enforced
server-side. Expanded/hidden comment display and the local resolved toggle do not
change statistics. Existing websocket invalidations refresh counts and colors;
there is no extra statistics polling, endpoint, or cached copy of conversations.

Thread message `author` and section message serialization now include the actual
author's existing `review_color`. Old-schema offline thread tests retain their
existing color fallback. There is no migration or database schema change.

## Words, estimates and section aggregation

The shared PDF.js extraction still counts the joined text runs with the existing
word segmenter and cooperative work yields. It also records numeric word counts
at text-run vertical centers, without retaining text. Section grouping assigns
these positions using the canonical PDF-space section boundaries, so a page
split between two sections does not duplicate all its words in both groups.
Positions have six decimal places; words on a boundary use the text run's center.
Images use the transformed illustration/placement vertical center. These are
layout assignments, not semantic paragraph or object ownership detection.

ERT retains the existing 400 WPM / 5-second per-page minimum policy and is distinct
from actual tracked time. For partial pages the existing page time budget is shared
by the assigned word counts (by covered area for blank pages), with integer largest-
remainder allocation. Page and section totals therefore agree, including gaps.
Missing extraction stays unavailable; partial known totals say Subtotal.

## Vector illustrations

PDFs do not retain SVG file identity. The PDF.js operator list exposes raster
painting, vector paths, forms and marked-content tags. The count now treats an
outer tagged Figure containing painted paths/images as one illustration, including
nested vector figures, raster tiles and placed PDF artwork. Ordinary page
backgrounds, rules and untagged vector decorations are not counted as illustrations.
Supported raster placements/repeats/groups outside a Figure retain placement counts.
Annotations are excluded; unsupported nested tiling/color patterns and extraction
failures remain unavailable. This is not a count of unique original image files.

Read-only inspection of the local Vena Book 1 PDF found chapter artwork tagged
Figure / PlacedPDF. The first 30-page check reports three figures on page 9 and zero
images on the following ordinary text pages, rather than counting dozens of drawing
paths or the full-page background as extra images. Untagged vector artwork cannot
be reliably distinguished from decorations and is explicitly excluded in the UI.

### Book 1 count diagnosis: clipped edge fragments

A later read-only scan of all 191 pages reproduced the reported section counts.
The Sunset Girl (pp. 9–33) has three figures, all on page 9. The Storm and The Dream
(pp. 36–52) has three on page 36 plus one on page 37. Emissary (pp. 80–94) similarly
has three on page 80 and one on page 81; Questioning Evil repeats this on pp. 112–113.
The extra figure is a duplicate of the opening page's bottom decoration, with the
facing-page clip spanning only x=0 to x=0.25 points and y=0 to y=132.48 points.
Rendered pages 36/37 confirm that this is not another full illustration in the text.
It is consistent with a spread-edge/export fragment, rather than a fourth SVG asset.

The current counter counts a painted Figure even when almost all of its artwork
is clipped away. It tracks transforms and painted bounds but does not intersect
all PDF clipping paths. Thus three intended illustrations can produce four counted
figure placements. A correction needs visible/clipped extent handling and an
explicit policy for negligible edge fragments; simply deduplicating identical SVG
art across pages would incorrectly merge intentional repeated illustrations.
This diagnostic did not change production counting or modify the PDF/review data.

The displayed Subtotal 31 was also reproduced: Lines in MinSet is unavailable
because page 139 contains a tiling-pattern fill (`setFillColorN`). Its unknown
section is excluded from the subtotal by the existing conservative policy.

## Cache and performance

Calculation schema 2 invalidates previous raster-only metadata once. IndexedDB
continues to hold only numeric PDF metadata per account, immutable version,
fingerprint and page count: word/image totals, physical page area and numeric
position/count pairs. It never stores extracted text, image bytes, PDF bytes,
comments or reading history. Existing bounded eviction and memory fallback remain.
Section edits and comment changes do not re-extract immutable PDF data.

Pages aggregation uses direct page totals; Sections pre-indexes page overlaps and
uses binary lookup for text/image positions instead of comparing every item with
every section. Stable DOM/revision signatures and changed-attribute patching remain.
Comments requires no PDF text/image scan. PDF.js, zoom, comment layout and tracking
timing/leases are unchanged. No chart dependency or new dashboard was introduced.

Focused checks cover 138 pages, mixed page sizes, a blank page, repeated raster
images, a multi-path tagged vector figure and an Artifact background; shared cache
reuse; author colors and 2:1 stack proportions; live reply counts without replacing
bars; Pages/Sections restoration; navigation/current-page feedback; unknown images;
partial-page/gap totals; nested figures and deleted/duplicate messages. Additional
checks cover existing reading cards, Tools and Firefox metric-switch responsiveness.
These browser checks do not claim physical iPhone testing.

All completed checks passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe tests/browser_sanity.py --page-properties
.\.venv\Scripts\python.exe tests/browser_sanity.py --reading-ui
.\.venv\Scripts\python.exe tests/browser_sanity.py --tools-menu
.\.venv\Scripts\python.exe tests/firefox_page_properties.py
```

Backend suite: 181 tests. Firefox's six cached switches, including Comments,
took 3–8 ms synchronously, kept all 138 bar elements and made zero chart mutations
when reselecting the current metric. An initial reading-card run timed out during
Close all tools; its focused rerun passed. This is not an iPhone success claim.
The normal local app was restarted and `/healthz` returned HTTP 200 at
http://127.0.0.1:5000/. No real versions/review data were deleted or changed by the
checks; the real-book artwork inspection was read-only.

Changed files for this refinement:

- `static/review/page_properties_card.js`, `page_properties_data.js`, and new
  `version_statistics.js`; `static/styles/page_properties.css`.
- `static/review/anchors.js`, `templates/viewer.html`, `review/threads.py` and
  `review/section_feedback.py`.
- `tests/page_properties_acceptance.py`, `firefox_page_properties.py`,
  `test_beta_c2.py`, and new `version_statistics_acceptance.py`.
- `README.md`, `ARCHITECTURE.md`, `PAGE_PROPERTIES_REPORT.md` and this report,
  all under `pdf_review/`. The repository root README was not edited.

Density was removed because equal-sized pages reproduce the word-count chart.
A possible future replacement is **text coverage**: the union of text-run areas as
a percentage of the visible page. That would show whitespace/layout differences,
but needs rotation-aware rectangle union and a clear policy for large typography;
it is not presented as another word-density number here.
