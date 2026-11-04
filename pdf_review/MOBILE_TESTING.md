# Temporary iPhone testing

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

On the physical iPhone:

1. Reload the HTTPS viewer to replace handlers from earlier revisions.
2. With cards hidden, pinch in/out near page 1 and well down the document. Watch a
   specific word between your fingers; it should remain near that midpoint.
3. Repeat several quick in/out reversals and pause with fingers still touching.
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
