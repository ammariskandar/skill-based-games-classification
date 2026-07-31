#!/usr/bin/env bash
# SBGC-43 — deployment check gate.
# Runs manage.py check --deploy against production settings with controlled
# dummy values.  Fails on WARNING or higher.  Makes no network or database
# connection.
set -euo pipefail

APPS_DIR="$(dirname "$0")/../apps/backend"

exec flatpak-spawn --host \
  --env=DJANGO_SECRET_KEY="abCDefGHijKLmnOPqrSTuvWXyz01-234567890abCDefGHuvWXyz" \
  --env=DATABASE_URL="postgresql://u:p@example.neon.tech/db?sslmode=require" \
  --env=DJANGO_ALLOWED_HOSTS="example.com" \
  --env=CSRF_TRUSTED_ORIGINS="https://example.com" \
  --env=ADMIN_URL_PATH="mygamedna-prod" \
  --env=DJANGO_LOG_LEVEL="INFO" \
  --env=DJANGO_SECURE_HSTS_SECONDS="3600" \
  "$APPS_DIR/.venv/bin/python" \
  "$APPS_DIR/manage.py" check --deploy \
  --fail-level WARNING \
  --settings=config.settings.production
