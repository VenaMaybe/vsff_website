#!/usr/bin/env bash
# Root-owned Certbot deploy hook, filtered to the separate review certificate.
set -Eeuo pipefail
if [[ ${RENEWED_LINEAGE:-} == /etc/letsencrypt/live/review.venasff.com ]]; then
    /usr/sbin/apache2ctl configtest
    /usr/bin/systemctl reload apache2
fi
