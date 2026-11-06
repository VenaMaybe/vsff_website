# PDF Review architecture decisions

These are permanent extension constraints, not temporary implementation details.

The owner-only document Share dialog reuses `AppDialog`, `appFetch`, and the
`_share_options.html` fragment also used by Manage access. The existing protected
access route returns that fragment for `?share=1`; no new public endpoint exists.
Existing sharing/invitation POSTs negotiate JSON with `Accept: application/json`
while retaining their HTML redirect behavior. Server-side owner/trust and CSRF
checks are unchanged. Inline pending-invitation links are returned only after an
authorized invitation creation. Errors preserve form input; native modal focus,
Escape, close/busy controls and return-to-opener behavior use the shared shell.

## Main-version designation (migration 15)

`document_main_versions` stores a single active version per logical document,
with selecting user/time. It does not change immutable version rows or anchor
identity. Foreign keys and insert/update triggers reject cross-document or
withdrawn version selections. Existing documents receive their newest active
version at migration; first import initializes a new document. Later imports
preserve the selection. Owner-only CSRF POST changes reauthorize within BEGIN
IMMEDIATE, preserve idempotence and append audit events atomically. Withdrawal
of the main version selects the newest active remainder or clears an empty
document's designation in the same transaction. Historical pre-15 offline
fixtures remain supported without implicitly applying migrations.

The dashboard exposes owner display names only on ACL-visible documents. Delete
version selection reuses canonical nested menus and the existing exact-version
confirmation/deletion service. No PDF bytes, comment geometry, invitation grants,
or real private runtime data are changed by this source task.

## Trusted Users and invitations (migration 14)

Trust is a site-level capability independent of document Owner/Reviewer/Viewer.
Only admins change trust or reinstate suspended membership. Trusted Users can
invite beta members and read a narrowly serialized member directory, without
additional document access. Site admins also retain ordinary document ACL checks.

`invitations.py` owns transactional membership, invitations, directory and history.
`invitation_routes.py` supplies thin form routes with explicit auth registries.
All writes use BEGIN IMMEDIATE and current actor eligibility/trust/ownership.
Membership blocks survive allowlist removal, preventing re-invitation from
silently undoing an admin suspension. Directory/history are separately authorized.

Invitations bind a normalized email, optional logical document and Viewer/Reviewer
role. A random nonce and invitation ID yield an HMAC signature under SECRET_KEY.
The signature is not stored or logged; links carry it in a fragment. A generic
public landing page consumes nothing and reveals no recipient/document data.
A CSRF POST verifies the signature and stores only ID/nonce through Google OAuth.
Validated OIDC email must match. Identity linking, beta admission, document grant
and acceptance audit are atomic; wrong accounts, bad OIDC, concurrent redemption
or stale authority cannot partially grant access. Existing grants are preserved.
Immediate sharing and recipient acceptance have distinct audit events.

Links expire after seven days. Renewal revokes/reissues atomically. Authority
mutations retire affected pending invites; acceptance rechecks authority even for
external/offline changes. Accepted grants remain until explicitly changed.
GET listings derive expiry without writes; creation/revocation and the optional
`expire-invitations` CLI record expiry events. Audit history is append-only.

Migration adds trusted_users, beta_memberships and invitations only, preserving
existing users, site admins, ACLs, immutable PDFs and history. Per user instruction,
a sole existing admin is the historical inviter; ambiguous cases retain known
creators and offer explicit attribution for unassigned records. Allowlist dates
are access records, not exact invitations; last login is only a joined-by bound.
Future first identity links record exact joins, preserved across email changes.
Backfill audit events are dated at migration, not fabricated historical sends.

Dashboard refresh uses a visible-tab 15-second poll and focus/visibility refresh
of the authorized HTML document grid, preserving creation drafts. No global
document directory, email service, new OAuth scope, private persistent cache or
reusable anyone-can-join link is introduced. See INVITATIONS_REPORT.md.

## Repository and production separation (Private Beta B1)

PDF Review may share a repository and VPS with VSFF but remains a separate
service, datastore, session domain, and application architecture. `pdf_review/`
is a sibling of `backend/` and `frontend/`, with independent dependencies and
no SQLAlchemy, Alembic, Vue, or VSFF session/model integration.

Production private state belongs outside the checkout under
`PDF_REVIEW_DATA_DIR`: SQLite, immutable SHA-256 blobs, and backup snapshots.
An explicit external SQLite override is allowed. Packaging never discovers,
moves, or rewrites standalone local data. SQLite migrations and all immutable
identity/history rules below remain authoritative. Online database backups use
SQLite's backup API; immutable blobs must be retained separately.

Production uses `wsgi:app` under one multithreaded Gunicorn `gthread` worker
with `simple-websocket`, because Socket.IO room/client state and presence are
process-local. No additional worker processes or independent instances are
supported until a shared message/presence backend exists. Default future bind
is loopback `127.0.0.1:8002`, separate from VSFF's `127.0.0.1:8001`.
Public origin and minimal proxy trust stay explicit environment configuration;
host-only `pdf_review_session` cookies remain independent of VSFF sessions.
This slice prepares source only: deployment, reverse proxy, DNS, TLS, service
management, Google production callback changes, and server backups are deferred.

The B2A operational bundle in `ops/pdf_review/` is source for later manual
installation. Production migrations still run in the single worker's application
factory, once per missing numbered migration. Pre-upgrade backups must use the
standalone SQLite backup helper without importing the new application factory;
ordinary Flask CLI initialization would apply migrations before its command.
`GET/HEAD /healthz` is an explicit public liveness exception to default deny:
constant text, no identity/database/blob reads, no session creation, and the
existing host validation and private/no-store headers. It authorizes no content.

`legal.privacy` (`/privacy`) and `legal.terms` (`/tos`) are also explicit public
GET/HEAD exceptions, registered in `legal_routes.PUBLIC_ENDPOINTS`. They render
policy text through the shared shell without account/database/blob lookups,
CSRF token creation or flash consumption. Public policy access also works with
an expired/revoked session. Only those exact endpoints bypass authentication;
the default-deny policy and production host/security headers remain in force.
Policy links belong in the shared footer and account menu, with a notice at sign-in.

## Immutable artifacts and versions

1. Imported PDF bytes are immutable. PDF Review never annotates, replaces, or rewrites them.
2. Different bytes require a different `document_version`; SHA-256 and canonical blob path identify the representation.
3. Logical documents outlive individual representations. Multiple version records may share a verified identical blob.
4. Review data lives in SQLite and remains external to PDFs.
5. Paths are storage implementation details, never document, version, anchor, or discussion identity.

## Anchor invariants

6. An `anchor_instance` belongs permanently to one exact immutable version.
7. Anchor and segment contents are immutable. Development deletion is explicit and cannot delete an anchor referenced by a thread target.
8. One logical anchor may have ordered consecutive page segments.
9. Canonical geometry is PDF page space. CSS pixels, zoom, rotation, canvas dimensions, DPI, and device pixel ratio are render state.
10. Text anchors are selector bundles: exact text, prefix/suffix, offsets where reliable, server-computed page-text fingerprint, selector version, and validated rectangles.
11. Capture and rendering convert through the current PDF.js page viewport. Rendering uses stable page bounds and does not depend on the recyclable text layer.
12. Overlay styling remains in the same-origin external `anchor_overlay.css`; PDF.js's CSP blocks dynamic style text. App code may set dynamic geometry properties on highlight elements.
13. Centered navigation is required. Navigating to an anchor must bring its first highlighted rectangle into the viewport, not only set the page number.

Mobile/coarse-pointer PDF selection retains native text selection and handles.
App-owned text-layer callout/contextmenu suppression is scoped to commenting
accounts and does not affect form-field editing menus. Since Safari can retain
system selection UI, Add comment is a labelled 44px-minimum action separate from
the selection, at the bottom of the visible PDF viewport; desktop keeps its
contextual icon. Placement tracks the visual viewport as well as PDF layout.
The desktop icon uses the final rectangle of the final selected page segment,
not the union of all selected lines. It therefore follows the selection's end
even when an earlier line is longer, selection is reversed, or it crosses pages.
This uses canonical PDF geometry; no live DOM Range is retained for layout.
Desktop selection changes immediately refresh a provisional endpoint rectangle
without traversing page text. The full validated anchor remains debounced by
80ms, and clicking the action captures it synchronously. Preview geometry is
never a submission payload, so rapid dragging stays responsive without stale
selectors or a delayed action button. Mobile docking retains its existing path.
Focused browser coverage is `tests/browser_sanity.py --selection-action`.
Mobile Cancel immediately restores the selection action's pre-composer corner.
That target stays fixed through intermediate keyboard-closing viewport sizes;
normal placement resumes when viewport height returns or viewport width changes.
New selections and composer opening reset the override. No delay or animation.
The mobile selection composer docks at the visual viewport's bottom-right as a
fixed body-level overlay, outside the PDF workspace's clipping and stage bounds.
Its lifecycle restores the original parent for desktop positioning and on close.
Keyboard sizing uses the full visual viewport height, never its intersection with
the PDF frame: Safari can pan that viewport independently and leave almost no
overlap. Draft and quote survive resizing, with scrolling only when the visual
viewport itself is too short for the card.
The first touch on an unfocused docked selection editor cancels default pointer
focus and calls `focus({preventScroll:true})` within that same user gesture. This
opens the keyboard without starting Safari's competing native reveal-scroll.
Already-focused editor taps retain native caret placement and selection behavior.
Coarse-pointer/narrow-layout users tap the editor to focus it; initial opening
and reopening use the same focus policy. Mobile textareas render at 16px to avoid
Safari's small-field focus zoom. Desktop retains autofocus and compact text.
The selection editor wraps a transformed 16px textarea in a fixed 72px field,
rendering compact 13px text without changing its native focus font metrics.
Keyboard resizing repositions the composer without resizing this field; only
genuinely insufficient viewport space requires scrolling the containing card.
The mobile page-number field also uses 16px native text and blurs on confirmation.

Highlight rendering deduplicates exact rectangles, omits fully contained boxes,
and joins touching or overlapping runs with nearly matching line bounds within
one anchor segment. Browser ranges can include text runs, spaces and enclosing
spans of slightly different heights. Separate fills/outlines otherwise create
seams and darker or stepped edges within a single phrase. Matching uses PDF units
(15% thickness tolerance for line bounds, at most 5% thickness / 0.5pt for gaps),
uses intrinsic PDF page rotation to select the canonical reading axis, and
retains the original rectangle order. Viewer rotation does not change grouping;
short successive lines are never joined along the perpendicular axis.
This display-only normalization in `anchor_geometry.js` / `anchor_overlay.js`
is cached by immutable rectangle-array identity, independent of zoom/rotation.
Canonical geometry and selector data are not rewritten; existing anchors benefit
without a migration. Separate lines, appreciable gaps and separate anchors remain
distinct, including overlapping conversations on the same text. Focused coverage:
`tests/browser_sanity.py --highlight-overlap`, including the reported fragment
coordinates, real multi-span capture, immutable storage and overlap click cycling.

Highlight rectangles are visual only (`pointer-events:none`), so PDF.js's native
text layer receives selection presses and drags even beneath existing comments.
Shared iframe pointer/click listeners distinguish a simple primary click from
movement, scrolling, cancelled/multi-pointer gestures and noncollapsed selection;
they never prevent pointer-down/move defaults or synthesize selection ranges.
Click/idle-hover hit testing uses the painted percentage regions, one page-overlay
bounds read and reverse DOM paint order. Hidden comments, PDF links/forms and
section controls do not participate. Hover is frame-coalesced and cleared during
dragging, scrolling or leaving the viewer. There are no per-rectangle listeners.
Hover applies the clickable hand cursor to the underlying text hit target. A
primary mouse press retains it for a quick click; movement or a 200ms hold clears
it. Release cancels the timer, and scrolling/cancellation/tool changes clear it.
This cosmetic delay never delays native selection, hit testing or click handling.
Thread IDs are deduplicated so multiple rectangles from one conversation count
once. With no selected conversation at the click point, selection starts at the
topmost hit; otherwise it advances and wraps around. Only highlights covering
that exact point participate; direct programmatic highlight clicks retain their
ordinary activation. Selected thread state supplies the cycle cursor across
overlay rebuilds. Saved anchors and native selection/zoom/panning remain unchanged.


## Stable authenticated authorship

14. Every comment has a stable `author_id` from `users` from its first commit.
15. Private Beta A replaces the Slice 3 selectable reviewer with a Google-authenticated principal mapped onto the existing stable local user ID. There is no public identity switching API.
16. Mutation routes derive author/editor/resolver/deleter identity from the session and do not accept arbitrary author IDs.
17. Signing in to another account affects only future actions and never rewrites historical authorship.
18. Google OIDC subjects map onto stable user IDs; explicitly prepared legacy email associations preserve historical authorship without display-name matching.

## Threads and version-specific targets

19. A thread is a logical conversation belonging to a `document`, not permanently to one version or one anchor.
20. `thread_targets` links a thread to immutable anchors. Roles reserve `origin`, `projection`, and `manual`; Slice 3 creates only `origin`.
21. Every committed thread has exactly one designated origin target. `threads.origin_thread_target_id` is a non-null deferred foreign key, and a partial unique index allows at most one `origin` row per thread.
22. Origin identity and origin target contents are immutable. The origin cannot be silently replaced, updated, or deleted.
23. Database triggers validate that a target anchor's version belongs to the same logical document as its thread. Service validation complements, but does not replace, this database rule.
24. Viewer retrieval is target/version based. A thread is returned for an exact version only when it has a target anchor on that version.
25. Future migration creates an additional projected/manual anchor and target. It never edits the origin target or origin anchor.

## Comments and revisions

26. Comments permanently belong to one thread and retain their original author and creation identity.
27. `comments.body` is the current plain-text value for normal reads. Comment content is never rendered as arbitrary HTML.
28. Each creation/edit appends an immutable `comment_revision` with an ordered revision number, body, timestamp, and editor identity. Revision 1 preserves the original.
29. Editing updates current body and `edited_at` only after adding the new historical state within the same transaction.
30. Comment deletion is a tombstone: current body is cleared, deletion metadata is recorded, and revisions/identity/replies remain. Tombstoned bodies are not returned by the normal API.
31. There is no normal hard-delete path for comments or threads.

## Resolution

32. Thread status is `open` or `resolved`. Resolved status requires both resolver and timestamp.
33. Reopening clears the current resolution fields but preserves all discussion, target, revision, and prior authored content.
34. Resolve/reopen operations are idempotent; repeating the current state does not rewrite its timestamp or actor.

## Atomic creation and service boundaries

35. Selection-to-comment creation is one transaction containing anchor, segments, thread, origin target, root comment, and initial revision.
36. Slice 2 anchor validation is reused through `validate_anchor_payload` and `insert_validated_anchor`; no weaker discussion-specific anchor validator exists.
37. Controlled failure at any insertion point rolls the entire bundle back.
38. `review/users.py` owns stable user records; `review/auth.py` owns OIDC linking, authentication and shared authorization.
39. `review/threads.py` owns discussion transactions, retrieval, revisions, tombstones, and resolution.
40. `review/routes.py` identifies session users, validates request shape/size, calls services, and formats responses. Business rules do not live only in routes.
41. Future Socket.IO handlers must call the same services and emit only after successful commits.

## Frontend boundaries

42. `anchor_selection.js` and `anchor_geometry.js` own capture and coordinate conversion.
43. `anchor_overlay.js` remains the single rendering/navigation layer for standalone and thread-backed anchors.
44. `thread_api.js` owns discussion/identity HTTP calls; `review_state.js` owns ephemeral selected/filter state; `thread_sidebar.js` owns safe sidebar DOM; `comment_composer.js` owns selection-composer lifecycle; `anchors.js` coordinates them.
45. Selected-thread state is browser-only. It coordinates card state, highlight state, and navigation and is never persisted.
46. Highlight clicks select/scroll the thread. Thread clicks select and center the target highlight. Resolved highlights remain visible but subdued.
47. PDF.js native annotation editing is not the application database and is not used for review persistence.

## Integration boundary

48. Version Tracker integration will be an adapter over optional external source/version metadata. Core PDF Review does not understand books, stories, InDesign, or Version Tracker storage.

## Deliberately deferred

- email invitation delivery and additional identity providers
- PostgreSQL/cloud deployment
- cross-version projection, fuzzy matching, and automatic carry-forward
- Version Tracker/story/source-snapshot coupling
- writing annotations or comments into PDFs
- Markdown/rich-text comment rendering

These deferred features must extend the identities, immutable origins, service transactions, and target model above rather than bypassing them.

## Realtime and presence invariants (Slice 4)

49. SQLite and HTTP/service commits remain authoritative. Socket.IO announces committed changes; it is not a second discussion mutation API. Existing service business rules are reused without socket-specific copies.
50. HTTP mutation routes broadcast only after the service transaction has committed. Realtime lookup/emit failures are secondary, logged, and cannot undo or falsely report failure of a committed mutation.
51. Version rooms use exact immutable version IDs (`version:<version_id>`), validated against the database. Filenames, client-supplied room names, and paths never determine room identity.
52. A thread mutation notifies every distinct version currently targeted by that thread, including future projection/manual targets. Realtime does not itself create projections or targets.
53. `review.changed` schema 1 contains ephemeral event identity, kind, timestamp, document/thread/comment identifiers, and recipient version. Persistent content comes from the canonical HTTP thread API, including target anchors and current revision numbers.
54. Every connection/reconnection rejoins its version, refreshes presence, and refetches canonical HTTP thread state. Missed events are repaired by refetch, never durable replay. No event table is introduced.
55. Canonical refreshes are serialized with a dirty flag for changes during an in-flight request. Successful local HTTP results invalidate older in-flight reads before applying their state. Failed refreshes preserve visible state and retry. Thread targets from canonical state feed the existing overlay.
56. Presence is ephemeral, in-memory, best-effort operational state, never stored as SQLite history, last-seen tracking, or an activity audit. Page information has no bearing on anchor identity.
57. Presence is internally per socket SID, externally aggregated by stable reviewer user ID with connection count and latest reported page among remaining connections. The reviewer remains until the last connection leaves. Anonymous sockets are rejected; document-authorized viewer accounts may receive notifications.
58. A socket has at most one active viewer-version membership. Switching, leaving, navigation, and disconnect remove old membership and publish aggregate presence. Pagehide disconnects explicitly; cached-page restoration reconnects. Abrupt network loss is cleaned up when the transport detects it.
59. The app-local presence registry and snapshot emissions are protected by an RLock in threading mode. Socket infrastructure is initialized per application factory invocation, avoiding cross-app presence leakage.
60. Socket presence reads the authenticated Flask-session user and database display name. Connect and join check the current allowlist/user state; joining a version additionally checks its document ACL through the same authorization functions used by HTTP. Client-supplied identities are ignored. Ordinary reconnect remains; selectable-identity reconnect logic is removed.
61. Comment edits require a positive integer expected revision and compare it transactionally with MAX(comment_revisions.revision_number) under BEGIN IMMEDIATE. Stale edits return HTTP 409, do not append history, and do not overwrite current text. The client preserves the draft and requires review of canonical text before retry.
62. Realtime is progressive enhancement: PDF viewing and HTTP review operations remain usable if Socket.IO fails. Local HTTP responses update the UI; connection/sync status and presence stay separate from mutation success. Open edit/reply drafts survive canonical refreshes.
63. Socket.IO runs in local single-process threading mode with same-origin policy and loopback binding. No wildcard CORS, broker, eventlet, gevent, durable event log, presence persistence, or frontend build system is introduced. The compatible browser client is vendored with its license.
64. App-owned realtime/presence modules retain connection and presence responsibilities; thread_api, review_state, thread_sidebar, comment_composer, and anchor modules retain the boundaries above. PDF.js core and external anchor_overlay.css remain unchanged.

## Authorship editing and resolution history

65. Only a comment's authenticated original author may edit or tombstone it. The service enforces this transactionally, returning HTTP 403 for another reviewer before any revision/body write; the sidebar exposes Edit/Delete only for the authenticated author. Historical edits and authorship are never rewritten. Private Beta A supplies verified, allowlisted Google authentication and document ACLs before these service ownership checks.
66. Every actual resolve/reopen transition appends an immutable, ordered thread_status_changes row with actor, action, and timestamp in the same transaction as the status update. Idempotent requests append nothing. Current resolution fields continue to clear on reopening as required by invariant 33; append-only history preserves earlier actors and actions. Canonical JSON and the sidebar expose this domain history, not socket payloads.
67. Migration 4 adds resolution domain history without modifying migrations 1–3. Only existing current resolutions can be backfilled from known actors/timestamps. Missing earlier history is never fabricated. This table is domain data, not a realtime event replay log or presence history.

## Effective targets and manual migration (Slice 5)

68. Historical thread targets and anchors remain immutable and cannot be deleted. `thread_target_heads` holds at most one effective target for each `(thread_id, document_version_id)`; normal viewer retrieval and thread broadcasts use heads, never all historical targets. Superseded anchors must not enter the standalone diagnostic rendering feed.
69. Database triggers validate head thread/version consistency, initialize every new origin's head atomically, and prevent replacing, moving, or detaching origin heads. The origin version always shows the exact immutable origin target. Non-origin heads may move only to consistent targets; there is no detach operation in this slice.
70. Manual carry creates a new immutable target-version anchor/segments, `manual` thread target, provenance, effective head, and carried item decision in one transaction. It reuses the existing strict anchor validator/insertion seam. It never clones threads, comments, revisions, authorship, or resolution history.
71. Re-anchoring creates new immutable objects and moves a non-origin effective head in the same transaction as provenance and item updates. Old targets/anchors/provenance remain queryable historically. Immutable provenance includes a supersedes-target relationship for explicit correction lineage; a separate supersession table is unnecessary.
72. Migration runs explicitly select distinct source/target versions belonging to one logical document. Filenames, labels, dates, page numbers, or version numbering never infer direction or identity. Runs store creator/time and completion actor/time; multiple runs for one pair are permitted.
73. Run creation snapshots every effective source thread target, including resolved discussions and manual targets in migration chains. Source snapshot identity is immutable even if that source head is later corrected. Existing destination mappings become carried items without duplicate targets. Source quote/geometry come from the snapshot; current discussion content remains the canonical shared conversation.
74. Pending/carried/skipped migration decisions are separate from global open/resolved thread status. Skipping creates no target and never resolves a discussion. Skipped decisions are terminal within their run. Completion requires no pending items, is idempotent, and freezes that run's decisions; later open runs may reconsider skips or correct mappings without freezing document review.
75. Every newly created non-origin target records source target, migration run, method, actor/time, and optional superseded target in immutable provenance. Cross-table database guards validate source/run/thread/version/destination consistency. Slice 5 uses `manual_selection`, role `manual`, null confidence and null algorithm version; unknown legacy diagnostic provenance is not fabricated.
76. Migration item revisions and expected destination head IDs are checked under `BEGIN IMMEDIATE`. Stale attempts return HTTP 409 before inserting any anchor or target. Concurrent runs may explicitly accept an existing destination instead of duplicating it. Origin replacements remain forbidden even in explicitly backwards runs.
77. Authenticated session identity and an owner document grant govern migration mutations; sockets remain notification/presence infrastructure. Target changes broadcast `thread.targeted`/`thread.reanchored` only after commit to every effective version room. Small ephemeral `migration.changed` notifications trigger canonical run refetch in source/target rooms. Notification failure cannot undo or falsely fail a committed mutation.
78. Migration UI reuses the existing target viewer, selection capture, PDF-space geometry, overlays, and centered navigation. App-owned migration modules handle decisions, source previews, and diagnostics. No automatic quote matching, fuzzy matching, page guessing, alignment, confidence scoring, or projection generation is implemented. Future automation must use the same provenance/head/run model with `projection` roles rather than replacing these identities.
79. Migration 5 extends the schema without altering migrations 1–4 or existing domain rows. Origin heads are backfilled; any pre-5 non-origin extra versions use a deterministic latest-target head. Migration decisions/provenance are domain history, not a durable Socket.IO event log or presence history.

## Private beta identity and authorization

80. Google OIDC `sub` is unique and immutable once linked. Current verified email is authorization evidence, normalized by trimming/case-folding only. Authlib owns the server code flow, state, signature/issuer/audience/expiry/nonce validation and PKCE. No OAuth tokens are persisted.
81. Stable local user IDs and historical attribution survive authentication. Legacy linking requires explicit offline email preparation for one active unlinked user; names never link accounts. Conflicting/ambiguous matches fail closed. New allowed accounts receive no existing document grants.
82. Active users with a verified Google identity and enabled `allowed_emails` entry are required for protected HTTP and socket connect/join. Database authorization is reread, never cached as session authority. Sessions contain stable `authenticated_user_id`, CSRF state and lifetime metadata only.
83. `document_access` grants owner/reviewer/viewer explicitly, with no blanket migration backfill. Owners import/verify and mutate migration workflows. Reviewers create/reply/resolve/reopen. Both edit/delete only their own comments. Viewers read. All roles read authorized history. Globally approved accounts may create a document and become owner atomically. C1 adds owner sharing and explicit site-admin beta membership administration; the offline CLI remains available for bootstrap/recovery.
84. Shared default-deny HTTP policy resolves resource ownership before content handlers. Missing/inaccessible resources return generic 404, insufficient roles on accessible documents 403, anonymous APIs/mutations 401, anonymous pages a login redirect. Lists contain granted documents only; reviewer lookup exposes only the current account.
85. Every PDF request, including GET/HEAD/conditional/valid or invalid Range, passes authentication and document ACL before blob access. Werkzeug conditional/206 behavior remains. Blobs stay outside static and receive no public URLs or tokens. Protected responses are private/no-store.
86. Every authenticated unsafe HTTP method requires session CSRF, compared in constant time. Forms submit hidden tokens; app-owned APIs share http.js. OAuth state is independent. Authenticated server identity supplies every review actor; clients cannot choose identities.
87. Sockets reuse HTTP identity/ACL functions and exact-version ownership checks. Presence derives from database identity. No socket mutation API exists; post-commit broadcasts/canonical refetch remain. Forced eviction of existing idle sockets is deferred; subsequent HTTP/connect/join checks enforce current revocation, and page reports revalidate membership.
88. Environment secrets persist across production restarts and never enter SQLite/source. Production refuses missing credentials/host, short secrets, HTTP scheme or insecure cookies. Cookies enforce HttpOnly, SameSite=Lax and production Secure. Development supports loopback HTTP, without an identity-selection fallback.
89. Proxy trust defaults to zero. One optional trusted isolated ingress may supply forwarded scheme only; canonical host/scheme are explicitly configured and hosts validated. Nosniff, same-origin referrer policy and SAMEORIGIN framing preserve PDF.js; production adds HSTS. Vendored PDF.js/CSP are unchanged. Deployment is outside this slice.
90. Migration 6 adds identity fields/indexes, immutable-subject protection, allowlist and document ACL constraints/indexes, without rewriting historical migrations/domain rows. Existing documents require explicit bootstrap grants. Back up a live SQLite database with SQLite's backup API before migration; a raw copy of an open WAL database is not sufficient.

## Private Beta C1: independent account, owner and site-admin scopes

Migration 7 adds explicit `site_admins(user_id, created_at, created_by)` and
append-only `access_audit_log(id, actor_user_id, action, target_type,
target_identifier, details, created_at)`. It replaces the unique display-name
index with a nonunique index; existing rows, constraints and historical
migrations are preserved. Admin membership is never inferred or backfilled.

`account_routes.py` handles server-rendered profile, owner-sharing and admin
forms. `auth.py` has explicit ACCOUNT_ENDPOINTS, OWNER_ENDPOINTS and
ADMIN_ENDPOINTS registries beside the existing document policy. Current database
identity/allowlist state precedes each scope check; unsupported endpoints remain
default-deny. Admin status never enters `document_role` or content-route policy.
Account editing accepts only a display name for the session user. Unknown
identity fields are rejected, and existing Google logins preserve chosen names.

`access.py` contains SQL and mutation business rules shared with `auth_cli.py`.
All writes use BEGIN IMMEDIATE. Mutations reauthorize their authenticated actor
inside that transaction, validate eligible recipient identities, preserve a
final document owner and an active final site admin, and append access audit
rows atomically. Null actors represent trusted offline recovery only; no HTTP
field can request offline privilege. Existing CLI legacy-user ACL bootstrap
remains possible without exposing placeholder creation through owner UI.

The owner-scoped sharing directory exposes only active verified Google-linked
allowlisted recipients' display names, verified emails and internal selector
IDs. It is separate from admin identity listings. Owners cannot expand global
beta membership. Allowlist removal needs confirmation for any associated user
and deletes no identity/history/grant. Disabling/removing the final usable
admin's email is rejected along with ordinary final-admin revocation.

New pages use existing Jinja escaping, CSS panels, POST/CSRF forms, private
no-store responses and security headers. Mutation errors return 422; stale
service-layer authority returns 403. Content/PDF/Range routes, review services,
Socket.IO semantics and infrastructure are unchanged. Idle sockets are not
proactively evicted, and presence names update on rejoin. No admin content
bypass or global web ACL override was added. See README and BETA_C1_REPORT for
routes, bootstrap commands, audit behavior and verification evidence.
## Viewer presentation ownership

The original same-origin PDF.js iframe and canonical selection/anchor APIs remain.
`viewer_bootstrap.js`, loaded before the iframe, handles `webviewerloaded` to set
read-only native editor configuration and inject app-owned `styles/pdfjs.css`.
The viewer's native zoom path has one documented local patch; see
`static/vendor/pdfjs/LOCAL_PATCHES.md`. `viewer_shell.js` bridges compact parent controls
to existing PDF.js handlers/properties and positions parent-owned comment cards
from canonical anchor segments using `pdfRectangleToCss`.

`document_stage.js` separates the native PDF canvas from card reachability.
The canvas keeps the scroll viewport's width; cards never change its padding,
minimum width or centering. A stable native scrollbar gutter also prevents a
tall card from changing centering when the PDF fits on screen. Right comments,
floating cards/composers and unpinned
left tools report their measured document-space rectangles to one coordinator.
It unions those bounds with the native viewer's scroll dimensions and owns one
absolute extent element. It neither assumes equal pages nor derives widths from
page counts, spread parity or card-size constants.

Content left of or above the scroll origin is made reachable by rebasing the
canvas margin and native scroll offset by the same amount, atomically. Parent
comment coordinates rebase in that transaction too. Pinned tools do not contribute
bounds. Closing/shrinking content cannot remove the current viewport from the
extent and force browser clamping; unused origin space is reclaimed as it scrolls
away. This can retain empty space while it is currently visible, intentionally.
Card collision and motion remain app-owned; canonical anchors remain PDF space.

Comment ordering, 6px card gaps (3px marker gaps), section insertion and
selection-pivot packing are unchanged. Mobile comments remain popovers. Unpinned
left tools stay beside the document at every viewport size; the shared extent
provides space to pan left to reach them. Pinned tools retain viewport positioning.
The iframe and native scrollbar still surround the entire reachable
workspace. Native page auto-centering is independent of card presence.

Shared tokens/base/account CSS are imported by `app.css`; viewer chrome,
comments/migration/debug styling and PDF.js integration each have explicit
ownership. See `VIEWER_REDESIGN_REPORT.md` for classification and test evidence.

## Shared visual language

New PDF Review server-rendered pages should use the shared application shell,
tokens and control/menu primitives rather than introducing one-off visual systems.
`base.html` and independent `viewer.html` share `.app-toolbar`, canonical
`.toolbar-menu` / `.toolbar-popover` styling in `base.css`, `menus.js` behavior,
and `_account_menu.html`. The viewer retains its special workspace DOM.
The viewer's Tools menu uses those same menu primitives for Search document,
Filter comments, and owner-only Review settings/Manage sections. It calls existing
card open/reveal handlers; search uses find.open rather than the native toggle.
Shared LeftCard open/close synchronizes menuitemcheckbox aria-checked using each
card's stateKey, including restored and shortcut-opened cards. Checkmarks reuse
the existing menu pseudo-element styling. Tools uses the existing keep-menu-open
attribute. Its actions go through the left-card registry: open/focus an inactive
tool, close an active tool, or close all tools (including pinned cards) via the
normal close lifecycle. Tools menu interaction preserves card active state so
pointerdown does not clear it before testing a repeated tool click. Clicking
outside the menu keeps the normal menu dismissal/card unfocus behavior.
View holds PDF viewing operations; Comments holds display/filter-state choices
and Reset to document defaults, with reviewer selection in Tools → Filter comments.
Native find controls retain their PDF.js listeners and matching engine, but their
DOM is adopted into the host document's reusable Search left card. The application
synchronizes card/native open and close state, match/status text, and prevents
input focus from scrolling the host website. Four native checkbox/label pairs
are always visible in a two-column grid, with centered vertical alignment; there
is no Options disclosure. Ctrl/Command+F and Escape work in
both documents; original match navigation and option handlers remain intact. Page borders and both row/spread gaps use the vendored
PDF.js defaults; no app-owned page-spacing override remains.
See `VIEWER_REFINEMENT_REPORT.md` for the current presentation contract.

## BETA C2: review privacy, preferences, colors and semantic sections

Migration 8 extends migration 7 without modifying historical migrations. It adds
a fixed 24-color palette, user review colors, document review settings, durable
personal viewer preferences/hidden authors, logical sections, exact-version
section placements and semantic section-response conversations. Existing users
receive deterministic palette colors; an insert trigger assigns a random valid
palette color to new users. Color never conveys authorization.

`review_policy.py` separates enforced shared/isolated confidentiality from
personal scope/hidden-author filters. A conversation belongs to its immutable
top-level author; replies remain coherent. SQL selects permitted conversations
before content serialization. HTTP policy also protects direct thread/comment,
anchor and target-history access. Isolated migration history is owner-only,
including the viewer's migration entry point. Site admin remains independent.
HTTP thread writes and section writes recheck authority inside their transaction.

Isolated review emits only `review.invalidated {schema_version, version_id}` to
the exact version room. New section/settings/color changes use that same generic
invalidation and authorized canonical refetch. No private actor/content/target
IDs accompany it. Every version emission prunes ineligible/revoked recipients
and refreshes presentation identity from SQLite. Already delivered bytes cannot
be retracted; no durable socket replay or session activity history is introduced.

GET preferences is read-only. The viewer's CSRF-protected initialization POST
freezes document defaults only if preferences do not exist. Later default
changes do not overwrite personal choices. Reset explicitly reapplies current
defaults and clears hidden authors. Enforced isolation overrides saved Everyone
and redacts saved hidden-person IDs from responses to isolated non-owners.

Presence remains ephemeral and aggregates the most recent reported connection
per stable user, with at most one page or two adjacent spread pages. Spread
membership is read after PDF.js rebuilds its spread DOM. Initials avoid external
image requests; multiple users get thin faint outlines and compact avatar stacks.

Sections are flat, ordered document objects with stable identity and an optional
author prompt. Deletion archives them, preserving prior placements and feedback.
Placements use canonical PDF page/Y values and view boxes from the owner viewer,
following the existing owner-supplied geometry boundary. They never persist CSS
pixels. Finite coordinates, page bounds, range ordering, non-overlap and expected
placement revision are checked under BEGIN IMMEDIATE. Adjacent ranges/gaps are
valid. New versions remain unmapped; previous placements are informative only.

Section boundary overlays render only while the Sections card is open.
Exact page-edge markers render 12 px inside their own page. Section overlays
never change page margins, spacing, dimensions or spread membership. Section
feedback and its author prompts remain available independently of the inspector. Section
feedback uses the existing collision-managed right rail, including on narrow
screens. No section conversation is persisted as an artificial text anchor.

`section_responses` uniquely targets (section, exact version, top-level author).
Section comments and revisions retain explicit separate foreign keys while
`comment_lifecycle.py` shares insertion, immutable revisions, optimistic editing,
ownership and tombstone logic with ordinary text comments. This preserves the
non-null immutable-origin constraints on existing text threads.

Outline extraction uses the already-loaded PDF.js document. Owner confirmation
selects/edits candidates before one atomic creation transaction; no outline is
silently imported. Flat page-range suggestions are a convenience, with precise
boundaries available through the visual editor. No font/text chapter detection,
semantic version matching or section hierarchy is introduced.

Resilient pseudo-offline review remains deferred to a future dedicated slice.
There is no outbox, IndexedDB, service worker or persistent private PDF cache.

## Management interaction rule

`left_card.js` is the reusable shell for simultaneous document utility cards on
one left rail. Sections and Review Settings coexist at natural content height;
there are no viewport/share height limits or internal card/list scrolling. New
cards open unpinned near the viewport center, then retain their document-relative
position. Header pointer dragging moves a card vertically; dragging a pinned card
releases it into document space. Header buttons retain their normal actions.
At most one card is pinned, snapped 8 px below the workspace top above other cards,
clamped downward to the first page top if that is lower.
The pinned card is an independent overlay, excluded from collision packing,
neighbor focus priority and scroll-extent calculations. Its content height and
activation cannot move unpinned cards. Pinning preserves existing document-card
positions; pinning a second card unpins the previous one into document flow. Unpinning releases the card downward into document space. Collision
packing only moves unpinned full-height cards up/down into free intervals; it never
shrinks them. Packing has a lower bound at the first PDF page top in document
coordinates, so active or neighboring utility cards cannot move above the document
start. When no gap fits above a card, packing chooses space below it. Pinning and
animations respect the same boundary. The overflow sentinel includes the bounded
stack. Right-hand comment packing retains its existing rules. A pinned card
participates only after it is unpinned.
The active unpinned card is the fixed point among document-attached neighbors.
Before an unfocused card takes that priority, it and its unpinned neighbors
adopt their rendered positions as document anchors. Activation cannot restore an
earlier pre-collision position. In-flight motion is flattened to the displayed
position before repacking. Pointer, header-grab and keyboard focus share this
rule; deliberate section-line centering and offscreen tool retrieval still move
the inspector explicitly.
Outside pointer/click events in either the host document or PDF iframe clear
left-card focus and blur its controls without closing or moving cards. Events
inside any left card retain focus; section-line activation may focus Sections.
Per-card event listeners are aborted on close.
The shared document extent makes below-document cards reachable via the PDF
scrollbar. Pinned cards remain top-snapped even when activating a section line;
unpinned inspectors retain line-centered activation.
Closing one retains the other cards and recomputes measured reachability. `card_motion.js` supplies the existing 160 ms ease-out comment
selection animation; scrolling itself remains immediate and reduced motion is honored.

Left-card space belongs to the shared document extent, using the PDF workspace
gray background and native scrollbars; it is not canvas padding. The outer workspace uses overflow
clipping so browser focus cannot programmatically scroll that fixed overlay;
the iframe retains the native PDF scrollbar. The iframe stays full width. There is
no separate sidebar background. Right-hand comments keep their existing layout.
`dialogs.js` remains for destructive/outline confirmations and Settings on a
PDF-less document. The document page has no Review Settings or Manage Sections
buttons; the tools remain in the PDF viewer.

Sections always uses the open PDF version. `section_order.js` orders mapped rows
by canonical start page/Y, filling mapped slots in the previous logical order so
unmapped rows retain their display positions. No UI reordering or order writes.
`section_placement_editor.js` owns transient, per-section boundary drafts shared by
page-number fields and owner-only draggable demarkers. Page entry means start
before the page or end after it. `section_boundary_geometry.js` supplies a
12 px visual inset and an 18 px edge snap zone, measured along the canonical
page axis through the PDF viewport (including rotation). These are overlay-only
choices: no section-driven page/spread margins, spacing classes or layout events
remain. Target-page hit
testing and near-edge auto-scroll support cross-page dragging, converting through
the destination PDF viewport/view box. Layout changes notify both card rails. Pointer
cancel/Escape restores the pre-drag draft. Page edits autosave on change and drags
autosave on release. Requests are serialized; newer drafts retain their geometry
and receive the committed revision. Validation/conflict errors retain the draft
and expose Retry. There is no persistent outbox.

`section_boundaries.js` derives shared endpoints from coincident canonical
locations; no shared-boundary table or migration is needed. One management divider
represents a touching end/start pair. Dragging it or editing a linked page field
changes both endpoints. Page-transition dividers use the following start member
for physical geometry, activation and inspector centering. A notice names the
moved neighbor endpoint. Sub-page sections are allowed; the one-page minimum
is removed from client and service. Positive range length and non-overlap
remain enforced. Split or
unlinked endpoints continue to edit independently. Independent boundaries clamp/snap to
the closest valid neighbor and show an overlap notice; unrelated placements are
never silently resized. `POST /api/versions/<id>/sections/shared-boundary` saves
the two adjacent placements in one transaction. Owner and CSRF guards, placement
validation and expected revisions remain enforced. The service permits only the
shared end/start to change, requires unchanged outer endpoints, and rolls back
both writes on failure. An explicit `split: true` on that operation separates the
endpoints around their old position. Interior splits shrink both ranges by about
6 rendered pixels to either side (bounded by the pair's outer endpoints). Near
an interior page edge, splitting places an explicit numeric end at the preceding
page's exact bottom and start at the next page's exact top, preserving the outer
endpoints. Those exact numeric edges intentionally remain independent in divider
grouping even though their canonical locations touch. Null page-edge pairs remain
shared. This representation uses existing geometry fields, keeps a split stable
across zoom/reload, and needs no schema migration. Both placements save atomically
through the same guarded service; range and non-overlap validation still applies.
Canonical location comparison uses 10 decimal places of page height on both
client and server, avoiding false gaps from viewport round trips. Each queued save
captures its geometry at gesture completion; subsequent saves rebase only onto
revisions acknowledged from this client's own earlier writes. Independent drags
across their own opposite edge clamp rather than appearing to overlap a neighbor.

Page-edge management dividers use a 2 px line with transparent backing, inside
their own page. There are no separate always-visible structural rails or ticks.
The shared divider at an exact page transition renders at the following page start; splitting displays the two edges on their
respective pages. PDF.js alone owns page/spread spacing and alignment.

`sections_workspace.js` is the sole boundary inspector. List rows show compact,
right-aligned page ranges derived from live geometry (including drafts); an end
at the following page top does not count that page. Unmapped ranges stay blank.
Compact horizontal
Start/End controls synchronize with the PDF markers. Names and prompts autosave
after a short typing pause or on change/blur; a small footer shows Saving, Saved
or a retryable error. Delete retains confirmation. The separate top section
editing toolbar and manual save/cancel workflow are removed. Start/End markers select and activate its section and
smoothly center the card beside the selected boundary (clamped to the viewport),
matching comment selection. Unpinned cards capture that document-relative position. Opening Sections reveals all mapped
start/end lines; closing removes all PDF section boundary overlays. Outline import, precise boundaries, in-page edge lines, spread rules,
prompts and right-side feedback remain. Review Settings retains its form fragment
and existing save service. Click-away checks use the event path so left-card DOM updates cannot deselect a
right-side comment. PDF/background clicks retain normal deselection.
Schema and immutable PDF bytes are unchanged. The shared-boundary operation
uses the existing owner-only authorization policy.

## Left-card layout persistence

The reusable `left_card.js` shell saves minimal UI metadata in browser
localStorage under `pdf-review:left-cards:v1:<user ID>:<version ID>`. Records
contain only the registered tool key (Sections, Review Settings, Search or Filter comments),
anchor page, normalized document-relative vertical position and pin state.
No search text, prompts, drafts, review payloads or PDF bytes are cached. This
is local presentation state, not a private-content cache or mutation outbox.

Layout changes save with a short debounce; pagehide and hidden-document events
flush current open/closed state. After personal viewer preferences and canonical
review data load, registered tool openers restore content through existing
permission-checked fetches, then the shell restores positions together using its
normal page-start bounds and collision packing. Only one restored card may be
pinned. Owner-only tool openers are not registered for other reviewers. Unknown
tools, invalid positions, malformed storage and unavailable storage cannot block
viewer startup. Account and exact-version keys prevent layout inheritance across
users or PDF versions; no schema, API or dependency changes are required.

Section feedback uses one header containing the section name and trimmed prompt,
with `Overall thoughts` as the empty-prompt fallback. A separate prompt paragraph
and empty response invitation are omitted; existing responses and Add response
remain. Comments places a separator before Reset to document defaults.

## Viewer interaction refinements

Selected right-hand comments use a brighter mix of the immutable root author's
review color (78% author color, 22% white). Utility cards keep their existing
accent. No review identities or palette choices are changed.

After right-rail layout applies visibility and card changes,
`reviewlayoutchanged` schedules every open left card against the newly positioned
PDF. It does not depend on selecting a card. Existing scrolling, pin independence
and natural-height collision packing remain in the reusable shell.

Expanded regular comments keep their document-anchor order and the existing
selection-pivot packing. Section responses are grouped by section, then inserted
into that ordered list at the boundary that places the group's bottom closest
to its section endpoint. Existing natural gaps are used when the whole group
fits; a dense insertion sits directly after its predecessor and pushes the
remaining list down with the existing 6px separation. Ties prefer less movement
of the next card. Multiple sections insert in endpoint order and their responses
stay contiguous. Ordinary comments never pass one another to fill spare space.

A section group may sit above or below its exact endpoint when that is the
closest available list insertion. Only section-only or sufficiently sparse
layouts can guarantee exact bottom alignment. Changes in content height, zoom
or spreads recompute the insertion using document coordinates; ordinary scrolling
without a selection change keeps the same positions. Ordinary-only and minimized
marker packing are unchanged. Floating section cards retain their end anchor.

Section response cards use the normal comment width plus 30px, including floating
presentations. Their measured bounds extend horizontal reachability without
changing page centering. All
thread controls have zero top margin. Card height observations recompute packing
when responses or reply forms grow.

Document-attached UI uses `card_scale.js`: its uniform visual scale is
`min(1, pdfViewer.currentScale)`. The stage synchronizes a workspace-scoped CSS
variable on native `scalechanging`; card layout and wrapping remain unscaled.
Left-card packing, comment packing, endpoint alignment and reachability use scaled
sizes while all positions and pointer deltas stay in screen CSS pixels. Independent
CSS translate animations preserve those deltas before card scaling. PDF page
centering, native scale/focal calculations and gesture handling are unchanged.
The toolbar and body-level mobile keyboard composer remain viewport controls.
Focused coverage: `tests/browser_sanity.py --card-scaling`; native focal and touch
regressions remain in `--zoom-layout`.

Left-card layout snapshots each card's size and visual top once, caches page/spread
geometry for that pass, computes collision packing without DOM reads, then writes
positions together. Scroll bounds come from those plans, avoiding a second round
of measurements after writes. `card_packing.js` packs around a placement pivot
independent of keyboard focus. Opening snapshots the neighbors' displayed document
positions and captures the viewport midpoint as a document anchor for the new
card's center. An insertion chooses the nearest internal gap when the midpoint
falls inside a multi-card stack; outside the stack, an outer gap is allowed.
The identities on each side are retained through subsequent loading/resizing,
instead of repartitioning by changing card centers every frame. Opening cancels
existing movement after capturing displayed tops, preventing an old translation
from being applied again to the new positions. Later content growth adjusts its
top around that center; scrolling
does not recenter it to the viewport. The upper chain moves backward only on
collision, the lower chain moves forward, and the nearest upper cards spill below
the pivot when their combined heights cannot fit above page one's limit. The new
card's center-to-top offset is capped by half the opening viewport height minus
8px. Oversized cards therefore open with the header visible, including when
asynchronous content grows beyond the viewport. The cap is attached to the
opening document anchor, so scrolling afterward still moves the entire card.
The first-page limit also applies. Focus/click/drag adopts displayed top anchors;
saved layouts restore top anchors. Pinned cards remain outside packing.

Initial placement skips position-travel animation while `openingCentered` is set.
After synchronous visibility/focus layout, `open()` starts one shared 160ms
ease-out fade and 4px slide. A separate entrance guard lasts until that animation
finishes or is cancelled: automatic pinning, focus and content-ready layouts cannot
replace it, even after centered placement has finished. This keeps fresh and reused
cards identical, including Ctrl/Cmd+F opening Search then pinning it. Direct pointer
interaction interrupts the entrance so dragging and manual pinning remain responsive.
Close cancels and releases the guard; old completion callbacks cannot affect a later
opening. Reduced motion skips it. Exact traces are covered by `--left-card-focus`
and the real first/reopened Search shortcut in `--tools-menu`.

`--left-card-insertion` checks unequal displacements, first-page spill, delayed
content growth and focus retention at 100% and 50% zoom, plus fixed-slot retention
when a tall neighbor shrinks. `--tall-stack-insertion` uses three tall cards, an
in-progress movement and the real asynchronously loaded Settings card.
Bounds reported during stage jobs use the current
frame's commit instead of scheduling an empty extra frame. Section divider layout
also measures all page geometry before mutating markers and preserves unchanged
labels, attributes and keyboard handlers. `--left-card-performance` exercises all
eight tools and a 64-section marker model; it asserts work counts and geometry,
without machine-dependent timing gates. Firefox long-document coverage supports
`tests/firefox_reading_cards.py --all-tools`.

Comment scope and reviewer choices live in `comment_filters.js`, opened from
Comments > Filter comments... as the reusable Filter comments left card. Native
radio controls choose All comments, Only mine or Selected reviewers; the latter
shows a reviewer checklist. All comments saves `scope: all, hidden_reviewers: []`,
Only mine preserves the hidden-author selection while saving `scope: mine`, and
reviewer edits save all scope with a hidden-author list. Existing preferences and
canonical context APIs remain authoritative; no schema or endpoint changes.

The card renders current canonical preferences, with a temporary in-memory draft
while queued saves complete so rapid checkbox changes do not discard one another.
Existing checkbox nodes are retained across refreshes to preserve keyboard focus.
All four tool cards register with shared layout restoration and retain dragging,
single-pin behavior, natural height and saved account/version positions. Only
minimal card layout metadata is stored locally, never reviewer filters or content.
The old Everyone/Mine dropdown entries and reviewer submenu are removed; Reset to
document defaults remains in Comments, separated from the card opener.

Isolated non-owners see Only mine selected, other modes disabled, and no reviewer
checklist. Existing backend policy still enforces privacy independently of these
controls. Viewer and reviewer roles can use personal filters where policy allows.


PDF.js retains its native TouchManager, scale limits, focal math, panning and
rendering. The coordinator wraps updateScale only to call native update() before
scaling, ensuring its location snapshot belongs to the old geometry. In a mixed
page-size fixture, native pan marked that snapshot stale and the scale routine
refreshed it after resizing pages; this caused a separate first-pinch jump.
The preflight fixes snapshot ordering without applying an extra focal pan or
computing a new scale factor.

The native viewer's scale/scroll transaction now captures the PDF-space point
under a supplied zoom origin before resizing pages. This is independent of the
first visible page: mixed page widths, rotations and wrapped rows can move by
different amounts. Native destination conversion restores that point, combining
its restoration offset with the origin/pan adjustment before each browser scroll
assignment. Intermediate negative offsets are no longer clamped separately;
genuine final limits still clamp normally. The requested final position updates
PDF.js's private fractional pan state. Paper, borders, gaps and background share
one page-relative plane. Background selects the nearest attached page, including
offscreen pages, and extrapolates coordinates outside its content. Native touch
callbacks hold that page identity for the gesture; camera coordinates resample
within the same plane on each step, including after a real scroll limit. Gesture
end/cancel, document reset and app blur/visibility cleanup release the reference.
An empty visible-page list never restores an old page location for an origin-based
zoom. Same-scale panning retains native panBy; ordinary non-origin navigation
keeps native view-location behavior.

This small viewer patch avoids DOM scroll-accessor interception, duplicate
app-owned page geometry and a deferred corrective scroll. It makes no assumptions
about page counts, spread parity or card dimensions. The patch and version-specific
upgrade procedure are recorded under `vendor_patches/` and
`static/vendor/pdfjs/LOCAL_PATCHES.md`. Rendering core, worker and TouchManager
are unchanged; the app stage remains the sole owner of card reachability.

`pdf_gestures.js` scopes pan-axis touch-action and Safari browser-gesture
cancellation to the PDF surface/embedding wrapper. Other app chrome retains
normal browser gestures. It observes PDF contacts without consuming the native
TouchEvent stream. If a touch's original DOM target is detached, only its otherwise
stranded events are relayed to the iframe window's native TouchManager; connected
events are not duplicated. Highlights use keyed DOM nodes and page-relative
percentage geometry: browser layout keeps them aligned throughout native page
resizing, without waiting for touchend or recreating touched nodes. Rotation and
review state reconcile in place. Section markers likewise update keyed nodes
while pinching; obsolete nodes are hidden during contact and removed afterward.
Ordinary boundary drag and text selection retain their existing handlers.
Touchend/cancel, blur and visibility changes clean up contact listeners.

The stage does not reclaim/rebase origins or shrink its extent during PDF touch
contacts or active native scrolling/momentum. A scroll-idle phase performs that
maintenance later, preserving the current viewport. During one-finger panning,
the browser exclusively owns scroll motion; no app scroll assignment runs.
This avoids interfering with WebKit's asynchronous touch scrolling. The measured
browser case used a 120px finger drag, produced 105px page motion and recorded
zero app scroll writes. Physical Safari's reported excess motion is not yet
verified as resolved.

Focused coverage uses an immutable synthetic eight-page PDF with mixed dimensions,
all four rail combinations, odd/even spreads, vertical/horizontal/wrapped scroll,
dynamic card bounds and origins in both axes. It measures PDF-space points after
deferred layout, real browser trackpad input, pinch/reversal, detached targets and
delayed drawing. Desktop touch emulation does not verify physical iPhone Safari;
see MOBILE_TESTING.md for the remaining device checks. Earlier research is retained
in MOBILE_ZOOM_ARCHITECTURE_REVIEW.md and TRACKPAD_ZOOM_DIAGNOSIS.md.

Temporary HTTPS mobile testing uses `mobile_https.ps1` and
[MOBILE_TESTING.md](MOBILE_TESTING.md). After an initial automatic approval
rejection, the user explicitly approved public Cloudflare forwarding on November
3, 2026. Startup and public health/login redirects were verified. One loopback app
process uses a generated trusted hostname, HTTPS callbacks, Secure cookies and
one trusted proxy hop. The normal `.env` is unchanged, and existing Google auth,
allowlists and document ACLs remain required. A user must register the generated
callback in their Google Web OAuth client. No VPS, production service, DNS or
router/firewall configuration is changed.

## Review palette refresh (migration 9)

The selectable palette is now the ten published Tableau 10 categorical colors,
in their original order: https://d3js.org/d3-scale-chromatic/categorical#schemeTableau10.
Migration 9 inserts these entries, maps existing review colors to an approximate
corresponding hue, then removes the old choices without breaking user foreign keys.
Names/hover labels identify the swatches. Historical migrations are unchanged;
new-user random assignment uses the new palette through the existing trigger.

## Document download controls (migration 10)

`document_review_settings.downloads_allowed` is an owner-controlled document
setting, defaulting to 1 for existing and new documents. Its checked integer
value is saved through the existing owner-only, CSRF-protected settings service;
partial settings updates preserve it. It applies to all roles and versions of
that document. Personal preferences cannot override it. Committed changes use
the existing version-room notifications and canonical context refresh.

The initial server-rendered viewer hides/disables host print and download buttons
when restricted. The existing PDF.js pre-run integration wraps application print,
save and download methods before native event-bus callbacks are bound. After
initialization, the shared native download manager also guards attachment exports.
The host and iframe intercept Ctrl/Cmd+S/P, hide native export/attachment controls,
and suppress page content in print media as a fallback. Live canonical refresh
updates the same gates, so disabling and enabling work without a reload. Vendor
sources and immutable PDF bytes remain unchanged.

This is a presentation/export policy, not DRM or a new read-access boundary. The
existing authenticated PDF GET/range endpoint remains available for rendering;
viewers can still obtain bytes or capture content using browser features outside
app control. No claim is made to block browser menus, developer tools, screenshots,
or raw PDF URL saves. Existing document ACLs and private response headers remain
the read-access boundary. No new PDF rewriting, caching, or content mutation is
introduced. Browser storage of left-card state never stores PDF bytes.

## Author-controlled reading activity (migrations 11–12)

Reading activity is a separate optional domain, not an extension of the presence
registry or review/anchor history. See [READING_PROGRESS_REPORT.md](READING_PROGRESS_REPORT.md)
for the complete model, schema and measurement limits. Migration 11 adds
`reading_consents`, `reading_totals`, `reading_pages`, `reading_sessions`,
`reading_leases` and `reading_visits`. User/version/page foreign keys and identity
triggers prevent reassignment; lease triggers require a session belonging to the
same reader. Prior migrations, immutable PDFs and review tables stay unchanged.

Tracking defaults on. Migration 12 adds document-wide `reading_tracking_enabled`
and `document_reading_pauses` (document/user key), across all versions. Only authors
can change either in Review settings. Readers cannot opt out, pause or erase.
The legacy reading_consents table now registers exact-version metadata and policy
generations; migration 12 resets prior personal states, advances generations and
releases leases. Policy changes reject stale batches and retain all history.
Authors inspect eligible document readers; all others see only themselves in both
shared and isolated review. Automatic personal session/batch endpoints permit even
read-only viewers without granting owner/comment mutations. The legacy consent
endpoint is now strictly owner-only. ACLs and CSRF remain enforced server-side.

`presence.js::viewingPages` is now the shared unchanged page/spread selection
source for live avatars and reading timing. Presence remains ephemeral and does
not itself persist viewing time. `reading_clock.js` owns monotonic eligible-time allocation;
`reading_tracker.js` owns visibility/focus/idle/connectivity gates, PDF.js counts
and batched transport. No zoom, native touch, page layout or gesture code changes.
One spread shares elapsed time by visible area. Active sampling requires a recent
interaction, settled scrolling and a user-wide server lease. Timer suspension and
offline periods never backfill time.

HTTP batches normally arrive every 15 seconds, with sequenced idempotency and a
single transactional server receipt-time budget bounded at 20 seconds. The global
25-second reader lease excludes simultaneous full-rate accumulation across tabs,
versions and devices. Cumulative page/reader totals update incrementally; visit
rows update per session/visit/page. Client timing, metadata and inferred completion
remain approximate. Policy is centralized at 400 words/minute and a 5-second page
minimum; considered-read timestamps are separate from measured time.
Section completion is derived from distinct pages intersecting the canonical
range: `pages_read * 100 > page_count * 90`, strictly above 90%, not rounded
percentage or any single read page. Fractional edge coverage prorates dwell time
only. Section labels give an explicit status and read/total pages. Time tracker's
Sections view defaults to Completion: bar widths and right-side values use the
section's page completion percentage. Its compact Dwell time toggle restores
relative active viewing-time bars and duration values. Switching patches existing
nodes; headings, explanatory text and accessible bar labels reflect the metric.
The account/exact-version reading-view preference saves `sectionMetric`, with
Completion as the default for old/absent/invalid preferences. Tracking, completion
thresholds and server data are unchanged.

The reading summary pages at 100 readers, per-page detail at 50 rows by default
(100 max). Committed batches send targeted, content-free `reading.changed` WebSocket
invalidations to authorized authors and the reader. Policy changes reach all
viewers across versions; live positions reuse presence. A 30-second open-card
poll and reconnect refresh remain recovery paths; page-only windows
skip section aggregate work. Section prefix sums and canonical boundary fractions
avoid repeatedly scanning visits. Consent/reading data is never stored in browser
layout storage or broadcast to the shared realtime room. History persists through Off/Paused; this slice introduces no automatic retention job or offline cache.

`reading_cards.js` composes exactly two shared `LeftCard` instances, registered as
`reading` and `analytics`. They inherit Tools focus/toggle, pin/drag, collision
packing and restoration. Label packing is internal to the proportional spine;
leaders retain true page positions. Native PDF.js destinations navigate pages and
in-page section starts. Analytics contains both Sections and expandable Pages,
not another card. Styles live in `static/styles/reading.css`. Saved layout parsing
now accepts a bounded 32 records so six tools restore without the former four-card
truncation. No private activity is saved there.

Reading analytics retains its page/group/statistics nodes during routine realtime
refreshes and patches values, preserving focus, expanded groups and loaded windows.
Reader/view/section-structure changes rebuild only the affected view. An account/
exact-version scoped browser record restores the reader, Pages/Sections tab and
expanded group identifiers; the authorized roster validates the saved reader.
Only UI choices, not measured activity, are stored in this record.

Reading-card rendering is visibility-gated: closed analytics cannot render its
expanded page groups or start/continue page-metric extraction. A stale page-list
body may retry only into a different, connected replacement. Detached groups in
closed cards must never recursively retry themselves through promise microtasks.
The Manuscript spine retains keyed section/reader/legend/SVG nodes and skips an
unchanged model; tracker/presence draws coalesce per animation frame. These rules
prevent closed-card work and refresh churn from blocking long-document viewers.

## Version statistics metadata and histogram

Version statistics retains the shared LeftCard/Tools registration (`properties`),
available to everyone who can view the PDF. It uses the existing pin, drag, focus,
collision, checkmark and account/version card-restoration paths. No new route,
server table, migration, chart dependency or PDF.js/vendor modification is needed.
`page_properties_card.js` maintains stable SVG bars across metric switches;
Pages/Sections changes the row layer; axis and section brackets update independently.
`version_statistics.js` aggregates canonical placements and authorized messages.
Page/spread highlighting
uses the same `viewingPages` helper as presence and reading analytics.

`page_properties_data.js` owns one metadata store per loaded PDFDocumentProxy.
It shares word-count extraction with ReadingTracker, deduplicates concurrent
requests, scans at two pages at a time with event-loop yields, and builds the chart
only when opened. Images scan only when selected. Persistent aggregate metadata
is keyed by account, immutable version, PDF fingerprint, page count and calculation
schema in browser IndexedDB, retaining at most 12 recent version records. Calculation
schema 2 also caches numeric count/vertical-position pairs for text runs and artwork
so partial-page section totals can be computed without re-extraction. No raw
PDF bytes, page text, reader activity or extracted image data is stored. Storage
failure falls back to the per-document memory cache. The existing server ACL read
endpoint is still required before a viewer can construct/use the store.

Words use PDF.js text runs and word segmentation. ERT uses the existing server
reading policy (400 WPM / 5-second minimum), independently of measured dwell time.
Density has been replaced by Comments: stacked author-color counts of non-deleted
messages/replies, including resolved conversations and section feedback. Canonical
thread/context refreshes enforce existing privacy and reviewer filters; websocket
invalidations update the card. Each message serializes its actual author's existing
review color. Comments are never put in the immutable PDF cache. Multi-page targets
count once at their first segment; section feedback stays with its own section/end.
Images include supported raster placements/repeats/groups/masks and outer tagged
Figures containing vector paths or raster painting. A nested illustration counts
once; untagged vector decorations and annotations are excluded. Unsupported patterns
or failed extraction are unavailable, never fabricated zeroes. Section word/image
ownership uses vertical text-run/illustration centers; integer ERT allocation shares
the existing page budget. Unsectioned gaps retain totals. Full details and checks:
VERSION_STATISTICS_REPORT.md; the original implementation is PAGE_PROPERTIES_REPORT.md.

Page Properties follow-up: count/time axes and page ticks are integer-only; gridlines
are unconditional. Rendering skips unchanged metadata/metric/section revisions and
patches only changed SVG attributes. Word segmentation yields in bounded work slices;
no per-page full segment array is materialized. Cached scans skip completed pages.
IndexedDB version 2 adds a timestamp index for key-only eviction, preserving metric
cache keys and numeric metadata. Firefox checks use isolated Marionette profiles.

## Version deletion / withdrawal (migration 13)

Owners may delete one version through the document page's explicit confirmation.
This is application withdrawal, not physical PDF/history erasure. Migration 13 adds
an append-only version_deletions ledger (version FK, deleting user FK, timestamp)
and active_document_versions view. Original version metadata, byte identity, PDF
blobs, immutable anchors/targets, comment revisions, section feedback, reading
history and migration runs remain untouched. Existing deduplicated blob references
remain authoritative, including withdrawn versions. There is no restore/purge UI.

`database.version_table(connection)` selects the active-version view at runtime;
it falls back to the original table only for trusted pre-migration offline import
compatibility. Lists, counts, resource authorization, version reads and transactional
review/reading/section/migration services use that scope. Source/target migrations
involving deleted versions are unavailable in normal UI, but their records remain.
Threads with a live projection retain their comments on surviving versions; their
deleted-version anchors/target entries are excluded from ordinary reads. Threads
with no live target and section conversations on withdrawn versions become
unavailable. Existing immutable identity/revision triggers are unchanged.

The delete service rechecks authenticated eligible ownership inside the same write
transaction as the deletion ledger, version.delete access audit, and release of
only this version's active reading leases. Confirmation must name the exact route
version. HTTP GET only displays confirmation; POST is owner-only and CSRF protected.
Deleting the final version keeps the logical document ready for another upload.
Re-importing identical bytes creates a new active version identity without undoing
the old deletion. No source file or shared blob is moved, rewritten or unlinked.

After commit, a content-free review.version_deleted event reaches eligible viewers
of that exact version. Clients disconnect and navigate back to the document; the
server retires room presence and denies subsequent joins/reads/writes. Previously
received PDF bytes cannot be recalled. Existing generic broadcasts also prune
withdrawn versions. Backup/storage verification retains the full historical ledger.
