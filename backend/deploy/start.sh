#!/bin/sh
# Start script for single-container hosts (e.g. Render's free plan, ADR-0016):
# apply migrations, create the first organisation once if asked to, then serve.
set -eu

alembic upgrade head

if [ -n "${LODGEOS_BOOTSTRAP_OWNER_EMAIL:-}" ] && [ -n "${LODGEOS_BOOTSTRAP_PASSWORD:-}" ]; then
  python -m app.cli bootstrap-organisation --if-empty \
    --name "${LODGEOS_BOOTSTRAP_ORG_NAME:-My Lodge}" \
    --slug "${LODGEOS_BOOTSTRAP_ORG_SLUG:-my-lodge}" \
    --currency "${LODGEOS_BOOTSTRAP_CURRENCY:-NAD}" \
    --timezone "${LODGEOS_BOOTSTRAP_TIMEZONE:-Africa/Windhoek}" \
    --country "${LODGEOS_BOOTSTRAP_COUNTRY:-NA}" \
    --owner-email "$LODGEOS_BOOTSTRAP_OWNER_EMAIL" \
    --owner-name "${LODGEOS_BOOTSTRAP_OWNER_NAME:-Owner}"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips '*'
