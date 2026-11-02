# PDF Review

## BETA C2 â€” review settings and document sections

This local version adds owner-controlled **Shared / Isolated** review, personal
**Everyone / Mine / People** filters, persistent document-specific viewer choices,
a 24-color Account palette, page/spread presence, logical sections and exact-version
section feedback. See [BETA_C2_REPORT.md](BETA_C2_REPORT.md) for the audit and checks.

- Owners open **Review settings** from the document page to set privacy and
  first-open spread/comment/scope defaults. Existing personal choices survive
  later default changes. **Reset to document defaults** is in Comments.
- Isolated non-owners receive only their own top-level conversations and replies
  within them. Owners can inspect all review and apply convenience filters.
  Personal filtering hides whole conversations by top-level author, preserving
  replies. People lists content authors for this exact version, never beta emails.
- **Account â†’ Review color** selects a fixed palette entry. Highlight and section
  response accents follow the top-level author. Initials supply presence avatars;
  the application makes no external avatar requests.
- Owners use **Manage sections** to add, rename, reorder, prompt or archive sections.
  Select a version and follow **Define boundaries / Import from PDF outline**.
  In the viewer, **View â†’ Edit sections** opens the deliberate edit mode. Choose
  Set start / Set end, click the PDF, inspect preview markers, then Save boundaries.
  A click near a page edge chooses a page boundary; an interior click chooses a
  precise canonical Y. Normal text commenting resumes after capture/Done.
- Precise ends have neutral left-edge ticks; page/spread-row ends have compact
  horizontal rails in the existing gap. Boundaries inside a spread retain that
  spread. Feedback stays on the right and supports one response per reviewer,
  section and exact version, with replies, author-only edits and tombstones.
- New PDF versions leave section placements unmapped. Management shows previous
  placement summaries; the owner confirms new placements. Outline import previews
  names/start pages and a selectable flat subset; nothing is created until confirmed.

Startup applies migration **8**. Back up real SQLite with the existing online
backup helper before a later approved deployment. No runtime data is migrated
by this development task. Existing immutable PDFs and migrations 1â€“7 are unchanged.

Local synthetic verification:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe tests/browser_sanity.py
.\.venv\Scripts\python.exe tests/browser_sanity.py --beta-c2
.\.venv\Scripts\python.exe tests/browser_sanity.py --comment-ui
.\.venv\Scripts\python.exe -m pip check
```

C2 screenshot artifacts remain ignored under `tests/visual-artifacts/`. Real
Google, production deployment and physical Safari/iPad testing are separate.
Resilient pseudo-offline review remains deferred to a future dedicated slice;
this version adds no outbox, IndexedDB, service worker or private PDF cache.

This directory is an independent service in the VSFF repository. It needs neither
the Vue frontend nor the VSFF backend. See [BETA_B1_REPORT.md](BETA_B1_REPORT.md)
for the packaging audit. No VPS deployment is included in this slice.

The [B2A deployment bundle and operator runbook](../ops/pdf_review/README.md)
contain proposed systemd, Apache, environment and deployment-script artifacts.
They have not been installed on the VPS. See [BETA_B2A_REPORT.md](BETA_B2A_REPORT.md)
for local validation and limits.

## Packaged runtime and production configuration

`PDF_REVIEW_DATA_DIR` selects a private runtime directory. When unset, development
uses `data/` beside this README, independent of the current working directory.
An absolute path is recommended. A new checkout starts empty: the standalone
project's data is never discovered, imported, moved, or modified automatically.

| State | Default location |
| --- | --- |
| SQLite, including WAL/SHM sidecars | `<data-dir>/pdf_review.sqlite3` |
| Immutable SHA-256 blobs | `<data-dir>/blobs/<sha256>.pdf` |
| SQLite backup snapshots | `<data-dir>/backups/` |

`PDF_REVIEW_DATABASE` optionally overrides the SQLite file only. Blob paths remain
relative to the storage root, so existing database identities need no rewrite.
Factory callers may still explicitly override `DATABASE`, `STORAGE_ROOT`, and
`BACKUP_DIR`; `DATA_DIR` is also accepted as factory configuration.

For isolated Windows development, set `$env:PDF_REVIEW_DATA_DIR` to an absolute
private directory before running the app or CLI. Keep the same setting for all
maintenance commands. Existing local data stays where it is unless an operator
deliberately copies it during a separate migration task.

```powershell
python -m flask --app app backup-database
python -m flask --app app verify-storage
```

`backup-database` uses SQLite's online backup API, including committed WAL data,
and writes a unique snapshot under the configured runtime backups directory.
It does not copy PDFs. A complete recovery requires the matching immutable blobs
as well as the database; production backup scheduling, destinations, retention,
restore acceptance, and off-host copies belong to the deployment slice. Never
copy a live SQLite database with a plain filesystem copy.

### Production entrypoint (Linux; preparation only)

Install `requirements.txt` into a dedicated environment. Gunicorn is included on
non-Windows platforms; `simple-websocket` explicitly supplies WebSocket support
for Flask-SocketIO's threading driver. From this directory, with the protected
production environment already loaded, use:

```sh
gunicorn --config gunicorn.conf.py wsgi:app
```

The configuration selects **one worker process**, the `gthread` worker, 100
threads, and `127.0.0.1:8002`. Each long-lived WebSocket occupies a thread; the
pool must also have capacity for ordinary HTTP requests. A startup guard rejects
multiple workers and incompatible workers. Socket.IO client/room state and
presence aggregation live in memory inside that single process. Additional
processes or instances require a future shared message and presence backend.
Do not use `--workers 2`, horizontal scaling, or overlapping service instances.

`PDF_REVIEW_HOST` and `PDF_REVIEW_PORT` override the bind. The supplied Gunicorn
configuration accepts loopback hosts only. `app.py` remains the Windows/local
development launcher, defaulting to `127.0.0.1:5000` and honoring those variables.
Its development server is not the production entrypoint. `wsgi.py` does not load
`.env`, run a server, or contact Google at import. It requires production mode
and an absolute external data directory, and rejects a database override inside
the repository. Existing production authentication checks run before SQLite setup.

Environment expected for the future Linux service (examples, never credentials):

| Variable | Production expectation |
| --- | --- |
| `PDF_REVIEW_ENV` | `production` |
| `PDF_REVIEW_DATA_DIR` | Absolute private path, for example `/var/lib/vsff-review` |
| `PDF_REVIEW_DATABASE` | Optional absolute external SQLite file override |
| `SECRET_KEY` | Strong random persistent secret, at least 32 characters |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Real Web application credentials supplied privately |
| `PDF_REVIEW_SERVER_NAME` | Verified public hostname; no scheme or path |
| `PDF_REVIEW_SCHEME` | `https` (production default) |
| `PDF_REVIEW_COOKIE_SECURE` | `1` (production default) |
| `PDF_REVIEW_PROXY_HOPS` | `0` default; `1` only after trusted ingress isolation |
| `PDF_REVIEW_HOST` / `PDF_REVIEW_PORT` | Optional loopback bind; default `127.0.0.1:8002` |

A later service may load `/etc/vsff-review.env` through its supervisor. No such
live file or service is created by these source tasks. Templates are in `ops/pdf_review/`.
The proposed origin
`https://review.venasff.com` is a future environment setting, not a code constant.
OAuth callbacks continue using the configured canonical host and HTTPS scheme.
ProxyFix trusts no headers by default; enabling one hop trusts forwarded scheme
only, not forwarded host, address, port, or prefix. Host validation and explicit
Socket.IO same-origin checks remain enabled. The future reverse proxy must
preserve the intended host and support WebSocket upgrades and long polling.

Production retains Secure, HttpOnly, SameSite=Lax, host-only cookies, with the
dedicated cookie name `pdf_review_session`. It shares no session, allowlist,
database, models, or routes with VSFF. Stable Google identities, verified-email
allowlisting, document ACLs, CSRF, and authorization before PDF/Range access are
unchanged. Real Google login and the future HTTPS reverse proxy require manual
acceptance when configured.

### Public repository boundary

Commit source, placeholder `.env.example`, public vendor assets/licenses, SQL
migrations, and synthetic tests only. Never add `.env`, credentials, allowlists,
real reviewer emails/comments, manuscript prose/PDFs, SQLite files, blobs,
backups/baselines, logs, browser profiles, or generated caches. Both ignore files
exclude common runtime artifacts; ignore rules do not replace content review.
The unused PDF.js demonstration PDF is omitted; retained vendor bytes are
unchanged. Tests generate their PDFs and keep runtime state in temporary folders.

The production configuration follows the official [Flask-SocketIO threaded
Gunicorn deployment guidance](https://flask-socketio.readthedocs.io/en/latest/deployment.html).

PDF Review is a local Flask application for reviewing immutable PDF versions. It stores exact PDF bytes in content-addressed storage, keeps text anchors in PDF coordinate space, and stores document-owned discussion threads outside the PDF.

Slice 5 adds deliberate manual carry-forward between immutable versions, re-anchoring, effective targets, provenance, and migration history. Realtime collaboration, author-only editing, and resolution history remain intact. Private Beta A adds Google OIDC authentication, a database allowlist, document ACLs, and mutation CSRF. Automatic migration remains deferred.

## Setup and launch

Python 3.11 or newer is recommended.

```powershell
cd "C:\vena\Obsidian\writing\Code\vsff_website\pdf_review"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with your Google development credentials and persistent secret.
python app.py
```

Open <http://127.0.0.1:5000>. The Socket.IO-capable development server binds only to `127.0.0.1`. Dependencies include Flask (`>=3.1.3,<4`), Flask-SocketIO (`>=5.7,<6`, threading mode), Authlib (`>=1.9.1,<2`) and requests (`>=2.32.5,<3`); SQLite is supplied by Python. Configure Google and a persistent session secret before signing in, as described below. PDF.js v6.4.299 and Socket.IO browser client v4.8.4 are vendored for offline use. No frontend build or runtime CDN is required.

`python app.py` uses `app.extensions["socketio"].run(...)` with Werkzeug explicitly enabled for this local development application. The application factory initializes an independent SocketIO instance per Flask app. Maintenance commands such as `python -m flask --app app verify-storage` still work.

## Review workflow

1. Create a logical document and import a PDF version.
2. Sign in with your allowlisted Google account and open a version you have permission to review.
3. Select PDF text and click **Comment**.
4. Enter a plain-text comment and submit it.
5. The server atomically creates the anchor, thread, origin target, root comment, and initial revision.
6. Click a highlight to select its sidebar thread. Click a thread card to navigate to and center its first anchor segment.
7. Reply, edit, soft-delete, resolve, or reopen from the thread card.

Clicking **Comment** only opens the composer. Canceling creates no database objects. The database commit is authoritative; the browser refreshes from successful API results.

The **Anchor diagnostics** disclosure keeps Slice 2's independent anchor tools available. Test anchors are intentionally separate from ordinary review threads.

## Authenticated identities (Private Beta A)

Google OIDC `sub` is the durable external identity. The authenticated Flask session contains the stable local `user_id`, a CSRF token, and the session lifetime flag. Verified Google email, an enabled database allowlist entry, active user status, and a document grant are all required. Authorization is reread from SQLite for each protected request. `GET /api/reviewers` now returns only the current account; reviewer creation/switch APIs have been removed.

Legacy stable users and historical authorship remain intact. Before first login, an administrator can prepare one enabled allowlisted email for one unlinked active user with `link-google-email`. Display names never link accounts. Subject matches take precedence; conflicting subjects/emails or ambiguous matches fail closed. New allowed accounts without an explicit legacy association receive a new stable user with no existing document grants. Current verified email changes must also be allowlisted, and cannot take another user's prepared email. Email normalization trims and case-folds only; dots, plus tags and domains are preserved.

See [Private beta setup and acceptance](#private-beta-setup-and-acceptance) below for the exact Google and CLI setup. No selectable identity fallback exists, including in development. Local service functions remain usable by trusted offline maintenance code; they are not public APIs.

## Thread and target model

A thread is a document-owned conversation, not a page/comment pair and not a permanent synonym for one anchor.

```text
document
  -> thread
       -> thread_target (origin)
            -> immutable anchor_instance
                 -> exact document_version
       -> comments
            -> append-only comment_revisions
```

Every committed thread has one designated immutable origin target. Migration 3 uses a deferred `threads.origin_thread_target_id` foreign key, an `origin` role, and a partial unique index to enforce exactly one origin. Triggers ensure the target anchor belongs to the thread's logical document and prevent the origin from being replaced or edited.

Slice 3 created `origin` targets. Slice 5 adds `manual` targets pointing at new immutable anchors; it never rewrites the origin. `projection` remains reserved for future algorithms.

Threads returned for a viewer use the single effective target head on that exact PDF version. Superseded targets remain historical and do not render duplicate highlights. A Draft 3-only thread does not appear on Draft 4 until deliberately carried. Ordering is deterministic by first target page, visual vertical position, creation time, and ID.

## Manual carry-forward and re-anchoring (Slice 5)

From a document page choose **Carry feedback forward / migration history**, sign in as a document owner and select explicit source/target versions, and start a run. Version labels, filenames, import dates, and page numbers never imply a source-to-target relationship. Both versions must belong to the same logical document and differ.

The run opens the existing target PDF viewer with `?migration=<migration_id>`. Its migration panel lists source discussions with pending/carried/skipped states and counts. Select a discussion to inspect its source quote, page, comments, and global resolution state; **Go to source** opens the source version and centers the current effective target. Select corresponding target text and click **Carry thread here**. No quote search, fuzzy match, page guess, or automatic projection occurs.

Carry-forward atomically creates a new immutable anchor and segments, a `manual` thread target, provenance, a destination effective head, and the carried item decision. It creates no thread, comment, revision, or resolution-history copies. Source and destination remain one logical conversation. Replies, author-only edits, tombstones, and global resolution changes synchronize across all effective version rooms.

Select an already carried discussion and new target text to **Re-anchor selected thread here**. This creates another immutable manual target and moves the head. The old anchor, target, and provenance remain stored. The origin version's head is permanently fixed to its origin target and cannot be replaced or detached. Corrections require an open run; after completion, create a later run between the same versions if needed.

**Don't carry to this version** records a reviewer, timestamp, and optional note for a pending item without a destination. It neither resolves the thread nor creates an anchor. Skipped decisions are final within that run; a later run can reconsider them. Complete a run only after every item is carried or skipped. Completion records its reviewer/time and is idempotent; it does not freeze review discussions or document versions.

The default source filter shows open discussions. **All** includes resolved discussions, which can also be carried. Runs snapshot the effective source targets when created (including manual targets in migration chains). New source threads added afterward require a new run. Source discussion content remains canonical rather than copied; before a pending thread has a destination, use **Refresh source discussions** to fetch source-only changes. Once carried, the normal target room receives its discussion updates automatically.

Existing destination heads are represented as carried at run creation without new anchors; the run creator/time records acceptance of that existing mapping for this run, while target provenance retains its original creator. If another run adds a destination while this run is open, **Keep existing target** explicitly accepts it for the pending item. Destination head IDs and item revision numbers provide optimistic concurrency; stale mapping decisions return 409 instead of silently overwriting another reviewer. Review/reselect the refreshed source item before retrying.

**Target history / diagnostics** in a selected migration item shows every target, its version and role, effective/superseded state, and full provenance. Historical anchors can also be inspected through the JSON history API. The ordinary viewer loads standalone diagnostic anchors separately from effective thread anchors, so superseded thread anchors cannot reappear as standalone highlights after reload.

### Migration 5 schema

- `thread_target_heads`: primary key `(thread_id, document_version_id)`, pointing to the effective immutable target with updater/time. Database triggers validate thread/version consistency and permanently protect origin heads. New origins automatically receive a head within thread creation's transaction.
- `migration_runs`: explicit document, source, target, creator/time, strategy (`manual` for this slice), open/completed status, and completion actor/time. Repeated runs between a version pair are allowed.
- `migration_items`: one source-thread snapshot per run, source target, pending/carried/skipped decision, destination target if carried, actor/time, optional skip note, and optimistic revision number. Source snapshot identity is immutable.
- `thread_target_provenance`: immutable source target, migration run, creator/time, method (`manual_selection`), and nullable future confidence/algorithm version. Manual operations leave automatic metadata null. `supersedes_thread_target_id` explicitly links corrections to the previous target, so a separate supersession table is unnecessary.

Foreign keys, checks, unique indexes, and cross-table triggers enforce consistency, history immutability, valid source snapshots/destination targets, and completion policy. Service validation also checks expected heads and item revisions under `BEGIN IMMEDIATE`. Migrations 1â€“4 are unchanged. Migration 5 backfills every origin head and deterministically selects the most recent existing non-origin target on any legacy extra versions. It does not invent unknown provenance for pre-5 diagnostic targets. No existing domain rows are rewritten.

### Migration HTTP APIs

- `GET/POST /api/documents/<document_id>/migrations`; creation accepts exactly `{source_version_id, target_version_id}`.
- `GET /api/migrations/<migration_id>` returns run metadata, counts, source context/current discussions, item decisions, and current destination IDs.
- `POST /api/migrations/<migration_id>/items/<item_id>/carry` accepts `{anchor, expected_revision, expected_target_id}`; the expected destination is null for initial carry.
- `POST .../reanchor` accepts the same fields and requires the currently effective non-origin destination ID.
- `POST .../skip` accepts `{expected_revision, note}`.
- `POST .../accept` accepts `{expected_revision, expected_target_id}` to explicitly keep a concurrently created destination.
- `POST /api/migrations/<migration_id>/complete` accepts `{}`.
- `GET /api/threads/<thread_id>/targets` returns all historical targets and provenance, marking current heads.

Mutations use the authenticated Flask-session user and require an owner grant plus CSRF. Unknown fields (including supplied author IDs) are rejected. Invalid mappings/notes return 422, missing objects 404, absent reviewer or stale/closed decisions 409. No migration writes occur through sockets.

Post-commit `thread.targeted` / `thread.reanchored` notifications use the existing schema-1 `review.changed` protocol. All thread mutation broadcasts now query effective heads, not historical targets. Small `migration.changed` notifications invalidate the current run UI in the explicit source/target rooms after run decisions/completion; they carry only schema version, run ID, and affected version ID. Clients refetch canonical HTTP state. Emit failures remain secondary and cannot undo successful writes.

## Comments, revisions, and deletion

Comments have stable IDs, thread relationships, original authors, timestamps, and a current plain-text body. Bodies are limited to 10,000 characters and are rendered with DOM `textContent`, not HTML or Markdown.

Every creation or edit appends an immutable row to `comment_revisions`:

- revision 1 contains the original body;
- later revisions contain each edited body and the reviewer who made that edit;
- `comments.body` holds the current body for ordinary reads;
- `edited_at` marks comments that changed.

Deleting a comment is a tombstone operation. The current public body becomes `NULL`, deletion metadata is recorded, and the UI displays `This comment was deleted.` Revision rows, comment identity, authorship, replies, thread, anchors, and PDF versions remain intact. Deleted comments cannot be edited. There is no ordinary hard-delete endpoint.

## Resolution

Threads move between `open` and `resolved`. Resolving records the timestamp and authenticated user; reopening clears current resolution fields without removing discussion history. Repeated resolve or reopen requests are idempotent. Resolved highlights are subdued and remain available through the **All** filter.

Every actual resolve/reopen transition now also appends immutable `thread_status_changes` history in the same transaction. Canonical thread JSON includes `status_history` with action, actor identity/display name, and timestamp. The sidebar shows the latest action (for example, **Reopened by ReviewerBeta**) and a **Resolution history** disclosure for earlier actions; these update through normal realtime canonical refreshes.

Migration 4 adds this domain history because the prior schema retained only the current resolution and cleared it on reopening. Migrations 1â€“3 are unchanged. Existing resolved threads retain their known resolver/time as an initial history entry. Earlier reopen actions and superseded resolutions cannot be reconstructed and are not invented. The migration is automatic on the next application start; restart the server to load the updated services and schema.

## Atomic selection-to-comment creation

`POST /api/versions/<version_id>/threads` uses Slice 2's strict anchor validator, then performs one SQLite transaction containing:

1. immutable anchor instance;
2. all anchor segments;
3. document-owned thread;
4. immutable origin thread target;
5. root comment;
6. initial comment revision.

If any insertion or validation fails, none of these objects remains. The independent anchor API continues to use the same reusable validated-anchor insertion seam.

## JSON APIs

Identity:

- `GET /api/reviewers` returns only the authenticated account.
- No reviewer creation or switching routes exist.

Discussions:

- `GET /api/versions/<version_id>/threads`
- `POST /api/versions/<version_id>/threads` with `{ "anchor": {...}, "body": "..." }`
- `POST /api/threads/<thread_id>/comments` with `{ "body": "..." }`
- `PATCH /api/comments/<comment_id>` with `{ "body": "...", "expected_revision": 1 }`
- `DELETE /api/comments/<comment_id>` (soft deletion)
- `POST /api/threads/<thread_id>/resolve`
- `POST /api/threads/<thread_id>/reopen`

Independent anchor diagnostics:

- `GET /api/versions/<version_id>/anchors`
- `POST /api/versions/<version_id>/anchors`
- `DELETE /api/anchors/<anchor_id>`

Mutation routes derive authorship from the authenticated Flask-session user. They do not accept client-supplied author IDs.

Canonical comments include `current_revision` (the maximum immutable revision number) and the existing `revision_count`. Edits require a positive integer `expected_revision`; missing fields return 400, invalid revision types/values return 422, and a stale revision returns 409 with `error.code = "comment_conflict"` and `error.current_revision`. The service checks the revision under the existing `BEGIN IMMEDIATE` transaction before appending history. A conflict creates no revision and emits no notification. The sidebar refreshes canonical state, preserves the draft, and requires explicitly accepting the latest revision before another save.

## Realtime collaboration

SQLite and HTTP services remain authoritative. All six discussion mutation routes call their existing services; only after a successful service return and commit do routes call `notify_thread_changed`. This helper queries the logical thread's effective version heads (origin, manual, or future projection) and emits to each `version:<version_id>` room. Lookup/emit errors are logged and do not turn committed HTTP writes into failures. Direct service calls outside the HTTP routes do not automatically broadcast.

The small `review.changed` notification has `schema_version: 1`, ephemeral UUID `event_id`, UTC `timestamp`, `kind`, `document_id`, `thread_id`, nullable `comment_id`, and the recipient `version_id`. Kinds are `thread.created`, `comment.created`, `comment.edited`, `comment.deleted`, `thread.resolved`, and `thread.reopened`. It carries no canonical comment body. Successful idempotent operations may emit a redundant invalidation; canonical state is unchanged.

Clients use same-origin Socket.IO and refetch `GET /api/versions/<version_id>/threads`. One refresh runs at a time; events during it mark the state dirty for a subsequent read. Local HTTP responses update the current browser immediately, invalidate older in-flight reads, and schedule canonical reconciliation. Target anchors from canonical threads update the existing overlay, including new remote highlights. Failed refreshes retain the current UI and retry after five seconds.

`Live`, `Reconnectingâ€¦`, `Offline`, and sync-error status explain connection state. Each connection/reconnection joins the validated exact-version room, obtains presence, and refetches threads. Events are never durably logged or replayed. HTTP reviewing continues if the socket or its browser library is unavailable. If the whole server is stopped, HTTP is naturally unavailable too; it resumes when the server restarts.

Socket handlers only support `review.join` (`{version_id}`), `review.leave`, and `review.page` (`{page}`), plus connection/disconnection. Join/page acknowledgements contain `ok` and an error message when rejected. A connection belongs to at most one viewer version room. Anonymous and globally unauthorized sockets are rejected. Joining requires a current document grant; viewers can receive notifications but cannot mutate through HTTP. Default same-origin checks remain enabled; there is no wildcard CORS.

`review.presence` snapshots contain `schema_version: 1`, `version_id`, and `reviewers` with stable `user_id`, database `display_name`, `connection_count`, and nullable `page`. An app-local `RLock` protects per-SID membership, aggregation, and snapshot emission. Named presence is aggregated by reviewer identity; one tab leaving decrements the count, and the final tab leaving removes that reviewer. The latest reported page among remaining sockets is advisory. It is sent only on page changes, throttled to one report per 350 ms. Presence is never stored in SQLite.

Sockets read the authenticated Flask-session identity without modifying the session. There is no reviewer switching or identity-reconnect UI. Navigation explicitly disconnects on `pagehide`; restoring a cached page reconnects on `pageshow`. Abrupt network loss is removed after Socket.IO detects the disconnect, rather than instantly.

## Immutable versions and storage

`documents` is the continuing logical work. `document_versions` is one immutable representation with an exact SHA-256, canonical `blobs/<sha256>.pdf` path relative to runtime storage, size, import timestamp, and optional external metadata. Different bytes create a new version; identical bytes may share a blob while retaining distinct version records.

Imports stream to a temporary file, hash and minimally validate the bytes, flush them, and publish without overwriting an existing digest path. Source files are read only. Comments and highlights never alter PDF bytes.

Verify all recorded blobs:

```powershell
python -m flask --app app verify-storage
```

## Anchors and PDF.js integration

Text selections retain exact selection text, per-page quote/context selectors, page-local offsets, server-computed page-text fingerprints, and one or more ordered page segments. Canonical rectangles are stored in PDF page coordinates and converted through the current PDF.js viewport for capture and rendering.

The app wraps the unmodified PDF.js v6.4.299 generic viewer. App-owned overlay code listens to page, text-layer, scale, rotation, initialization, and view-area events. It renders against stable page bounds rather than the recyclable text layer, rebuilds idempotently, and centers navigation on the target highlight.

PDF.js's CSP blocks dynamically inserted style text. Highlight styling therefore lives in `static/review/anchor_overlay.css`, loaded as a same-origin external stylesheet. Dynamic element positioning remains inline because it is required for PDF-space geometry and works under the existing CSP.

Thread highlights have normal, selected, hover, and resolved states. Standalone test anchors retain the Slice 2 highlight. No PDF.js annotation editor data is used.

## Migration 3 schema

- `users`: stable UUID identity, display name, active flag, creation time.
- `threads`: document identity, creator, designated origin target, open/resolved state.
- `thread_targets`: immutable link from a thread to an anchor with `origin`, `projection`, or `manual` role.
- `comments`: stable message identity, current body, author, edit and tombstone metadata.
- `comment_revisions`: immutable ordered body history with editor identity.

Foreign keys, checks, partial unique indexes, deferred origin linkage, and triggers enforce history and document consistency. Migrations 1 and 2 are unchanged.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use isolated temporary databases/storage and cover migrations, immutable storage, anchors, users, session identity, atomic rollback, document consistency, replies, revisions, tombstones, resolution, exact-version filtering, ordering, and APIs.

`tests/test_realtime.py` uses Flask-SocketIO's test client for room isolation, anonymous rejection, authenticated session identity, multi-tab presence, page validation, committed mutation events, rollback, multi-target broadcasts, emit failure independence, reconnect recovery, and edit conflicts.

An optional headless Chrome/Edge sanity check uses DevTools directly, with no browser framework or additional package dependency:

```powershell
python tests/browser_sanity.py
```

It creates temporary generated PDFs, storage, database, and independent browser sessions. It checks the actual viewer, cross-browser updates, presence, draft preservation/conflicts, centered highlights, offline HTTP actions, reconnection, version isolation, and refresh coordination. It never uses the application's persistent review data.

## Two-browser collaboration acceptance test

Use two browsers, separate browser profiles, or a regular and an incognito window so A and B have independent authenticated Flask sessions. Ordinary windows in the same profile share the signed-in account.

1. Start `python app.py`; open the same exact PDF version in A and B. Sign in to separate allowed accounts in A and B, each with document access. Both should show **Live** and both names under **Viewing now**.
2. Change B's page; A should show its new page shortly afterward. Open a second ReviewerBeta tab: ReviewerBeta should still appear once. Close that tab: ReviewerBeta should remain until the last ReviewerBeta connection leaves.
3. Select text in A, click **Comment**, and submit. B should show the thread and its PDF highlight without reload. Click the thread to confirm centered navigation.
4. Reply in B; confirm A updates. Edit in A; confirm B shows the canonical edited body.
5. Delete a comment in B; confirm A shows the tombstone. Resolve in A; select **All** in B and confirm the resolved card and subdued highlight. Reopen in B; confirm A updates.
6. Confirm ReviewerBeta cannot edit ReviewerAlpha's comments and ReviewerAlpha cannot edit ReviewerBeta's comments. To test simultaneous editing, sign in as the same comment author in both browsers and open that comment's edit form in each. Save A, then save B's stale draft. B must show the explicit conflict, preserve its unsaved text, and display A's canonical text. Review the current body, choose **Use latest revision for next save**, and retry or cancel. Log out and sign B back in as the second account; resolve in A and reopen in B. Confirm both action names/timestamps appear in Resolution history after refresh/reload.
7. Close/navigate away from B; confirm ReviewerBeta leaves A's presence. Reopen B and confirm membership returns.
8. Block only `/socket.io/` in B's browser developer tools and reload B to trigger a reconnect. Confirm the connection status changes while HTTP create/reply/edit/delete/resolve/reopen remain usable and update B locally. Change discussion data in A while B is disconnected. Unblock Socket.IO; confirm **Live**, refreshed presence, and all canonical comments return without reload.
9. Stop/restart the server and confirm both browsers reconnect and refetch. HTTP requests cannot succeed during the period when the entire server is stopped.
10. Open Draft 3 in A and Draft 4 in B. Create/change a Draft 3-only thread in A; it must not appear in B.
11. Repeat highlight navigation at 50%, 100%, 150%, 200%, Fit Width, Fit Page, and rotated views. Check multi-page selections and standalone anchor diagnostics as in the original acceptance test below.

## Manual acceptance test

### Slice 5 carry-forward acceptance

1. Start `python app.py`; use one logical document with two imported versions, Draft 3 and Draft 4.
2. Open Draft 3 as ReviewerAlpha and create two comments on selected text. Keep one source viewer open in another browser/profile.
3. Return to the document, choose **Carry feedback forward / migration history**, as a document owner select Draft 3 as source and Draft 4 as target, and start a run.
4. Confirm the two threads are pending. Select the first; inspect its source quote/page and discussion. **Go to source** should center its source highlight in another tab.
5. Select corresponding text in Draft 4 and click **Carry thread here**. Confirm one carried item and one destination highlight, with the same thread ID and comments as Draft 3.
6. Reply from Draft 4; confirm Draft 3 updates automatically. Resolve in Draft 3; choose **All** in Draft 4 to confirm shared resolution/highlight state and reviewer attribution. Reopen in Draft 4; confirm Draft 3 updates.
7. In the same open migration run, reselect the carried item, select different destination text, and click **Re-anchor selected thread here**.
8. Confirm the old destination highlight disappears and the new one appears. Expand **Target history / diagnostics**: the old manual target must remain as superseded and the replacement as effective, with a supersedes link in provenance. The Draft 3 origin must remain unchanged.
9. Leave migration mode, reload Draft 4 normally, and click its thread to verify the replacement highlight is centered and the old highlight does not return.
10. Return through document migration history to the open run. Skip the other item with a note. Confirm its source thread stays open, the decision records the reviewer/time, and no destination anchor appears.
11. Complete the run; verify zero pending items, carried/skipped counts, completion actor/time, and the completed run on the document's migration history page.
12. Start another run between the same pair: existing destination mappings should already be carried. To reconsider a skip or correct a completed mapping, use this new open run.
13. For a chain, import Draft 5 and start Draft 4 â†’ Draft 5. Verify its source quote/page comes from Draft 4's effective manual target, then carry explicitly again.
14. Test two concurrent runs attempting the same destination: the stale attempt must conflict; refreshed UI can keep the existing target or deliberately re-anchor it. Try a backwards run to Draft 3 and confirm its origin target cannot be replaced.
15. Repeat zoom (50/100/150/200%), rotation, centered navigation, reconnect, and standalone-anchor diagnostics checks below. Source/target PDFs must remain unchanged.

### Original review acceptance

1. Launch PDF Review and open a text PDF version.
2. Sign in as an allowlisted account with an owner/reviewer document grant.
3. Select a sentence, click **Comment**, enter `This sentence confused me.`, and submit.
4. Confirm the selection becomes a persistent highlight and the selected thread appears in the sidebar.
5. Clear the browser selection; click the highlight and confirm its thread activates.
6. Click another thread and confirm its first segment is centered, not merely its page top.
7. Reply as the first account, then sign in to a second permitted account in another browser and reply again. Confirm both author names remain correct.
8. Edit a comment, reload, and confirm current text persists. Inspect SQLite if needed to confirm ordered old revisions remain.
9. Resolve, reload, select **All**, and confirm the subdued resolved thread persists; reopen it.
10. Delete a reply and confirm a tombstone replaces it without removing other comments.
11. Reload and confirm all state remains.
12. Test 50%, 100%, 150%, 200%, Fit Width, Fit Page, and rotations. Confirm highlights remain aligned and centered navigation still works.
13. Scroll target pages out of view and back; confirm one overlay per page and no duplicates.
14. Open another immutable version and confirm threads appear only where that version has a target.
15. Repeat with a wrapped multi-line selection and, where the browser/PDF permits reliable capture, a multi-page selection.
16. Expand **Anchor diagnostics** and confirm old standalone anchors still render, navigate, and remain exact-version isolated.

## Directory layout

```text
review/
  auth.py               Google OIDC, shared authorization, CSRF and security headers
  auth_cli.py           offline allowlist, legacy linking and ACL administration
  migration6.sql        Google identity, allowlist and document grants
  users.py              stable user records and identity validation
  threads.py            thread/comment/revision lifecycle and transactions
  anchors.py            strict anchor validation and reusable insertion seam
  database.py           numbered migrations and connection policy
  documents.py          logical document/version persistence
  storage.py            immutable content-addressed PDF storage
  routes.py             HTML, JSON APIs, and integrity CLI
  realtime.py           SocketIO setup, exact-version rooms, presence, notifications
  migration5.sql        effective heads, runs, decisions, provenance, database guards
  migrations.py         transactional manual carry/re-anchor/skip/completion services
  migration_routes.py   migration HTML entry point and strict HTTP APIs
  targets.py            historical target/provenance diagnostics
static/review/
  http.js               central same-origin mutation CSRF transport
  anchors.js            viewer/review orchestration
  thread_api.js         discussion and identity HTTP client
  review_state.js       selected-thread and filter state
  thread_sidebar.js     safe DOM rendering and comment controls
  comment_composer.js   selection composer lifecycle
  realtime.js           connection/reconnect and serial canonical refresh coordinator
  presence.js           safe presence rendering and throttled PDF.js page reports
  migration_api.js      migration/history HTTP client
  migration_start.js    document-owner run creation
  migration_sidebar.js target viewer's manual migration workflow
  anchor_*              Slice 2 capture, geometry, overlay, API, diagnostics
tests/
  test_auth.py           real Authlib validation with stubbed provider transport
  auth_helpers.py        explicit isolated authenticated-session fixtures
  test_foundation.py
  test_anchors.py
  test_threads.py
  test_realtime.py
  browser_sanity.py      optional direct-DevTools Chrome/Edge sanity check
  test_migrations.py     effective targets, migration services/schema/API/realtime tests
```

## Deferred work

Email delivery, PostgreSQL, automatic projection/migration, fuzzy matching, Version Tracker coupling, manuscript snapshots, and PDF annotation writing/export remain deferred. Realtime runs in a single process with no broker, persistent event log, or presence history. Standalone diagnostic anchor operations remain non-realtime. Schema is now numbered migration 8. Vendored PDF.js remains unchanged.

See `ARCHITECTURE.md` for invariants future slices must preserve.

## Private beta setup and acceptance

This is local implementation only; nothing has been deployed. Private historical backups and baselines are excluded. Existing documents received **no automatic grants**.

### Google Cloud and local configuration

1. In [Google Cloud Console](https://console.cloud.google.com/), select/create a project and open Google Auth Platform. Configure Branding (app name, support email, developer contact). For accounts outside your organization, choose an External audience; while testing, add intended Google test accounts under Audience/Test users when required by Google's console.
2. In Clients, create an OAuth client of type **Web application**. Register the exact authorized redirect URI `http://127.0.0.1:5000/auth/google/callback`. No JavaScript client/origin is needed for this server flow. If using `localhost` instead, configure it consistently as a separate exact redirect URI and server name.
3. Use only `openid email profile`. Enable no Gmail, Drive, Contacts, Calendar, offline access, or unrelated API scopes. Google test-user eligibility does not grant PDF Review access.
4. Set the client ID/secret in your process environment or an ignored local `.env` copied from `.env.example`. `python app.py` and the Flask CLI load `.env` through python-dotenv; existing process variables take precedence. Never put credentials in tracked source or SQLite. The example contains placeholders only. Direct application-factory callers supply their own environment/configuration.

References: Google's [OIDC setup and redirect rules](https://developers.google.com/identity/openid-connect/openid-connect), [web client setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid), and [Authlib Flask OIDC](https://docs.authlib.org/en/latest/oauth2/client/web/flask.html).

```powershell
cd "C:\vena\Obsidian\writing\Code\vsff_website\pdf_review"
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
# Keep this generated value securely for later launches; do not regenerate each restart.
$env:GOOGLE_CLIENT_ID = "YOUR-WEB-CLIENT-ID"
$env:GOOGLE_CLIENT_SECRET = "YOUR-WEB-CLIENT-SECRET"
$env:PDF_REVIEW_ENV = "development"
$env:PDF_REVIEW_SERVER_NAME = "127.0.0.1:5000"
$env:PDF_REVIEW_SCHEME = "http"
$env:PDF_REVIEW_COOKIE_SECURE = "0"
$env:PDF_REVIEW_PROXY_HOPS = "0"

python -m flask --app app list-identities
python -m flask --app app allow-email "your-google-email@example.com" --note "Private beta owner"
# Copy USER_UUID and DOCUMENT_UUID from list-identities; never use display names as IDs.
python -m flask --app app link-google-email "your-google-email@example.com" USER_UUID
python -m flask --app app grant-access DOCUMENT_UUID USER_UUID --role owner
python -m flask --app app list-allowed-emails
python -m flask --app app list-document-access DOCUMENT_UUID
python app.py
```

Email preparation does not mark it verified: Google must verify and link the subject on first login. Linking an already linked/inactive user or an email assigned to another user fails. If no legacy identity should be retained, allow the email, log in once to create its user, then obtain the ID with `list-identities` and grant access explicitly.

The offline CLI remains the bootstrap/recovery path. `allow-email EMAIL` adds/re-enables; `disallow-email EMAIL` disables; `remove-email EMAIL [--confirm-established]` deletes only the allowlist row. `revoke-access DOCUMENT_UUID USER_UUID` removes a grant; `grant-access ... --role owner|reviewer|viewer` adds/changes one grant. Removing/demoting the final owner is rejected. Creator/grantor/audit actor fields are nullable for offline operators instead of inventing actors. Re-enabling preserves subjects and prior document grants. Private Beta C1 also provides owner sharing and explicit site-admin web administration, described below.

### Authorization and session policy

| Role | View PDF/discussions/history | Create/reply/resolve/reopen | Edit/delete own comments | Import/verify PDF and mutate migration runs |
| --- | --- | --- | --- | --- |
| owner | Yes | Yes | Yes | Yes |
| reviewer | Yes | Yes | Yes | No |
| viewer | Yes | No | No | No |

All active globally permitted accounts may create logical documents; the creator becomes owner atomically. This grants no access to existing documents. Nobody, including owners, can edit/delete another author's comments. All roles can read authorized migration history. Document owners manage their own ACLs. Only explicit site administrators manage global beta membership; site administration grants no document/PDF access.

`review/auth.py` implements default-deny authorization for `core` and `carry`, resolving document ownership from document/version/thread/comment/anchor/migration IDs before content handlers execute. Inaccessible/missing resources return the same generic 404. Insufficient roles on accessible documents return 403. Anonymous safe requests redirect to login; anonymous API/mutation requests return 401. The dashboard lists granted documents only; reviewer lookup exposes only the current account.

PDF authorization runs **before** content lookup, blob resolution, integrity reads, or `send_file`. It covers GET, HEAD, Range (including malformed/unsatisfiable ranges), and conditional requests. Authorized requests retain Werkzeug/PDF.js conditional and 206 behavior. Blobs remain outside static, without public URLs/tokens. Flask also denies the unused vendored example PDF without changing any vendor file.

Authlib uses Google discovery, OAuth state, signed OIDC issuer/audience/expiry validation, saved nonce, and PKCE S256. Only validated ID-token claims reach linking. Access/refresh/ID tokens are never persisted, rendered or logged; callback token data is transient. Failed callbacks clear session state and show minimal denial. Return URLs accept local absolute paths only, conservatively rejecting protocol-relative, encoded-path, backslash and control-character forms.

The signed Flask session contains `authenticated_user_id`, random CSRF state and a permanent-session flag, with a 12-hour rolling lifetime. HttpOnly and SameSite=Lax are enforced. Every authenticated mutation, including logout and HTML forms, requires CSRF. Central `static/review/http.js` attaches `X-CSRF-Token`; forms submit a hidden field. Server comparison is constant-time. Safe methods need no mutation token; OAuth state is separate.

Development without a secret logs an ephemeral-key warning (sessions expire on restart), never an authentication bypass. Missing development Google credentials produce 503 at sign-in. Production startup requires a persistent `SECRET_KEY` of at least 32 characters, both Google credentials, external server name, HTTPS scheme and Secure cookies; invalid configuration fails before database initialization. Future production settings are `PDF_REVIEW_ENV=production`, `PDF_REVIEW_SERVER_NAME=review.example.com`, `PDF_REVIEW_SCHEME=https`, `PDF_REVIEW_COOKIE_SECURE=1`. Register `https://review.example.com/auth/google/callback` separately at Google. No deployment is included.

Forwarded headers are ignored by default. Set `PDF_REVIEW_PROXY_HOPS=1` only when exactly one trusted proxy is the sole network-isolated ingress and overwrites `X-Forwarded-Proto`. Only that scheme header is trusted; forwarded host/IP/port/prefix are not. Configured server name supplies canonical host; Flask validates incoming hosts; callback generation explicitly uses configured scheme. A future deployment must block direct public backend access. No Apache/systemd/network configuration changed.

Responses include nosniff, `Referrer-Policy: same-origin`, and `X-Frame-Options: SAMEORIGIN`, preserving PDF.js same-origin embedding. Dynamic/auth/PDF responses use `Cache-Control: no-store, private`; static assets retain normal caching. Production adds one-year HSTS without includeSubDomains/preload. PDF.js CSP is unchanged.

Socket.IO rejects unauthenticated/disabled/disallowed connections. Its explicit same-origin check uses the configured public origin (or direct WSGI origin for unconfigured loopback development), ignoring forwarded host/protocol headers. Each version join rereads identity/allowlist and checks document ACL using the shared authorization functions. Presence uses database identity, ignoring supplied actor fields. Viewers receive events; sockets cannot mutate review data. Exact-version rooms and post-commit broadcasts remain intact. HTTP revocation takes effect on the next request. C2 rechecks identity and ACL before every version broadcast and removes revoked idle recipients before new notifications/presence; page reports and joins also recheck access. No periodic background eviction task is used. Logout cannot erase bytes already downloaded while authorized.

### Manual acceptance with real Google accounts

1. Complete setup, start the app and visit `/` in a fresh browser: only sign-in, no document titles/IDs or reviewer names. Try a known PDF URL and a Range request while logged out: no PDF bytes.
2. Sign in with the allowed, prepared owner account. Verify stable user ID and historical authorship. Open its PDF and inspect Network tools. To explicitly test Range, run `fetch(PDF_URL, {headers:{Range:'bytes=0-99'}})` in that signed-in page's console: expect 206 and 100 bytes. PDF.js may fetch small PDFs in one ordinary request.
3. Create/reply/edit/delete your own comments, resolve/reopen, inspect actor/time history and reload. Check varied zoom/rotation and centered highlights. Editing another author's comment must return 403 without a revision.
4. As owner import another version if needed, create a migration run, carry/re-anchor, skip another item and complete. Confirm immutable origins/history and shared discussion identity. Reviewers/viewers must be unable to mutate migration decisions.
5. Log out; revisit the exact PDF URL (also HEAD/Range): no PDF bytes. Sign in with an unapproved Google account eligible for your Cloud audience: minimal denial, no application session or protected metadata.
6. Allow another account and let it log in without document grants. Dashboard omits the document; known document/version/PDF/anchor/thread/migration URLs return 404. Grant viewer: reads work, mutations return 403. Grant reviewer: comments work, imports/migration mutations do not.
7. If two Google accounts are available, use separate profiles with grants. Test Live/presence, replies, author-only edits, resolution history, cross-version changes and exact-version isolation. For edit conflicts, sign the same author into two profiles, open both edit drafts, save one then submit the stale draft: 409 with draft retained.
8. Run `disallow-email EMAIL` during its session: next protected request and future socket connect fail. Re-enable with `allow-email EMAIL`; fresh login works. Run `revoke-access DOCUMENT_UUID USER_UUID`: next document/PDF request and socket room join fail. C2 prunes revoked idle recipients before the next version broadcast.

### Verification

```powershell
python -m unittest discover -s tests -v
python tests/browser_sanity.py
python -m flask --app app verify-storage
python -c "import sqlite3; from app import app; c=sqlite3.connect(app.config['DATABASE']); print(c.execute('PRAGMA quick_check').fetchall()); print(c.execute('PRAGMA integrity_check').fetchall()); print(c.execute('PRAGMA foreign_key_check').fetchall()); c.close()"
```

The browser harness uses temporary data and offline signed fixture sessions injected through DevTools, never a production bypass route. Real Google consent/login and future HTTPS proxy operation require manual acceptance. See [BETA_A_REPORT.md](BETA_A_REPORT.md) for implementation and verification results.

## Private Beta C1: accounts, document sharing and site administration

Every active, verified, allowlisted user has **Account** navigation, including
from the viewer. `/account` shows the verified Google email, account status,
editable display name, a subdued technical account ID, and separate **Owned by
me** / **Shared with me** lists with current roles. Document links use the
existing ACL-protected routes.

Display names are trimmed, nonempty, at most 100 characters, and reject Unicode
control/hidden formatting characters. Duplicate names are allowed. Jinja escapes
names normally. Profile updates change only `users.display_name`; Google logins
retain an existing user's chosen name. UUID, Google subject, verified email,
authorship, historical foreign keys, grants and admin membership stay intact.

Owners use **Manage access** on the account or document page. They select an
existing active beta identity by name and verified email, choose Viewer,
Reviewer or Owner, and grant access. Existing grants can be changed or revoked.
A document must retain one owner, including self-removal and CLI changes. To
transfer ownership, add another owner first. Owners cannot invite new beta
members or create placeholder users. Ask a site admin to allow the person's
Google email, then have that person sign in once before sharing.

The sharing directory is owner-scoped to a specific document; it returns only
`user_id` (the selector key), `display_name`, and verified `email` for active,
Google-linked, enabled-allowlisted identities. Unlinked users, inactive or
disallowed accounts, and allowlist-only invitations are excluded. It never
returns subjects, login timestamps, administrator state or audit data.

Only explicit `site_admins` members see **Admin** navigation or enter `/admin`.
Its Beta access, Users and Site admins panels allow/re-enable/disable/remove
emails and grant/revoke site administration. Allowing an email does not send an
email, create a user, or grant document access. There is no automatic admin
inference from document ownership, email domain, first login or session flags.
An administrator still needs an ordinary ACL grant to read any document/PDF.
Global document support/recovery uses the retained offline ACL commands.

Disabling an allowlist entry retains its row/note. Removing a mistaken entry
deletes only that row. Both stop new HTTP requests from existing sessions and
prevent login; neither deletes stable users, comments, revisions, grants or
history. Established accounts require a confirmation checkbox or the CLI's
`--confirm-established` flag. Re-enabling restores global eligibility while
retaining prior grants. Normal operations cannot revoke the final active site
admin or disable/remove that admin's allowlist entry. Add an active successor
first; the offline CLI remains available if Google email changes or external
account state require recovery.

| Method | Route | Authorization |
| --- | --- | --- |
| GET | `/account` | Active authenticated beta user |
| POST | `/account/profile` | Current user only |
| GET | `/documents/<document_id>/access` | Current document owner |
| POST | `/documents/<document_id>/access` | Current document owner; grant/change/revoke |
| GET | `/api/documents/<document_id>/shareable-users` | Current document owner; limited directory |
| GET | `/admin` | Explicit site admin |
| POST | `/admin/beta-access` | Explicit site admin; allow/disable/remove |
| POST | `/admin/site-admins` | Explicit site admin; grant/revoke |

All new mutations use the existing CSRF token system and POST forms. Unknown
identity/authority fields are rejected. Anonymous HTML GETs redirect to login;
anonymous APIs/mutations return 401. Inaccessible documents return 404; an
existing viewer/reviewer attempting owner sharing receives 403. Non-admin beta
users receive 403 for admin endpoints. Validation failures return an explained
422 without mutation. Pages/API responses retain private/no-store and existing
security headers. No GET mutates state.

`review/access.py` shares transactional profile/access/allowlist/admin services
between thin Flask/Jinja routes and the CLI. Write transactions use
`BEGIN IMMEDIATE`; actor eligibility and owner/admin authority are checked again
inside the transaction. Final-owner/admin checks and audit insertion commit
atomically with the mutation. Offline operators are explicitly represented by
a null actor; HTTP always passes the authenticated stable ID.

Migration **7**, `accounts_sharing_and_site_admins`, adds `site_admins` and
`access_audit_log` and replaces the old unique display-name index with a
nonunique lookup index. It rewrites no domain rows, creates no admins or grants,
and leaves migrations 1-6 unchanged. Audit rows record actor, fixed action,
target type/identifier, small JSON details and timestamp. The audit table has
update/delete rejection triggers. Email allow/re-enable/disable/remove,
admin grant/revoke and document grant/role change/revoke are audited; failed
operations and unchanged grants create no records. Details contain only target
user ID and old/new role for document changes, never notes, comment bodies,
OAuth values, cookies or session data. Audit records are private runtime data;
there is no audit web endpoint in this slice.

Additional recovery commands:

```text
python -m flask --app app list-site-admins
python -m flask --app app grant-site-admin USER_UUID
python -m flask --app app revoke-site-admin USER_UUID
python -m flask --app app remove-email EMAIL [--confirm-established]
```

After the ordinary production deploy/startup applies migration 7, an operator
can bootstrap the existing signed-in user using the same environment wrapper as
`ops/pdf_review/README.md`. Run these commands on the server as the existing
privileged operator; they are documentation, not executed by this local task:

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

Refresh the account page and open `/admin` for routine beta invitations. A new
admin must already be an active, verified, Google-linked, allowlisted identity.
No real email or user ID belongs in source. No new port, service, secret,
dependency, proxy/OIDC callback, broker or worker is needed. Existing SQLite
snapshot/startup-migration/health-check deployment remains compatible.

Full validation remains `python -m unittest discover -s tests -q`,
`python tests/browser_sanity.py`, and `python -m pip check`. The C1 browser
extension uses only disposable synthetic data and a fixture-process offline
provider; the existing auth tests still exercise real Authlib JWT validation.
It covers account/profile, sharing and ownership transitions, revocation,
owner/invitation and admin/PDF separation, first-login identity creation, and
layouts at 1024x768, 768x1024 and 390x844. Existing WebSocket/review acceptance
remains in the same harness.

Admin/account pages refresh normally. C2 checks idle Socket.IO recipients before
version broadcasts and refreshes presentation identity while doing so. Page
reports and join/reconnect also check authorization. Account deletion/deactivation UX, email delivery,
audit browsing, global web ACL recovery and a larger searchable directory are
outside this slice.
## Local viewer UI

The document viewer uses a compact app-owned toolbar with PDF.js rendering,
navigation, search and viewing commands underneath. Select PDF text to reveal
the contextual comment button, or press **Enter** or **Ctrl+Alt+M** (**Command+Option+M** on Mac).
Submit the selection composer with **Ctrl/Command+Enter**, or post any active
comment/reply/edit with **Ctrl+Shift+Enter**; **Escape** closes
the composer or active thread.
Comments always use one right-hand rail, including both pages of a spread.
Expanded shows compact cards; Minimized uses narrow markers and one active full
card opening to the right; Hidden reserves no width. Mobile uses markers with
the active comment over the PDF below its highlight, and activates automatically
at widths below 750px. Clicking highlights or inserting a comment aligns the
active card and moves neighboring comments while keeping the PDF still.
Comments sit beside the page/spread inside the
same native scrolling workspace. Small screens and large zoom use its horizontal
scrollbar instead of a drawer. Empty/hidden comments reserve no document width.
Account, admin and logout are in the identity menu.

`static/app.css` imports shared tokens, base and C1 account styles. Viewer-only
styles live in `static/styles/viewer.css`, `comments.css` and `pdfjs.css`.
`viewer_bootstrap.js` configures the vendored viewer through its pre-run hook;
`viewer_shell.js` owns toolbar integration and canonical-anchor rail layout.
Vendored PDF.js files remain unchanged. Native preferences are disabled to
prevent saved PDF editor settings from enabling a competing annotation model.
Developer anchor tools are available deliberately with `?debug=anchors`.

View, Comments, identity and management actions share the canonical menu styles
and `static/review/menus.js` behavior. Scrolling and Spreads are submenus with
checkmarks. Search keeps native PDF.js inputs/listeners/matching in a compact
header-attached surface. Shared account markup lives in `_account_menu.html`.
New PDF Review server-rendered pages should use the shared application shell,
tokens and control/menu primitives rather than introducing one-off visual systems.

Run the existing synthetic acceptance environment with
`.venv/Scripts/python tests/browser_sanity.py` on Windows. It now also runs
`tests/viewer_acceptance.py` and writes ignored synthetic screenshots under
`tests/visual-artifacts/`. See [the viewer redesign report](VIEWER_REDESIGN_REPORT.md)
for the original audit and control classification; see
[the refinement report](VIEWER_REFINEMENT_REPORT.md) for the current right-only
rail, markers, menus, shared shell and verification results.
