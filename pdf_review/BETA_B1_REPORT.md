# Private Beta B1 packaging report

Completed locally November 1, 2026. Source preparation only. Nothing was staged,
committed, pushed, deployed, or changed on the VPS.

1. **Structure before and after.** The existing public repository contained
   `.github/`, `backend/`, `frontend/`, and root `.gitignore`. It now also contains
   sibling `pdf_review/` and a root README. The standalone PDF Review project is
   unchanged. PDF Review remains a separate service, application, datastore,
   session domain, dependency environment, and migration architecture.

2. **Transferred files.** An explicit source selection transferred 472 files:
   seven top-level source/configuration/documentation files, 16 files under
   `review/`, eight templates, 431 static assets, and ten test files. These
   include all application Python, numbered SQL migrations, app-owned frontend
   modules, offline public PDF.js/Socket.IO dependencies, licenses, and tests.
   Vendored files total 19,714,108 bytes (about 18.8 MiB); retained vendor bytes
   match the standalone source exactly. They are library distributions, fonts,
   maps, localization, images, color profiles, and WebAssembly, not browser caches.
   New files are `review/backup.py`, `wsgi.py`, `gunicorn.conf.py`,
   `tests/test_packaging.py`, and this report. Total proposed additions: 477 files
   under `pdf_review/`, plus the root README.

3. **Excluded files.** No `.env`, OAuth client JSON, local credentials, session
   secret, standalone `data/` directory, SQLite database/sidecar, manuscript PDF,
   blob, backup, baseline dump, verification dump, log, virtual environment,
   Python cache, browser profile, upload, or editor/OS temporary file was copied.
   The unused public PDF.js demonstration PDF was also omitted. Fresh local
   dependencies were installed into the new ignored `.venv`; it is not a source
   addition and was not copied from the standalone project.

4. **Secret and private-content audit.** Before transfer, selected bytes were
   compared against actual local credential values without displaying them.
   Scans included Google client ID/secret formats, private keys, access/API keys,
   service tokens, credential-bearing URLs, and application/test email addresses.
   Runtime databases and backups were opened read-only with immutable SQLite
   connections to compare long private text and non-example emails against the
   proposed public source. No matches were found. The selected source was also
   reviewed for credential configuration, generated PDF fixtures, selectors,
   comments, and reviewer fixtures. Personal fixture display names were replaced
   with `ReviewerAlpha`/`ReviewerBeta`, identifiers with `alpha`/`beta`, and the
   generic book title with `Synthetic Document`. All fixture emails now use
   example domains. The historical report's private blob fingerprint and backup
   identifiers were removed before copying. Only test secrets and placeholder
   configuration remain; they provide no access to any real service. Final scans
   cover the actual nonignored additions, including this report. Pattern scans
   and exact comparisons are evidence, not a guarantee against every possible
   unrecognized secret format.

5. **Ignore rules.** Root and service ignore files protect `.env` variants,
   virtual environments, caches, `data/`, `instance/`, nested blobs/backups,
   SQLite files/sidecars, database files, PDFs, logs, temporary files, browser
   profiles, credential JSON filenames, PEM/key files, and dumps. Existing root
   environment rules retain the `.env.example` exception. Representative paths
   were checked with `git check-ignore`; legitimate source SQL/vendor files
   remain visible. The original root ignore file now ends with a newline.

6. **Runtime directory design.** `PDF_REVIEW_DATA_DIR` is the common private
   runtime root. Development defaults to `pdf_review/data/`, resolved from the
   project directory rather than the shell working directory. Absolute external
   paths work on Windows and Linux. Factory configuration also accepts `DATA_DIR`;
   existing explicit `DATABASE` and `STORAGE_ROOT` overrides remain compatible.
   No original data is automatically discovered, moved, or deleted.

7. **SQLite, blobs, backups.** Defaults are `<data-dir>/pdf_review.sqlite3`,
   `<data-dir>/blobs/<sha256>.pdf`, and `<data-dir>/backups/`.
   `PDF_REVIEW_DATABASE` can override only the SQLite file. Factory callers can
   override `BACKUP_DIR`. Canonical database blob paths remain `blobs/<sha256>.pdf`;
   SHA-256 identity, non-overwrite publication, integrity verification, and
   authorization before bytes/Range responses are unchanged. `backup-database`
   creates a consistent uniquely named SQLite snapshot using SQLite's backup API.
   This formalizes the previous manually invoked backup API; the standalone
   source had no reusable backup CLI. Blobs must be retained separately for full
   recovery. Actual production locations, scheduling, retention, and off-host
   backup policy remain deferred.

8. **Production dependency and entrypoint.** `requirements.txt` adds
   `simple-websocket>=1.1,<2` explicitly and `gunicorn>=26,<27` on non-Windows
   platforms. Linux launch from `pdf_review/`:
   `gunicorn --config gunicorn.conf.py wsgi:app`. The entrypoint uses the existing
   factory and Flask-SocketIO WSGI middleware, does not run the development
   server or load local `.env`, and requires production mode plus absolute runtime
   paths outside the repository. Existing credential/HTTPS/host/session checks
   still run. Gunicorn configuration defaults to loopback port 8002, 100 threads,
   and one `gthread` worker. Bind host/port are configurable.

9. **Single-process rationale.** Socket.IO client/room state and presence
   aggregation are in-memory and app-local. Multiple threads in one process are
   supported; multiple workers or independent instances are not. A startup hook
   rejects multiple workers and incompatible worker settings. No broker,
   eventlet, horizontal scaling, shared presence store, or systemd unit was added.

10. **Proxy and public origin.** Existing ProxyFix behavior is preserved: trust
    zero hops by default; one optional hop trusts forwarded scheme only, with
    forwarded host/address/port/prefix trust disabled. Explicit server name,
    scheme, trusted hosts, and Socket.IO same-origin checks remain. The future
    public hostname is environment configuration, not an application constant.
    HTTPS callback generation, Secure/HttpOnly/SameSite cookies, auth, verified
    email allowlisting, ACLs, CSRF, and protected PDF/Range handling are preserved.
    The dedicated host-only cookie name is now `pdf_review_session`, isolated
    from VSFF; old development cookies require a new sign-in in the packaged app.

11. **Environment.** Production expects `PDF_REVIEW_ENV=production`, absolute
    external `PDF_REVIEW_DATA_DIR`, persistent random `SECRET_KEY` of at least
    32 characters, private `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, and
    `PDF_REVIEW_SERVER_NAME`. Production defaults are HTTPS and Secure cookies;
    optional settings are `PDF_REVIEW_SCHEME`, `PDF_REVIEW_COOKIE_SECURE`,
    `PDF_REVIEW_PROXY_HOPS`, `PDF_REVIEW_DATABASE`, `PDF_REVIEW_HOST`, and
    `PDF_REVIEW_PORT`. The latter defaults to 5000 in the development launcher and
    8002 in Gunicorn configuration. `.env.example` contains placeholders only.
    A future protected supervisor environment, conceptually `/etc/vsff-review.env`,
    is not created by this task. Google development setup and exact loopback
    callback instructions remain in the README.

12. **Existing VSFF files changed.** Root `.gitignore` gained private artifact
    protections, and a new root README explains service separation. Existing
    `backend/`, `frontend/`, and `.github/` tracked contents are byte-for-byte
    unchanged compared with HEAD. There are no application, API, Vue router,
    model, session, socket, or deployment-workflow changes to the VSFF site.

13. **PDF Review adaptations.** `review/__init__.py` derives runtime paths,
    registers backup CLI, and assigns an independent cookie name; `app.py`
    supports development host/port overrides. Requirements, example environment,
    ignore rules, README, and architecture documentation describe the package.
    Historical report and test data were sanitized for public use. The browser
    harness follows the dedicated cookie name and adds actual WebSocket transport
    acceptance. New production entrypoint/configuration, backup CLI, and six
    packaging tests cover the new behavior. The migration engine and all SQL,
    service logic, authorization implementation, app-owned JavaScript, templates,
    and retained vendor files remain unchanged.

14. **Validation.** From the new directory and its own virtual environment:
    `python -m unittest discover -s tests -q`: **109 passed** (103 preserved
    regression/security tests plus six packaging tests). Coverage includes
    immutable storage, anchors, threads, revisions, realtime, presence, migrations,
    OIDC validation with stubbed provider transport, allowlist, ACLs, CSRF, PDF and
    Range authorization, sockets, and proxy/cookie/host checks. New tests exercise
    external paths, actual PDF import/integrity, consistent backup contents,
    production entrypoint initialization without a dev-server call, and Gunicorn
    bind/worker guards. `pip check`: **passed**.

    `python tests/browser_sanity.py`: **passed** with temporary generated PDFs,
    database, synthetic signed sessions, and headless Chrome. Verified actual
    WebSocket-only transport, anonymous rejection, authorized room join, presence,
    multi-account collaboration, author controls, edit conflicts/drafts,
    tombstones, resolution history, centered navigation, zoom/rotation geometry,
    offline HTTP/reconnect, version-room isolation, carry-forward/re-anchor,
    historical preservation, skip/completion, refresh coordination, and no
    uncaught browser exceptions. Sandbox restrictions initially prevented local
    networking; the completed local browser run used approved loopback access.

    The real `app.py` also launched successfully with a temporary external runtime
    directory and configured temporary loopback port, returned HTTP 200 for login,
    and was stopped. Production `wsgi:app` initialized with synthetic production
    configuration and the threading WebSocket driver. Gunicorn 26's configuration
    API was checked against its wheel source; an actual Gunicorn worker was not
    run on Windows and needs Linux acceptance later.

    VSFF backend Python files compiled successfully for syntax, and Git confirms
    existing backend/frontend/workflow bytes unchanged. No existing backend or
    frontend automated tests were found. A Vite build and VSFF runtime/dependency
    check were not run: Node/npm and the backend's required Python 3.13 runtime
    are unavailable here. These are explicit validation limits.

15. **Private manuscript/reviewer data in Git tree.** None. No PDF, database,
    backup, baseline, real allowlist/email, manuscript prose, or reviewer content
    appears among proposed additions. Original runtime files still match their
    pre-task SHA-256 snapshot; the snapshot stays outside this repository.

16. **Credentials in Git tree.** None found. No real credentials were copied,
    staged, or committed. Exact local credential comparisons and likely-secret
    scans passed before copying and again on final proposed additions. `.env`
    was read only by the local audit to compare values without exposing them.

17. **Git status.** Initially clean. Final intended summary: modified root
    `.gitignore`, untracked root `README.md`, untracked `pdf_review/`. Nothing is
    staged. Ignored local dependencies/caches are absent from the proposed source
    set. All untracked files belong to the documented source categories. No
    commit, push, remote access, or deployment was performed.

18. **Exact local setup.** Run in PowerShell:

    ```powershell
    cd "C:\vena\Obsidian\writing\Code\vsff_website\pdf_review"
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    Copy-Item .env.example .env
    # Edit .env: persistent random SECRET_KEY and your Google development credentials.
    # Optionally set PDF_REVIEW_DATA_DIR to an absolute private development folder.
    python app.py
    ```

    Open `http://127.0.0.1:5000`. Register the exact Google development callback
    `http://127.0.0.1:5000/auth/google/callback`. Follow README allowlist/identity
    and document-grant setup; no test identity bypass is installed. No Vue or
    VSFF backend is needed. On this workspace the ignored environment is already
    installed, while `.env` is deliberately absent. Existing standalone private
    data and credentials have not been copied; a fresh packaged app starts empty.

19. **Dedicated VPS deployment slice.** Decide/prepare isolated runtime ownership,
    install Linux dependencies, provide protected production environment and
    credentials, test Gunicorn/WebSocket behavior, prepare the separate service
    and reverse-proxy virtual host, configure DNS/TLS and exact Google production
    callback, deliberately transfer approved private data if needed, verify
    migration/integrity and real Google/HTTPS acceptance, choose backup/restore
    policy, and deliberately extend deployment logic/permissions and health checks.
    Do not infer that the unchanged existing deployment workflow deploys PDF Review.

20. **Deviations and limits.** The unused public PDF.js sample PDF was omitted to
    keep all PDF files out of proposed additions; retained library files are
    unchanged. A small backup CLI was added because prior backups were manual
    API invocations. Fixture cookies were adapted to the dedicated session name.
    Windows cannot validate an actual Linux Gunicorn worker here, and absent
    Node/npm/Python 3.13 limit VSFF executable checks as described above. Real
    Google login was not attempted. No infrastructure configuration or deployment
    behavior was modified. Local audit scripts and private hash snapshots live
    outside the public repository and are not proposed additions.
