# Private Beta C1 — accounts, owner sharing and site administration

Local implementation and verification completed November 1, 2026. Nothing was
staged, committed, pushed or deployed. No production system, production database,
SSH, Google, Cloudflare or GitHub Secrets was accessed.

1. **Authorization model.** Three independent scopes are enforced: a user edits
   their own profile; document owners manage that document's ACL; explicit site
   admins manage beta membership and admin privileges. Existing owner/reviewer/
   viewer content semantics remain unchanged. Document ownership grants no site
   administration, and site administration grants no ordinary document/PDF access.

2. **Account/profile design.** `/account` is available to every current active,
   verified, allowlisted authenticated identity. It shows display name, verified
   Google email, active account status and a collapsed technical account ID. It
   exposes no Google subject, OAuth values, session contents or credentials.
   Account navigation is present on normal pages and in the viewer. Admin
   navigation is rendered only for explicit site admins.

3. **Display names.** The existing `users.display_name` field is reused. Names
   are trimmed, nonempty, at most 100 characters, and reject Unicode control or
   hidden formatting characters. Names are Jinja-escaped; duplicates are allowed.
   Only the authenticated user's name is writable. Unknown profile fields,
   including another user ID or identity/admin fields, are rejected. Existing
   Google logins preserve the chosen name. UUID, Google subject, verified email,
   grants, admin membership, comments and historical foreign keys are preserved;
   canonical comments naturally show the current presentation name.

4. **Document dashboard.** Owned by me and Shared with me are separate account
   sections. Current roles are displayed as badges. SQL selects only the user's
   ACL grants. Owners get Manage access links. Document links continue through
   the original ACL-protected detail/viewer/PDF endpoints.

5. **Owner sharing workflow.** Manage access is available from the account and
   document pages. It shows grants, display names, verified emails and roles.
   Owners select an existing active beta account and grant Viewer, Reviewer or
   Owner; existing grants support role changes and revocation. A newly granted
   owner immediately receives the same document-level controls.

6. **Sharing-directory privacy.** A dedicated service and owner-scoped endpoint
   return only `user_id`, `display_name` and verified `email`. IDs are selector
   keys, not a general identity dump. Users must be active, email-verified,
   Google-linked and enabled on the allowlist. Disabled/inactive/unlinked users
   and allowlist-only invitations are excluded. No admin flags, Google subjects,
   login timestamps or internal audit metadata are returned. The small beta uses
   a native dropdown; no new frontend dependency is introduced.

7. **Global invitations.** Owners cannot allow arbitrary emails, create users,
   prepare legacy identities or promote site admins. The owner UI explicitly
   explains that a missing recipient must first be invited by a site admin and
   sign in once. Crafted unknown-email/ID grants fail without expanding the
   allowlist or creating placeholder users.

8. **Admin dashboard.** `/admin` has Beta access, Users and Site admins sections
   with anchor navigation. Beta access lists email, enabled state, note and
   whether a stable identity exists. Users show account/admin state and stable
   UUIDs for administration. Forms allow/re-enable/disable/remove emails and
   grant/revoke admins. Allowing an email sends no email and grants no document
   access. There is no global document ACL web override in this slice; the
   existing offline CLI remains the support/recovery path.

9. **Site-admin model.** Migration 7 creates
   `site_admins(user_id, created_at, created_by)` with stable-user foreign keys.
   No first-user/domain/owner inference or automatic backfill occurs. Granting
   administration requires an existing eligible Google-linked beta identity.
   CLI commands are `list-site-admins`, `grant-site-admin USER_UUID`, and
   `revoke-site-admin USER_UUID`. HTTP always uses the session's stable ID and
   current database membership, never submitted or session-cached privilege flags.

10. **Final-owner protection.** Role changes, revocation and self-removal cannot
    remove/demote a document's last owner. The shared ACL service enforces the
    same rule for web and CLI under `BEGIN IMMEDIATE`. Add another owner before
    transferring ownership. Concurrent removal tests prove one owner survives.
    Legacy documents with no owner are not silently assigned; CLI bootstrap can
    explicitly grant their initial owner.

11. **Final-admin protection.** Revocation must leave another active eligible
    administrator. A disabled administrator does not count as a usable successor.
    Disabling or removing the final usable admin's allowlist entry is also
    rejected. Web and CLI share these rules; concurrent removal is tested.
    Offline CLI recovery can allow/re-enable an email and grant administration
    to another existing eligible identity when external account changes require it.

12. **Disable/delete semantics.** Disable retains the allowlist row. Remove
    deletes only that row and requires explicit confirmation for any associated
    established/prepared user. The web UI explains the effect and presents a
    required checkbox; CLI uses `remove-email EMAIL --confirm-established`.
    Unused typo entries need no established-account confirmation. Neither action
    deletes users, comments, revisions, grants or history. Both stop later HTTP
    access and login; re-enabling retains identities and prior grants.

13. **Audit trail.** `access_audit_log` stores ID, nullable actor user ID, fixed
    action, target type/identifier, JSON details and timestamp. It records email
    allow/re-enable/disable/remove, admin grant/revoke, and owner/offline document
    grant/role-change/revoke. Mutation and audit insertion are atomic. Document
    details contain target user ID and prior/new role; other details are empty
    objects. Notes, comment bodies, OAuth values, cookies and secrets are never
    copied into details. Offline actions have a null actor rather than an
    invented user. Update/delete triggers make audit rows append-only. Failed
    operations and unchanged grants create no records. Audit browsing and
    retrospective backfill are not included.

14. **Routes.** The new `accounts` blueprint has these explicit policies:

    | Method | Endpoint | Required scope |
    | --- | --- | --- |
    | GET | `/account` | Current active beta identity |
    | POST | `/account/profile` | Current user's profile |
    | GET | `/documents/<document_id>/access` | Document owner |
    | POST | `/documents/<document_id>/access` | Document owner |
    | GET | `/api/documents/<document_id>/shareable-users` | Document owner |
    | GET | `/admin` | Explicit site admin |
    | POST | `/admin/beta-access` | Explicit site admin |
    | POST | `/admin/site-admins` | Explicit site admin |

15. **Migration/schema.** The actual next migration is **7**, named
    `accounts_sharing_and_site_admins`. It adds the two tables above and replaces
    `idx_users_display_name` with a nonunique lookup index. It does not rewrite
    domain rows, create identities/grants/admins, or edit migrations 1–6. Tests
    compare all old table rows across repeated migration, check foreign keys,
    and prove duplicate names work afterward. The existing migration-6 legacy
    history preservation test also remains passing through current startup.

16. **Service architecture.** `review/access.py` contains account documents,
    profile changes, shareable users, ACL writes, allowlist writes, admin writes
    and administrative listings. Thin routes contain no raw SQL. The CLI calls
    the same mutation services. HTTP supplies an actor; absent actors are
    reserved for trusted offline operations. Existing CLI legacy ACL bootstrap
    remains available, while owner UI recipients must already be eligible beta
    identities. Write transactions recheck actor eligibility and owner/admin
    authority before mutation, preserving protection if authority changes after
    middleware authorization.

17. **CSRF/security.** All new writes are POST forms using the existing CSRF
    implementation. Every mutation family rejects missing, incorrect and
    non-ASCII invalid tokens. No GET writes state. Explicit account/owner/admin
    endpoint registries complement the existing document registry and keep
    default-deny behavior. Anonymous HTML reads redirect; anonymous APIs/writes
    return 401. Unrelated document access is 404, insufficient document roles
    and non-admin access are 403. Controlled validation failures return 422;
    authority changes inside write transactions return 403. New surfaces retain
    private/no-store caching and security headers. PDF GET/HEAD/Range checks
    still happen before content/blob lookup, including for site admins.

18. **UI/responsiveness.** Existing Jinja panels, typography, colors, form and
    flash conventions are reused. Access lists use wrapping rows and role badges
    rather than wide mandatory tables. Selectors and small-screen actions are
    touch-friendly; identity text wraps. Browser layout assertions passed at
    1024×768, 768×1024 and 390×844 for account, owner sharing and admin pages.
    The viewer change is limited to account/admin navigation in its existing
    identity area; review/PDF behavior is preserved.

19. **Tests/browser results.** `python -m unittest discover -s tests -q`:
    **135 tests passed** (115 existing plus 20 C1 tests). Coverage includes all
    requested scope boundaries, profile/history invariants, sharing eligibility,
    admin actions, CSRF, final-owner/admin rules, concurrency, migration safety,
    audit atomic rollback and stale authority between policy and transaction.
    Existing OIDC/Authlib, ACL, PDF/Range, comments/revisions, migration,
    Socket.IO, immutable storage, proxy/host, backup and health tests pass.
    `python -m pip check`: **passed**. Browser/WebSocket acceptance: **passed**,
    including existing collaboration/migration checks and all 19 C1 workflow
    expectations with no uncaught browser exceptions. Google is replaced only
    at the provider boundary inside the disposable browser fixture process;
    production has no fixture/login-bypass route. Real Authlib validation remains
    covered offline by existing JWT tests. Chrome's GPU process could not start
    in the restricted sandbox; the permitted local harness run outside that
    sandbox passed. Browser profiles, databases, PDFs and identities were synthetic.

20. **Secret/private-data scan.** Changed/new source and documentation were
    scanned for private keys, common provider tokens, real Google client
    identifiers, credential-bearing URLs, non-example email addresses, newly
    added literal UUIDs, and accidental runtime artifacts. No findings. Only
    example-domain/synthetic fixtures and placeholders were introduced. No
    environment file, PDF, database, cookie jar, browser profile, manuscript,
    production data or credential was added. Runtime `.env` and data were not
    opened or changed. This is a scoped source scan, not proof against every
    possible secret format. Git whitespace and diff review passed.

21. **Exact production bootstrap commands — documentation only.** After the
    existing deployment applies migration 7, use the existing privileged
    operator account and protected runtime environment wrapper:

    ```bash
    review_admin() {
        systemd-run --quiet --wait --pipe --collect \
            --uid=vsff --gid=vsff \
            --working-directory=/srv/vsff_website/pdf_review \
            --property=EnvironmentFile=/etc/vsff-review.env \
            --property=UMask=0077 \
            --property=Environment=PYTHONDONTWRITEBYTECODE=1 \
            /srv/vsff_website/pdf_review/.venv/bin/python -m flask --app wsgi "$@"
    }
    review_admin list-identities
    read -r -p 'Existing signed-in user UUID: ' REVIEW_USER_UUID
    review_admin grant-site-admin "$REVIEW_USER_UUID"
    review_admin list-site-admins
    unset REVIEW_USER_UUID
    ```

    Select the current user's existing stable UUID from `list-identities`.
    The user must already be active, verified, linked and allowlisted. Refresh
    Account, then use `/admin` for routine beta invitations. These commands were
    not executed against production by this task.

22. **Deployment compatibility.** No new dependency, secret, port, worker,
    Redis, callback, systemd unit, Apache rule, Cloudflare change or service is
    required. The existing dependency-update, SQLite-snapshot, restart,
    startup-numbered-migration and `/healthz` flow remains compatible. No
    infrastructure or existing VSFF frontend/backend/workflow file was changed.

23. **Files changed.** Fourteen existing files:
    `pdf_review/README.md`, `ARCHITECTURE.md`, `review/__init__.py`,
    `review/auth.py`, `review/auth_cli.py`, `review/database.py`, `review/users.py`,
    `static/app.css`, `templates/base.html`, `templates/document.html`,
    `templates/viewer.html`, `tests/browser_sanity.py`, `tests/test_auth.py`, and
    `tests/test_packaging.py`. Eight new files: `review/access.py`,
    `review/account_routes.py`, `review/migration7.sql`, `templates/account.html`,
    `templates/access.html`, `templates/admin.html`, `tests/test_accounts.py`,
    and this report. Paths after the first are relative to `pdf_review/`.
    Everything remains unstaged/uncommitted.

24. **Limits/deviations.** The dedicated sharing endpoint is owner-scoped to a
    document, narrower than a global authenticated directory. Small-beta native
    selectors are used instead of autocomplete. Global web ACL support/override
    and audit browsing are optional and omitted; CLI recovery remains. No account
    deletion, account-deactivation UI or email delivery was added. Admin/account
    pages refresh normally. Existing idle sockets can retain room membership
    until the next authorization check (page event, join/reconnect); there is no
    proactive eviction. Presence may retain the old display name until rejoin.
    Final-owner safety counts owner grants; disabling a beta account retains its
    grants by design, so offline recovery remains relevant for inaccessible
    owners. External Google email/account changes can require offline admin
    recovery. Real Google, real iPad hardware and production deployment were not
    exercised. No production access is claimed.
