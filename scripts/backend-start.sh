#!/usr/bin/env bash
# SBGC-43 — backend start (Gunicorn WSGI).
# Run as the Render start command.  Must not migrate, collect static files,
# create users, or print secrets.
set -euo pipefail

cd "$(dirname "$0")/../apps/backend"

exec python -m gunicorn \
  config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --access-logfile - \
  --error-logfile -
