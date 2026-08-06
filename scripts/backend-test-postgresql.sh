#!/usr/bin/env bash
# SBGC-52 — PostgreSQL integration test runner.
#
# Runs constraint, migration, and transaction tests against an isolated
# PostgreSQL database.  Requires POSTGRES_TEST_DATABASE_URL.
#
# Usage:
#   POSTGRES_TEST_DATABASE_URL='postgresql://...' npm run test:backend:postgresql
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="$REPO_ROOT/apps/backend"
PYTHON="$APPS_DIR/.venv/bin/python3"
MANAGE="$APPS_DIR/manage.py"

# ---------------------------------------------------------------------------
# Guard — POSTGRES_TEST_DATABASE_URL required
# ---------------------------------------------------------------------------

if [ -z "${POSTGRES_TEST_DATABASE_URL:-}" ]; then
  echo "ERROR: POSTGRES_TEST_DATABASE_URL is required."
  echo ""
  echo "Set it to a disposable PostgreSQL connection string:"
  echo "  POSTGRES_TEST_DATABASE_URL='postgresql://user:pass@host:5432/db' npm run test:backend:postgresql"
  echo ""
  echo "Never use a production Neon URL."
  exit 1
fi

# Verify the URL uses a PostgreSQL scheme.
if [[ ! "$POSTGRES_TEST_DATABASE_URL" =~ ^postgres(ql)?:// ]]; then
  echo "ERROR: POSTGRES_TEST_DATABASE_URL must use a postgresql:// scheme."
  exit 1
fi

export POSTGRES_TEST_DATABASE_URL

# ---------------------------------------------------------------------------
# Migration check (state consistency)
# ---------------------------------------------------------------------------

echo "=== Migration consistency check ==="
"$PYTHON" "$MANAGE" makemigrations \
  --check --dry-run \
  --settings=config.settings.test \
  --noinput

# ---------------------------------------------------------------------------
# PostgreSQL migration tests
# ---------------------------------------------------------------------------

echo ""
echo "=== PostgreSQL migration tests ==="
"$PYTHON" "$MANAGE" test \
  config.tests.test_pg_migrations \
  --settings=config.settings.postgresql_test \
  --noinput \
  -v 2

# ---------------------------------------------------------------------------
# PostgreSQL Game constraint tests
# ---------------------------------------------------------------------------

echo ""
echo "=== PostgreSQL Game constraint tests ==="
"$PYTHON" "$MANAGE" test \
  games.tests.test_pg_constraints \
  --settings=config.settings.postgresql_test \
  --noinput \
  -v 2

# ---------------------------------------------------------------------------
# PostgreSQL Classification constraint tests
# ---------------------------------------------------------------------------

echo ""
echo "=== PostgreSQL Classification constraint tests ==="
"$PYTHON" "$MANAGE" test \
  classifications.tests.test_pg_constraints \
  --settings=config.settings.postgresql_test \
  --noinput \
  -v 2

echo ""
echo "PostgreSQL verification complete."
