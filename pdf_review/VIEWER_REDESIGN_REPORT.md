> **Current refinement:** [VIEWER_REFINEMENT_REPORT.md](VIEWER_REFINEMENT_REPORT.md)
> supersedes this original pass for rail placement, minimized markers, menus,
> search presentation and the shared application shell. This report retains the
> original audit and verification history.

# Viewer redesign — local work

## Pre-edit architecture audit

- Flask renders `viewer.html` independently of `base.html`; document/account/access/admin
  use the shared base. C1 changes were already unstaged at task start and are retained.
- `app.css` owns every server-rendered surface, with duplicated viewer grid/header rules
  from successive slices (330/370px sidebar, 54px header). Account/access styles are
  appended at the end. `anchor_overlay.css` alone is injected into the PDF iframe.
- Shell: parent header → iframe + full-height independently scrolling review panel.
  Review panel contains status, filter, presence, migration, composer, threads, diagnostics.
- PDF.js: same-origin unmodified vendored viewer HTML/CSS/module, native toolbar and
  secondary menu, search, views manager, text/annotation/editor layers. Its
  `webviewerloaded` event reaches the parent before `PDFViewerApplication.run`.
- Comments: `anchors.js` coordinates `ReviewState`, thread/anchor HTTP APIs,
  `thread_sidebar.js`, `SelectionCommentComposer`, `AnchorOverlay`, migration UI,
  `ReviewRealtime`, refresh coordinator and presence. Thread/reply/edit forms preserve
  drafts across canonical refreshes. Resolution, revision conflict and own-author rules
  are existing behaviors to retain.
- Selection → `captureTextSelection` validates PDF text layers and serializes canonical
  PDF rectangles, text offsets/context, schema and page metadata. Geometry conversion
  handles viewport rotation. Thread POST atomically persists anchor + initial comment;
  selecting text or opening/canceling a composer performs no write.
- Overlay maps canonical rectangles through current PDF viewports; navigation uses
  PDF.js destinations. Realtime fetches canonical HTTP state after authorized events,
  preserves drafts, retries reads and reconnects; presence tracks page changes.
- Existing browser harness uses Chrome DevTools with disposable synthetic PDFs,
  identities, SQLite, signed fixture sessions and real Socket.IO/WebSocket transport.
  Unit suite covers authorization, immutable storage, exact-version anchors, comments,
  migrations, C1 and deployment configuration. Existing responsive viewer rules only
  reduce sidebar width; they do not provide a document-first mobile fallback.

## Reference principles

Original implementation; no Google/Adobe assets or source copied. Public references:

- [Google comment interactions and visibility](https://support.google.com/docs/answer/65129)
- [Google expanded/minimized/hidden comments](https://workspaceupdates.googleblog.com/2024/02/manage-comments-faster-google-docs-sheets-slides.html)
- [Adobe panel organization](https://helpx.adobe.com/indesign/desktop/get-started/settings-and-preferences/customize-panels.html)
- [PDF.js viewer options](https://github.com/mozilla/pdf.js/wiki/Viewer-options)

Apply compact control groups, flat surfaces, contextual selection actions, spatially
associated comments and collapsible panels. The repository's vendored code is
authoritative for integration details.

## Implementation

### CSS organization, tokens and density

Before: one accumulated `app.css`, duplicated header/grid/sidebar definitions and
breakpoint overrides, plus iframe overlay CSS. After:

| File | Ownership |
| --- | --- |
| `static/app.css` | Shared stylesheet entry point; three imports |
| `static/styles/tokens.css` | System font, existing semantic colors, 13/11px UI scales, 30px controls, 4/8/12px spacing, 264px comments, layer levels |
| `static/styles/base.css` | Existing server-rendered pages, shared controls/forms/focus and migration history |
| `static/styles/account.css` | Existing C1 account/access/admin layout and mobile rules |
| `static/styles/viewer.css` | Compact application chrome, menus, workspace, rail/drawer positioning, composer, contextual action and viewer breakpoints |
| `static/styles/comments.css` | Thread content, edit/reply/resolution, migration tools, deliberate anchor diagnostics |
| `static/styles/pdfjs.css` | Thin app-owned iframe integration; native toolbar visibility, popup placement, document workspace insets |
| `static/review/anchor_overlay.css` | Existing canonical highlight presentation |

Removed obsolete fixed-sidebar/header rules, reviewer-creation dialog/control styles,
empty thread-panel presentation and the unused sidebar scrolling helper. No
`!important` layer. C1 selectors and form behavior are retained. The viewer has
12–13px system text, 11px metadata, flat 30px controls (32px on phone), 1px borders,
3px card corners and small functional gaps. Desktop header measures about 43px.
The measured header height drives workspace height without feeding its own minimum
height, so resizing back from phone restores desktop density.

### Unified toolbar and native control classification

Parent shell owns the only visible toolbar. It groups document/version/back,
pages/outline, search, previous/page/total/next, zoom, View, comment visibility,
collaboration count and identity. View/identity use native accessible disclosures.
Icon controls have accessible names, focus outlines and tooltips. Search delegates
to the native find bar; Ctrl/Command+F from the parent also opens it. Native keyboard
handling within the PDF remains available. Escape and outside clicks close menus.

| Native control or family | Classification | Result |
| --- | --- | --- |
| Page number/total, previous/next | MOVE | Compact parent controls; native handlers/PDFViewer properties |
| Zoom out/in, scale, auto, fit page, fit width | MOVE | Parent toolbar; native PDFViewer scale |
| Search, previous/next match, case/diacritics/whole word/highlight-all/results | KEEP / MOVE | Parent search action; existing native search popup and internals |
| Pages/thumbnails, outline, attachments, layers, current outline item | KEEP / MOVE | Parent navigation button; existing views-manager popup |
| First/last page, rotation clockwise/counterclockwise | MOVE | Parent View menu, existing native buttons |
| Selection/hand tool | MOVE | Parent View menu, existing native handlers |
| Vertical/horizontal/wrapped/page scrolling | MOVE | Compact View selector; native scroll mode |
| None/odd/even spreads | MOVE | Compact View selector; native spread mode |
| Presentation, properties | MOVE | Parent View menu; native behavior |
| Print/download, including secondary duplicates | MOVE / HIDE | One parent View entry each; hidden native duplicates remain wired |
| Open local file | REMOVE FROM NORMAL UI | Cannot replace the exact-version source under existing review anchors |
| Free text, ink, highlight, image/stamp, signature, native comment editors | REMOVE FROM NORMAL UI | Editor mode disabled before initialization; editor controls/properties hidden |
| Editor alt-text, signature/comment dialogs, undo, floating editor controls | HIDE | Native editing unavailable; dormant vendor implementation retained |
| Page insertion/import/copy/cut/delete/export/manage editing actions | REMOVE FROM NORMAL UI | Native page mutation controls hidden; useful page navigation remains |
| Native secondary toolbar/toggle and redundant separators | HIDE | Viewing operations accessible through parent View menu |
| Source PDF annotation/signature rendering | KEEP | Rendering layers retained; app does not edit source annotations |

No vendored PDF.js file changed. `viewer_bootstrap.js` registers before iframe load,
checks the event's source window, uses PDF.js's explicit pre-run hook, disables the
native editor and injects app CSS. Native preferences are disabled deliberately:
this vendor version warns that stored preferences can override manually supplied
editor options. PDF.js viewing commands still work; native preferences are not
restored between visits. This avoids a stored competing editor model. On a vendor
upgrade, retest the hook, options, native control IDs, popup structure and spread
DOM membership. No rendering/navigation fork or new dependency was introduced.

### Selection action and composer

The former yellow toolbar Comment button is now a small original outlined balloon
icon next to valid PDF selections. `captureTextSelection` remains unchanged and
validates text layers; the temporary button/composer geometry maps its canonical
rectangles through current PDF viewports. Multiline rectangle bounds, rotation,
zoom, scroll and viewport clamping do not alter anchor serialization. Button
placement stays within the browser viewport; selections outside the PDF do not
activate it. Clearing selection, Escape and clicking elsewhere dismiss it.

Ctrl+Alt+M / Command+Option+M opens the same composer. The composer opens in the
rail (drawer on constrained layouts), retains the canonical payload while editing,
and posts through the existing atomic thread API. Cancel/Escape performs no write.
Ctrl/Command+Enter submits. Duplicate submission and cancellation during a pending
write are guarded; invoking the shortcut on an open composer retains its draft.
Failed writes retain content for retry. Existing drafts, replies, revision conflicts,
author-only edits, resolution history, migration and exact-version targets remain.

### Rail layout, collisions, active threads and performance

`CommentRail` in `viewer_shell.js` owns temporary layout. It derives a thread's
position from its effective anchor's first segment using `pdfRectangleToCss` and
the current page viewport, sorts by page/visual y/thread ID, and places each card
at `max(anchorY, previousCardBottom + 6)` separately in each outside rail. This
keeps ordering deterministic and avoids overlap, including neighboring anchors.
The composer acts as an obstacle in the right rail. Existing cards are content-sized;
only the active thread exposes its reply form. Active threads have a restrained
border/background; clicking navigates through the existing overlay destination.
After that navigation, displaced active cards are brought into view if necessary.

The primary PDF scrollbar translates cached rail positions. Render, rotation, zoom,
mode and resize changes schedule a single animation-frame layout pass. A current-page
geometry signature detects real content-layout changes without laying out every
thread on every scroll. ResizeObserver observes workspace/scroller/card dimensions;
removed cards are unobserved. Scroll work updates one translation, the current
selection control and, when open, the composer. Overlay full renders are coalesced
as well. There is no scroll listener per thread or mousemove layout loop.

Rails reserve 284px for expanded 264px cards, or 48px for minimized markers, only
while populated or composing. Empty/hidden comments reserve zero width. The PDF
centers in the remaining document area, keeping page plus comments balanced. A
trailing spacer makes collision overflow reachable using the document scrollbar.

Actual PDF spread membership chooses outside-left for a left page and outside-right
for a right page. An isolated cover page uses the right rail. Below 1700px, spreads
fall back to a shared drawer; fixed zoom also falls back when pages plus rails do
not fit. Single-page rails use a 1050px minimum workspace; fit/auto zoom can resize
to the usable area, while large fixed zoom retains document space and uses a drawer.
At 700px and below the toolbar wraps and controls have 32px minimum height; 1050px
also compacts title/identity metadata. Shared non-viewer C1 breakpoints remain.

Expanded, minimized and hidden modes use one toolbar select. Selecting a marker or
annotation expands its thread. Hidden mode also hides app-owned thread highlights;
ordinary source PDF annotations remain. Empty reviews have no empty-state card,
presence section or full-height sidebar. The small Open/All filter appears only
when comments exist. Presence moves into a participant count and named popover,
with live/offline status, current pages and visible offline coloring. Its transport,
authorization and reconnect logic are unchanged. Anchor tools require the deliberate
`?debug=anchors` URL toggle; diagnostics code and save/delete test tools remain.

### Accessibility and security

Semantic controls/disclosures, labels for page/zoom/modes/comment/reply text,
keyboard comment creation/submission/Escape, visible focus, live status announcements
and reduced-motion rules are included. The contextual action is a real focusable
button, and its keyboard shortcut avoids depending on pointer hover. Density does
not remove account/admin/logout access or native document navigation.

This slice changes no backend route, auth policy, database migration, storage or
Socket.IO room policy. OIDC/allowlist/CSRF/ACL/GET-HEAD-Range authorization, immutable
blobs, exact-version anchors, transaction semantics, post-commit events, reconnect,
revision conflicts and C1 behavior remain covered by the existing suites.

## Files changed by this slice

Existing C1 working-tree changes were present before this work and remain unstaged.
This slice modifies `.gitignore`, `pdf_review/README.md`, `ARCHITECTURE.md`,
`templates/viewer.html`, `static/app.css`, and these `static/review/` modules:
`anchors.js`, `anchor_overlay.js`, `comment_composer.js`, `presence.js`,
`realtime.js`, `thread_sidebar.js`; plus `tests/browser_sanity.py`.

New: this report; `static/styles/{tokens,base,account,viewer,comments,pdfjs}.css`;
`static/review/viewer_bootstrap.js`, `viewer_shell.js`; and
`tests/viewer_acceptance.py`. Screenshots are ignored under `tests/visual-artifacts/`.

## Verification

- Project interpreter: `.venv/Scripts/python`. The initial global-Python attempt
  failed imports because it lacks Authlib; the existing project environment works.
- Full unit suite: `python -m unittest discover -s tests -q` — **135 passed**.
- `python -m pip check` — **No broken requirements found**.
- Existing browser/WebSocket suite and added redesign checks — passed against
  disposable synthetic PDFs, identities, SQLite and offline provider-boundary fixtures.
  Real WebSocket-only authentication/rejection and room join, two browser sessions,
  presence/page changes, remote thread/reply/edit/tombstone, stale-edit conflict,
  resolve/reopen/history, reconnect/refetch, room isolation, migration carry/re-anchor,
  historical targets, skip/completion and all existing C1 workflows remain exercised.
- Added browser checks cover parent navigation/page/zoom/search/rotate/scroll/spread
  controls, disabled native editing, selection/cancel/Escape/keyboard creation,
  application-UI selection rejection, canonical capture at 50/100/150/200% and 90°,
  visibility/empty-width rules, nearby collisions, active visibility, resize and
  opposite left/right outside-rail association. No uncaught browser exceptions.
- **27 ignored synthetic screenshots**: empty, populated single-thread case, many
  nearby threads and spread at 1440×900, 1280×800, 1024×768, 768×1024 and 390×844;
  contextual composer; 1900×1000 outside rails; populated zoom/rotation states.
  Rendered screenshots were visually inspected at all five requested sizes and wide
  spread, including composer placement and zoom. Inspection found and corrected
  residual native toolbar controls, a responsive header-height feedback loop and
  stale workspace geometry. Desktop toolbar is compact, cards do not overlap,
  no-comment screens have no blank comments column, and constrained layouts retain
  the PDF with an overlay drawer rather than shrinking it into a narrow column.
- Restricted Chrome crashed before DevTools handshake; the permitted local harness
  outside that sandbox completed. Its owned browser/server processes are torn down.
- Changed/new source scan: no private-key headers, common provider tokens, credential
  URLs, real Google client IDs, non-example email addresses or private/runtime files
  found. Screenshots are synthetic and Git-ignored. This is a scoped scan, not a
  guarantee against every secret format. Runtime `.env`, private PDFs and production
  data were not read or modified.
- Git diff/whitespace review: clean. No vendor, infrastructure, frontend/backend,
  OAuth, Cloudflare, SSH, Apache or systemd changes by this slice. Nothing staged,
  committed, pushed or deployed.

## Limits and remaining tradeoffs

- Dense same-anchor conversations cannot all remain vertically adjacent to the
  same text without overlap. Cards shift downward in document order; revealing a
  heavily displaced active card can scroll its anchor outside the viewport. Markers
  or hiding comments provide a compact alternative. No decorative connector lines.
- Drawer scrolling is intentionally independent only when viewport/zoom/spread
  constraints prevent rails. Expanded drawer content overlays part of the PDF;
  use Minimized/Hidden for document focus. Phone chrome uses multiple compact rows.
- No real iPad/touch hardware, Safari, native screen-reader audit, production data
  or real Google/Adobe account was exercised. Device coverage uses Chrome viewport
  emulation. Browser fixtures have synthetic two-page PDF content, not a large
  production-document performance benchmark.
- Native PDF.js preferences are disabled as described above; viewer choices are
  functional for the current session. App comment visibility is session-local.
- Rails use the first canonical anchor segment for a multi-page thread's card;
  existing highlights still render all segments. A selection composer follows its
  document anchor when scrolling; narrow layouts keep it in the drawer.
- No production or deployment compatibility claim beyond the existing local suite.
