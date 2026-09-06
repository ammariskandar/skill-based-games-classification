#!/usr/bin/env bash
# SBGC-43 / SBGC-196 — backend build (install production deps + collectstatic).
#
# Run once during the Render build phase.  Must not migrate, start the server,
# create users, run tests, or print secrets.  Database migrations run in the
# pre-deploy phase (scripts/backend-migrate.sh) — never here.
#
# SBGC-196 (audit R4-01): a custom Render buildCommand replaces the platform's
# default dependency install, so production requirements MUST be installed here
# before collectstatic can import Django at all.
set -euo pipefail

cd "$(dirname "$0")/../apps/backend"

echo "=================================================="
echo "Starting Backend Production Build"
echo "=================================================="

# 1. Install production-only dependencies (never requirements-dev.txt).
echo "Installing production Python dependencies..."
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r requirements.txt

# 2. Collect static assets.
echo "Collecting static assets..."
exec python manage.py collectstatic --noinput --settings=config.settings.production
