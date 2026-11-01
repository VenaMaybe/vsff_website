# Private Beta B2A — production deployment bundle report

Prepared locally November 1, 2026. No VPS access, SSH, deployment, provider/API
action, `/etc` or `/home/vsff` modification, credential change, staging, commit,
or push was performed. Commands in the operator runbook are instructions for a
later approved root session, not a record of executed server operations.

1. **Bundle structure.** Added nine public source artifacts under
   `ops/pdf_review/`: `README.md`, `vsff-review.service`,
   `vsff-review.env.example`, `apache-review-http.conf`,
   `apache-review-ssl.conf.example`, `sudoers-vsff-deploy.example`,
   `deploy-vsff.sh`, `backup_review.py`, and `renew-review-apache.sh`.

2. **Application changes.** Added a minimal GET/HEAD `/healthz` route and an
   exact endpoint-name exception in authentication middleware. Request routing
   errors/host validation still run first, and all other authorization is
   unchanged. No model, storage, migration SQL/engine, OIDC, cookie parser,
   Socket.IO, PDF, frontend, or VSFF application behavior was changed.

3. **Health check.** Constant plain-text `OK\n`, HTTP 200, no private-state I/O,
   no identity lookup or session creation, and existing private/no-store/security
   headers. Only GET/HEAD; unsafe methods and OPTIONS return 405. The deployment
   check uses loopback with `Host: review.venasff.com` and
   `X-Forwarded-Proto: https`, retries, rejects HTTP failure, and requires the
   exact `OK` body. This is process liveness after startup initialization, not a
   continuous database/blob/Google/CDN readiness check.

4. **Systemd design.** Separate `vsff-review.service` runs as `vsff:vsff` from
   `/srv/vsff_website/pdf_review`, reads `/etc/vsff-review.env`, and launches
   `.venv/bin/gunicorn --config gunicorn.conf.py wsgi:app`. The existing config
   enforces one `gthread` worker, 100 threads and default loopback 8002. A master
   plus one worker is expected. Process-local Socket.IO rooms/client state and
   presence prohibit multiple workers/instances. No dependency on the VSFF unit
   was added; the existing `vsff-api.service` remains unchanged.

5. **Hardening.** `NoNewPrivileges=true`, `ProtectSystem=strict`,
   `ProtectHome=read-only`, `PrivateTmp=true`,
   `ReadWritePaths=/var/lib/vsff-review`, `UMask=0077`, bytecode writes disabled,
   journal output, restart on failure with three-second delay and 45-second stop
   timeout. Home remains readable/executable for uv-managed Python; hiding it
   would break the interpreter path. Persistent writes are limited to review
   runtime storage, with private temporary files also writable. Networking stays
   available for OIDC and HTTP/WebSocket traffic. Each choice is documented in
   the runbook. Using the same UID is operational separation, not an OS-user
   isolation boundary from VSFF.

6. **Production environment.** The public template contains only placeholders
   for persistent `SECRET_KEY`, `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
   Settings are `PDF_REVIEW_ENV=production`,
   `PDF_REVIEW_DATA_DIR=/var/lib/vsff-review`,
   `PDF_REVIEW_SERVER_NAME=review.venasff.com`, `PDF_REVIEW_SCHEME=https`,
   `PDF_REVIEW_COOKIE_SECURE=1`, `PDF_REVIEW_PROXY_HOPS=1`,
   `PDF_REVIEW_HOST=127.0.0.1`, and `PDF_REVIEW_PORT=8002`. No database override is
   used. The proposed `true` cookie value in the request was corrected to `1`
   because that is the existing code's exact parser contract. The actual file
   will be root:root 0600; systemd reads it, and deployment never sources it.
   The runbook checks that placeholders were replaced without printing values.

7. **Runtime permissions.** `/var/lib/vsff-review`, `blobs/` and `backups/` will
   be `vsff:vsff` mode 0700. The database and WAL/SHM sidecars reside under that
   root; service umask restricts new files. No source-checkout writes are required
   during normal runtime, and Apache never maps this directory. Initial setup
   creates an empty runtime and stops if an existing database needs a separate
   migration plan. No real runtime material was included in this task.

8. **Python strategy.** Root instructions run uv as `vsff` to install managed
   Python 3.13 and create/update only review's `.venv`. Bounded direct
   `requirements.txt` dependencies are installed with `uv pip install`, followed
   by `uv pip check` and import checks. `uv pip sync` is deliberately not used on
   an incomplete direct-dependency requirements list. The backend retains its
   independent `uv sync --frozen` behavior. Existing review interpreters are not
   silently recreated. There is no frozen review dependency lock yet; satisfied
   packages are not all automatically upgraded.

9. **Apache HTTP.** A separate review-host bootstrap serves public ACME tokens
   and proxies `/healthz` only, returning 503 for other paths until TLS exists.
   This prevents HTTP sign-in/private-content exposure during setup. No existing
   VSFF vhost, `/api` routing, frontend path, or backend proxy was changed.

10. **HTTPS/WebSocket.** The final separate review vhost proxies the entire host
    to loopback 8002, preserves Host and overwrites forwarded scheme with HTTPS.
    Explicit `/socket.io/` WebSocket upgrade rewriting precedes the HTTP catch-all;
    ordinary Socket.IO polling remains HTTP. App auth/static/PDF.js/PDF/API routes
    all go through Flask. No static PDF/blob alias exists. The final port-80 vhost
    redirects to the fixed HTTPS host except ACME challenges. Review request
    access logs are suppressed to reduce OAuth query-code retention; warning/error
    logs remain. Existing private/no-store response headers are preserved.

11. **Cloudflare.** The runbook requires cache bypass for **the entire**
    `review.venasff.com` hostname, effective despite other rules/Workers, plus
    purging previously cached hostname content. Static and dynamic paths are both
    covered. It explains expected proxied DNS, optional temporary DNS-only setup,
    restoring proxying after origin TLS verification, Full (strict), WebSockets,
    and repeated edge-header/cache acceptance before real data. A first MISS is
    insufficient evidence of bypass; no HIT/STALE/UPDATING or Age is acceptable
    for authenticated private responses. No Cloudflare operations were performed.

12. **Let's Encrypt.** Separate `certbot certonly --webroot` issuance uses the
    dedicated ACME directory and exact `review.venasff.com` certificate name and
    domain. No expansion/replacement of apex/www certificates. Direct origin
    verification uses hostname/SNI and normal CA verification, without `curl -k`.
    The final HTTP challenge exception supports renewal; a root-owned hook reloads
    Apache only for the review lineage and only after configtest. Renewal dry-run
    and the existing renewal schedule are explicit operator checks. No Certbot
    command or certificate creation occurred locally.

13. **Google.** The exact production callback to register later is
    `https://review.venasff.com/auth/google/callback`; keep the existing
    `http://127.0.0.1:5000/auth/google/callback` development URI. No Google settings
    were touched. The runbook supports private allowlist administration through
    a root-launched, unprivileged transient systemd unit reading the protected
    environment, then real sign-in and synthetic-document acceptance.

14. **Sudoers.** Proposed complete target content permits exactly
    `/usr/bin/systemctl restart vsff-api` and
    `/usr/bin/systemctl restart vsff-review` as root, passwordless for `vsff`.
    No wildcard verbs/arguments or unrestricted shell/systemctl/sudo permission.
    Commands validate candidate and full policy with `visudo -cf` before/after
    installation; the old policy is backed up first.

15. **Proposed deploy behavior.** Keep strict Bash mode and the same nonblocking
    deployment lock. Fetch/reset main; retain existing backend dependency update,
    Node 24 frontend build and VSFF migration sequence under the existing VSFF
    environment in a subshell; independently prepare review dependencies; take
    a pre-upgrade SQLite snapshot without app import; restart and health-check
    VSFF; restart review and check canonical-host `/healthz`. Original comments
    and submissions checks remain. Existing builds use umask 022 for Apache
    readability; review preparation/backups use 077. Review secrets never enter
    build shells. The installed forced-command path and GitHub workflow remain
    unchanged; only a later operator installation activates this proposed script.

16. **Failure/partial deployment.** Lock/fetch/dependency/build/migration/backup
    failures abort before restarts. Failed VSFF health aborts before review
    restart; failed review health fails deployment after VSFF may already be
    running successfully. No automatic rollback is attempted. Source reset,
    in-place environment changes, frontend output and prior database migrations
    may already have happened. Review migrations execute at worker startup, each
    numbered migration transactionally with its history record; earlier completed
    migrations survive a later failure. The independent backup helper reads live
    WAL using SQLite's backup API before any new app initialization. It cannot
    promise zero-loss rollback for later writes before restart. Matching immutable
    blobs remain necessary for recovery.

17. **Rollback.** Before edits, the runbook takes root-only backups/absence
    records for deploy script, sudoers, review environment/unit/vhost/enablement
    link/renewal hook, and a safety copy of unchanged VSFF unit/Apache sites.
    It provides exact restoration/removal commands, validates sudoers and Apache,
    disables the new review service, and restores existing VSFF deployment
    independence. It does not overwrite all Apache sites or delete private
    runtime/certificates. Code/schema/virtual-environment/data rollback requires
    separate compatibility and recovery decisions; no automatic downgrades.

18. **Manual runbook.** [ops/pdf_review/README.md](../ops/pdf_review/README.md)
    is the exact root-session procedure, with all 12 requested phases: preflight,
    runtime, environment, Python, systemd/loopback, HTTP origin, TLS, public HTTPS,
    Google, security acceptance, deployment integration, and deferred private-data
    migration. It includes maintenance locking and recovery after a failed shell.
    The bundle must be separately released to origin/main before server use.

19. **Tests/validation.** From the packaged location,
    `python -m unittest discover -s tests -q`: **115 passed**, comprising the
    existing 109 plus three health security tests and three pre-upgrade backup
    tests. Backups include committed live WAL state, preserve the source schema,
    avoid creating a nonexistent source DB, and clean failed snapshots.
    `pip check`: **passed**.

    `python tests/browser_sanity.py`: **passed** using temporary synthetic PDFs,
    database, signed fixture sessions and browser profiles. Actual local
    WebSocket transport/authorization, presence, comments/replies, author controls,
    conflicts/drafts, tombstones, resolution, geometry/navigation, reconnect,
    version isolation, carry/re-anchor/history/skip/completion and refresh behavior
    passed with no uncaught browser exceptions. This local test used approved
    loopback access; it did not contact Google or production.

    Git Bash `bash -n`: **passed for both shell artifacts and all 13 Bash command
    blocks in the runbook**. An isolated local control-flow harness replaced all
    external deployment commands with stubs and redirected absolute paths to
    disposable fixtures; it passed **11 cases**: success, lock failure, fetch
    failure, backend dependency failure, frontend build failure, VSFF migration
    failure, review dependency failure, backup failure, VSFF health failure,
    review health failure and wrong review health body. It also checked ordering,
    canonical health headers and VSFF-environment separation. This validates
    shell control flow, not actual infrastructure operations.

    Static systemd/environment/Apache/sudoers structure checks passed, including
    LF-only bundle bytes, proxy ordering, fixed review certificate paths, no
    private filesystem aliases and exact restart grants. Git diff/whitespace and
    ignore checks passed. Native systemd/Apache/visudo/Certbot/Gunicorn-on-Linux,
    public HTTPS, Cloudflare and real Google acceptance were **not** executed on
    Windows; the runbook requires them on target. Existing backend/frontend and
    workflow changes are empty against HEAD. No claim of a Vite build or deployed
    service test is made.

20. **Secrets/private-data audit.** Final changed/new source was scanned for
    exact actual local credentials (values never printed), likely Google
    IDs/secrets, private keys, API/access/service tokens, credential-bearing URLs
    and non-example emails. It was compared with long text/non-example emails
    from local review databases/backups read through immutable read-only SQLite
    connections. No matches were found. Changed/source-tracked paths contain no
    environment file with values, PDF, database, blob, backup, log, credential key,
    browser profile or generated cache. Existing local `.env` files remain
    ignored and untouched. No private data or credential was staged or copied
    into the bundle. These scans complement source review; they are not a proof
    against every conceivable unrecognized secret format.

21. **Files changed.** Six existing files changed: root `.gitignore` and
    `README.md`, `pdf_review/README.md`, `pdf_review/ARCHITECTURE.md`,
    `pdf_review/review/__init__.py`, and `pdf_review/review/auth.py`. Thirteen new
    files: root `.gitattributes`, nine bundle artifacts, two test modules, and
    this report. Root ignore rules now cover filled bundle environments and
    common private runtime artifacts; `.gitattributes` keeps all bundle text LF
    on Windows. Existing backend, frontend, migrations, workflow, production
    infrastructure, credentials and original standalone project were not changed.
    All changes remain unstaged/uncommitted.

22. **Deviations/limits.** Added a standalone pre-upgrade backup helper because
    the ordinary backup CLI initializes/migrates the app before backing up. Added
    a certificate-specific renewal hook because webroot issuance alone does not
    reload Apache with a renewed certificate. Used `1` for secure cookies to
    preserve the real parser contract. Restricted HTTP bootstrap to ACME/health
    while HTTPS owns the full application. No explicit migration CLI was needed;
    single-worker restart uses the existing migration engine. No new service
    account or review dependency lock was introduced. Native Linux/provider
    validation and all private-data migration remain later operator work.
