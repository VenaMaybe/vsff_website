# PDF Review production deployment bundle — Private Beta B2A

This is a proposed, version-controlled operator bundle. **Nothing in this slice
has been installed or run on the VPS.** Execute the commands below only during a
later approved maintenance session as root on the VPS. Do not run this runbook on
the Windows development machine. No SSH command, key, credential, manuscript,
database, or production environment file is supplied here.

Current application update: migration **14** adds Trusted Users/invitations.
Migration **15** additionally records a document's main version. Existing documents
default to the newest active version; PDF/version bytes and identities are unchanged.
Use the existing pre-start SQLite backup and single-worker migration flow.
It preserves identities, content and grants. If exactly one site admin exists,
historical invitations are attributed to that admin; otherwise use the admin
directory's explicit attribution action for unassigned historical records.
Old allowlist/last-login dates are labelled as access records/joined-by bounds.
No new environment variable, OAuth scope, email provider or proxy rule is needed.
After deploying, check Admin > Trusted Users, Beta members, Invitations and
Access history with synthetic identities first. Expiration is enforced on
redemption without a scheduler; optionally run `review_admin expire-invitations`
using the existing protected environment wrapper to record periodic expiry events.

The reviewed bundle and `/healthz` application change must first be published to
`origin/main` through the normal review/release process. This task does not push
them. Initial installation requires a root session; the forced deployment SSH
key remains restricted to its existing `/home/vsff/deploy-vsff.sh` command.

## Files and fixed production boundaries

```text
ops/pdf_review/
  README.md                         this root-session runbook
  vsff-review.service               separate Gunicorn/systemd service
  vsff-review.env.example            placeholders; actual file stays in /etc
  apache-review-http.conf            ACME/health-only HTTP bootstrap
  apache-review-ssl.conf.example     final HTTPS proxy + HTTP redirect/ACME
  sudoers-vsff-deploy.example        exactly two permitted restart commands
  deploy-vsff.sh                     proposed replacement, not a live deploy action
  backup_review.py                   pre-migration SQLite API snapshot, no app import
  renew-review-apache.sh             certificate-specific root renewal reload hook
```

Known target: Ubuntu 22.04.5, `srv445818`, origin `85.31.233.18`, public repository
`/srv/vsff_website` owned by `vsff:vsff`, branch `main`, remote
`https://github.com/VenaMaybe/vsff_website.git`. Existing VSFF remains on loopback
8001 with its current service, environment, SQLAlchemy schema, Vue build, hosts,
and `/api/` + `/socket.io/` routing. Do not edit its unit or virtual hosts.

Review owns **all of `review.venasff.com`**, proxies to loopback 8002, runs one
Gunicorn `gthread` worker with 100 threads, and uses its own host-only session
cookie and datastore. No Redis, shared database, broker, or additional instance.
One master process plus one worker is expected; threads are not worker processes.

## Phase 1 — preflight, maintenance lock, and originals

Use one root **Bash** session throughout these phases. Arrange a maintenance
window with no concurrent deployments or pushes. Holding the existing lock also
causes GitHub's forced deploy command to fail promptly rather than race this work.

```bash
set -Eeuo pipefail
umask 077
test "$(id -u)" -eq 0
REPO_DIR=/srv/vsff_website
BUNDLE="$REPO_DIR/ops/pdf_review"
UV=/home/vsff/.local/bin/uv
ROLLBACK_DIR=$(mktemp -d /root/vsff-review-b2a.XXXXXXXX)
chmod 0700 "$ROLLBACK_DIR"
mkdir -m 0700 "$ROLLBACK_DIR/files"
: >"$ROLLBACK_DIR/absent.txt"
printf 'Private rollback directory: %s\n' "$ROLLBACK_DIR"

# Create/open the same lock without replacing its inode or making it root-owned.
sudo -u vsff -H touch /home/vsff/.deploy-vsff.lock
exec 9>>/home/vsff/.deploy-vsff.lock
flock -n 9

getent passwd vsff
id vsff
test -d "$REPO_DIR/.git"
test "$(sudo -u vsff -H git -C "$REPO_DIR" branch --show-current)" = main
sudo -u vsff -H git -C "$REPO_DIR" status --short
sudo -u vsff -H git -C "$REPO_DIR" diff --quiet
sudo -u vsff -H git -C "$REPO_DIR" diff --cached --quiet
test -z "$(sudo -u vsff -H git -C "$REPO_DIR" ls-files --others --exclude-standard)"
sudo -u vsff -H git -C "$REPO_DIR" rev-parse HEAD >"$ROLLBACK_DIR/repository-before.txt"

systemctl is-active --quiet vsff-api
ss -ltnp '( sport = :8001 )'
if ss -H -ltn '( sport = :8002 )' | grep -q .; then
    echo 'Port 8002 is already in use; stop and identify it before proceeding.' >&2
    exit 1
fi
python3 --version
sudo -u vsff -H "$UV" --version
sudo -u vsff -H "$UV" python list --only-installed
command -v curl flock visudo systemd-analyze certbot
certbot --version
for module in headers proxy proxy_http proxy_wstunnel rewrite ssl; do
    apache2ctl -M 2>/dev/null | grep -q " ${module}_module "
done
test -r /etc/letsencrypt/options-ssl-apache.conf
apache2ctl configtest
apache2ctl -S >"$ROLLBACK_DIR/apache-vhosts-before.txt" 2>&1

check_vsff() {
    curl --fail --silent --show-error --max-time 20 http://127.0.0.1:8001/api/comments >/dev/null
    curl --fail --silent --show-error --max-time 20 http://127.0.0.1:8001/api/submissions >/dev/null
    curl --fail --silent --show-error --max-time 20 https://venasff.com/ >/dev/null
    curl --fail --silent --show-error --max-time 20 https://www.venasff.com/ >/dev/null
}
check_vsff

# Save every infrastructure file that this runbook may replace, privately.
# cp -a preserves existing metadata/symlinks. Record absence for clean removal.
for target in \
    /home/vsff/deploy-vsff.sh \
    /etc/sudoers.d/vsff-deploy \
    /etc/vsff-review.env \
    /etc/systemd/system/vsff-review.service \
    /etc/systemd/system/vsff-api.service \
    /etc/apache2/sites-available/review.venasff.com.conf \
    /etc/apache2/sites-enabled/review.venasff.com.conf \
    /etc/letsencrypt/renewal-hooks/deploy/reload-vsff-review-apache.sh; do
    if [[ -e "$target" || -L "$target" ]]; then
        cp -a --parents "$target" "$ROLLBACK_DIR/files/"
    else
        printf '%s\n' "$target" >>"$ROLLBACK_DIR/absent.txt"
    fi
done
systemctl is-enabled vsff-review >"$ROLLBACK_DIR/review-enabled-before.txt" 2>&1 || true
cp -a /etc/apache2/sites-available "$ROLLBACK_DIR/apache-sites-available-before"
cp -a /etc/apache2/sites-enabled "$ROLLBACK_DIR/apache-sites-enabled-before"

# Never use ignored checkout .env files for production review configuration.
test ! -e "$REPO_DIR/pdf_review/.env"
test ! -e "$REPO_DIR/pdf_review/data/pdf_review.sqlite3"
```

Stop on failed preflight; do not work around occupied ports or overwrite unknown
review infrastructure. Saved originals may contain secrets: keep the rollback
directory root-only, outside Git, and do not paste its contents into reports.

If the reviewed bundle is not yet checked out, update the **clean** checkout under
the held lock (this intentionally resets tracked files to the reviewed main):

```bash
sudo -u vsff -H git -C "$REPO_DIR" fetch origin main
sudo -u vsff -H git -C "$REPO_DIR" reset --hard origin/main
test -f "$BUNDLE/vsff-review.service"
sudo -u vsff -H git -C "$REPO_DIR" rev-parse HEAD >"$ROLLBACK_DIR/repository-installed.txt"
```

Compare that commit with the release you reviewed before proceeding. This bundle
does not change existing backend/frontend source; unexpected unrelated changes
on main need their own review. No `git clean`, data copy, or automatic rollback.

## Phase 2 — empty private runtime storage

For the initial empty installation, stop if there is already a review database;
use a deliberate upgrade/data-migration plan instead of overwriting it.

```bash
test ! -e /var/lib/vsff-review/pdf_review.sqlite3
install -d -o vsff -g vsff -m 0700 \
    /var/lib/vsff-review \
    /var/lib/vsff-review/blobs \
    /var/lib/vsff-review/backups
```

`vsff` owns the runtime state and is the only ordinary user with directory access.
The service's `UMask=0077` makes new files private. SQLite WAL/SHM files, upload
staging, immutable blobs, and backups stay here. Never put them under `/srv` or
create Apache aliases to this tree. No real manuscript is introduced in this phase.

## Phase 3 — root-owned production environment

Only create a new file if absent; if it exists, inspect and edit it privately
after confirming its saved backup, rather than copying over it.

```bash
if [[ ! -e /etc/vsff-review.env ]]; then
    install -o root -g root -m 0600 "$BUNDLE/vsff-review.env.example" /etc/vsff-review.env
fi
chown root:root /etc/vsff-review.env
chmod 0600 /etc/vsff-review.env
editor /etc/vsff-review.env
if grep -q 'REPLACE_WITH_' /etc/vsff-review.env; then
    echo 'Replace all production placeholders privately before starting the service.' >&2
    exit 1
fi
```

Use an editor/password manager to generate a persistent high-entropy session
secret (at least 32 characters) and supply real Google Web client credentials.
Keep values out of shell command arguments/history, Git, screenshots, and logs.
Do not `source`, `cat`, or `printenv` the review environment. Systemd reads the
root-only file as the supervisor and passes variables to the unprivileged service;
the `vsff` deploy shell never needs to read this file.

Exact production names/values are in the example. In particular:

- `PDF_REVIEW_DATA_DIR=/var/lib/vsff-review`; omit `PDF_REVIEW_DATABASE` so SQLite,
  blobs, and snapshots stay together. Do not add alternate runtime paths without
  updating service hardening, backups, and operator instructions together.
- `PDF_REVIEW_COOKIE_SECURE=1`, **not `true`**. The existing parser compares the
  literal string `1`, and production rejects an insecure cookie setting.
- `PDF_REVIEW_SERVER_NAME=review.venasff.com`, scheme `https`, proxy hops `1`,
  host `127.0.0.1`, port `8002`. Apache overwrites forwarded scheme; the app does
  not trust forwarded host/address/port/prefix. Cloudflare is not another trusted
  application proxy hop; Apache supplies the final trusted scheme header.
- Do not add `GUNICORN_CMD_ARGS`, `WEB_CONCURRENCY`, preload, extra workers, or
  another instance. The configured service has one worker and process-local state.

## Phase 4 — independent Python environment, as vsff

Ubuntu's base Python may be older than this application supports. Use uv-managed
Python 3.13 without changing the OS Python or the existing backend environment.
The application currently uses bounded `requirements.txt`, not a lockfile.

```bash
sudo -u vsff -H bash -c '
    set -Eeuo pipefail
    umask 077
    cd /srv/vsff_website/pdf_review
    /home/vsff/.local/bin/uv python install 3.13
    if [[ ! -x .venv/bin/python ]]; then
        /home/vsff/.local/bin/uv venv --python 3.13 .venv
    fi
    /home/vsff/.local/bin/uv pip install --python .venv/bin/python --requirement requirements.txt
    /home/vsff/.local/bin/uv pip check --python .venv/bin/python
    .venv/bin/python --version
    .venv/bin/python -c "import flask_socketio, gunicorn, simple_websocket"
'
```

An existing review environment must already use a supported interpreter; do not
silently delete/recreate one during an upgrade. `uv pip install` resolves
transitives; `uv pip sync` against this direct-dependency list would be incorrect.
Satisfied dependencies are retained; requirements changes install required
versions. This is not a frozen/reproducible production dependency lock, and does
not automatically upgrade every satisfied package. Review dependency upgrades
deliberately. Never point these commands at `backend/.venv`.

Do not invoke `flask --app app` or import `wsgi` for a pre-upgrade backup: creating
the app applies migrations first. The new `backup_review.py` helper requires no
secrets and imports only Python standard library modules.

## Phase 5 — systemd and loopback acceptance

```bash
systemd-analyze verify "$BUNDLE/vsff-review.service"
install -o root -g root -m 0644 "$BUNDLE/vsff-review.service" /etc/systemd/system/vsff-review.service
systemd-analyze verify /etc/systemd/system/vsff-review.service
systemctl daemon-reload
systemctl enable --now vsff-review
systemctl is-active --quiet vsff-review
curl --fail --silent --show-error --retry 10 --retry-delay 2 --retry-connrefused \
    --connect-timeout 2 --max-time 5 --noproxy '*' \
    --header 'Host: review.venasff.com' --header 'X-Forwarded-Proto: https' \
    http://127.0.0.1:8002/healthz
ss -ltnp '( sport = :8002 )'
systemctl show vsff-review --property=MainPID --property=User --property=Group
systemd-cgls /system.slice/vsff-review.service
check_vsff
```

Expect `OK`, a loopback-only listener, a Gunicorn master and **one** worker.
A Host header of `127.0.0.1:8002` is deliberately rejected by Flask trusted-host
validation. `/healthz` is unauthenticated process liveness with constant `OK\n`,
no database queries, no session creation, and private/no-store headers. Startup
completed factory/migration initialization before serving it; it is not an
ongoing database, blob, Google, or end-to-end readiness check.

On failure, inspect `journalctl -u vsff-review -n 80 --no-pager` privately; do not
paste identity/request details publicly. Never print the service Environment.

Hardening choices, compatible with Ubuntu 22.04 systemd:

| Directive | Reason and operational effect |
| --- | --- |
| `User/Group=vsff` | Uses the existing account as requested; separate process/paths, not an OS-user security boundary from VSFF |
| `NoNewPrivileges=true` | No privilege gain through executed programs; app requires none |
| `ProtectSystem=strict` | Read-only filesystem view, including checkout and virtual environment |
| `ReadWritePaths=/var/lib/vsff-review` | Persistent writes limited to private SQLite/WAL, blobs, and backups |
| `ProtectHome=read-only` | Retains read/execute access to uv-managed Python under `/home/vsff`, while forbidding home writes; `true` would hide that interpreter |
| `PrivateTmp=true` | Writable isolated temporary files, including Gunicorn heartbeat files, not shared host temp files |
| `UMask=0077` | Restricts new private files/directories |
| `PYTHONDONTWRITEBYTECODE=1` | No runtime attempts to write Python caches in the read-only checkout |
| `Restart=on-failure`, `RestartSec=3` | Restarts failed processes; does not hide failures from the deployment health check |
| `TimeoutStopSec=45` | Allows Gunicorn's default graceful shutdown before forced stop; old worker stops before replacement starts |

Network access is retained for Google OIDC, DNS, HTTP/Socket.IO and loopback.
Persistent runtime writes are the explicit exception; private temporary storage
is also writable. No `PrivateNetwork`, hidden home, or unsupported blanket syscall
filter is added. Journal logs stay outside the checkout. Existing VSFF has no
systemd dependency on this service, so review failure does not stop VSFF.

Migration behavior: `wsgi:app` calls `create_app()`, which validates production
auth settings then calls `init_database()`. Missing numbered SQLite migrations
are applied in order; each migration and its version record use one transaction.
Already-applied migrations are skipped. A failure rolls back the current
migration; earlier completed migrations remain. Restart stops the old process
before the new worker starts; do not run another factory concurrently during a
schema upgrade. No Alembic, Flask-Migrate, second migration system, or additional
pre-start migration service is used.

## Phase 6 — Apache HTTP origin and ACME bootstrap

In the Cloudflare dashboard, require a **cache-bypass rule for the entire hostname**
before exposing application content: expression
`(http.host eq "review.venasff.com")`, action **Bypass cache**. Ensure no later
matching rule, Cache Everything setting, Worker, or page rule overrides it.
Purge any previously cached responses for this hostname. Keep this rule after
deployment, including for static assets. Never rely only on app headers or a
cache rule restricted to `.pdf` paths; protected bytes use dynamic routes.

Temporarily set only the `review` DNS record to **DNS-only** for initial ACME/origin
testing if useful. Its proxied public DNS normally returns Cloudflare addresses;
that is expected and is not evidence of a wrong origin. Do not modify the apex or
www records. Port 80 must be reachable for HTTP-01 renewal; if an existing origin
firewall blocks it, resolve that deliberately before Certbot rather than adding
unreviewed firewall commands from this bundle.

```bash
install -d -o root -g root -m 0755 \
    /var/www/vsff-review-acme \
    /var/www/vsff-review-acme/.well-known \
    /var/www/vsff-review-acme/.well-known/acme-challenge
install -o root -g root -m 0644 "$BUNDLE/apache-review-http.conf" \
    /etc/apache2/sites-available/review.venasff.com.conf
a2ensite review.venasff.com.conf
apache2ctl configtest
systemctl reload apache2
curl --fail --silent --show-error --resolve review.venasff.com:80:85.31.233.18 \
    http://review.venasff.com/healthz
check_vsff
```

HTTP bootstrap exposes only `/healthz` and the public ACME challenge directory;
other paths return 503 until TLS is ready. Do not sign in over HTTP. The ACME
directory never contains PDFs, databases, environment files, or application
source. Stop and restore this review vhost on a configtest failure; never reload
an invalid configuration. Existing venasff.com virtual hosts stay unchanged.

## Phase 7 — separate certificate, HTTPS proxy, renewal

Request a separate named certificate using the existing Certbot installation.
Webroot issuance avoids editing either site's existing certificate or vhost:

```bash
certbot certonly --webroot --webroot-path /var/www/vsff-review-acme \
    --cert-name review.venasff.com --domain review.venasff.com
test -r /etc/letsencrypt/live/review.venasff.com/fullchain.pem
test -r /etc/letsencrypt/live/review.venasff.com/privkey.pem
openssl x509 -in /etc/letsencrypt/live/review.venasff.com/fullchain.pem \
    -noout -subject -issuer -dates

# One file replaces bootstrap: final TLS proxy plus HTTP redirect/ACME exception.
install -o root -g root -m 0644 "$BUNDLE/apache-review-ssl.conf.example" \
    /etc/apache2/sites-available/review.venasff.com.conf
apache2ctl configtest
systemctl reload apache2
curl --fail --silent --show-error --resolve review.venasff.com:443:127.0.0.1 \
    https://review.venasff.com/healthz
curl --fail --silent --show-error --resolve review.venasff.com:443:85.31.233.18 \
    https://review.venasff.com/healthz
check_vsff

bash -n "$BUNDLE/renew-review-apache.sh"
install -o root -g root -m 0755 "$BUNDLE/renew-review-apache.sh" \
    /etc/letsencrypt/renewal-hooks/deploy/reload-vsff-review-apache.sh
certbot renew --cert-name review.venasff.com --dry-run
systemctl list-timers certbot.timer
```

Do not use `--expand`, `--reinstall`, an apex/www `--cert-name`, or `curl -k`.
Certificate verification must succeed with the review hostname/SNI and a trusted
chain. No certificate/key goes into Git. Existing Certbot scheduling remains;
if the installation uses cron/snap instead of that timer, confirm its existing
renewal schedule rather than creating a competing scheduler. The root-owned hook
reloads Apache only for the review certificate and only after configtest passes.
Dry-run verifies challenges; by default it does not execute deploy hooks.

HTTPS proxies the whole host, including Flask static assets/PDF.js, OIDC,
protected PDFs/APIs and Socket.IO. `ProxyPreserveHost On` preserves canonical
host validation. Apache overwrites `X-Forwarded-Proto` with `https`, irrespective
of incoming client/Cloudflare values. Explicit WebSocket upgrade rules for
`/socket.io/` run before the ordinary HTTP catch-all; long polling stays HTTP.
No app data is served through Apache filesystem aliases. HTTP redirects to the
fixed HTTPS hostname except ACME challenges, allowing later webroot renewals.

Review vhosts suppress per-request access logs to avoid retaining transient OAuth
codes in query strings; warning/error logs remain. Do not enable proxy debug,
Gunicorn access logs, or header/environment dumps during real private review.

## Phase 8 — public HTTPS and Cloudflare acceptance, still no real data

Restore Cloudflare proxying for `review` after direct origin TLS succeeds. Select
**Full (strict)** SSL/TLS mode, retain WebSocket support, and keep the **entire-host
cache bypass** effective. Never use Flexible mode. If an account-wide SSL setting
affects other hosts, preserve their working behavior and scope/configure the rule
appropriately; do not downgrade existing site TLS. No Cloudflare API changes are
performed by this bundle.

```bash
curl --fail --silent --show-error https://review.venasff.com/healthz
curl --silent --show-error --dump-header - --output /dev/null \
    https://review.venasff.com/healthz |
    sed -n -e '/^HTTP\//p' -e '/^[Cc]ache-[Cc]ontrol:/p' \
        -e '/^[Cc][Ff]-[Cc]ache-[Ss]tatus:/p' -e '/^[Aa]ge:/p'
check_vsff
```

Test repeatedly through the public hostname. Expect app private/no-store headers,
no `Age`, and no `HIT`, `STALE`, `UPDATING`, or other evidence of edge-cached content.
Cloudflare commonly reports `DYNAMIC` or `BYPASS`; some responses/transports may
have no cache-status header. Confirm the effective bypass rule in the dashboard,
not just one initial MISS. Visit `/`: an anonymous browser reaches sign-in and
sees no document/user/reviewer metadata. No production navigation link is added.

## Phase 9 — Google callback and real sign-in with empty/synthetic data

In the existing Google **Web application** OAuth client, register the exact URI:

```text
https://review.venasff.com/auth/google/callback
```

Keep `http://127.0.0.1:5000/auth/google/callback` for development. Do not substitute
an origin-only URL or a trailing slash, and do not remove development settings.
Audience/test-user eligibility and verified-email application allowlisting are
separate. This bundle performs no Google configuration.

To administer the runtime without reading the root-only environment into a shell,
define this root helper. Use it only after the current service has started its
migrations, not as a pre-migration backup command:

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
read -r -p 'Permitted operator Google email (private runtime only): ' REVIEW_EMAIL
review_admin allow-email "$REVIEW_EMAIL"
unset REVIEW_EMAIL
```

Use private terminal output; no real identity or allowlist file goes into the
checkout/runbook. Sign in as that account through public HTTPS. A newly allowed
account has no grants to existing documents. It can create its own logical
**synthetic acceptance document** and becomes its owner. Use a generated/public
synthetic PDF only for acceptance. If using two approved accounts, explicitly
grant the second account access to that synthetic document using the documented
`grant-access DOCUMENT_ID USER_ID --role reviewer` CLI through `review_admin`.
Do not bootstrap permissions on real manuscripts yet. Real legacy linking and
historical ACL preparation belong to the later private-data migration.

## Phase 10 — security and collaboration acceptance

Use the synthetic document's real IDs in a private terminal. Signed-out/private
browser windows must show no private content for dashboard, document/version
pages, PDF GET/HEAD, valid/invalid Range, threads/comments/history, or migrations.
For a repeatable anonymous check (no cookies and no redirect following):

```bash
read -r -p 'Synthetic document UUID: ' TEST_DOCUMENT
read -r -p 'Synthetic version UUID: ' TEST_VERSION
for route in / \
    "/documents/$TEST_DOCUMENT" \
    "/versions/$TEST_VERSION/view" \
    "/versions/$TEST_VERSION/pdf" \
    "/api/versions/$TEST_VERSION/threads" \
    "/api/documents/$TEST_DOCUMENT/migrations"; do
    status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
        --header 'Range: bytes=0-99' "https://review.venasff.com$route")
    case "$status" in 302|401) ;; *) echo "Unexpected anonymous response: $status" >&2; exit 1;; esac
done
for range in bytes=0-99 bytes=999999999- invalid; do
    status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
        --header "Range: $range" "https://review.venasff.com/versions/$TEST_VERSION/pdf")
    test "$status" = 302
done
status=$(curl --silent --show-error --head --output /dev/null --write-out '%{http_code}' \
    --header 'Range: bytes=0-99' "https://review.venasff.com/versions/$TEST_VERSION/pdf")
test "$status" = 302
unset TEST_DOCUMENT TEST_VERSION
```

In browser developer tools, also confirm:

- Anonymous responses contain no PDF bytes, Content-Range, titles, comments,
  metadata, paths, or real identities. A globally unapproved account is denied;
  an approved account without a document grant cannot access its known URLs.
- An authorized owner's PDF/Range requests work (206 for a valid requested range),
  and protected responses retain `Cache-Control: no-store, private`. Repeated
  authenticated requests never become Cloudflare cache HITs. After logout, the
  same URLs yield no bytes. Do not paste authenticated cookies into public logs.
- No-CSRF mutations fail; viewer writes fail; reviewers cannot import or carry
  feedback, and cannot edit another author's comment. Normal owner/reviewer
  comments, replies, revisions, resolution and explicit migration work.
- Authenticated two-browser presence, remote comment updates, reconnect, and
  per-version isolation work over public HTTPS. Network tools show an actual
  WSS `/socket.io/` upgrade (101), not only polling. Force WebSocket transport
  for an additional check if needed. The existing browser sanity harness can be
  used locally for fixture behavior; it is not a production auth bypass.
- A signed-out Socket.IO connection is rejected at the Socket.IO authentication
  layer; it cannot join a review room. An Engine.IO handshake alone may return
  200/101 **before** Socket.IO authentication; that is not evidence of review-room
  access. Check `connect_error`/rejection and absence of room/presence data.
- Verified-email allowlisting, document revocation, and the existing idle-socket
  revocation limitation are understood: revocation is checked on subsequent
  HTTP/connect/join/page reports; an already idle socket is not instantly evicted.

`/healthz` discloses only process liveness. The later public `/privacy` and `/tos`
pages disclose policy text only and must also work while signed out.
All existing private-content authentication/ACL checks stay in effect. Stop
before real data migration if any origin, cache, authorization, or WebSocket check
fails. Confirm existing VSFF API/site health again with `check_vsff`.

## Phase 11 — integrate deployment only after manual service acceptance

The originals were saved in phase 1. Validate the exact least-privilege sudoers
candidate **before** replacement. It grants only these two literal commands:
`/usr/bin/systemctl restart vsff-api` and `/usr/bin/systemctl restart vsff-review`.
No wildcard arguments, other verbs, daemon reload, shell, or unrestricted sudo.

```bash
visudo -cf "$BUNDLE/sudoers-vsff-deploy.example"
install -o root -g root -m 0440 "$BUNDLE/sudoers-vsff-deploy.example" \
    /etc/sudoers.d/vsff-deploy.candidate
visudo -cf /etc/sudoers.d/vsff-deploy.candidate
mv -T /etc/sudoers.d/vsff-deploy.candidate /etc/sudoers.d/vsff-deploy
visudo -cf /etc/sudoers

bash -n "$BUNDLE/deploy-vsff.sh"
install -o root -g root -m 0755 "$BUNDLE/deploy-vsff.sh" /home/vsff/deploy-vsff.sh
sudo -u vsff -H sudo -n -l

# Release the maintenance lock before the script tries to acquire the same lock.
flock -u 9
exec 9>&-
sudo -u vsff -H /home/vsff/deploy-vsff.sh
check_vsff
```

This last command is a **real deployment**, even at the same commit: it rebuilds,
checks migrations, snapshots review SQLite, and restarts services. It is not a
dry run. No authorized_keys, forced-command path, GitHub workflow or Secrets
change is required. Once installed, the existing forced command executes this
replacement on later deploys. Do not install it until review works manually.

The script's precise order and failure behavior:

1. Require the normal `vsff` account/home and no arguments; take the same
   `/home/vsff/.deploy-vsff.lock` with nonblocking flock.
2. Fetch `origin main`, reset tracked source to `origin/main`; either failure
   exits before restarts. Never touch private runtime storage with Git commands.
3. In a subshell with the original `/etc/vsff.env`, run backend `uv sync --frozen`,
   Node 24 `npm ci`/`npm run build`, and the existing `flask --app main db upgrade`.
   Preserve a web-readable build umask of 022. Stop on each failure.
4. Outside that environment, prepare **only** review `.venv`, install its bounded
   requirements, check dependencies/imports, and switch umask to 077. Review
   secrets are never sourced. An existing review interpreter is retained.
5. Snapshot existing `/var/lib/vsff-review/pdf_review.sqlite3` to its private
   backups directory using `backup_review.py`, reading committed live WAL data
   with SQLite's backup API and validating the result. No app import/migration
   or secret is needed. Missing database means first startup; corrupt/unreadable
   data or failed backup aborts. Immutable blobs are retained separately.
6. Restart `vsff-api` using its existing exact sudo command; health-check comments
   and submissions with the original retry behavior. Stop on failure, leaving
   review un-restarted.
7. Restart `vsff-review`; the old worker stops before the new one automatically
   applies its numbered migrations. Check `/healthz` on loopback with the canonical
   Host/HTTPS headers, retrying connection failures/transient HTTP failures. A
   non-success response or body other than `OK` fails the deployment.

There is **no atomic two-service release or automatic rollback**. Source reset,
in-place environments, built frontend and VSFF migrations may already have
changed before a later failure. After VSFF restarts, review can still fail; VSFF
then stays running while the deployment exits nonzero. A successful restart
command does not guarantee worker readiness; the health check catches that.
A snapshot can precede additional writes made by an old worker before restart;
it is a recovery point, not a zero-loss rollback promise. Dependencies are
updated in place, so a failure can leave an environment requiring operator repair.
Do not keep serving a known-bad review deployment just because VSFF is healthy.

## Phase 12 — private-data migration is a separate operation

Only after all earlier phases pass, separately plan and authorize transfer of the
existing SQLite database and matching content-addressed blobs. No transfer command
or private payload is included here. Use SQLite's backup API or a clean stopped
database snapshot, retain original copies, stop review for replacement, and
preserve immutable SHA-256 identity. Do not raw-copy an open WAL database, merge
with VSFF SQLAlchemy, rewrite authorship, or auto-grant existing documents.
Perform integrity/hash, identity-link/ACL and production acceptance checks before
resuming real review. Preserve matching blobs for every recoverable snapshot.
Keep databases, backups, allowlists, emails, reviewer content and PDFs exclusively
under private runtime storage, never in Git or Apache's ACME directory.

## Rollback — restore existing VSFF deployment independence

Stop on any failed phase. The existing website has no routing/service dependency
on review. Keep the root session and private rollback directory available.
Before changing files again, reacquire the same lock if phase 11 released it:

```bash
# A failed strict-mode command may have ended the earlier shell. If so, use a
# fresh root Bash session and the PRIVATE directory path printed in phase 1.
set -Eeuo pipefail
umask 077
test "$(id -u)" -eq 0
if [[ -z ${ROLLBACK_DIR:-} ]]; then
    read -r -p 'Private /root/vsff-review-b2a.* rollback directory: ' ROLLBACK_DIR
fi
test -d "$ROLLBACK_DIR/files"
check_vsff() {
    curl --fail --silent --show-error --max-time 20 http://127.0.0.1:8001/api/comments >/dev/null
    curl --fail --silent --show-error --max-time 20 http://127.0.0.1:8001/api/submissions >/dev/null
    curl --fail --silent --show-error --max-time 20 https://venasff.com/ >/dev/null
    curl --fail --silent --show-error --max-time 20 https://www.venasff.com/ >/dev/null
}
sudo -u vsff -H touch /home/vsff/.deploy-vsff.lock
exec 9>>/home/vsff/.deploy-vsff.lock
flock -n 9
test -d "$ROLLBACK_DIR/files"

restore_file() {
    local target="$1"
    local saved="$ROLLBACK_DIR/files$target"
    if [[ -e "$saved" || -L "$saved" ]]; then
        cp -a --remove-destination "$saved" "$target"
    elif grep -Fxq -- "$target" "$ROLLBACK_DIR/absent.txt"; then
        rm -f -- "$target"
    else
        echo 'No recorded original/absence; stop rather than guessing.' >&2
        return 1
    fi
}

# Restore the existing forced-deploy script and sudo policy first.
bash -n "$ROLLBACK_DIR/files/home/vsff/deploy-vsff.sh"
visudo -cf "$ROLLBACK_DIR/files/etc/sudoers.d/vsff-deploy"
restore_file /home/vsff/deploy-vsff.sh
restore_file /etc/sudoers.d/vsff-deploy
visudo -cf /etc/sudoers

systemctl disable --now vsff-review || true
restore_file /etc/systemd/system/vsff-review.service
restore_file /etc/vsff-review.env
systemctl daemon-reload

# Restore/remove ONLY this hostname's site and its enablement symlink.
restore_file /etc/apache2/sites-available/review.venasff.com.conf
restore_file /etc/apache2/sites-enabled/review.venasff.com.conf
restore_file /etc/letsencrypt/renewal-hooks/deploy/reload-vsff-review-apache.sh
apache2ctl configtest
systemctl reload apache2
check_vsff

flock -u 9
exec 9>&-
```

If an inactive prior review unit existed, consult its saved enablement record and
restore that state deliberately; do not start it against an unknown newer schema.
The VSFF unit itself was never edited and needs no replacement. Do not overwrite
all Apache sites with the snapshots or modify the apex/www certificates. Keep
Cloudflare's private-host cache bypass even during rollback. The new review
certificate/ACME directory may remain unused; removing its lineage or DNS record
is a separate deliberate action and must not affect existing certificates.

This restores infrastructure files, not database schemas, code versions, or
virtual environments. Never automatically downgrade code after committed
migrations. Preserve runtime/backups and match a compatible code/schema version
before restoring a database; restoration requires stopping review and a separately
reviewed data-recovery plan. Restoring a snapshot can lose writes after that
snapshot. Existing VSFF migration/data recovery follows its own procedure.

## Local validation and limits

From `pdf_review/`, run `python -m unittest discover -s tests -q`. Health tests
check anonymous GET/HEAD, constant body, no private reads/session creation,
nearby-path/method rejection, production host validation and existing private
route protection. Backup tests check live WAL consistency, first-start behavior,
and failure cleanup without importing/migrating the application.

Locally run `bash -n` on both shell artifacts. Systemd/Apache templates have been
reviewed for directive structure, source paths, write boundaries, proxy order,
and secrets. Windows does not supply the target Ubuntu systemd/Apache/Certbot
environment: their actual native checks and Gunicorn/HTTPS/Google/Cloudflare
acceptance are explicit operator gates above, not claimed local executions.
