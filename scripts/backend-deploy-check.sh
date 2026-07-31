#!/usr/bin/env bash
# SBGC-43 — deployment check gate.
# Runs manage.py check --deploy against production settings and classifies
# warnings via the shared config.deploy_warnings module.  Fails on any
# Django error or unexpected warning.  Makes no network or database
# connection.
set -euo pipefail

APPS_DIR="$(dirname "$0")/../apps/backend"
MANAGE="$APPS_DIR/manage.py"

# Accepted staged-HSTS warnings (space-separated).
# Remove as each deployment stage progresses.
ACCEPTED_WARNINGS="security.W005 security.W021"

set +e
output=$(flatpak-spawn --host \
  --env=DJANGO_SECRET_KEY="abCDefGHijKLmnOPqrSTuvWXyz01-234567890abCDefGHuvWXyz" \
  --env=DATABASE_URL="postgresql://u:p@example.neon.tech/db?sslmode=require" \
  --env=DJANGO_ALLOWED_HOSTS="example.com" \
  --env=CSRF_TRUSTED_ORIGINS="https://example.com" \
  --env=ADMIN_URL_PATH="mygamedna-prod" \
  --env=DJANGO_LOG_LEVEL="INFO" \
  --env=DJANGO_SECURE_HSTS_SECONDS="3600" \
  "$APPS_DIR/.venv/bin/python" "$MANAGE" check --deploy \
  --fail-level ERROR --settings=config.settings.production 2>&1)
rc=$?
set -e

# Print Django output first.
echo "$output"
echo ""

# Fail on Django error.
if [ $rc -ne 0 ]; then
  echo "DEPLOY CHECK FAILED (Django exit $rc)"
  exit $rc
fi

# Classify warnings.
classify_output=$(echo "$output" | "$APPS_DIR/.venv/bin/python" -c "
import sys
sys.path.insert(0, '$APPS_DIR')
from config.deploy_warnings import classify_warnings
accepted = set('$ACCEPTED_WARNINGS'.split())
cr = classify_warnings(sys.stdin.read(), accepted)
for cw in cr.accepted:
    print(f'[ACCEPTED] {cw.warning_id}')
for cw in cr.unexpected:
    print(f'[UNEXPECTED] {cw.warning_id}')
if cr.has_unexpected:
    sys.exit(1)
")
classify_rc=$?

echo "$classify_output"

if [ $classify_rc -ne 0 ]; then
  echo ""
  echo "DEPLOY CHECK FAILED: Unexpected warnings detected."
  echo "Accepted warnings: $ACCEPTED_WARNINGS"
  exit 1
fi

echo ""
echo "Deploy check passed (accepted: $ACCEPTED_WARNINGS)."
