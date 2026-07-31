#!/usr/bin/env bash
# SBGC-43 — backend migration release.
# Run once during the Render pre-deploy phase.  Must not start the server,
# collect static files, create users, or print secrets.
# Requires a valid PostgreSQL DATABASE_URL in the environment.
set -euo pipefail

cd "$(dirname "$0")/../apps/backend"

exec python manage.py migrate --noinput --settings=config.settings.production
