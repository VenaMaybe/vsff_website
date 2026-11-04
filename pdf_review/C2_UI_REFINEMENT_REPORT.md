# C2 management interaction refinement

## Reading progress spine and reader analytics

Two new opt-in reading tools use the shared card shell and existing live-avatar
page/spread selection source. Migration 11 adds separate consent, total, page,
session, lease and visit tables. Measured active viewing and inferred completion
are distinct; owners inspect consented readers and other roles see only themselves.
Pause/Resume and explicit history erasure are available in the cards. The spine
uses proportional section nodes and collision-packed reader labels; analytics
contains section dwell bars and expandable paged page activity.

See [READING_PROGRESS_REPORT.md](READING_PROGRESS_REPORT.md) for the database
relationships, timing/lease model, privacy rules, focused checks and limits.

## Tools menu close actions and persistent selection

Added Close all tools and a separator above the tool list. Tools stays open via
the existing keep-menu-open attribute. Selecting a closed or inactive tool uses
its registered open/reveal handler; selecting its item again while the card is
active closes it. Close all uses the shared card close lifecycle, including
pinned cards and normal busy guards. No separate card instances or pin/layout
implementation were introduced.

Tools menu interaction preserves left-card active state so pointerdown does not
clear it before deciding whether to close. Clicking elsewhere still dismisses
the menu normally. Updated focused checks cover open/focus/repeat-close, X close,
Close all with a pinned tool, live checkmarks, keyboard/mobile menu behavior and
owner visibility.

## Compact Tools toolbar menu

Added Tools beside View and Comments using the existing disclosure/menu system.
It contains Search document and Filter comments, plus server-rendered owner-only
Review settings and Manage sections. Removed management injection into View and
the Filter comments action from Comments. Existing search icon and shortcuts stay.
Each item calls the existing left-card open/reveal handler; opening an existing
tool focuses/retrieves it rather than closing or duplicating it. Search uses the
existing find.open entry point instead of the PDF.js toggle for this menu action.

LeftCard's shared open/close lifecycle updates aria-checked by stateKey, including
shortcut opens and restored cards. Tools uses the same checkmark styling and
keyboard/dismissal behavior as the other menus, with focus left in the opened
card. Pinning, positions, collision packing and persistence logic are unchanged.
The compact mobile header grid accounts for the extra menu.

Validation: `tests/browser_sanity.py --tools-menu` passes all four actions,
reopening without duplicates, live checks and X closes, native search shortcut,
keyboard navigation, mobile popup bounds and reviewer/owner visibility.
The existing `--six-refinements` check also passes search/filter behavior,
left-card alignment and mobile composer interactions.

## Immediate mobile Cancel action placement

Mobile composer opening saves Add comment's normal corner and viewport size.
Cancel immediately restores that position and shows the action using existing
selection/permission checks. Intermediate keyboard-closing resize/scroll events
keep the saved target, rather than positioning the button above the keyboard.
Normal placement resumes when viewport height returns; width changes, new
selections and reopening the composer reset the override. No timer or movement
animation is added. The closing keyboard can still cover the final corner until
it retracts.

Changed `anchors.js` and existing six-refinement checks. Coverage verifies the
button is immediately unhidden at its pre-composer coordinates on Cancel,
retains those coordinates through viewport events, and resumes normal placement
when the full-height viewport returns. Architecture/mobile notes updated.

## Reverted movement animation and selection-action delay

At the user's request, removed the 140ms composer position transition and the
180ms viewport-settling delay for restoring Add comment after Cancel. Earlier
keyboard clipping, editor sizing and preventScroll focus fixes remain in place.

## Mobile keyboard-opening reveal-scroll jump

The full-height viewport overlay fixed clipping, but a first native textarea tap
could still initiate Safari's focus reveal-scroll animation while app positioning
followed visual viewport changes. That is a separate likely source of the brief
upward overshoot seen before the card settles. WebKit's
[reveal-focused-element code](https://github.com/WebKit/WebKit/blob/main/Source/WebKit/UIProcess/ios/WKContentViewInteraction.mm)
returns before that native scroll/zoom path when focus requests preventScroll.

`comment_composer.js` now handles only the first primary touch on an unfocused
viewport-docked editor: cancel default pointer focus and synchronously call
`focus({preventScroll:true})`. The user gesture still opens the keyboard. Taps
after focus, desktop input and other fields keep their native pointer behavior.
No automatic focus on composer opening, keyboard delay, animation, timer or
document-scroll reset is introduced.

The focused six-refinement regression sends real Chrome touch input and checks
that first focus uses preventScroll, a subsequent pointerdown remains uncanceled,
and previous clipping/draft/height/desktop checks remain valid. Physical Safari
keyboard-animation timing cannot be verified by Chrome emulation.

## Safari keyboard clipping of the whole composer

The screenshot exposed a container-height bug rather than an editor-height bug.
The previous placement capped the entire composer to the intersection of the
PDF frame, review panel and visual viewport. Safari's keyboard can pan that
viewport independently; a small overlap reduced the card to its heading/quote.
Earlier checks only resized the layout and visual viewports together, missing
this failure mode.

The mobile composer now uses a fixed body-level overlay sized to the full visual
viewport, outside workspace clipping. It keeps its natural height when the screen
above the keyboard can fit it, even if that screen barely overlaps the PDF frame.
It is excluded from PDF stage reachability and comment collision packing, and
returns to its original parent on close or a switch to desktop placement. The
same editor, draft and focus survive viewport changes.

Changed `comment_composer.js`, `viewer_shell.js`, `viewer.css` and the existing
six-refinement checks. A new case independently offsets the visual viewport by
430px while reducing its height to 320px: the full editor and submit button must
remain inside the unchanged-height card, above the keyboard. This exercises the
previously missing geometry; actual iPhone keyboard behavior remains manual.
See the [Visual Viewport API explanation](https://developer.mozilla.org/en-US/docs/Web/API/VisualViewport).

## Compact mobile selection editor and page-number entry

The mobile selection textarea retains 16px native font metrics but is transformed
to render at 13px inside a 72px-tall wrapper. This restores compact text while
reserving the editor's visible height as the keyboard changes viewport bounds.
The composer keeps its normal height when it fits above the keyboard; extremely
small viewports retain the existing scrollable-card fallback.
WebKit's [focused element information](https://github.com/WebKit/WebKit/blob/main/Source/WebKit/WebProcess/WebPage/ios/WebPageIOS.mm)
uses the renderer's font size separately from its transformed interaction bounds.
Physical Safari verification remains necessary.

The header page number uses 16px text on mobile to avoid focus zoom, requests a
numeric keyboard and Go action, and blurs after a change or Enter confirmation.
The field remains directly editable. No automatic page-field focus was present.

Changed `viewer.css`, `viewer.html`, `viewer_shell.js` and six-refinement checks.
Coverage includes compact visual/native font sizes, stable field and composer
height after viewport resizing, preserved draft, non-overlapping actions, page
navigation and focus dismissal. Desktop composer focus/placement remain covered.

## Mobile composer focus and Safari controls

The selection composer no longer automatically focuses its textarea for coarse
pointer input or narrow layouts. Initial opening and reopening an already-open
composer now share this policy; the latter previously still forced focus.
Tap the comment field to start typing; desktop autofocus remains.
Mobile viewer textareas now use 16px text rather than 12px to avoid Safari's
automatic whole-site input-focus zoom, which could move the composer out of view.
No viewport zoom restriction or PDF gesture change is introduced.
This avoids unnecessarily activating Safari's native form-navigation accessory
when opening the card. Safari owns the previous/next/Done bar and URL display;
the website cannot reliably hide those while the user edits a native text field.
The URL shown is the current Cloudflare test hostname, not an app overlay.

Changed `static/review/comment_composer.js`, `anchors.js`, `viewer.css` and the
existing six-refinement check. Coverage includes desktop autofocus, initial and
repeated mobile opening without editor focus, preserved drafts, real touch input
on the card title, computed editor font size, and direct editor focus. Physical
Safari focus zoom/chrome remain manual checks. The 16px approach is also used in
[Flutter's iOS Safari input integration](https://docs.flutter.dev/ui/accessibility/web-accessibility#viewport-zoom-and-mobile-text-inputs).

## Mobile selection composer at the viewer corner

The Comment on selection composer now opens at the bottom-right of the visible
PDF viewport on mobile/touch layouts. It stays there during PDF scrolling and
tracks visual viewport changes when the keyboard opens. The available viewer
area limits its width/height, with internal scrolling for smaller spaces.
The selected quote and draft survive viewport resizing. Desktop placement and
existing comment popovers retain their behavior.

Changed `static/review/viewer_shell.js` and the existing six-refinement browser
check; validation covers bottom/right alignment, PDF scroll, viewport resizing,
selected quote and draft preservation. Physical iPhone keyboard behavior remains
a manual check.

## Mobile PDF selection callout and comment action

Added coarse-pointer PDF-only context-menu cancellation and WebKit touch-callout
suppression on the native text layer for accounts that can comment. Native text
selection remains enabled; input fields and application controls keep their menus.
The mobile Add comment action is now a labelled 44px-minimum button at the bottom
right of the visible PDF viewport, separate from selection handles and Safari's
selection bubble. Desktop retains its compact contextual icon. Visual viewport
resize/scroll keeps the mobile action inside the visible area.

Safari's system selection menu is not reliably controllable by web content;
callout suppression is best effort. The separate action addresses access even
when the native menu remains. See [Apple's callout property documentation](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariCSSRef/Articles/StandardCSSProperties.html)
and [WebKit's context-menu cancellation issue](https://bugs.webkit.org/show_bug.cgi?id=260722).

Changed `anchors.js`, `viewer.html`, `viewer.css`, `pdfjs.css` and the existing
six-refinement browser checks. That check passes PDF-only cancellation, preserved
selection, the 44px action, and opening the composer with the selected quote.
Actual iPhone selection handles and system-menu behavior remain a manual check.

## Background and cross-boundary pinch continuity

Completed the remaining background and boundary fix in the documented native
viewer patch. Background origins select the nearest attached page, including
offscreen pages, and extrapolate coordinates outside paper. Touch keeps that
reference page through the gesture rather than switching calculations whenever
the midpoint enters a gap or crosses a page edge. Each step reads the current
camera; end/cancel, document changes and app blur/visibility cleanup release the
reference. An origin-based zoom never restores stale visible-page location.

Changed `static/vendor/pdfjs/web/viewer.mjs`, the cleanup hook in
`static/review/pdf_gestures.js`, and the focused `tests/document_zoom.py` checks.
The version-specific patch and current architecture/testing notes are updated.
Scale recognition, rendering core, workers, card layout and backend are unchanged.

Validation: 80 desktop and 28 fit/overflow cases pass. Offscreen-background,
boundary crossing/reversal and fresh-gesture selection checks measure at most
0.49px error. Actual two-touch divider/background pinch with midpoint translation
keeps one reference page (1.97px drift). Live highlights, detached contacts,
fractional panning and one-finger scrolling pass. Physical Safari remains manual.

## Native zoom across fitting-page transitions

Fixed loss of intermediate scroll offsets when zoom grows small centered pages
into an overflowing page. The native viewer now captures the PDF point under the
gesture and combines restoration with origin/pan adjustment before the browser
clamps scrolling. The same page-relative conversion handles mixed dimensions,
rotation and wrapped-row reflow. Native fractional pan state is preserved.

The implementation is a documented patch to `static/vendor/pdfjs/web/viewer.mjs`;
its private scale/scroll state cannot be changed cleanly from an external wrapper.
The app's measured card bounds and independent stage remain unchanged. No card
sizes, page counts or spread constants enter the fix. The exact patch and upgrade
instructions accompany it under `vendor_patches/` and
`static/vendor/pdfjs/LOCAL_PATCHES.md`. Tests extend `tests/document_zoom.py`.

Validation: 80 existing desktop steps pass (2.12px max drift); 28 fitting/overflow
cases with reversals pass across all rails, mixed/later pages, rotation, spreads
and scroll modes (2.50px max reachable error). Actual Chrome touch transition and
reversal measured 2.95px maximum drift. Fractional panning, live highlights,
detached contacts and browser-owned one-finger scrolling pass, along with the
existing six-refinement search/card/navigation check. Physical Safari remains a
manual check; reload and repeat several-pages-to-one-page pinch with/without cards.

## Mobile left cards beside the document

Removed the narrow-viewport override that clamped unpinned left cards to the
screen. They now use the same document/spread-relative left rail on phones as
on desktop. The shared stage supplies horizontal scroll space to reach them;
pinned cards keep their existing viewport behavior.

Changed `static/review/left_card.js`, the mobile assertions in
`tests/six_refinements.py`, and the current architecture/mobile testing notes.
The six-refinement browser check passes, including document-edge alignment,
horizontal reachability and full content height at a 390px mobile viewport.
The native zoom regression also passes all 80 desktop steps and mobile touch
checks, with maximum desktop focal drift unchanged at 2.12 CSS px.
Physical iPhone confirmation remains manual.

## Live mobile highlight geometry and browser-owned one-finger scrolling

The physical iPhone test confirmed good desktop trackpad behavior, but showed
highlights drifting during pinch and snapping back after release. The previous
attempt to retain touch targets paused all highlight geometry updates. That
froze pixel positions while the native PDF page resized, directly explaining the
screenshots. This touch-only protection was incorrect.

Highlights now reconcile keyed DOM nodes and use page-relative percentage
geometry. They resize with the native page immediately, without per-move node
replacement or waiting for touchend. Rotation, colors, resolution state and
highlight click cycling update in place. Obsolete touched nodes can remain hidden
until contacts end. Section dividers also reuse their nodes and update during
pinches. Canonical anchors and PDF bytes remain unchanged.

The user clarified that excessive panning occurred with **one finger**. Native
PDF.js manual touch-pan callbacks concern two-contact gestures; one-finger motion
belongs to browser scrolling. The stage could previously rebase origins/write
scroll offsets while a browser drag was underway. It now defers origin maintenance
and extent shrinking through active contacts and native scrolling/momentum, then
reclaims space when idle. No speed multiplier or competing one-finger pan handler
was added. This removes a competing writer; the physical Safari symptom still
requires confirmation rather than being declared solved from Chrome.

Validation: desktop's 80-step focal check still passes (maximum 2.12 CSS px drift).
The new check measures canonical highlight geometry during each actual browser
touch move: maximum live error 0.02px, including zoom/reversal and detached-target
cases. A 120px one-finger drag produced 105px page motion with zero app scroll
writes while origin space awaited reclamation. Highlight containment, immutable
geometry, overlapping-thread cycling, zoom and rotation checks passed. Physical
iPhone Safari remains unverified. See MOBILE_TESTING.md for the specific retest.

Edited: static/review/anchor_overlay.js, document_stage.js, section_viewer.js;
tests/document_zoom.py and browser_sanity.py; ARCHITECTURE.md, MOBILE_TESTING.md
and this report. The working desktop layout fix and native PDF.js zoom math stay
in place; no backend, vendor, deployment or version-control publishing changes.

## Independent document stage and native gesture coordination

Implemented the architectural follow-up to the confirmed trackpad diagnosis.
`document_stage.js` owns one measured scroll extent while native page centering
uses a card-independent viewport width. Right comments, floating cards/composers
and unpinned left tools supply actual bounds. Origins left/above zero rebase
canvas, scroll offset and parent comment coordinates atomically. Card size,
column depth and spread/page counts do not appear in canvas-width corrections.
The separate left/right tails and page-width freeze are removed. A stable native
scrollbar gutter prevents tall cards from changing a fitted PDF's centering.
Measured reachability includes both current and final animated card bounds.

A separate mixed-page pinch reproduced a first-step jump caused by native stale
view-location refresh after page resizing. Calling native update() before native
updateScale fixes the snapshot order. All gesture, scale, focal/pan and rendering
math remains native. `pdf_gestures.js` adds scoped browser-gesture suppression and
relays only events stranded on detached touch targets to the native manager.
Highlights defer destructive rebuilding until PDF contacts end; section markers
defer it during pinches. Narrow left tools remain readable without forced PDF
horizontal navigation. Backend, database, security and vendored code are unchanged.

Validation: focused zoom run passed 80 native steps, four rail combinations,
eight mixed-size pages, odd/even spreads, vertical/horizontal/wrapped scroll,
card open/close/resize/pin changes, actual trackpad input, negative-origin and
far-column bounds, and atomic overlay rebasing. Maximum desktop drift: 2.12 CSS
px. Real Chrome touch input, quick reversals, delayed drawing, detached targets,
one-finger scroll and scoped gesture cancellation passed; maximum measured touch
drift: 2.37 CSS px. The existing six-refinement viewer check passed. Physical
Safari is not verified; see MOBILE_TESTING.md for the exact retest. Native scroll
limits at actual document edges remain. No deployment, staging, commit or push.

Changed implementation: new document_stage.js and pdf_gestures.js; viewer_shell.js,
left_card.js, anchors.js, comment_filters.js, anchor_overlay.js, section_viewer.js,
styles/pdfjs.css and styles/viewer.css. Targeted coverage is tests/document_zoom.py
plus its disposable browser_sanity.py fixture/entry point. Existing viewer
acceptance assertions now check visibility/canvas independence instead of removed
gutter CSS variables. Current README,
ARCHITECTURE, MOBILE_TESTING and TRACKPAD_ZOOM_DIAGNOSIS describe the result;
earlier implementation/rollback notes below are historical.

## Confirmed card-dependent trackpad zoom displacement

Investigated before changing behavior, as requested. The app's card-dependent
`--review-stage-width` updates on a later animation frame, after PDF.js has
already corrected native zoom around the cursor. Automatic page margins then
recenter the PDF a second time. A disposable desktop fixture reproduced a
77.516px extra leftward page shift in one zoom-out step. Disabling only that
minimum-width rule in the fixture DOM, while retaining the right comment gutter,
removed the extra shift; native cursor-point drift was approximately 0.46px.
Left-only and combined gutters showed the same timing problem.

See [TRACKPAD_ZOOM_DIAGNOSIS.md](TRACKPAD_ZOOM_DIAGNOSIS.md) for the exact code
path, measurements and zoom-in/out asymmetry. This is a confirmed horizontal
layout integration problem, distinct from speculative mobile gesture causes.
Application and vendor source are unchanged; this turn adds the diagnosis and
an ignored synthetic probe only.

## Revert all custom zoom and touch integration

At the user's request, restored default PDF.js zoom behavior. Removed the
pdf_zoom_layout.js wrapper and its stage-width refactor, the forced native pinch
option, Safari gesturestart/gesturechange cancellation in both documents, and
viewer/iframe touch-action overrides. The earlier pdf_touch.js implementation
remains removed. PDF.js vendor files are unchanged; default TouchManager and
browser negotiation now govern pinch behavior.

Removed the experiment-specific mobile_pinch test and its harness entry point,
and removed the custom pinch assertions from the existing six-refinement check.
The latter retains its comment, card, section feedback and mobile search checks.
Unrelated left-card, comment, section and download-policy behavior is preserved.
The HTTPS tunnel setup is retained. Reloading the viewer is required to discard
handlers already installed in an open tab. Physical Safari improvement is not
claimed. Earlier zoom implementation notes below are historical and superseded.

Edited: static/review/viewer_bootstrap.js, static/review/viewer_shell.js,
static/styles/pdfjs.css, static/styles/viewer.css, tests/browser_sanity.py,
tests/six_refinements.py; deleted static/review/pdf_zoom_layout.js and
tests/mobile_pinch.py; updated README.md, ARCHITECTURE.md, MOBILE_TESTING.md,
MOBILE_ZOOM_ARCHITECTURE_REVIEW.md and this report.

Validation: the remaining six-refinement browser checks passed; whitespace and
source checks confirm no custom pinch/gesture handler or zoom wrapper remains.

## Mobile zoom architecture review after the second iPhone test

The user reports remaining jitter and occasional upward jumps. Reviewed the
native gesture lifecycle, app layout and browser touch behavior instead of
running another broad regression loop. Findings and implementation priorities
are recorded in [MOBILE_ZOOM_ARCHITECTURE_REVIEW.md](MOBILE_ZOOM_ARCHITECTURE_REVIEW.md).

The strongest new finding is target lifetime: highlight overlays are replaced
on scale changes, although touch events retain their original targets and can
stop reaching PDF.js's window listener when those targets are detached. Section
markers are rebuilt too. The additional focal pan wrapper, repeated rail layout
and changing overflow sentinels introduce further position/layout work during
pinches. These are architectural concerns; the particular physical upward jump
has not been traced to one cause. Existing tests wait for rendering to settle,
which leaves rapid reversals and target replacement insufficiently covered.

Recommended order: preserve touch targets, introduce a shared presentation pinch
lifecycle, stabilize app-owned gutters/scroll extents during the gesture, then
remove redundant focal correction once scale/stage layout is coordinated.
Retain PDF.js. A preview-transform/commit design is a later option if the simpler
native integration remains unreliable on physical Safari. This turn changes
documentation only and does not claim another runtime fix.

## Keep the native zoom focal point stable beside review rails

The user tested the public HTTPS session on an iPhone SE and reported that native
zoom improved but still drifted toward the upper left. Upstream also tracks iOS
jumping in [PDF.js #20480](https://github.com/mozilla/pdf.js/issues/20480).
The vendored build already contains the client-coordinate origin fix discussed
in [PDF.js #21659](https://github.com/mozilla/pdf.js/pull/21659), so that patch was
not duplicated.

A fitted-page browser reproduction measured approximately 18 CSS px of drift.
Our comment rail updated the PDF stage minimum width on a later animation frame,
after native zoom had calculated its scroll offset. New `pdf_zoom_layout.js`
preserves the point within the visible page during native focal zoom, updates the
app stage width immediately, and corrects only the resulting position through
native `panBy`. The fitted reproduction improved to below 2 CSS px. Scale factors,
gesture tracking, rendering and toolbar zoom remain native. This is a verified
integration issue, not a claim that every physical Safari glitch is resolved.

Edited files: new `static/review/pdf_zoom_layout.js`,
`static/review/viewer_shell.js`, `tests/mobile_pinch.py`, `ARCHITECTURE.md`,
`MOBILE_TESTING.md`, and this report. Native vendor files remain unchanged.

Validation includes fitted and scrolled pages, zoom in/out, moving finger
midpoints with simultaneous panning, stable outer-site scale and one-finger
scrolling. Focal regression tolerance is now 5 CSS px rather than 24 CSS px.
The existing six-refinement browser check passed. The public session remains
running; another physical Safari test is required. The earlier native-only
implementation and validation below describe the previous revision.

## Restore native pinch zoom; prepare HTTPS iPhone testing

Removed the custom `pdf_touch.js` implementation and its installation call, as
requested. PDF.js now retains its native TouchManager, zoom calculations and
finger-origin handling. The pre-run hook explicitly enables native pinch zoom.
A narrow Safari integration only cancels browser-level gesture events over the
PDF/iframe; it does not swallow native touch events or calculate zoom itself.
Existing pan-axis CSS and one-finger scrolling remain. Vendor files are unchanged.

The user observed that the custom version behaved better near the top and seemed
to zoom toward a corner farther down. This is consistent with focal/scroll issues,
but no exact physical-device cause is claimed. Research found upstream
[PDF.js #16328](https://github.com/mozilla/pdf.js/issues/16328), where the same
Safari/iframe symptom is discussed. Automated coverage now measures the content
under the finger midpoint on a scrolled second page, away from scroll-edge clamps.
Pinches wait for native canvas/text rendering to settle before the next gesture;
rapid gestures during canvas replacement and physical Safari remain unverified.

Prepared `mobile_https.ps1` and `MOBILE_TESTING.md` for a temporary Cloudflare HTTPS
session. The official 2026.10.7 executable was downloaded into ignored runtime
storage and verified against its release SHA-256. The launcher preserves `.env`,
uses one loopback app process, HTTPS origin/Secure cookies/one trusted proxy hop,
and existing Google authentication and document ACLs. It refuses an occupied port
and validates recorded process identities on stop. Its PowerShell syntax passed,
and public startup succeeded after explicit user approval on November 3, 2026.

Automatic approval review initially rejected public forwarding. The user then
explicitly approved it, and the tunnel and single loopback app process started.
Public `/healthz` returned HTTP 200; `/` redirected to login; `/auth/google`
redirected to Google with the exact generated HTTPS callback. No Google
configuration was changed. The user must register that callback manually in the
existing Google OAuth client before signing in. Physical iPhone testing remains
pending.
See [Cloudflare's temporary endpoint documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

Edited files: `static/review/viewer_shell.js`, `static/review/viewer_bootstrap.js`,
removed `static/review/pdf_touch.js`, `static/styles/pdfjs.css`,
`tests/mobile_pinch.py`, new `mobile_https.ps1`, new `MOBILE_TESTING.md`,
`.gitignore`, `README.md`, `ARCHITECTURE.md`, and this report.

Validation: native pinch-in/out checks passed on the first and scrolled second
pages, including a midpoint check allowing up to 24 CSS px of native drift, stable
site scale and one-finger scrolling. This is a regression guard against large
corner jumps, not a pixel-perfect focal guarantee. Tests wait for rendering to
settle between gestures. The existing six-viewer regression and whitespace check
passed. The HTTPS launcher also passed public startup and unauthenticated routing
checks after explicit approval. End-to-end Google sign-in remains unverified.
No backend, schema, dependency or vendor changes. The earlier custom-pinch notes
below are historical and their implementation has been reverted.

## Explicit PDF pinch handling and Safari gesture fallback

The user confirmed the earlier touch-action change blocked website zoom but did
not make pinch zoom work on iPhone Safari. The earlier Chrome emulation test was
insufficient evidence for that device; its previous success is historical.

Added `pdf_touch.js` to own PDF multi-touch input and call the existing PDF.js
updateZoom API. Distances use client coordinates and stable finger identifiers,
with a gesture-start scale to retain small movements. PDF.js supplies scale
limits, focal-point adjustment, pan and render scheduling. The application's
native TouchManager instance is destroyed to avoid a competing recognizer;
vendored PDF.js is unchanged. Existing pan-axis CSS and one-finger native
scrolling remain; form controls and section-line dragging are excluded.

Safari's gesturestart/change/end input is also handled in the iframe and for
PDF-targeted host gestures. The first stream that actually moves owns the pinch,
so a touchstart followed only by gesturechange still scales the PDF, while
parallel touch and gesture streams cannot double-apply scaling. End/cancel,
finger-count changes and blur clear/rebase gesture state. No site-wide viewport
zoom prohibition is introduced. API references:
[MDN GestureEvent](https://developer.mozilla.org/en-US/docs/Web/API/GestureEvent),
[MDN multi-touch interaction](https://developer.mozilla.org/en-US/docs/Web/API/Touch_events/Multi-touch_interaction).

Edited files:

- New `static/review/pdf_touch.js`: direct pinch and Safari gesture handling.
- `static/review/viewer_shell.js`: install the integration after viewer setup.
- `static/styles/pdfjs.css`: clarify ownership of existing pan-axis rule.
- New `tests/mobile_pinch.py`, `tests/browser_sanity.py`: focused browser checks.
- `README.md`, `ARCHITECTURE.md`, and this report.

Validation: focused browser checks passed genuine pinch-in and pinch-out with
sequential finger placement, gentle movement with unchanged screen coordinates,
reordered touch lists, touch cancellation, native one-finger scrolling, stable
site viewport scale, gesture-only and touchstart-plus-gesture-only Safari paths,
host-iframe gesture delivery and duplicate-stream suppression. Existing six-viewer
refinement checks also passed with the final stream-ownership adjustment. The
whitespace check passed. Physical iPhone/Safari is unavailable
in this environment and is not claimed as tested. The user should fully reload
the viewer on their iPhone and retest. Work remains local and uncommitted; no
backend, schema, dependency or vendor changes.

## Move comment scope and reviewer filters into a left card

Removed Everyone/Mine and the Everyone submenu from the Comments dropdown.
Comments > Filter comments... now opens a standard left utility card with All
comments, Only mine, and Selected reviewers. The last option reveals the reviewer
checklist. All comments selects everyone; Only mine preserves any custom reviewer
selection for later. Changes use the existing personal preference API immediately.
Reset to document defaults remains in Comments with its separator.

The new card shares content-sized layout, dragging, single-card pinning, focus
rules, mobile gutter access and saved open/closed positions. Restoration now
allows all four known left tools. Reviewer filters stay in server preferences;
localStorage contains only existing minimal card layout metadata. Queued edits
retain a temporary draft, and stable checkbox nodes preserve focus during refresh.

Isolated non-owners receive a policy note and Only mine; other modes are disabled
and the reviewer checklist is hidden. Backend privacy enforcement is unchanged.

Edited files:

- New `static/review/comment_filters.js`: card controls and preference drafts.
- `static/review/viewer_preferences.js`: Comments opener and canonical updates.
- `static/review/left_card.js`: restore up to four known utility cards.
- `static/styles/dialogs.css`, `static/styles/comments.css`: compact card controls
  and removal of unused reviewer submenu styling.
- New `tests/comment_filters_acceptance.py`, `tests/browser_sanity.py`: focused
  filter/card browser regression.
- `tests/six_refinements.py`, `tests/beta_c2_acceptance.py`: use the moved controls.
- `README.md`, `ARCHITECTURE.md`, and this report.

Validation: focused browser checks passed All/Mine/custom subsets, rapid checkbox
changes, saved preferences, all four cards restored with filter pin state,
isolated review, close/reopen persistence and mobile opening. Existing six-viewer
refinement checks and the full C2 browser regression passed, including sections,
shared/isolated review, persistent viewer preferences and responsive layouts.
Desktop/mobile filter screenshots were inspected and the whitespace check passed. No backend, schema, dependency or vendor changes. Work remains
local and uncommitted.

## Cycle overlapping comment highlights

Repeated pointer clicks at overlapping comment highlights now cycle through the
conversations at that exact point, including those beneath the topmost highlight.
Selection starts with the topmost hit when no participating comment is selected,
then advances from the selected thread and wraps around. Distinct rectangles of
one thread count as one choice. Clicking a non-overlapping highlight keeps normal
selection behavior; programmatic clicks without pointer coordinates retain their
original target selection.

The overlay uses the iframe's actual elementsFromPoint stack and only includes
thread highlights belonging to that page overlay. Selection state supplies the
cycle position across overlay re-rendering; no persistent state or database
changes are required. Existing selected colors, card focus, click-away behavior
and contained-rectangle filtering are retained.

Edited files: `static/review/anchor_overlay.js`, `tests/highlight_overlap.py`,
`README.md`, `ARCHITECTURE.md`, and this report.

Validation extends the disposable highlight browser fixture with three distinct
conversations, one covering only half of the others. Real pointer input checks
cycling and wraparound, the two-thread portion, a single-thread portion, and
repeated selection after zoom and rotation. The focused overlap browser check
passed, including the previous contained-rectangle and immutable-geometry checks.
The ordinary-comment UI regression and whitespace check also passed. Work remains local and uncommitted; no backend, schema,
dependency or vendor changes.

## Avoid painting nested highlight rectangles twice

Read-only inspection of the localhost SQLite anchor matching the paragraph-style
phrase confirmed two rectangles with identical horizontal bounds and slightly
different vertical bounds. One sits entirely inside the other. The overlay drew
both translucent fills, making that portion of the same comment look darker.

Rendering now removes exact duplicates and fully contained rectangles within an
anchor segment before creating highlight elements. The enclosing rectangle keeps
the full selected coverage. Persisted rectangles and immutable anchors remain
unchanged; separate overlapping conversations retain their own highlights and
click targets. No real localhost data was edited or migrated.

Edited files: `static/review/anchor_geometry.js`, `static/review/anchor_overlay.js`,
new `tests/highlight_overlap.py`, `tests/browser_sanity.py`, `README.md`,
`ARCHITECTURE.md`, and this report.

Validation uses a disposable browser fixture containing an inner rectangle, its
enclosing rectangle, an exact duplicate and a disjoint rectangle. It checks
single coverage, unchanged canonical API geometry, zoom/rotation, click selection
and independent highlights for a second conversation on the same text. The
focused browser regression and whitespace checks passed; the rendered fixture
screenshot was inspected. Work remains
local and uncommitted; no backend, schema, dependency or vendor changes.

## Restore ordered comments and insert section responses into the list

Removed the closest-fitting-gap placement introduced in the previous refinement.
Regular comments retain their document-anchor order and existing selection-pivot
packing. Shorter later comments cannot jump above taller earlier comments.

Each section's responses form one contiguous group. The layout considers the
insertion boundaries in the existing comment list and selects the one that places
the group's bottom closest to its section endpoint. A natural gap is used when
it fits the group; a dense insertion goes directly after its predecessor and
pushes the later list downward. Equal distances prefer less movement of the next
comment. Section groups retain endpoint order. This may put a section response
slightly above or below its endpoint instead of keeping an exact endpoint at the
cost of reordering ordinary comments or leaving a forced hole.

The 30px section-card width increase and zero thread-controls margin remain.
Ordinary-only and minimized comment layouts retain their existing behavior.

Edited files: `static/review/viewer_shell.js`, `tests/section_card_packing.py`,
`README.md`, `ARCHITECTURE.md`, and this report.

Validation: the dense-layout browser regression now asserts preserved ordinary
comment order with a tall early card, compares section placement against every
original list insertion boundary, checks response grouping and no overlap, and
covers scroll stability, selection, reply expansion, zoom, spreads and visibility
modes. It passed, along with the existing six-viewer refinement regression.
The ordinary-comment UI regression passed too, including selection, replies,
edits and mobile anchoring. The ordered-insertion screenshot was inspected
and the whitespace check passed. No backend, schema, dependency or vendor changes. Work remains local
and uncommitted. The gap-filling behavior described below has been reverted.

## Fill usable gaps in dense comment rails

The previous section-first pass still inherited each ordinary comment's displaced
position. If an early tall comment could not fit before a section response, it
moved below the response and forced every later comment down too, leaving space
that a shorter comment could have used.

Mixed section/comment rails now use the left-card closest-fitting-gap approach.
Section response stacks remain reserved near their endpoints. The active ordinary
card gets placement priority, then other comments are considered in stable anchor
order. Each ordinary card chooses the available gap closest to its own anchor,
with a 6px separation. A short later card can fit above a tall earlier card instead
of inheriting its displacement. Ties prefer downward placement; positions are
calculated in document coordinates so ordinary scrolling does not reshuffle them.
Sparse natural anchor gaps remain; this avoids collapsing distant conversations
into one arbitrary stack. Ordinary-only and minimized layouts are unchanged.

Edited files: `static/review/viewer_shell.js`, `tests/section_card_packing.py`,
`README.md`, `ARCHITECTURE.md`, and this report.

Validation: extended dense-layout browser checks create distinct nearby anchors,
one tall early comment and several shorter later comments. They assert that a
later short comment fills space above the reserved section stack while the tall
comment sits below, retain endpoint alignment and separation, and verify stable
positions while scrolling. The focused browser checks passed, including
selection, reply expansion, zoom, spreads and visibility modes. The existing
ordinary-comment UI regression passed. The gap-filling screenshot was inspected
and the whitespace check passed. No backend, schema, dependency or vendor changes.
Work remains local and uncommitted. Earlier refinement notes below are historical.

## Section response priority and compact controls

Expanded section responses now reserve their positions before regular comments.
Section responses stack upward toward their section endpoints, with the final
response bottom aligned to the endpoint. Regular comments retain their document
order while fitting into free space above or below those stacks; colliding normal
comments advance downward rather than pushing the section feedback away. Section
stacks take priority even when a regular comment is selected. Dense neighboring
section stacks can move earlier section responses upward to avoid overlaps.

Section response cards are 30px wider, with the expanded PDF gutter reserving
that extra width. Floating section cards also use the wider presentation. Removed
the 9px top margin from thread controls for all comments. Natural content heights,
scrolling, compact marker packing and ordinary-only selected-card behavior remain.

Edited files:

- `static/review/viewer_shell.js`: reserve section stacks and interleave regular
  comments; include the wider section cards in gutter width.
- `static/styles/viewer.css`: 30px section-card width increase.
- `static/styles/comments.css`: zero top margin on thread controls.
- New `tests/section_card_packing.py` and `tests/browser_sanity.py`: focused
  dense-layout browser regression.
- `README.md`, `ARCHITECTURE.md`, and this report.

Validation: section-card browser checks passed two real reviewer responses among
five nearby ordinary comments, section-end alignment, interleaving and no overlap,
regular-comment selection, reply expansion, 30px width difference, zero controls
margin, zoom, spread modes and minimized/expanded switching. Existing six-viewer
refinement checks and the ordinary-comment UI regression passed, including
selection, replies, edits, click-away and mobile anchoring. The dense-layout
screenshot was inspected and the whitespace check passed. No backend, schema or dependency
changes in this refinement. Work remains local and uncommitted.

## Owner-controlled PDF downloads and printing

Review Settings now offers **PDF downloads: Allowed / Off**, enabled by default.
Off hides and disables the View menu Download/Print buttons, hides native PDF.js
export and attachment controls, blocks PDF.js save/download/print actions and
attachment exports, and intercepts Ctrl/Cmd+S/P in both the host and PDF iframe.
Print-media content is hidden as a fallback. The document policy applies to all
roles and versions, updates already-open viewers, survives reopening, and can be
re-enabled without reloading.

Migration 10 adds a checked boolean integer to document review settings and
preserves existing defaults. Settings remain owner-only and CSRF-protected;
personal preferences cannot override this policy. The existing version-room
notification refresh updates the policy without a new transport or endpoint.

This restricts application export controls, not browser access to renderable
bytes. The authenticated PDF read/range endpoint must stay available for PDF.js;
browser menus, raw URLs, developer tools and screen capture cannot be reliably
blocked. The settings card states this limitation. PDFs and vendor sources are
unchanged. Only disposable test databases have been migrated during this work.

Files edited for this refinement:

- New `review/migration10.sql` and `review/database.py`: numbered migration.
- `review/review_policy.py`, `review/preferences.py`: defaults, validation and save.
- `review/review_routes.py`: parse the owner settings field.
- `review/routes.py`: initial viewer policy.
- `templates/review_settings.html`, `templates/viewer.html`: setting and initial controls.
- `static/review/viewer_bootstrap.js`: early native action and shortcut guards.
- `static/review/viewer_preferences.js`: canonical live updates.
- `static/styles/pdfjs.css`, `static/styles/viewer.css`: native controls and print fallback.
- `tests/test_beta_c2.py`: owner enforcement, invalid values, partial updates,
  all-version rendering, and idempotent migration from schema 9.
- New `tests/download_policy_acceptance.py`, `tests/browser_sanity.py`: browser checks.
- `README.md`, `ARCHITECTURE.md`, and this report.

Validation: the focused C2 server suite passed 31 tests. The download-policy
browser checks passed owner save, live reviewer updates, hidden controls,
application/event-bus/attachment guards, Ctrl/Cmd+S/P in both documents, rendering
after reload, print fallback and re-enabling exports. All 166 server tests and
the existing settings/sections management browser regression passed. The
whitespace check passed; the disabled-download viewer screenshot was inspected. Work remains local and uncommitted; no deployment.

## Remember left tools and simplify section feedback

Open Sections, Review Settings and Search cards now restore after reopening this
PDF viewer in the same browser. The reusable card shell saves open tool keys,
document-relative page/fraction positions and pin state per signed-in account and
exact PDF version. Closing a card removes it from the saved layout, including
when navigating immediately afterward. Restored cards retain natural height,
page-start bounds, collision packing and the independent single pinned overlay.
They reopen unfocused. Browser storage failures leave the tools usable; invalid
records and tools unavailable to the current role are ignored.

Only UI metadata is stored: no search terms, settings drafts, section prompts,
review content or PDF bytes. Restoration uses existing permission-checked tool
loads after viewer preferences and canonical review data are ready. Layout is
browser-local and does not sync across devices.

Section feedback now shows `Section name · Prompt` in one header, with
`Overall thoughts` for a blank prompt. The separate prompt paragraph and empty
invitation are removed; the response count, Add response action and existing
responses remain. Comments has a divider before Reset to document defaults.

Files edited for this refinement:

- `static/review/left_card.js`: shared storage, validation, restore and lifecycle saves.
- `static/review/anchors.js`: configure and restore after viewer initialization.
- `static/review/management.js`: register permitted owner tool openers.
- `static/review/sections_panel.js`: stable Sections persistence key.
- `static/review/viewer_shell.js`: Search persistence key and opener.
- `static/review/thread_sidebar.js`: compact section name/prompt header.
- `static/review/viewer_preferences.js`: Comments menu separator.
- `tests/card_state_acceptance.py` (new): focused browser regression.
- `tests/browser_sanity.py`: focused regression entry point.
- `README.md`, `ARCHITECTURE.md`, and this report.

Validation: focused card-state browser checks passed open/closed restoration,
real header dragging, normalized document positions, single-pin restoration,
account/version isolation, omitted search content, corrupt-state recovery,
prompt/default headers and menu separation. Existing no-jump focus/drag browser
checks also passed. The C2 browser acceptance suite passed sections, actual
response submission, shared/isolated review, viewer preferences, outline import,
presence, zoom/rotation/spreads and responsive layouts. The whitespace check
passed and the restored-card screenshot was inspected. No backend, schema, dependency or vendor changes. All work remains
local and uncommitted. Earlier refinement notes below are historical.

## Preserve displayed positions when focusing utility cards

Clicking, grabbing or keyboard-focusing an unfocused left card now adopts its
rendered position as its document anchor before it takes packing priority. Other
unpinned cards in the same workspace also retain their rendered positions, so
focus changes do not undo previous collision displacement. Existing animations
are flattened to the displayed position instead of applying their offset twice.
Dragging begins at that displayed position. Pinned cards retain their independent
behavior; deliberate section-line centering and offscreen tool retrieval remain.

Edited files: `static/review/left_card.js`, `tests/browser_sanity.py`, new focused
regression `tests/left_card_focus.py`, `README.md`, `ARCHITECTURE.md`, and this report.

Validation: focused activation and management browser checks passed, along with
the whitespace check. The regression
creates two cards with the same preferred anchor, confirms that packing displaces
one, and uses real pointer input to check clicking and dragging from its displayed
position. Keyboard focus, an already running animation and deliberate centering
are covered too. No backend, schema or dependency changes. Work remains local
and uncommitted. Earlier refinement notes below are historical.

## Search option grid and document-start card bound

Search options are now always visible in a two-by-two grid, with each native
checkbox and its label vertically centered. The Options disclosure is removed.
Existing checkbox IDs, labels and PDF.js change handlers remain intact.

Left-card collision packing now starts at the first PDF page top in document
coordinates. Dragging, activation, pinning and animations cannot place a utility
card above that boundary. Cards retain their full height and use space below when
an upper gap does not fit. The overflow sentinel includes the bounded stack.
Right-hand comment packing is unchanged.

The outer workspace now clips overflow without becoming a programmatically
scrollable container. This prevents focus-driven host scrolling from shifting
cards a few pixels above the first-page bound; PDF scrolling remains native.

Edited files:

- `static/review/viewer_shell.js`
- `static/review/left_card.js`
- `static/styles/dialogs.css`
- `static/styles/viewer.css`
- `tests/six_refinements.py`
- `README.md`, `ARCHITECTURE.md`, and this report.

The focused browser checks passed grid layout, checkbox/label centers and
first-page bounds through header dragging, packing, pinning and unpinning,
along with the existing six-refinement behavior. Management and full browser
acceptance checks passed, including keyboard search and unchanged comment
scrolling/layout. The whitespace check passed and the search grid screenshot
was inspected.
No backend, schema, dependency or vendor changes. Work remains local and
uncommitted. Earlier refinement notes below are historical.

## Six viewer refinements: color, layout, zoom, thoughts, filters and search

1. Selected right-side comments brighten the original poster's review color,
   replacing the green selection border. Utility-card accents are unchanged.
2. Right-rail layout dispatches `reviewlayoutchanged` after stage/gutter changes.
   Open left cards recalculate against the PDF when comment visibility, filtering
   or related layout changes, without requiring selection.
3. The PDF surface keeps native one-finger pan axes while two-finger pinch is
   handled by the existing PDF.js TouchManager. No global browser zoom restriction
   or vendor change is needed.
4. Section overall-thoughts cards prefer their bottom at the section end. Selected
   and floating section cards retain this anchor; normal collision packing remains.
5. Everyone now opens the person checklist and selects Everyone scope. All selects
   every person and clears hidden-author filters. Mine remains separate. Checklist
   actions keep the menu open; isolation and saved preferences retain their policy.
6. Search adopts PDF.js's existing controls into the shared LeftCard shell, with
   pinning, header drag, packing and focus behavior. Matching, navigation, options,
   Ctrl/Command+F and Escape use the existing engine. Match/status text is rendered
   by the host, and field focus avoids scrolling the host page. Old floating-find
   styles were removed.

Edited files:

- `static/review/viewer_shell.js`
- `static/review/left_card.js`
- `static/review/viewer_preferences.js`
- `static/review/menus.js`
- `static/styles/comments.css`
- `static/styles/dialogs.css`
- `static/styles/pdfjs.css`
- `static/styles/viewer.css`
- `tests/six_refinements.py` (new focused browser checks)
- `tests/browser_sanity.py`
- `tests/viewer_acceptance.py`
- `README.md`, `ARCHITECTURE.md`, and this report.

Validation: the focused six-feature Chrome checks passed, including real
CDP two-touch input changing PDF scale while visualViewport scale stays fixed.
Full existing browser acceptance and C2 privacy/preferences/responsive checks
passed, along with all 164 unit tests. Desktop search, Everyone checklist and
mobile pinch/search screenshots were inspected. The final mobile focus/bounds
check and whitespace check passed. New mobile search opens with its left gutter
exposed after a pinch-induced horizontal pan, without changing PDF scale. Physical iOS/Safari was not available for testing.

No backend, schema, dependency or vendored PDF.js changes. Work remains local,
unstaged and uncommitted. Earlier refinement notes below are historical.

## Inspector-only boundaries, following-page borders and click-away focus

Removed the separate structural end rails/ticks that were visible with Sections
closed. PDF section boundary lines and labels now render only while the Sections
card is open. Section feedback remains independent and available on the right.

Linked page-transition dividers render 12 px inside the following section's first
page, and use that start member for activation and card centering. This corrects
the previous interpretation that selected the preceding end while retaining its
physical position. Split boundaries remain on their respective pages.

Left cards drop active styling, focus priority and input focus on PDF, background
or comment clicks. This works in the iframe and host document, preserves card
positions and keeps cards open. Inside-left-card events still preserve selected
right comments. Listeners are cleaned up on close. Boundary activation can still
focus the Sections card. Constraint colors now reflect actual clamping rather
than every informational endpoint-moved notice.

Removed the one-page minimum in the editor and paired-save service. Linked
neighbors can shrink below one page; positive range length and non-overlap still
apply. The regression now verifies sub-page saving and rejects an empty range.

Edited files:

- `static/review/section_viewer.js`
- `static/review/section_placement_editor.js`
- `static/review/left_card.js`
- `review/sections.py`
- `tests/management_acceptance.py`
- `tests/beta_c2_acceptance.py`
- `tests/viewer_acceptance.py`
- `tests/test_beta_c2.py`
- `README.md`, `ARCHITECTURE.md`, and this report.

Validation: management, C2 and comment UI browser checks passed, together with
all 164 unit tests. Updated following-page spread screenshot inspected.
Management coverage includes following-page geometry, close/reopen visibility,
click-away focus (including after another card closes), linked sub-page edits
and existing drag/split/range behavior. The final whitespace check passed.
No schema/dependency changes or deployment. Work remains local and uncommitted.
Earlier refinement notes below are historical.

## Linked page edits and viewer-only tool access

A linked divider at a page transition now defaults to the preceding section's
end, even if the following section was selected. Its line still sits inside the
upper page. Both pointer and keyboard activation use that member.

Page-number edits now move the linked neighbor endpoint atomically, just like a
shared-divider drag. For example, 1-4 / 5-10 becomes 1-5 / 6-10 when the first
end changes to page 5. Notices identify the moved start/end. The neighbor keeps
at least one full page of canonical length; an already shorter neighbor cannot
be shortened further. Client movement clamps at that limit and the service checks
the same minimum for paired writes carrying `edited_id`. Unlinked or explicitly
split boundaries keep their independent behavior. No schema change is required.

Removed Review Settings and Manage Sections buttons from the document page.
Their PDF viewer controls remain available. Browser flows now use those controls.

Edited files:

- `static/review/section_viewer.js`
- `static/review/section_placement_editor.js`
- `review/sections.py`
- `templates/document.html`
- `tests/management_acceptance.py`
- `tests/beta_c2_acceptance.py`
- `tests/test_beta_c2.py`
- `README.md`, `ARCHITECTURE.md`, and this report.

Validation: focused management and broader C2 browser checks passed, along with
all 164 unit tests and the whitespace check. The C2 outline check now waits for
the import commit before closing the inspector. The new service regression covers 1-4 / 5-10 to 1-5 / 6-10,
reverse start edits, minimum-length rollback, and absent document-page buttons.
Work remains local and uncommitted; no deployment or runtime data migration.
Earlier refinement notes below are historical.

## In-page edge zones and section page ranges

Removed section-driven page/spread margins, gap classes, layout events and
between-page divider positioning. PDF.js owns page spacing. Boundary overlays
now snap within 18 px of either canonical page edge and render 12 px inside it;
page-edge controls say Start of page / End of page. Each spread page keeps its
own boundary line. The inset follows canonical geometry through rotation.

Double-clicking a shared boundary inside or near an edge zone splits it across
the page transition: an end at the preceding page bottom and start at the next
page top. Explicit numeric PDF-edge coordinates retain independent dividers at
all zooms and after reload, while null page-edge pairs can share a divider.
Interior splits still separate slightly within the page. The existing owner-only
atomic split operation accepts the exact-edge pair with unchanged outer endpoints
and existing range/revision/non-overlap validation. No schema migration is needed.

The Sections list now has a compact right-aligned page-range column, derived from
live draft geometry and updated while dragging. Single-page ranges show one number;
unmapped sections leave it blank. Names truncate cleanly without displacing ranges.

Edited files for this follow-up:

- `static/review/section_boundary_geometry.js`: inset geometry and edge-zone helpers; removed gap layout.
- `static/review/section_placement_editor.js`: symmetric snapping and cross-page edge splits.
- `static/review/section_boundaries.js`: explicit split grouping and page-range formatting.
- `static/review/section_viewer.js`: page-contained dividers and structural markers.
- `static/review/sections_workspace.js`: live page ranges and edge labels.
- `static/review/left_card.js`, `static/review/viewer_shell.js`: removed obsolete section layout event listeners.
- `static/styles/sections.css`, `static/styles/dialogs.css`: removed page margins; in-page labels and list columns.
- `review/sections.py`: validated atomic exact-page-edge split.
- `tests/management_acceptance.py`, `tests/beta_c2_acceptance.py`, `tests/test_beta_c2.py`: edge zones, stable spacing, ranges and split regressions.
- `README.md`, `ARCHITECTURE.md`, and this report.

Validation: management browser checks cover edge snaps from both directions,
unchanged page positions, shared and near-edge cross-page splits, multiple zooms,
page ranges, spreads, autosave/retry and delayed saves. The broader C2 browser
checks passed zoom/rotation, spread modes, feedback, review visibility, outline,
privacy and responsive layouts. Desktop split screenshot inspected.
Final management browser rerun passed, including zoom-stable explicit edge splits.
All 163 unit tests and the final whitespace check passed.

No dependency changes, deployment or runtime data migration. Work remains local
and uncommitted. Earlier refinement notes below are historical.

## Shared-divider fixes and double-click separation

Removed the structural rail beneath management dividers, which caused the white
box between pages. Marker backings are transparent and inter-page editing lines
are now 2 px rather than 3 px.

Fixed false shared-boundary errors in two places: client/server location comparison
now uses matching precision, and each queued save captures its own geometry at
gesture completion. Later drags cannot change an earlier request. Revision rebasing
uses only this client's acknowledged writes. Overlap checks now use the fixed
opposite endpoint, so dragging past a section's own start/end clamps correctly
without treating the pointer's temporary range as an overlapping section.

Double-click a shared divider to separate it into two independent edges, about
6 rendered pixels on either side. This creates a small gap and saves both shrunk
ranges atomically through the existing guarded endpoint with an explicit split
flag. Outer endpoints and unrelated sections remain untouched. Independent edges
can still snap back together, and the rejoined divider can be dragged normally.
Retry retains whether a failed operation was a split.

Edited files for this follow-up:

- `review/sections.py`
- `static/review/section_boundaries.js`
- `static/review/section_placement_editor.js`
- `static/review/section_viewer.js`
- `static/review/sections_workspace.js`
- `static/styles/sections.css`
- `tests/test_beta_c2.py`
- `tests/management_acceptance.py`
- `README.md`, `ARCHITECTURE.md`, and this report.

Focused management browser checks pass, including native double-click split,
rejoin/re-drag, delayed save snapshots, own-edge and neighbor clamps, transparent
2 px lines and spread alignment. The updated desktop screenshot was inspected.
Unit coverage adds floating-point round trips and validated atomic splits.
All 162 unit tests passed in one full suite run. The final whitespace check passed.

No schema/dependency changes or deployment. Work remains local and uncommitted.
Earlier refinement notes below are historical.

## Draggable cards and autosaving section inspector

New left cards open unpinned near the viewport center. Dragging the header moves
one vertically without changing its horizontal alignment. Natural content height,
comment selection motion and the independent single pinned overlay are preserved.

Sections now uses compact horizontal Start/End controls and an autosave footer.
Names and prompts save after a short typing pause or on change/blur; page edits
save on change, and PDF boundary drags save on release. Fields and markers share
transient canonical geometry. Saving, Saved and retryable errors replace the
manual Save boundaries, Cancel changes and Save section workflow. Delete remains
explicit and confirmed. Failed saves retain the entered values or geometry.

Touching section endpoints render one shared divider. Dragging that divider saves
both placements atomically, preserving their outer endpoints. Gaps remain separate;
independent movement clamps at the nearest valid neighbor, shows an overlap notice
and can snap into a shared divider. Unrelated sections are never resized. The new
owner-only, CSRF-protected shared-boundary endpoint reuses placement validation and
revision checks inside one transaction; stale revisions roll back both writes.
There is no schema migration or dependency change.

Between-page lines are thicker. Spread spacing belongs to the whole spread row;
stale per-page margins are cleared after PDF.js reuses page nodes. Both pages stay
aligned and a shared row-edge divider spans the spread. PDF bytes and page dimensions
are unchanged.

Edited files for this follow-up:

- [left_card.js](static/review/left_card.js): centered opening and header drag.
- [sections_workspace.js](static/review/sections_workspace.js): compact autosaving inspector.
- [section_placement_editor.js](static/review/section_placement_editor.js): synchronized drafts, clamping and serialized saves.
- [section_boundaries.js](static/review/section_boundaries.js): shared endpoint derivation (new).
- [section_viewer.js](static/review/section_viewer.js): shared management dividers and status styling.
- [section_boundary_geometry.js](static/review/section_boundary_geometry.js): spread-wide rails and row spacing.
- [management.js](static/review/management.js): reusable card loading/reopening.
- [dialogs.css](static/styles/dialogs.css), [sections.css](static/styles/sections.css): compact inspector, drag affordance and thicker lines.
- [sections.py](review/sections.py), [review_routes.py](review/review_routes.py), [auth.py](review/auth.py): guarded atomic shared-boundary save.
- [test_beta_c2.py](tests/test_beta_c2.py): revision rollback, unchanged outer endpoints, owner and CSRF guards.
- [management_acceptance.py](tests/management_acceptance.py): focused browser coverage.
- [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md), and this report.

Validation: focused management and comment UI browser checks passed. Management
coverage includes header dragging, centered unpinned opening, metadata/page/drag
autosave, failed-save Retry, shared divider updates, preserved gaps, overlap
clamping, natural card height and aligned spreads. Desktop spread and tablet
screenshots were inspected under ignored `tests/visual-artifacts/`. All 161 unit tests passed in one full suite run; the final whitespace check passed.

Work remains local, unstaged and uncommitted. No deployment or runtime data
migration was performed. Earlier refinement notes below are historical.

## Independent pinned overlay

The pinned card is now excluded from document-card collision packing, focus
priority and scroll-extent calculations. Resizing, activating or closing it does
not displace unpinned cards. Pinning preserves the existing positions of document
cards. No document card tracks or reserves the pinned card's height. Only after
unpinning does a card join normal collision handling. Full content height and the
single top-snapped pin remain unchanged.

Changed `static/review/left_card.js` and the focused checks in
`tests/management_acceptance.py`, plus README, ARCHITECTURE and this report.
Browser checks passed pinned growth/shrink, activation and stable scroll extent,
as well as existing section interactions. All 160 unit tests and the whitespace
check passed. No backend/schema/dependency changes. Work remains local and
uncommitted.
Earlier refinement notes below are historical.

## Natural card height and a single top pin

Left cards, bodies and section lists now use their full content height. Shared
layout height limits, viewport caps and internal scrolling are removed, including
limits inherited from active comment styles. Collision resolution moves cards;
it never resizes them. Overflow below the PDF uses the native PDF scrollbar.

Only one card may be pinned. It snaps to the top and stays above other cards.
Pinning a second releases the old pin beneath the new one; unpinning drops a card
into document space. The old card remains below when newly loaded pinned content
grows. Unpinned cards retain full height and move apart to prevent overlap.
Pinned cards stay top-snapped on section activation; unpinned cards can center on
section lines. Existing comment animation, boundary editing and focus remain.

Implementation: `static/review/left_card.js`, `static/styles/dialogs.css`.
Focused checks: `tests/management_acceptance.py`, including content taller than
the viewport, pin replacement, natural heights, scrolling and collision packing.
Documentation: README, ARCHITECTURE and this report. Focused browser checks, all
160 unit tests and the whitespace check passed. Desktop/tablet screenshots were
inspected. No backend or schema changes. Work remains local and uncommitted.
Earlier refinement notes below are historical.

## Cross-page boundaries and shared card focus

Comment click-away now preserves selection for every left-card control, including
rows that replace their DOM during the click. PDF/background clicks still clear it.
Boundary activation centers the Sections card beside the selected line with the
shared comment animation. Both pinned and document-attached cards participate in
nearest-free-space packing; the active card is the fixed point and others move.

Start/End page fields replace percent and Set start / Set end controls. Page entry
creates an explicit page-edge boundary. Small row gaps fit the line and title;
PDF page dimensions and spread pairs are preserved. Boundaries drag across pages
in either direction, with near-edge auto-scroll and canonical conversion using
the target page viewport. Changes remain pending until Save boundaries.
Cancel restores saved geometry. Boundary spacing changes notify both card rails.

Focused browser checks cover comment focus retention, background deselection,
cross-page drag/auto-scroll, centered activation, mixed pin-state collision packing,
page-only controls and existing save/cancel/outline behavior. Updated desktop and
tablet screenshots were inspected. The focused management and comment UI checks
passed, along with all 160 unit tests in one final run and the whitespace check.
Backend, schema and dependencies are unchanged. Work remains local and uncommitted.
Earlier refinement notes below are historical.

## Concurrent cards and inline boundary inspector

Left utility cards now coexist. Pin means viewport-fixed; unpinned means attached
to the current document position. The reusable shell packs pinned cards vertically
and gives long bodies independent scrolling. Card activation/retrieval and pinning
use the shared comment animation. Closing one card retains the others.

Sections is now the sole boundary editing surface. The top toolbar, row drag
handles and manual order controls are removed. Mapped rows follow canonical PDF
start order; unmapped rows retain previous logical slots. Inline page/percentage
fields, PDF picking and owner-only draggable Start/End lines share pending drafts.
Blank percentages use explicit page edges. Dragging a page edge into the page
produces precise Y. Save boundaries uses the existing revision-checked service;
Cancel restores saved placement. Markers select and retrieve the inspector.

Backend/schema/authorization and dependencies are unchanged. Existing prompts,
outline import, spread/row rails and right-side section feedback remain intact.
Focused browser checks cover concurrent packing, pin semantics, PDF ordering,
canonical dragging, fields/picking synchronization, explicit save/cancel, marker
activation and card-only editing. Save validation errors retain pending geometry.
Three desktop/tablet screenshots were inspected. All 160 existing unit tests passed
in one final suite run; the focused browser checks and whitespace check passed.
Changes remain local, unstaged and uncommitted. No deployment actions were taken.
Earlier notes below are historical.

## Reusable left cards and section ordering

Sections and Review Settings now share `left_card.js`: comment styling, exact
page-relative pinning, viewport following, close/focus/busy handling and listener
cleanup. `card_motion.js` shares the existing comment selection animation (160 ms,
ease-out, reduced-motion support). The white sidebar is removed; left space now
belongs to the PDF canvas, with the same background and native scrollbars.

Sections uses the open PDF version automatically. Drag handles replace Move up /
Move down, with pointer support and Alt + Arrow Up / Down keyboard ordering.
Hover/selected rows now specify readable foreground and background colors.
Existing section, privacy and settings APIs are unchanged. No new dependencies.

Focused browser checks cover pointer/keyboard reorder, exact pin position, shared
animation timing, both settings/section scroll modes, document entry, save failures,
outline import and boundary save/Cancel. Updated desktop/tablet screenshots were
inspected. The focused management and existing comment UI browser checks passed,
as did all 160 unit tests and the whitespace check. Changes remain local, unstaged
and uncommitted. Earlier refinement notes below are historical.

## Comment card and pin follow-up

Sections now reuses the comment card styling: the same width, muted background,
compact controls and accent edge, positioned beside the PDF on the left. A pin
button sits beside Close and is pressed by default. Pinned, the card tracks its
opening position on the PDF and can scroll off screen. Unpinned, it follows the
viewport down the document. Pinning again attaches at the current position;
Manage Sections retrieves a card that has scrolled away. Section boundary lines
and settings behavior remain available in both modes. No backend changes.

Focused browser checks passed pinned movement/offscreen retrieval, unpinned
following, boundary overlays, CRUD, outline import and boundary save/Cancel.
Updated screenshots at 1440 and 768 pixels were inspected. All 160 existing unit
tests and the whitespace check passed. Changes remain local and uncommitted.

## Earlier fixed Sections panel follow-up

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

Reading follow-up: tracking defaults on with author-only document/per-reader controls
in Review settings (migration 12). Targeted WebSocket invalidations refresh activity
after 15-second commits; live positions reuse presence. Both cards remain available
to readers with self-only analytics. See READING_PROGRESS_REPORT.md.
