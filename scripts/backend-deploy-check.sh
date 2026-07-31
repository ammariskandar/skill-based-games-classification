#!/usr/bin/env bash
# SBGC-43 — deployment check gate.
# Runs manage.py check --deploy against production settings.  Permits only
# explicitly documented staged-HSTS warnings; fails on any error or
# unexpected warning.  Makes no network or database connection.
set -euo pipefail

APPS_DIR="$(dirname "$0")/../apps/backend"
PYTHON="$APPS_DIR/.venv/bin/python"
MANAGE="$APPS_DIR/manage.py"

# Accepted staged-HSTS warnings (space-separated IDs).
# Remove these as each deployment stage progresses:
#   W004 — SECURE_HSTS_SECONDS < 31536000  (appears when HSTS seconds are 0 or small)
#   W005 — SECURE_HSTS_INCLUDE_SUBDOMAINS is False
#   W021 — SECURE_HSTS_PRELOAD is False
ACCEPTED_WARNINGS="security.W004 security.W005 security.W021"

# Run check and capture output.
set +e
output=$(flatpak-spawn --host \
  --env=DJANGO_SECRET_KEY="abCDefGHijKLmnOPqrSTuvWXyz01-234567890abCDefGHuvWXyz" \
  --env=DATABASE_URL="postgresql://u:p@example.neon.tech/db?sslmode=require" \
  --env=DJANGO_ALLOWED_HOSTS="example.com" \
  --env=CSRF_TRUSTED_ORIGINS="https://example.com" \
  --env=ADMIN_URL_PATH="mygamedna-prod" \
  --env=DJANGO_LOG_LEVEL="INFO" \
  --env=DJANGO_SECURE_HSTS_SECONDS="3600" \
  "$PYTHON" "$MANAGE" check --deploy \
  --fail-level ERROR --settings=config.settings.production 2>&1)
rc=$?
set -e

# Fail on any error.
if [ $rc -ne 0 ]; then
  echo "DEPLOY CHECK FAILED (exit $rc):"
  echo "$output"
  exit $rc
fi

# Print all output first.
echo "$output"
echo ""

# Extract warning IDs (match 'security.W###' or 'caches.W###' etc.)
# and check against the accepted list.
unexpected=0
while IFS= read -r line; do
  warn_id=$(echo "$line" | sed -n 's/.*(\([a-zA-Z][a-zA-Z0-9]*\.W[0-9][0-9]*\)).*/\1/p')
  if [ -z "$warn_id" ]; then
    continue
  fi
  accepted=0
  for a in $ACCEPTED_WARNINGS; do
    if [ "$warn_id" = "$a" ]; then
      accepted=1
      break
    fi
  done
  if [ $accepted -eq 1 ]; then
    echo "[ACCEPTED] $line"
  else
    echo "[UNEXPECTED WARNING] $line"
    unexpected=1
  fi
done <<< "$output"

if [ $unexpected -ne 0 ]; then
  echo ""
  echo "DEPLOY CHECK FAILED: Unexpected warnings detected."
  echo "Accepted warnings: $ACCEPTED_WARNINGS"
  exit 1
fi

echo ""
echo "Deploy check passed (accepted staged-HSTS warnings only)."
