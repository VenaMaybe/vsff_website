# Viewer and application refinement — local only

This continues the successful viewer redesign. The original architecture audit is
retained in [VIEWER_REDESIGN_REPORT.md](VIEWER_REDESIGN_REPORT.md); this report is
the current contract for the refinements below. Existing C1 and redesign changes
were already unstaged at the beginning of this pass and have been retained.

1. **Architecture preserved.** The independent viewer workspace, app-owned PDF.js
   bootstrap, canonical selection/anchor geometry, existing thread presentation,
   atomic thread API, realtime coordinator and presence remain. No rendering,
   search-matching, authentication or annotation service was replaced.

2. **Adjacent right rail in the document workspace.** Comments sit 6px beyond
   their owning page/spread's outer box, rather than at the far workspace edge.
   Both pages of a spread use its right edge. The full-width native PDF scrollbar
   surrounds pages and comments; the document stage reserves room internally.
   Cards translate with both scroll axes and wheel scrolling over cards scrolls
   that same document. Horizontal document mode places comments after the page row.
   There are no left rails or connector lines.

3. **Comment focus without PDF movement.** The page/visual-y/thread-ID order
   remains deterministic. With no active item, cards pack down with a 6px gap
   (3px for markers). Selecting a thread centers its card at its canonical
   highlight Y; neighbors pack upward and downward around that fixed item.
   The selection composer uses the same packing rule. Opening/inserting comments
   does not scroll the document. Width is held while opening a comment/composer
   so reserving room does not recenter the PDF. Explicit navigation to an off-screen
   target still reveals its page. Scroll, zoom and rotation retain canonical geometry.

4. **CSS architecture retained.** `app.css` still imports `tokens.css`, `base.css`
   and `account.css`; viewer-specific ownership remains in `viewer.css`,
   `comments.css` and `pdfjs.css`. No parallel style layer was added. Shared toolbar
   and menu rules moved from viewer-only ownership into the existing `base.css`.
   Remaining viewer rules own only document workspace and review presentation.

5. **Shared shell/primitives.** `.app-toolbar`, grouped flat controls, system
   typography, compact fields, thin borders, small section headings, quiet metadata,
   role badges and canonical menus apply across server-rendered pages. Default
   application text is 13px, controls/menu rows 12px, metadata 11px; fields and menu
   rows are 30px, with 32px menu/touch rows on phone. Page headings are 20px rather
   than the previous large editorial headings. Viewer desktop height remains
   approximately 40-43px. `viewer.html` was not forced into `base.html`.

6. **Canonical menus.** Native disclosure elements with `.toolbar-menu` and
   `.toolbar-popover` share borders, surface, padding, row sizing, hover/focus,
   separators, submenu arrows and checkmarks. `menus.js` positions them against
   their triggers, flips submenus left, clamps to the viewport and limits height.
   Escape closes the current submenu or top menu and returns focus; outside clicks
   (including inside the PDF iframe) dismiss menus. Arrow keys/Home/End navigate
   menu rows; right opens submenus and left returns to the parent. No component
   framework or dependency was introduced. Plain inline data-entry selects remain
   native fields, rather than being converted indiscriminately into menus.

7. **Scrolling submenu.** Page, vertical, horizontal and wrapped scrolling are
   radio-like menu rows. Selecting one updates the existing PDFViewer `scrollMode`;
   native mode events synchronize the checkmark. No embedded select remains.

8. **Spreads submenu.** No/odd/even spreads use the same submenu/radio treatment
   and the existing PDFViewer `spreadMode`. The native rendering behavior remains.

9. **Search integration.** The actual native find field, result count, previous/
   next buttons, option checkboxes and message node remain in the PDF.js iframe
   with their original listeners and state. The app arranges them into a compact
   header-attached search surface, adds a close button, and restyles them using
   shared tokens. Ctrl/Command+F, typing, native counts/highlights, next/previous,
   Enter/Shift+Enter and Escape remain native. Options expand in a small disclosure.
   There is no duplicate parent query/matching state. The app explicitly overrides
   PDF.js's zero-toolbar-height rule on find-bar child rows so they are not clipped.

10. **Native page spacing.** The custom visible 1px page border and 14px
    bottom-margin override were removed. The vendored PDF.js defaults now control
    vertical gaps and horizontal spread gaps, including its transparent 9px page
    border, -8px bottom margin and -3.5px spread-page side margins. The transparent
    border is spacing, with no visible outline. Canonical anchor placement uses
    the content box inside that border.

11. **Minimized markers.** Each thread has a real compact button with an original
    outline comment icon, an optional reply/comment count, a tooltip and an
    accessible thread/page name. Full card DOM remains separate and hidden for
    inactive threads; no full card is squeezed into a miniature rectangle.
    Canonical anchor Y and the same deterministic pass position the markers.
    The rail reserves **48px**, including while inspecting one active full card.
    Clicking a marker activates/navigates that thread without changing global
    Minimized mode. Its full card opens to the right of its still-visible marker; Close
    returns it to a marker. Other markers remain reachable and do not overlap.

12. **Expanded/Hidden.** Approved compact expanded cards are retained, now always
    on the right. Hidden renders neither cards nor markers and reserves zero width;
    the document recenters. Contextual commenting still works in Hidden mode.
    Empty reviews reserve zero width. The composer and atomic canonical payload
    workflow are retained. Comments now provides Expanded/Minimized/Hidden/Mobile and
    Open only/All checkmarked groups in the canonical menu. The separate filter
    dropdown was removed. Presence remains a compact count and named popover,
    and anchor diagnostics still require `?debug=anchors`.

13. **Dashboard.** The previous document-card grid becomes compact full-width
    document rows through shared CSS, retaining existing title/version-count/
    creation metadata and document creation functionality. No backend query was
    broadened simply to add decorative fields.

14. **Document page.** Compact versions, import controls, metadata and integrity
    controls use shared styling. A canonical Document actions menu groups owner
    access management and migration/history navigation. Authorization conditionals
    and POST integrity/import operations are retained.

15. **Account.** The profile becomes a compact inspector with verified identity,
    status and display-name form. Owned/shared documents use compact rows and
    small role badges. No profile semantics or presentation-history rules changed.

16. **Admin.** Beta access, users and administrators use compact management rows.
    Per-entry Actions uses the same menu grammar; removal has a deliberate nested
    confirmation surface retaining the established-account required checkbox and
    explanatory text. Grant/revoke/allow/disable/remove remain existing CSRF POSTs.

17. **Access management.** Grant, role change and revoke remain compact inspector
    controls. Existing-user restrictions, owner/reviewer/viewer distinctions,
    final-owner safety and authorization semantics remain unchanged.

18. **Account menu.** `_account_menu.html` is shared by both shells. It shows the
    current display name and verified email, Account, conditional explicit-admin
    navigation, and logout. Logout remains a POST form with CSRF, never a GET.
    Document/admin actions and future overflow menus use the same canonical CSS.

19. **Responsive behavior.** Expanded and Minimized retain the adjacent document
    rail, with no separate drawer. When pages plus comments exceed the viewport,
    the native horizontal scrollbar reaches the whole workspace. Selecting a
    visible highlight moves comments without scrolling the PDF. Minimized retains
    its 48px reservation and opens the active card to the marker's right. Mobile
    becomes active at widths below 750px and puts the active card over the PDF.
    Hidden reserves zero width. Management forms wrap; menus clamp to the viewport.

20. **Performance.** Scroll translates cached review positions; full geometry is
    still coalesced through requestAnimationFrame and ResizeObserver. Removed
    observed elements are unobserved. A marker map avoids a per-thread DOM search.
    No scroll listener per thread, mousemove layout loop or second anchor system
    was added. Native PDF.js retains search/rendering/navigation work.

21. **Files changed this pass.** `templates/base.html`, `viewer.html`,
    `document.html`, `admin.html`; new `templates/_account_menu.html`;
    `static/styles/{tokens,base,account,viewer,pdfjs}.css`;
    `static/review/viewer_shell.js`, `anchors.js`, `thread_sidebar.js`; new
    `static/review/menus.js`; `tests/viewer_acceptance.py`,
    `tests/browser_sanity.py`; `README.md`, `ARCHITECTURE.md`,
    `VIEWER_REDESIGN_REPORT.md`, and this report. Other pre-existing C1/redesign
    working-tree changes remain intact. No vendor or backend file changed this pass.

22. **Tests.** Full project unit suite: **135 passed**. `pip check`: **No broken
    requirements found**. The existing synthetic Chrome/WebSocket harness passes,
    extended rather than duplicated. It exercises native parent controls, menu
    pointer/keyboard interaction, checkmarks, Escape/outside click, viewport bounds,
    native search next/previous/Enter/Shift+Enter/close, selection and 50/100/150/200%
    zoom, 90° rotation, single/continuous/page-scroll and odd/even/cover modes,
    marker collision/activation/narrow width and right-only placement. The obsolete
    opposing outside-rail assertion was replaced. Existing realtime, reconnect,
    room isolation, migrations, stale edits and C1 workflows continue to pass.

23. **Screenshot inspection.** Ignored synthetic screenshots are regenerated at
    1440×900, 1280×800, 1024×768, 768×1024 and 390×844 for expanded/minimized/hidden,
    odd/even spreads, search, View/Scrolling/Spreads/Comments/account menus and the
    dashboard/document/account/access/admin/history surfaces. Login and minimized
    active-card examples are included. Browser-rendered inspection galleries collect
    those images for comparison; selected images were also opened at full size.
    Visual review checks right placement, small markers, separation of sheets,
    menu bounds/text, search row sizing, toolbar density and shared page styling.
    Source contains no screenshot/private manuscript data.

24. **Security/regressions.** No backend/database migration, endpoint, ACL, OIDC,
    allowlist, admin policy, CSRF, GET/HEAD/Range authorization, immutable storage,
    canonical coordinate schema, exact-version rule, revision/resolve/migration
    service or Socket.IO authorization changed. Existing account/admin/owner
    workflow checks pass. Browser fixtures use disposable synthetic identities,
    PDFs, SQLite and offline provider-boundary sessions. Real production/OIDC
    accounts are not used. Vendored PDF.js files remain unchanged.

25. **Privacy/local-only checks.** Changed/new source is scanned for private-key
    headers, common provider tokens, credential URLs, real Google client IDs,
    non-example email addresses and accidental private/runtime artifacts. Git
    whitespace/diff review passes; the scoped scan found no findings. Vendor/
    infrastructure changes and staged paths are empty.
    Screenshots and inspection galleries stay under the existing ignored directory.
    No staging, commit, push, SSH, deployment, production, Google, Cloudflare or
    infrastructure action was performed.

26. **Limits.** Dense neighbors may move outside the viewport while the active
    card stays aligned with its highlight. Clicking another highlight brings that
    comment into alignment. Very tall active cards scroll internally. Minimized
    cards open rightward and may require horizontal scrolling on narrow viewports;
    Mobile mode offers a popup over the document instead.
    Page-width zoom fits the PDF itself; the shared horizontal scrollbar reaches
    adjacent comments when the combined width exceeds the viewport.
    On very narrow screens a flipped submenu may overlap its parent while remaining
    within the viewport. Native PDF.js preferences remain disabled as before; modes
    are session-local. Multi-page thread cards still use the first anchor segment;
    all canonical highlights remain. Testing uses Chrome viewport emulation and
    synthetic PDFs, not real iPad/Safari hardware, a screen-reader audit, large-document
    performance benchmarking or production deployment.

New PDF Review server-rendered pages should use the shared application shell,
tokens and control/menu primitives rather than introducing one-off visual systems.

27. **Follow-up controls and verification.** Open PDF is at the outer top right
    of each version card, with Verify integrity below. Native file input buttons
    use shared typography, borders and hover styling. Browser checks verify these
    controls, adjacent spread placement inside the scrollbar, native page spacing,
    minimized/expanded behavior, zoom/rotation, selection, and collaboration.

28. **Keyboard, focused styling and Mobile mode.** Escape deselects the active
    thread and closes a selection composer from either the parent or PDF iframe.
    Enter or Ctrl+Alt+M (Command+Option+M) after selecting PDF text opens the
    composer; editable fields retain normal typing. Ctrl/Command+Enter submits
    the composer. Inactive cards use a background close to the workspace; active
    cards keep #f7faf8 and gain a shadow. Mobile is a fourth explicit menu choice
    and becomes active on entering a viewport below 750px wide. On leaving that
    breakpoint, the previous desktop mode returns. It retains marker buttons and
    displays the active card/composer over the page just below the highlight,
    kept directly below the highlight even as it scrolls beyond the viewport. The PDF does not scroll to
    reveal the popup. Browser coverage includes stationary dense selection and
    insertion, both creation shortcuts, Escape, rightward expansion and Mobile.

29. **Motion and mobile refinement.** Switching comments animates their vertical
    rearrangement over 160ms, including neighboring cards, while PDF coordinates
    stay unchanged. Motion resumes across canonical sidebar rerenders and honors
    reduced-motion preferences. The composer opens with a 130ms fade/slide.
    Mobile popups are at most 280px wide, leave more space at narrow widths, and
    remain 8px below the highlight without vertical viewport clamping. The mobile
    header uses a fixed top grid row for back/document/View/Comments/live/account;
    long document and account labels truncate. PDF controls occupy the next row.
    Focused browser checks cover sliding neighbors, stationary PDF scrolling,
    offscreen mobile anchoring, reduced motion and 280/320/390/480/749px headers.

30. **Compact threads and consistent header controls.** Narrow headers retain
    the desktop menu font, padding, gap, alignment and control height. The first
    row stays together; only available label width changes, and PDF controls
    remain on the second row. Reply opens its textarea on demand. Comment count,
    Resolve/Reopen and Reply/Post reply share one footer row. Long threads show
    their root and two latest comments until Show all is chosen; Show less restores
    that preview. Click-away in either the parent UI or PDF deselects a thread,
    while clicks on thread controls/highlights preserve it. Ctrl+Shift+Enter posts
    the active new-comment, reply or edit form. Hidden reply drafts survive closing.
    Focused browser checks compare header styles at 750px and 749px, exercise
    expansion/collapse, footer alignment, click-away in both documents, keyboard
    submission for all three form types, and existing motion/mobile behavior.

31. **750px breakpoint and inline expansion.** Two-row/mobile presentation now
    applies strictly below 750px. View, Comments, live status and the account
    control form a right-aligned group with their desktop styling. A collapsed
    thread's Show all button sits immediately after its root comment, before the
    two latest replies. Expanded threads retain Show less at the end. Focused
    browser checks cover both sides of the breakpoint, right alignment down to
    280px and the expansion button's placement.
