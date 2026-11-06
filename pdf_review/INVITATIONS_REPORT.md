# Trusted Users and private beta invitations

Implemented locally November 5, 2026. No production access, deployment, push,
credential changes or real database migration was performed. Pre-existing root
README and operations runbook edits were preserved.

## Behavior

- Site admins alone grant/revoke Trusted User status and manage beta suspension.
  The migration does not add admins or promote existing members.
- Trusted Users/admins can create email-bound beta invitations, see the member
  directory and manage their invitations. Document ownership is separately
  required for document invitations. Ordinary owners can share with existing
  active members by email. New document invitations offer Viewer/Reviewer only.
- A new recipient opens the copied link, continues through Google with the
  matching verified email and lands on the shared document or beta dashboard.
  The account, beta admission, grant and acceptance audit commit together.
  Existing active members receive access immediately; existing roles are preserved.
- Links expire after seven days. Duplicate pending recipient/document invitations
  reuse the existing invitation for its creator; other creators get an explained
  conflict without the link. Revoke/renew controls invalidate old links. Renewal
  is atomic. At most 100 pending invitations are allowed per inviter.
- Pending invitations are retired when their creator loses the trust/ownership/
  membership used to invite. Acceptance rechecks current authority transactionally.
  Already accepted membership/grants remain. An admin removal/suspension creates
  a persistent membership block, which Trusted Users cannot bypass by re-inviting.
- Dashboard document lists refresh while visible every 15 seconds and on tab
  focus/visibility changes, preserving an unfinished document-title draft.
- Admin history presents readable events with actor, recipient, dates and inviter,
  plus collapsed technical details and older-event pagination. Invitation lists
  show 200 recent entries. Directory and policy disclosures were updated.

## Privacy and identity

Trusted Users see only names, emails, site roles, membership status, inviter and
available dates in the directory. It does not include documents, per-document
roles, feedback, reading activity, Google subjects or private admin notes.
Invitations do not grant any unrelated document access. Site admins still need
normal document ACLs for content, including PDF GET/HEAD/Range and realtime rooms.

Only `openid email profile` is requested. Authlib state, nonce, PKCE and signed
OIDC validation remain. Wrong-account retry uses Google's account chooser.
An invitation's signature is HMAC-SHA256 over an ID and random nonce with a
domain-separated message under the persistent application secret. Signatures
are not stored in SQLite or audit logs. The URL fragment keeps the credential
out of HTTP paths/query logs; the landing script removes it from visible browser
history and submits it by CSRF-protected POST. A generic public GET reveals no
recipient or document and never redeems an invitation. OAuth retains only the
verified invitation ID/nonce in the signed session. No reusable public link or
automatic email delivery is introduced.

## Migration and historical attribution

Migration 14 adds trusted_users, beta_memberships and invitations plus indexes.
It preserves existing identity, site admin, document/ACL, immutable PDF and review
records. Existing memberships are attributed to the sole existing site admin,
as requested. Without a sole admin, known creators are preserved; an explicit
admin action or `attribute-legacy-invitations ADMIN_USER_ID` attributes remaining
unassigned historical memberships. No name/email heuristic selects an admin.

Old allowlist creation dates are shown as **Beta access recorded**, not exact
invitation dates. Historical `last_login_at` is a **Joined by** bound; an earlier
first login is not invented from legacy user creation dates. New invitations and
first Google identity links record exact UTC timestamps, with join information
preserved across Google email changes. Backfill audit events have the real
migration timestamp and are distinguished from newly sent invitations.

Back up real SQLite before normal startup/deployment applies migration 14. No
schema is automatically downgraded. The existing single-worker backup/migration
deployment flow applies; no dependency, secret, port or proxy change is needed.

## Validation

- Full unit/security suite: **211 tests passed**. Coverage includes signed OIDC
  invitation login, wrong-account retry, bad signatures, revocation during OAuth,
  scopes, CSRF, role/ACL privacy, admin-only actions, suspension/re-invitation,
  duplicate creation, concurrent redemption, renewal rollback, retained ownership,
  expiration and secret-free append-only audit. The final malformed-token guard
  was additionally verified with its focused lifecycle test.
- Populated synthetic migration-13 upgrade is repeatable, preserves original
  user rows, attributes the sole admin and labels historical dates accurately.
  SQLite integrity and foreign-key checks pass.
- `tests/browser_sanity.py --invitations` passes with the existing temporary
  fixture and offline Google provider boundary: trust promotion, populated member
  directory, desktop/mobile bounds, copyable link/fragment handling, wrong-account
  rejection, new-member sign-in/direct document access, immediate sharing, dashboard
  update without reload or draft loss, and audit history. No uncaught JS exceptions.
- Rendered creation, populated mobile directory and mobile history screenshots
  were inspected under ignored `tests/visual-artifacts/`. Browser execution used
  an approved run outside the sandbox after its local Chrome DevTools connection
  failed inside the sandbox. No real account, browser profile or PDF was used.
- Git whitespace checks pass. Vendored PDF.js, existing migration SQL, VSFF
  frontend/backend and deployment workflow are unchanged.

## Operating limits

Real Google consent/production HTTPS and physical mobile-device acceptance remain
operator checks. Email delivery, open reusable links and account erasure remain
deferred. Expiry is always enforced at redemption; listings derive expired status
without GET writes. Creation/revocation and the optional `expire-invitations` CLI
record expiration events. No background scheduler is installed. Invitations to
logical documents remain independent of individual PDF versions: deleting a
version does not delete the document or revoke its ACLs.
