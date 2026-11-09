# Mobile comment taps and detail loading — November 8, 2026

## Physical iPhone trace follow-up (November 8)

The supplied `pdf-review-touch-trace.json` contains 4,321 events over 26.8 seconds
on a 191-page PDF. During the first pinch the midpoint moves only a few pixels,
but the page beneath it changes from 109 to 131. Across the recording, PDF scale
starts at 1 and ends at 1.02 while the reported page changes from 109 to 187.
The top-level visual viewport remains at scale 1: this is not whole-site zoom.

The decisive ordering is at 8,893ms: scale 0.88, scrollTop 78,851; then at
8,895ms a scroll event restores 83,190, the exact position written for scale
0.93 at 8,869ms. There are 116 such exact earlier-position replays during pinch
with vertical errors above 100px; the largest differs by 9,329px. This is
consistent with stale asynchronous browser scroll acknowledgements. The trace
cannot inspect WebKit's internal scrolling process, but proves the stale camera
input and its amplification in our local zoom patch. Stage origin rebasing does
not explain these vertical jumps.

The old local patch resampled browser scroll offsets at every zoom step. It
therefore interpreted an old-scale offset in the new-scale layout, feeding a
large error into the next step. The deeper the page, the larger the scale-related
scroll offsets. Unintended page changes also trigger page rendering; this trace
does not establish that every visible loading indicator was a detail redraw.
It contains only one highlight rejection (`default-prevented` during a pinch),
so it does not independently establish a stationary comment-tap failure.

### Fix and validation

`static/vendor/pdfjs/web/viewer.mjs` retains the active native gesture's requested
camera, clamped to real document limits, for both scale updates and native pan.
Native scroll updates reconcile stale acknowledgements while the gesture is
active. Gesture end restores the final camera and releases ownership. Native
PDF.js recognition, scale calculation, drawing, and ordinary one-finger scrolling
remain in place. No CSS was changed for this fix.

`tests/zoom_rollback.py` and its `--zoom-rollback` harness flag replay older scroll
positions between native zoom transactions. Before the fix, even page 1 diverged
by 197px and failed. After the fix the clean and disturbed runs agree exactly
on pages 1/109/120 across all four modes, including midpoint pan, stationary
fingers, release, settled geometry and free scrolling. This is controlled fault
injection in Chrome, not emulation of Safari's scrolling process.

Follow-up checks: `--zoom-rollback` passes with existing comments on the three
test pages (0.00px difference); `--zoom-layout` passes all 80 desktop steps,
28 fit transitions, native touch/one-finger checks, 32 comment-touch cases and
five detail redraw checks; `--comment-ui` passes its existing UI checks plus
32 immediate/settled touch cases. `--comment-touch` passes all 64 cases on pages
1 and 101 of the 128-page fixture across all display modes. Patch reverse-apply and Python compilation
checks pass. All browser automation here uses Chrome.

The follow-up vendor diff is
`vendor_patches/pdfjs-6.4.299-pinch-camera.patch` (apply after atomic-zoom and
detail-loading). `static/review/touch_diagnostics.js` adds a revision tag and
`zoomscrollreconciled` observed/intended offsets for a new phone recording.
`MOBILE_TESTING.md` and `static/vendor/pdfjs/LOCAL_PATCHES.md` document retesting
and patch order. The raw phone trace is not copied into the repository.

**Physical Safari verification of this new fix remains pending.** In particular,
a new trace must check whether the browser still replays a stale position after
gesture ownership ends. The earlier findings below describe the previous fixes,
not proof that this new phone-reported defect was already solved.


## Verified causes and limits

The highlight recognizer rejected a stationary touch whenever either native
scroll offset changed by more than 1 CSS pixel. A controlled Chrome touch trace
on the 128-page fixture used PDF.js `panBy(0, 2)` between touch-down and release:
the same text span/highlight remained under the finger, but both pointer-up and
the compatibility click logged `highlight-rejected: scroll-changed` with a
`[0, -2]` scroll delta. This verifies the rejection condition. It does **not**
establish that physical Safari autonomously produces that adjustment after a
pinch; that requires a device trace. Ordinary Chrome pinch/reversal sequences
did not reproduce persistent lost taps.

Touch activation now uses the existing 8px movement budget for scroll settling
and intersects the thread IDs under press and release. It rejects any scale
change, remembers scroll movement beyond the budget even if it returns, and
retains pointer movement, multiple-pointer, cancellation, long-press, selection
and compatibility-click checks. Mouse behavior retains its strict scroll gate.
No pointer/touch defaults are cancelled by the new checks.

The supplied spinner is PDF.js's `images/loading-icon.gif`, painted by
`.page.loadingIcon::after`. `PDFPageDetailView` shared the base page's DOM element
and inherited a state setter that toggled its loading classes. Native panning
redraws the visible detail region; six successive detail renders in the fixture
all set the loading indicator while the base page was already FINISHED. High DPR
and PDF.js's mobile canvas cap make detail rendering more frequent. This is
rendering activity, not evidence of repeated PDF downloads.

The viewer patch gives only the base page ownership of that indicator. Detail
views still render at full detail and retain existing scheduling/cancellation,
but cannot show or clear the base page's spinner. Initial/full-page rendering
keeps its existing indicator. No CSS workaround or canvas-resolution change is
applied. The separate patch file and upgrade order are in
`static/vendor/pdfjs/LOCAL_PATCHES.md`.

## Other hypotheses and zoom audit

* `CommentRail` already schedules on scale/render notifications and translates
  with scroll events. The tests compare actual `elementFromPoint` hits to visual
  marker/card boxes, including immediate post-pinch input. No independent missing
  end-of-gesture reconciliation was established. `viewer_shell.js` is unchanged.
* Translated rail parents, scaled children, clipping and pointer-event rules
  agree with hit-testing in Chrome touch emulation. `viewer.css` is unchanged.
  A Safari compositor-specific failure remains possible and unverified.
* The old `pdf_zoom_layout.js` custom focal wrapper is gone. Current integration
  is PDF.js TouchManager plus `pdf_gestures.js` contact/target continuity,
  `document_stage.js` scroll extents and pre-scale location snapshot, and the
  documented native atomic zoom patch. Scale/pan/focal calculations are retained.
* Native zoom refreshes page views and native detail rendering follows the
  visible region. The shared stage defers origin reclamation during contacts or
  scrolling. Long-document tests exercise page 101 and large translated rail
  coordinates. They are correctness checks, not physical-device frame-time or
  memory benchmarks; additional high-page-count slowness is not claimed fixed.

## Temporary opt-in diagnostics

Append `?debug=touch` to an authenticated viewer URL and reload. The phone panel
now provides **Start recording**, **Stop**, **Download trace** and **Share trace**.
Recording starts only after Start is tapped. Reproduce on the problematic page,
stop, and attach the downloaded JSON in this chat. See `MOBILE_TESTING.md` for
phone steps and limits. Movement, frame intervals, stage origins and bounded
nearby-page geometry are now included in the v2 export.

For developer access, in the parent
page's console, inspect or copy `JSON.stringify(reviewTouchDiagnostics.entries)`.
`reviewTouchDiagnostics.clear()` starts a fresh trace;
`reviewTouchDiagnostics.pause()` freezes the trace;
`reviewTouchDiagnostics.stop()` removes listeners and the panel. Reload without the query to
leave diagnostics disabled. The bounded in-memory buffer contains event/geometry
data, not comment text, and neither persists nor transmits it.

The trace distinguishes:

* Wrong document/element hit: parent and iframe capture logs include actual target,
  `elementFromPoint`, bounds, CSS scale/transform and rail translation.
* Missing compatibility click: compare the same pointer-down/up coordinates to
  subsequent click records. Highlights deliberately activate without a click.
* Highlight rejection: named reasons include scroll, scale, movement,
  cancellation/multitouch, selection, long press and missing release hit.
* Stale geometry: correlate scale/scroll and `reviewlayoutchanged` against the
  event's hit-test rectangle; `pdftouchended` and render events delimit the phases.

## Regression commands

Run with the project's `.venv/Scripts/python.exe`:

```
tests/browser_sanity.py --zoom-layout
tests/browser_sanity.py --comment-ui
tests/browser_sanity.py --comment-touch
tests/browser_sanity.py --highlight-overlap
tests/browser_sanity.py --detail-loading
```

`--zoom-layout` and `--comment-ui` include `comment_touch_zoom.py`. It sends real
Chrome CDP touch input, verifies that native pinch changes PDF scale, and tests
Expanded, Minimized, Mobile and Hidden modes before and after repeated reversals.
Highlight and rail taps run immediately after touch-end and after settling.
Hidden mode must not activate comments. `--comment-touch` repeats the matrix on
pages 1 and 101 of a disposable 128-page mixed-size PDF. Separate controlled
scroll and cancellation tests isolate the rejection conditions. `--zoom-layout`
also includes the detail-loading regression.

### Results

All runs used isolated databases, PDFs and Chrome profiles:

| Check | Result |
| --- | --- |
| `--zoom-layout` | PASS: 80 desktop steps (2.12px maximum drift), 28 fitting/overflow transitions (2.50px), background/boundary cases, live highlights (0.02px), touch reversals (2.55px), later-page touch transition (2.95px), divider gesture (1.97px), one-finger drag without app scroll writes; plus 32 comment-touch cases and detail rendering. |
| `--comment-ui` | PASS: existing animation, replies, editing, keyboard and anchoring checks; 32 additional comment-touch cases on a separate page-2 anchor. |
| `--comment-touch` | PASS: 64 cases across pages 1 and 101 of the 128-page fixture, all display modes, immediate/settled highlight and rail taps. |
| `--highlight-overlap` | PASS: native touch, click deduplication, overlapping threads, replaced targets, selection/drag, pinch/cancel/long-press rejection; added settling, changed scale/thread identity and scroll-away-and-return checks. |
| `--detail-loading` | PASS: six native detail redraws without the page spinner; full-page loading still indicated. The final zoom suite also passed five detail redraws. |
| Patch / syntax checks | `git diff --check`, reverse-apply check of the new vendor patch, and Python compilation passed. Changed JS modules executed in the browser suites without uncaught exceptions. |

The animation test's former raw-scroll assertion intermittently failed when
UUID ordering made the selected card require an origin rebase. It now uses the
same camera invariant as the existing dedicated motion suite; runtime animation
code was not changed. Test preparation also avoids sampling a deliberately
moving deselection animation or tapping a marker moved outside the viewport by
a real document-edge limit. No animation or native zoom behavior was suppressed.

Physical iPhone Safari is **not verified**. The requested
`arrangement-gently-previously-diary.trycloudflare.com` hostname did not resolve
on November 8, including outside the sandbox; localhost port 5000 was stopped.
No production document, authentication or database was changed. A fresh tunnel
requires a new URL and corresponding Google OAuth redirect registration.

## Changed files

* `static/review/anchor_overlay.js`: stationary-touch guard and named rejection
  diagnostics; preserve native interaction and overlap cycling.
* `static/review/anchors.js`, `static/review/touch_diagnostics.js`: opt-in trace
  installation and removable parent/iframe event/geometry listeners.
* `static/vendor/pdfjs/web/viewer.mjs`,
  `vendor_patches/pdfjs-6.4.299-detail-loading.patch`: loading-indicator ownership.
* `tests/comment_touch_zoom.py`, `tests/detail_loading.py`: touch/hit-testing and
  detail-loading browser regressions.
* `tests/browser_sanity.py`, `tests/document_zoom.py`, `tests/highlight_touch.py`:
  suite integration, 128-page fixture and cancellation/identity regressions.
* `tests/viewer_acceptance.py`: compare the camera after subtracting the existing
  stage origin in the animation assertion. Raw scroll offsets legitimately
  change when a tall card stack causes an equal document/scroll origin rebase;
  that is not visible PDF scrolling. The dedicated comment-motion suite already
  uses this invariant. Input setup waits for deliberate deselection animations
  before measuring targets; post-pinch taps still have no settling wait.
* `ARCHITECTURE.md`, `MOBILE_TESTING.md`,
  `static/vendor/pdfjs/LOCAL_PATCHES.md`, `MOBILE_COMMENT_TOUCH_REPORT.md`:
  implementation, upgrade and verification records.
