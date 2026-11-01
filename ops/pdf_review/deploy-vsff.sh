#!/usr/bin/env bash
# Proposed replacement for /home/vsff/deploy-vsff.sh; manual installation only.
set -Eeuo pipefail
# Apache must still be able to read the existing generated frontend dist files.
umask 022

if [[ $(id -un) != vsff || ${HOME:-} != /home/vsff || $# -ne 0 ]]; then
    echo "Run without arguments as the vsff deployment account with its normal home." >&2
    exit 1
fi

export NVM_DIR="/home/vsff/.nvm"
REPO_DIR="/srv/vsff_website"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
REVIEW_DIR="$REPO_DIR/pdf_review"
UV="/home/vsff/.local/bin/uv"

exec 9>"/home/vsff/.deploy-vsff.lock"
if ! flock -n 9; then
    echo "Another deployment is already running."
    exit 1
fi

# Review secrets remain root-only and are loaded by systemd, never this script.
source "$NVM_DIR/nvm.sh"
echo "Fetching latest code..."
cd "$REPO_DIR"
git fetch origin main
git reset --hard origin/main

# Preserve the existing VSFF dependency/build/migration sequence and environment.
# The subshell prevents VSFF secrets/configuration from entering review commands.
(
    set -a
    source /etc/vsff.env
    set +a
    echo "Updating existing backend environment..."
    cd "$BACKEND_DIR"
    "$UV" sync --frozen
    echo "Building Vue frontend..."
    cd "$FRONTEND_DIR"
    nvm use 24 >/dev/null
    npm ci
    npm run build
    echo "Applying existing VSFF database migrations..."
    cd "$BACKEND_DIR"
    "$UV" run flask --app main db upgrade
)

echo "Preparing independent PDF Review environment..."
umask 077
cd "$REVIEW_DIR"
if [[ ! -x .venv/bin/python ]]; then
    "$UV" venv --python 3.13 .venv
fi
# requirements.txt contains bounded direct dependencies, not a complete lock:
# use install (resolves transitives), not pip sync on an incomplete requirements list.
"$UV" pip install --python .venv/bin/python --requirement requirements.txt
"$UV" pip check --python .venv/bin/python
.venv/bin/python -c 'import flask_socketio, gunicorn, simple_websocket'
# No app/factory import: the snapshot MUST precede automatic review migrations.
.venv/bin/python "$REPO_DIR/ops/pdf_review/backup_review.py" /var/lib/vsff-review

echo "Restarting and checking existing VSFF API..."
sudo -n /usr/bin/systemctl restart vsff-api
curl --fail --silent --show-error --retry 10 --retry-delay 2 --retry-connrefused \
    http://127.0.0.1:8001/api/comments >/dev/null
curl --fail --silent --show-error --retry 10 --retry-delay 2 --retry-connrefused \
    http://127.0.0.1:8001/api/submissions >/dev/null

echo "Restarting PDF Review (startup applies its numbered SQLite migrations)..."
sudo -n /usr/bin/systemctl restart vsff-review
review_health=$(curl --fail --silent --show-error --retry 10 --retry-delay 2 \
    --retry-connrefused --connect-timeout 2 --max-time 5 --noproxy '*' \
    --header 'Host: review.venasff.com' --header 'X-Forwarded-Proto: https' \
    http://127.0.0.1:8002/healthz)
if [[ "$review_health" != OK ]]; then
    echo "PDF Review health check returned an unexpected response." >&2
    exit 1
fi
echo "Deployment completed successfully."
