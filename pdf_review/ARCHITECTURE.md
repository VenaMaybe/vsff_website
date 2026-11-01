# PDF Review architecture decisions

These are permanent extension constraints, not temporary implementation details.

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

- invitation/admin web UI and additional identity providers
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
83. `document_access` grants owner/reviewer/viewer explicitly, with no blanket migration backfill. Owners import/verify and mutate migration workflows. Reviewers create/reply/resolve/reopen. Both edit/delete only their own comments. Viewers read. All roles read authorized history. Globally approved accounts may create a document and become owner atomically. Permission management is offline CLI only.
84. Shared default-deny HTTP policy resolves resource ownership before content handlers. Missing/inaccessible resources return generic 404, insufficient roles on accessible documents 403, anonymous APIs/mutations 401, anonymous pages a login redirect. Lists contain granted documents only; reviewer lookup exposes only the current account.
85. Every PDF request, including GET/HEAD/conditional/valid or invalid Range, passes authentication and document ACL before blob access. Werkzeug conditional/206 behavior remains. Blobs stay outside static and receive no public URLs or tokens. Protected responses are private/no-store.
86. Every authenticated unsafe HTTP method requires session CSRF, compared in constant time. Forms submit hidden tokens; app-owned APIs share http.js. OAuth state is independent. Authenticated server identity supplies every review actor; clients cannot choose identities.
87. Sockets reuse HTTP identity/ACL functions and exact-version ownership checks. Presence derives from database identity. No socket mutation API exists; post-commit broadcasts/canonical refetch remain. Forced eviction of existing idle sockets is deferred; subsequent HTTP/connect/join checks enforce current revocation, and page reports revalidate membership.
88. Environment secrets persist across production restarts and never enter SQLite/source. Production refuses missing credentials/host, short secrets, HTTP scheme or insecure cookies. Cookies enforce HttpOnly, SameSite=Lax and production Secure. Development supports loopback HTTP, without an identity-selection fallback.
89. Proxy trust defaults to zero. One optional trusted isolated ingress may supply forwarded scheme only; canonical host/scheme are explicitly configured and hosts validated. Nosniff, same-origin referrer policy and SAMEORIGIN framing preserve PDF.js; production adds HSTS. Vendored PDF.js/CSP are unchanged. Deployment is outside this slice.
90. Migration 6 adds identity fields/indexes, immutable-subject protection, allowlist and document ACL constraints/indexes, without rewriting historical migrations/domain rows. Existing documents require explicit bootstrap grants. Back up a live SQLite database with SQLite's backup API before migration; a raw copy of an open WAL database is not sufficient.
