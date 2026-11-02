# C2 management interaction refinement

## Fixed Sections panel follow-up

Sections now uses a compact non-modal panel fixed to the left of the PDF. Controls
scroll independently, and PDF scrolling leaves the panel in place. Opening it
shows labeled start/end lines for every mapped section, with the selected section
emphasized. Closing it removes these extra lines. Boundary editing keeps the panel
open; document-page entry opens the current PDF with the panel. Settings and outline
confirmation retain their dialogs.

Focused browser checks passed panel CRUD, outline import, all boundary lines, fixed
position during PDF scroll, boundary save/Cancel, close/focus and document entry.
Screenshots at 1440 and 768 pixels were inspected. All 160 existing unit tests
passed; the whitespace check passed. Backend and dependencies are unchanged. The earlier dialog implementation notes below are historical.

## Earlier refinement

- **Dialogs:** `dialogs.js` supplies a small native `<dialog>` shell with four
  size choices, accessible titles, native focus trapping, safe Escape, focus
  restoration, busy states and explicit destructive confirmation. Shared CSS uses
  the existing compact controls and tokens.
- **Review Settings:** opens over the document/viewer, fetches one Jinja form
  fragment and saves asynchronously through the existing owner service and CSRF.
  Errors retain the form/input. Success closes without changing the page URL.
- **Sections:** a workspace dialog offers an ordered master list and inline detail
  inspector. Selection/arrow keys update details; Add focuses a temporary Name
  editor; Save, up/down ordering and confirmed archival use existing section APIs.
  Name/prompt drafts survive selecting another section within the workspace.
- **Outline:** the existing PDF.js extraction/confirmation flow uses a secondary
  shared dialog, then refreshes and returns to Sections. Nested entries are indented;
  server validation and atomic import are unchanged.
- **Boundary handoff:** the workspace hands the selected section to the existing
  viewer strip. Done commits pending boundaries and returns to the refreshed same
  selection. Cancel/Escape discards unsaved preview geometry. The initial document
  page has no PDF canvas, so it temporarily hosts the existing viewer in an iframe
  workspace; checked same-origin/source return messages preserve the outer URL.
- **Responsive/visual:** the master/detail workspace fits laptop/tablet sizes,
  stacks below 650px, and scrolls within viewport bounds. Six ignored synthetic
  screenshots were opened and inspected: Settings, Add, detail, outline, boundary
  strip and return-to-workspace, at 1440×900, 1024×768 and 768×1024.
- **Files:** new `static/review/{dialogs,management,sections_workspace}.js`,
  `static/styles/dialogs.css` and `tests/management_acceptance.py`; updates to
  base/document/viewer/settings templates, viewer management controllers,
  `review/review_routes.py`, browser harness/C2 UI selectors, README and ARCHITECTURE.
  The obsolete standalone Sections template and page-only manager JS are removed.
  The settings route now supplies its form fragment; Sections supplies owner-scoped
  JSON. No second standalone management UI is maintained.
- **Checks:** existing unit suite run once: **159 passed**. Focused browser checks
  passed asynchronous settings success/failure, no navigation, focus/Escape,
  master/detail keyboard selection, add/edit/reorder/archive, outline confirmation,
  boundary Done with an actual placement save, Cancel, same-selection restoration,
  and the document-shell iframe handoff. No uncaught browser exceptions. Git
  whitespace check passes. Dependencies are unchanged; `pip check` and the broad
  C2 browser/security/screenshot matrix were not repeated.
- **Limits:** native dialog support is required; testing uses Chrome viewport
  emulation, not physical Safari/iPad hardware. Account, Admin, login, document list
  and general document pages remain ordinary pages. C2 schema, services,
  authorization, privacy, colors, presence and feedback semantics are unchanged.
  Everything remains local, unstaged and uncommitted; nothing was deployed.
