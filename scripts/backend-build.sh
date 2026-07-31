#!/usr/bin/env bash
# SBGC-43 — backend build (collectstatic).
# Run once during the Render build phase.  Must not migrate, start the
# server, create users, run tests, or print secrets.
set -euo pipefail

cd "$(dirname "$0")/../apps/backend"

exec python manage.py collectstatic --noinput --settings=config.settings.production
