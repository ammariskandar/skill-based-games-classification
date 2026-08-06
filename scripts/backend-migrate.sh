#!/usr/bin/env bash
# SBGC-43 / SBGC-52 — backend migration release.
#
# Run once during the Render pre-deploy phase.  Must not start the server,
# collect static files, create users, or print secrets.
#
# SBGC-52: Supports MIGRATION_DATABASE_URL for a direct Neon connection.
# If set, it is used instead of DATABASE_URL for migration execution.
# This allows runtime to use a pooled connection while migrations use
# a direct connection.
#
# Requires a valid PostgreSQL DATABASE_URL (or MIGRATION_DATABASE_URL)
# in the environment.
set -euo pipefail

cd "$(dirname "$0")/../apps/backend"

if [ -n "${MIGRATION_DATABASE_URL:-}" ]; then
  export DATABASE_URL="$MIGRATION_DATABASE_URL"
fi

exec python manage.py migrate --noinput --settings=config.settings.production
