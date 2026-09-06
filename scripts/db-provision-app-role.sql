-- =============================================================================
-- scripts/db-provision-app-role.sql
-- Least-privilege application role provisioning for MyGameDNA — SBGC-185.
--
-- Creates (or resets the password of) a scoped runtime role with DML-only
-- privileges on the public schema, explicit access to the unmanaged
-- DatabaseCache table, and NO SUPERUSER / NOCREATEDB / NOCREATEROLE /
-- NOREPLICATION.  The missing REPLICATION attribute is what neutralises the
-- CVE-2026-6471 ("PostGREShell") logical-decoding escalation path and the
-- large-object / COPY ... FROM PROGRAM privilege-escalation class: the app
-- role can never load server-side objects or write outside its tables.
--
-- DDL (migrations, createcachetable) is intentionally NOT granted here —
-- it runs under MIGRATION_DATABASE_URL (project-owner, direct connection)
-- during the release phase (scripts/backend-migrate.sh).  Runtime
-- Gunicorn/Django workers connect with this role via DATABASE_URL.
--
-- Idempotent: safe to re-run on every release or credential rotation.
--
-- Usage (never put the password on the command line of a shared shell):
--
--   psql "$MIGRATION_DATABASE_URL" \
--     -v app_user="$APP_DJANGO_DB_USER" \
--     -v app_password="$APP_DJANGO_DB_PASSWORD" \
--     -f scripts/db-provision-app-role.sql
--
-- Audit existing roles for the REPLICATION attribute (CVE-2026-6471):
--   SELECT rolname FROM pg_roles WHERE rolreplication;
-- =============================================================================
\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------------
-- 0. Input variables: app_user defaults to app_django; app_password is
--    required (psql -v app_password=...).  A missing password fails fast
--    instead of provisioning a role with an empty/placeholder credential.
-- ---------------------------------------------------------------------------
\if :{?app_user}
\else
  \set app_user 'app_django'
\endif
\if :{?app_password}
\else
  \echo 'ERROR: app_password not provided. Run with -v app_password=...'
  \quit 1
\endif

-- ---------------------------------------------------------------------------
-- 1. Role: create if missing, otherwise reset password and drop any elevated
--    attributes an earlier ad-hoc grant may have added (idempotent repair).
-- ---------------------------------------------------------------------------
DO $do$
DECLARE
  _user text := :'app_user';
  _pass text := :'app_password';
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = _user) THEN
    EXECUTE format(
      'CREATE ROLE %I LOGIN PASSWORD %L '
      'NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
      _user, _pass
    );
  ELSE
    EXECUTE format(
      'ALTER ROLE %I WITH LOGIN PASSWORD %L '
      'NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
      _user, _pass
    );
  END IF;
END
$do$;

-- ---------------------------------------------------------------------------
-- 2. Database connect privilege (the database you are currently connected to).
-- ---------------------------------------------------------------------------
DO $do$
DECLARE
  _user text := :'app_user';
BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), _user);
END
$do$;

-- ---------------------------------------------------------------------------
-- 3. Schema + DML on existing tables and sequences.
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO :"app_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_user";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"app_user";

-- ---------------------------------------------------------------------------
-- 4. Default privileges so tables/sequences created by future migrations
--    (run under the same owner role that executes this script) inherit the
--    same grants automatically.
-- ---------------------------------------------------------------------------
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"app_user";

-- ---------------------------------------------------------------------------
-- 5. Unmanaged DatabaseCache table (SBGC-107) — created by createcachetable
--    under the migration role, so grant explicitly when it already exists.
-- ---------------------------------------------------------------------------
DO $do$
DECLARE
  _user text := :'app_user';
BEGIN
  IF to_regclass('public.django_cache') IS NOT NULL THEN
    EXECUTE format(
      'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.django_cache TO %I',
      _user
    );
  END IF;
END
$do$;
