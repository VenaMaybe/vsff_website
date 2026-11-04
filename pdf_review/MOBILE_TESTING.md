# Temporary iPhone testing

## Reading tools (migrations 11–12)

The local app currently runs at http://127.0.0.1:5000/ on the laptop; the old public
tunnel is stopped. Mobile HTTPS testing needs a new explicit tunnel session.
Reload and open Tools > Reading progress / Reader analytics. Tracking starts on;
only the author can set document On/Off or per-reader Pause in Review settings.
Readers can open both cards but see only their own analytics.

Stay focused and active on a page for over 15 seconds; saved time should update
in open cards via WebSocket notification. Reader positions use live presence.
Test author Pause/Resume with the reader's viewer already open. Repeat in a spread:
visible pages share one time budget. Switch apps or lock the phone and return;
background time must not catch up. Physical iPhone lifecycle behavior is not proven
by Chrome emulation. See [Reading progress report](READING_PROGRESS_REPORT.md).

## Temporary HTTPS session

The user explicitly approved public Cloudflare forwarding on November 3, 2026,
after an earlier automatic approval rejection. The launcher successfully started
the tunnel and local app. Public checks returned HTTP 200 for `/healthz`, a login
redirect for `/`, and a Google authorization redirect using the generated HTTPS
callback. Google client registration and physical iPhone testing remain manual.
The normal `.env` has not been changed. Current session details are in ignored
`.mobile-test/session.json`; this temporary session ends when stopped.

## What the launcher does

`mobile_https.ps1` uses the official Cloudflare 2026.10.7 Windows executable,
downloaded into ignored `.mobile-test/` and checked against the release SHA-256:
`2493dbc168923bb3e59e5e7716f71deced92992eea9acd6e9d74f84ac7751343`.

It starts a temporary public HTTPS address forwarded to `127.0.0.1:5000`. The
normal local app must be stopped first; the launcher refuses an occupied port
rather than starting a second process against the same database. It configures
only the child app process with the generated hostname, HTTPS callbacks, Secure
cookies, a single trusted proxy hop, disabled debugging and loopback listening.
Existing Google credentials, session secret, allowlist and document access remain
in force. There is no authentication bypass and no router/firewall change.

Cloudflare terminates and forwards the test traffic, including authenticated PDF
and review traffic. The address is publicly reachable; Google sign-in and app ACLs
remain the controls protecting private content. The session is temporary, not a
production deployment or Windows service. Runtime logs and PID state are private,
ignored local files, and the ordinary `.env` is not edited.

Starting the launcher prints the HTTPS URL and exact OAuth callback. Public
startup and unauthenticated routing have been verified; successful Google login
still requires registering the callback in the existing OAuth client.

## Google configuration and iPhone test

1. With the endpoint running, copy its printed callback:
   `https://<generated-name>.trycloudflare.com/auth/google/callback`.
2. Add it to **Authorized redirect URIs** on the existing Google Web application
   OAuth client. Keep the existing localhost callback too. This requires access
   to your Google Cloud client settings; this environment cannot edit them.
3. Open the printed HTTPS address in Safari on the iPhone and sign in normally.
   Use the same address on the laptop during this session.
4. Fully reload after frontend changes. Test both pinch-in and pinch-out near the
   first page, then after scrolling well down the document. The content between
   the fingers should remain near their midpoint, except at scroll boundaries.
5. Stop the session afterward with `mobile_https.ps1 -Stop`. The launcher checks
   process identities before stopping them. Then use the normal local launcher
   again if desired.

Quick Tunnel hostnames change when restarted, so a later session needs its new
callback registered. Google rejects ordinary LAN IP callbacks; the registered
HTTPS hostname is why this test uses a tunnel.

Sources: [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/),
[Google callback rules](https://developers.google.com/identity/protocols/oauth2/web-server#uri-validation).

## Current native zoom integration

PDF.js still owns pinch recognition, scale limits, focal-point math and rendering.
The document stage no longer changes its centering width when cards are present.
Before native scaling, the app refreshes PDF.js's own view-location snapshot.
The documented native viewer patch anchors the PDF point under the gesture and
combines scroll restoration with pan before browser clamping. Its final offsets
feed native fractional pan state; real document limits still apply.
The reference also covers background and page gaps by extrapolating from a nearby
attached page. Touch holds the same reference page until the gesture ends, so
crossing edges does not switch zoom calculations. Completely offscreen pages are
included; origin-based zoom never restores an obsolete visible-page snapshot.
Scoped touch-action and Safari gesture cancellation apply only to the PDF/frame
wrapper. Highlights now keep keyed elements with page-relative geometry, so
they follow page resizing while fingers are still down. Section markers update
in place as well. Stranded native events from detached canvas targets are relayed
without calculating zoom. Stage origin reclamation and extent shrinking wait
until touch scrolling/momentum is idle; the app does not write scroll offsets
during a one-finger drag.

The focused command is:

```powershell
.\.venv\Scripts\python.exe tests/browser_sanity.py --zoom-layout
```

It measures desktop PDF-space point retention across card states, mixed pages,
spreads, scroll modes and resizing; it also sends real Chrome two-touch input in
both directions, quick reversals, a detached-target gesture and one-finger scroll.
It also checks live highlight alignment during every touch move, rather than
only after release. The measured run had 0.02px maximum live highlight error.
A 120px one-finger drag moved the page 105px with zero application scroll writes,
including while card-origin space was pending reclamation. Outer-site scale and
scoped Safari-event cancellation are checked after delayed layout/drawing. These checks do **not** verify actual iPhone Safari.

The November 4 fitting-page transition fix is implemented in the native viewer.
The focused check now adds 28 fitting/overflowing transitions and reversals across
all card states, mixed pages, later pages, rotation, odd/even spreads and horizontal/
wrapped layouts. Maximum nearest-reachable focal error was 2.50px, including
deferred layout/drawing. A real Chrome two-touch transition/reversal on a later
mixed-size page measured 2.95px maximum drift, followed by fractional-pan checks.
The existing 80 desktop steps still pass (2.12px maximum drift). These are browser
measurements, not physical Safari verification. See the
[diagnosis and implementation record](MOBILE_ZOOM_STEPPING_DIAGNOSIS.md) and
[vendor patch notes](static/vendor/pdfjs/LOCAL_PATCHES.md).

The follow-up background/boundary correction is now implemented. The earlier
source audit identified a changing anchor strategy and stale-location restoration
when no pages were visible. Regression checks now cover that entirely offscreen
case, boundary crossing/reversal within one gesture, selection of a fresh reference
for a new gesture, and actual two-touch input straddling a divider. See the
implementation record at the top of the diagnosis. Physical Safari confirmation
of this revision is still required.
The new background/boundary check measured 0.49px maximum error, and the real
Chrome two-touch divider gesture with midpoint translation measured 1.97px drift.

On the physical iPhone:

1. Reload the HTTPS viewer to replace handlers from earlier revisions.
2. With cards hidden, pinch in/out near page 1 and well down the document. Watch a
   specific word between your fingers; it should remain near that midpoint.
   Specifically zoom out until multiple pages are visible, then pinch into one
   page. Repeat slowly and quickly, including near page transitions and while
   both card rails are present; watch for the previous abrupt jump.
3. Repeat several quick in/out reversals and pause with fingers still touching.
   Also try both fingers on side background, one on each side of a page divider,
   and moving the midpoint across a paper edge. Watch the zoom percentage as well
   as page movement: a camera snap and an excessive scale update are distinct.
4. Show comments and open a left tool; pinch on uncovered PDF content. Check
   highlights, a page transition and near the last page. Tool controls themselves
   remain ordinary controls. Unpinned left cards sit outside the document's left
   edge on mobile too; pan left to reach them. Check that they follow the PDF
   during horizontal panning. Pinned cards retain their viewport position.
5. Pan with **one finger** after pinching. While the finger remains down, check
   that the page follows it without jumping ahead. Distinguish that from normal
   coasting after release. Watch highlights throughout pinch-in and pinch-out,
   before lifting either finger: they should not need to snap back afterward.
   Tap a highlight, select text, add/cancel a comment, and use the tool controls. Pinch on app chrome separately: PDF-specific
   browser-zoom suppression must not apply there.
6. Report whether any remaining jump happens during finger movement, during a
   pause, on lifting fingers, or on starting the next pinch. Real document edges
   still constrain native scrolling; exact focal retention cannot require a
   scroll position beyond those limits.

The tunnel and OAuth callback do not change with these frontend edits. The
previous mobile research remains historical; successful emulation is not an iOS
Safari success claim.

## Mobile text selection

Reload the viewer, long-press PDF text and adjust its selection handles. PDF-only
callout/context-menu suppression is enabled for touch input when commenting is
allowed. Safari may still display its system Copy / Find Selection / Look Up menu.
The labelled Add comment action now stays at the bottom right of the visible PDF
viewport, with a minimum 44px touch target. Tap it and confirm the composer keeps
the selected quote and opens at the bottom-right of the viewer without automatically
focusing the editor. Tap the comment field to open the keyboard
without whole-site focus zoom (mobile textareas use 16px text). Tapping the title
or quote, or reopening the existing card, must not focus the text field. Open it
and scroll the PDF: the composer should remain in that visible corner, above the
keyboard, with the draft preserved. Cancel, change the selection and repeat near the viewport
bottom. Check that search and comment text fields keep normal editing menus.
Desktop retains the small icon beside the selection. Chrome automation verifies
selection preservation, scoped cancellation, button placement and composer flow;
physical iPhone native menu/handle behavior is not emulated.

The selection editor now renders compact 13px text using a transformed native
16px textarea, inside a stable 72px field. Check its height before and after the
keyboard opens: it should move up with the card rather than compress. In very
short viewports the containing card can scroll. Verify caret positioning,
multiline typing and selecting/editing a draft on the physical iPhone.
The card is now a fixed overlay outside the PDF's clipped workspace. Keyboard
positioning uses the full visual viewport, including Safari's viewport pan, rather
than its overlap with the PDF. Confirm the entire editor and Cancel/Comment
buttons remain visible when Safari moves the page/header offscreen on focus.
On the first editor tap, check the keyboard-opening animation specifically: the
card should move above the keyboard without briefly shooting toward the top.
That touch now requests focus with preventScroll to avoid Safari's native reveal
scroll competing with viewport docking. Once focused, tap within existing text
and adjust the selection to confirm normal caret behavior remains available.
On mobile Cancel, Add comment now immediately returns to its pre-composer bottom
corner, instead of following the keyboard down. The keyboard may cover that
corner until it closes. Check it does not hover above the retracting keyboard,
and that new selections and rotating the phone restore normal positioning.
Tap the header page number: it should open numeric entry without zooming the
website. Confirm a page using Go/Enter; navigation should dismiss field focus.

Safari controls the native previous/next/Done keyboard accessory and its URL bar.
They can still appear when the comment field is tapped; web content cannot reliably
remove them while preserving normal native editing. The URL is the tunnel hostname.
