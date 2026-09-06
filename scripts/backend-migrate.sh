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

# SBGC-185 — Neon PgBouncer (-pooler suffix) runs in transaction mode and
# does not support the DDL/session semantics migrations rely on.  Migrations
# and createcachetable must always hit the direct (unpooled) compute endpoint,
# so refuse to run when the effective URL still targets a pooled host.
case "$DATABASE_URL" in
  *"-pooler."*)
    echo "ERROR: DATABASE_URL targets the Neon PgBouncer pooler (-pooler)."
    echo "Migrations must run against the direct compute endpoint. Set"
    echo "MIGRATION_DATABASE_URL to the non-pooled connection string."
    exit 1
    ;;
esac

python manage.py migrate --noinput --settings=config.settings.production
# SBGC-107 — provision the DatabaseCache table (idempotent).
python manage.py createcachetable --settings=config.settings.production
