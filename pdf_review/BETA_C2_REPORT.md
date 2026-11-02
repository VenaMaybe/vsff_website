# BETA C2 — local development

## Pre-edit architecture audit (November 2, 2026)

The existing ARCHITECTURE.md, README.md and beta/viewer reports define the
extension constraints. The working tree already contains viewer refinements;
these are retained. No deployment, staging, commit or infrastructure work is
authorized in this slice.

- SQLite migrations 1–7 run transactionally at factory startup. Migration 8 is
  the next number. Immutable blobs, anchors, origins, effective heads, comments,
  revisions, resolution history, ACLs and access audit history must survive.
- `auth.py` uses explicit default-deny endpoint registries and resolves document
  ownership before handlers or PDF blob access. Site admin grants no content
  access. New owner writes must reauthorize inside `BEGIN IMMEDIATE`.
- `threads.py` selects effective targets but currently retrieves all document
  review. Direct comment/thread/history routes also need isolation checks.
  Diagnostic anchor reads can expose thread anchors unless filtered.
- `realtime.py` has process-local version rooms and a locked presence registry.
  Current events broadcast thread/comment IDs to all version members. C2 must
  prevent that under isolated review, including existing room memberships.
- `access.py` owns transactional profile/sharing/admin writes. Account and
  document pages use Jinja and the shared compact shell. Colors are presentation
  state and must not influence identity or authorization.
- Viewer orchestration is `anchors.js`; `review_state.js` feeds sidebar and
  overlays; `viewer_shell.js` positions cards on the right using canonical
  geometry. The same-origin PDF.js vendor is unmodified. External app styles
  are required by iframe CSP. Page spacing and spreads must remain intact.
- Presence currently aggregates one page per user, never durable activity.
  Extend the latest connection to one/two active pages, without accumulating
  every visible page. Initials avoid third-party avatar requests.
- Sections need stable document identities and independently confirmed exact
  version placements. Precise PDF Y boundaries must add zero layout spacing;
  intra-spread boundaries must not split a spread. Structural markers remain
  visible with hidden discussion; feedback stays on the right.
- Section conversations require explicit semantic section/version/author
  targets. They must share revision/edit/conflict/tombstone logic without fake
  text anchors or changing the immutable origin rules for text threads.
- Existing tests use temporary SQLite/PDFs, offline identity fixtures, direct
  DevTools and real local WebSockets. No real Google or private runtime data is
  needed for acceptance.

Resilient pseudo-offline review is deferred to a future dedicated architectural
slice. No outbox, service worker or persistent private PDF cache is included.

## Implementation and review

1. **Schema/migration.** Migration 8, `review_policy_preferences_and_sections`,
   adds `review_palette`, `document_review_settings`, `viewer_preferences`,
   `hidden_reviewers`, `sections`, `section_placements`, `section_responses`,
   `section_comments` and `section_comment_revisions`, plus `users.review_color`.
   Historical migrations 1–7 are unchanged. SQLite cannot add a REFERENCES column
   with a non-null default to a populated table: the migration adds the nullable
   reference, deterministically backfills it and uses insert/update triggers to
   ensure valid persisted colors. New-user insert assignment is random and stable
   thereafter. No identity, grant, authorship, immutable origin or blob is rewritten.

2. **Comment visibility.** Enforced privacy and personal display filtering are
   separate. Shared review permits all authorized conversations. Isolated review
   restricts non-owners to conversations they originated. Owners retain access to
   all conversations and may use personal convenience filters. Root authorship
   governs visibility; reply authors do not split a conversation.

3. **Isolated confidentiality.** SQL predicates run before canonical comment and
   section-response serialization. Direct thread/comment operations, target
   history and anchor feeds also enforce policy. Isolated migration listings,
   details and the `?migration=` viewer entry point are owner-only to avoid
   source-thread/count leakage. Hidden objects return 404. Saved hidden-person
   IDs are redacted from isolated non-owner preferences. The browser never receives
   a forbidden discussion merely to hide it through CSS.

4. **Personal reviewer filters.** Comments includes Everyone, Mine and People.
   Hidden authors suppress their whole top-level conversations, retaining replies
   inside visible conversations. Preferences live per document/user in SQLite.
   People exposes only content-author IDs, names and palette colors for the exact
   version, including section authors; it exposes no global beta directory/email.

5. **Owner defaults.** Document → Review settings provides enforced Shared /
   Isolated policy plus initial Everyone / Mine, No / Odd / Even spreads and
   Expanded / Minimized / Hidden defaults. The surface uses the existing shell,
   compact controls, POST forms, Jinja escaping and document owner authorization.

6. **Personal preferences.** GET is read-only. The viewer initializes established
   preferences through a CSRF-protected POST only when none exist. Later owner
   default changes preserve existing choices; later first-time users get the new
   defaults. Reset clears hidden reviewers and applies current document defaults.
   Viewer-role users may change their own preferences without gaining review-write
   permission. Isolation overrides a harmless saved Everyone preference.

7. **Palette and assignment.** The fixed palette contains 24 restrained medium
   colors with database references. Existing-user assignment derives from stable
   IDs, new-user assignment occurs once at insertion, duplicate colors are valid,
   and out-of-palette values are rejected. Colors have no role in ACLs or identity.

8. **Account UI.** Account adds small radio swatches and Save review color. Labels
   include palette number/value, selected states have outlines, and keyboard focus
   is visible. It retains existing own-profile/account/admin boundaries.

9. **Highlight behavior.** Text highlights use their top-level author's current
   palette color at restrained opacity. Hover/selected/resolved states preserve
   that hue with different emphasis. Section cards and markers use their response
   author's accent. Selection geometry and immutable anchors are unchanged.

10. **Avatar handling.** No external profile image is stored or fetched. Small
    initials are the explicit fallback used throughout page presence; this avoids
    new remote URL validation, image CSP, tracking or upload requirements.

11. **Active-page/spread model.** Presence remains process-local and ephemeral.
    The current PDF page determines one page in single mode or its current pair
    in spread mode. Reporting waits until PDF.js has rebuilt spread DOM. Server
    validation accepts only one page or two distinct adjacent pages containing
    the active page, never an accumulated viewport-page list. The latest reporting
    connection determines one aggregate user's pages; closing a tab falls back to
    the remaining connections. Existing legacy single-page reports still work.

12. **Multiple collaborators.** Remote users get faint 1px outlines and tiny
    initials, capped at three visible outlines/avatars with a +N overflow label.
    The viewer's own identity is omitted from page decorations. The existing
    participant menu remains and includes accessible names/page information.

13. **Logical sections.** Sections have stable IDs, logical-document ownership,
    flat order, name and optional author prompt. Numeric order controls support
    reordering. Delete archives the section; historical placements, conversations
    and revisions remain in SQLite. Nested hierarchy is intentionally absent.

14. **Version-specific placement.** Each `(section, version)` placement holds
    canonical start/end page numbers, PDF Y values or exact-page boundary values,
    canonical view boxes, optimistic revision and authenticated updater/time.
    Each new version remains unmapped. Prior-version placement summaries help the
    owner deliberately define the next placement without guessing pagination.

15. **Range validation.** Under BEGIN IMMEDIATE, placement writes reauthorize the
    owner and check matching document/version, finite coordinates, view boxes,
    page bounds, start-before-end, non-overlap and expected revision. Adjacency
    and gaps are supported. PDF Y increases upward, so comparisons normalize to
    ordered page/top-distance locations. The DB additionally rejects mismatched
    section/version documents and identity changes.

16. **Precise-Y markers.** Absolute neutral left-edge ticks attach to the relevant
    page. Their positions convert through the current PDF.js viewport and actual
    page content box, accounting for native page borders. Zoom and rotation change
    presentation only. Ticks add no layout height or page/spread gap.

17. **Between-page rails.** Exact page ends use a 10px neutral label/rail in the
    existing native inter-row spacing. They do not resize the PDF or insert a new
    page. Structural labels include accessible names and the optional author prompt.

18. **Spread rules.** A boundary inside one spread uses a compact page-edge tick;
    the spread remains intact. A boundary after a spread row uses the compact rail.
    No opposing/left discussion rail is introduced. Structural markers remain
    when review discussion is Hidden.

19. **Owner management/editor.** Manage sections lists order, name, prompt,
    current-version mapping and prior mappings, with Save/Delete/Add and version
    selection. Define boundaries opens View → Edit sections in the viewer. Set
    start/end deliberately captures an edge or precise click, presents transient
    preview ticks/text, and saves only on Save boundaries. Done leaves edit mode.

20. **PDF outline import.** The existing loaded PDF.js document supplies outline
    candidates. A compact owner-only preview lets the owner choose a subset and
    edit names/start pages; nested items start unchecked. Confirmation creates
    the selected flat page ranges atomically through the same placement service.
    A failing overlap rolls the entire import back. No automatic outline import
    or heuristic text/font chapter detection runs.

21. **Author prompts.** Prompts appear with section-feedback cards and in the
    structural marker's accessible/hover label. Crossing a boundary never opens
    a modal or form. Outline confirmation has a deliberate owner-invoked dialog;
    reading and responding do not automatically open it.

22. **Feedback model.** `section_responses` explicitly targets the logical section,
    exact version and top-level author, with a unique constraint on that triple.
    Replies use `section_comments`. There are no artificial text anchors or fake
    origin targets. Ordinary text-thread origin constraints remain unchanged.

23. **Feedback versioning.** A review on Draft 1 stays on Draft 1, including when
    the logical section gains a confirmed Draft 2 placement. The same reviewer may
    create a separate Draft 2 response. No response migration is inferred.

24. **Feedback privacy/filtering.** Section reads use the same server policy and
    top-level-author filter as text threads. Isolated reviewers cannot reply to or
    edit hidden responses through guessed IDs. Owners can read all; author-only
    edit/delete still applies to everybody, including owners and site admins.

25. **Right-rail feedback.** Compact response cards and an own-response affordance
    participate in the existing collision-managed rail. Minimized mode provides
    distinct dashed markers; Hidden removes review cards/markers, retaining
    structural markers. Section feedback remains rightward on narrow screens,
    using the document's existing horizontal scrollbar as needed.

26. **Shared lifecycle logic.** `comment_lifecycle.py` supplies insertion, immutable
    revision append, positive expected revision checks, conflict detection,
    ownership, no-op edits and tombstones for text and section comments. The
    explicit table families prevent arbitrary table-name input. Existing text
    services continue to own their conversation and transaction boundaries.
    Section conflicts preserve drafts and use the existing latest-revision
    acknowledgement UI before retry. No mature edit algorithm is copied into a
    second independent service.

27. **Realtime.** SQLite/HTTP remain authoritative. Shared text events retain the
    existing compatible notification shape. Isolated review sends only
    `review.invalidated {schema_version, version_id}` with no actor/thread/comment
    metadata; section/settings/color changes reuse that generic event. The serial
    coordinator refetches authorized threads and context. Notifications occur after
    commit and failures cannot turn successful writes into reported mutation failure.
    Idle socket recipients are revalidated and pruned before any version broadcast.

28. **Security/privacy audit.** Explicit endpoint registries cover every new route.
    Owner-only section/settings surfaces and services reject reviewers; viewer
    preference writes are the narrow personal exception. All writes require CSRF.
    Cross-document section/version combinations fail before handlers. New response
    operations reauthorize under the write lock; text operations now recheck review
    visibility under that same lock. A policy-change-between-middleware-and-service
    test proves hidden replies are not inserted. PDF/GET/HEAD/Range, immutable storage,
    OIDC, site-admin separation and private/no-store headers remain covered.

29. **Accessibility.** Radio swatches have labels/focus indicators; interactive
    structural markers are focusable with names/prompts; People uses native
    checkboxes; existing keyboard menus/forms remain. Initials/names supplement
    color. Edit mode has explicit named controls and preview text. Existing
    reduced-motion handling is retained. This is browser/DOM acceptance, not a
    physical assistive-technology or screen-reader certification.

30. **Responsive/visual behavior.** The compact application style is reused.
    Settings, sections and palette pages pass no-horizontal-overflow checks at
    1440×900, 1280×800, 1024×768, 768×1024 and 390×844. Viewer pages retain document
    horizontal scrolling for large pages/spreads plus right-hand feedback. C2 mode,
    editor and management screenshots cover all five requested viewport sizes.

## Validation evidence and final boundaries

31. **Files changed.** New service/schema files: `review/migration8.sql`,
    `review/review_policy.py`, `review/preferences.py`, `review/sections.py`,
    `review/section_feedback.py`, `review/comment_lifecycle.py`, and
    `review/review_routes.py`. New UI files: `templates/review_settings.html`,
    `templates/sections.html`, `static/review/viewer_preferences.js`,
    `static/review/section_manager.js`, `static/review/section_viewer.js`, and
    `static/styles/sections.css`. New tests: `tests/test_beta_c2.py` and
    `tests/beta_c2_acceptance.py`. This report is new. Existing factory/auth,
    account routes, anchors, threads, realtime, users, viewer orchestration/state,
    overlay/sidebar/shell/presence, account/document/viewer templates and app-owned
    styles are extended. README/ARCHITECTURE are updated. The existing route-policy
    test includes the new blueprint; the C1 migration preservation test now compares
    original columns so the additive C2 color field is permitted. The synthetic PDF
    fixture gains an outline. Pre-existing viewer/report/test edits remain intact.

32. **Tests.** Final unit suite: **159 passed**, comprising 135 existing tests and
    24 C2 tests. The complete existing `tests/browser_sanity.py` Chrome/WebSocket
    regression passed with no uncaught browser exceptions: transport/auth, comments,
    drafts/conflicts, tombstones, resolution, zoom/rotation, offline socket fallback,
    reconnect, version isolation, carry/re-anchor/history, C1 and viewer layout.
    The focused `--comment-ui` run passed compact replies/expansion/shortcuts/mobile
    anchoring. The dedicated `--beta-c2` acceptance passed preferences persistence,
    owner section UI, visual boundary capture, response/realtime, personal scope,
    policy tightening while connected, palette, confirmed outline subset, multiple
    collaborators, zoom/spreads/rotation and responsive captures. `pip check` passed.
    The browser requires permitted local Chrome/loopback DevTools access; restricted
    sandbox transport failed, and approved runs outside that sandbox succeeded.

33. **Screenshot inspection.** Synthetic C2 screenshots and ten browser-rendered
    contact galleries are under ignored `tests/visual-artifacts/`. All ten galleries
    were opened and inspected, covering the requested marker/rail/spread distinctions,
    section prompt/feedback, shared/isolated UI, People, palette, one/two-page and
    multiple-user presence, comment modes, owner settings, Sections and edit mode.
    Representative spread, page-row and People captures were also opened individually.
    Inspection resulted in vertical People rows, a compact Save settings button and
    content-box-correct marker conversion. Page geometry assertions cover 50%, 100%,
    150%, 200% and 90° rotation; intra-spread boundaries retain both pages. Artifacts
    contain generated fixture PDFs and example-domain identities only, and remain
    ignored. Some feedback at page ends requires scrolling, as intended by the
    document-attached right rail; screenshot coverage is not a large-manuscript
    usability/performance benchmark.

34. **SQLite/migration verification.** Startup migration tests upgrade synthetic
    populated legacy databases, compare all original columns/rows, repeat startup,
    verify stable valid palette assignment and run `quick_check`, `integrity_check`
    and `foreign_key_check`. Results: `ok`, `ok`, and no foreign-key violations.
    Existing complete legacy comment/manual-migration history preservation tests
    continue to pass. No persistent user database or private manuscript is opened,
    migrated or rewritten by this task.

35. **Source/private-data checks.** A scoped scan of 46 changed/new source paths
    found no private-key headers, common provider secrets, actual-format Google
    client credentials, credential-bearing URLs, non-example reviewer email domains
    or runtime/private artifacts. Git whitespace checks pass with CRLF handling.
    Staged paths are empty. Git diffs for vendored PDF.js, historical SQL migration
    files, infrastructure, workflows and VSFF backend/frontend are empty. This is
    a scoped source review, not proof against every possible unknown secret format.

36. **Limitations/deferred work.** Canonical page/Y placement metadata comes from
    the authorized owner PDF.js viewer, matching the existing client-supplied
    geometry model; no new server-side PDF parser is introduced. Outline suggestions
    use page starts/ranges rather than semantic chapter matching; precise correction
    uses the visual editor. Sections are flat; deletion archives rather than removing
    historical feedback. One aggregate presence user shows only the latest reporting
    tab's one/two pages, not all tabs. Revocation pruning occurs before the next
    broadcast/check, not through a periodic eviction service, and previously received
    content cannot be withdrawn. Real Google, production, real Safari/iPad hardware,
    external avatar images, assistive-technology certification and large-document
    stress testing are not claimed. **Resilient pseudo-offline review remains deferred
    to a future dedicated architectural slice.** No IndexedDB/outbox, queued writes,
    service worker, PWA or persistent private PDF cache is added.

Everything remains local, unstaged and uncommitted. No SSH, deployment, push,
Google/Cloudflare operation or Apache/systemd/infrastructure change was performed.
