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

## Default PDF.js zoom

At the user's request, all app-owned pinch/zoom experiments have been removed:
custom touch handlers, the native-scale focal correction, Safari gesture-event
cancellation, forced supportsPinchToZoom and viewer/iframe touch-action overrides.
PDF.js vendor files and defaults are unchanged. Ordinary card dragging and
section-boundary interactions remain. No improved physical Safari behavior is
claimed; this is a return to the basic viewer behavior.

Reload the HTTPS viewer to discard previously installed JavaScript handlers.
The public test setup and Google callback do not need to change for this rollback.
The earlier research is retained in MOBILE_ZOOM_ARCHITECTURE_REVIEW.md as history.
