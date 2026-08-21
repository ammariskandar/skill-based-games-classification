# Backend Operations — SBGC-43

Operational foundation for the MyGameDNA Django backend on Render.

## Runtime Architecture

```
Render HTTPS proxy
  → Gunicorn (synchronous WSGI)
  → Django WSGI (config.wsgi:application)
    → /health/         (liveness probe)
    → /{admin-path}/   (Django Admin via WhiteNoise)
    → /api/v1/         (Django Ninja)
```

## Gunicorn

Synchronous WSGI workers started via `scripts/backend-start.sh`:

- **Application:** `config.wsgi:application`
- **Bind:** `0.0.0.0:${PORT}`
- **Workers:** `${WEB_CONCURRENCY:-2}`
- **Access logs:** stdout
- **Error logs:** stderr

No Uvicorn, ASGI, WebSockets, or async workers.

No migration, collectstatic, or user creation in the start command.

## Logging

`DJANGO_LOG_LEVEL` controls the root Django logger threshold.

| Environment | Default |
|-------------|---------|
| Production | `INFO` |
| Development | `INFO` |
| Test | `WARNING` |

Accepted values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (case-insensitive).

Invalid or blank production values raise `ImproperlyConfigured`.

### Sensitive-Data Rules

Never intentionally log:

- `DJANGO_SECRET_KEY`
- `DATABASE_URL` or database credentials
- `STEAM_WEB_API_KEY`
- Authorization headers
- Cookies / CSRF tokens
- Request/response bodies
- Raw upstream response bodies
- Environment dumps

Render captures process streams (stdout/stderr). Retention, alerting, and searching remain deployment-owned and unverified.

## Health Endpoint

`GET /health/` — public liveness/startup probe.

- **Response:** `{"status": "ok"}` (200 JSON)
- **HEAD:** 200, no body
- No authentication
- No database query
- No Steam request
- No migration check
- No environment, version, commit, or secret disclosure
- Separate from `/api/v1/`

This is liveness/startup only. It does not assert database readiness, Steam readiness, migration currency, or full production readiness.

## WhiteNoise

`whitenoise.middleware.WhiteNoiseMiddleware` serves collected static files (Django Admin CSS/JS).

- **Middleware order:** Immediately after `SecurityMiddleware`
- **Storage:** `CompressedManifestStaticFilesStorage`
- **Static root:** `apps/backend/staticfiles/` (gitignored)

Django does not own Astro/Vercel assets.

## Static Collection

Static files are collected once during the Render build phase.

```bash
python manage.py collectstatic --noinput --settings=config.settings.production
```

Collected output is gitignored. The build phase does not migrate, start the server, create users, run tests, or print secrets.

## Migration Release

Migrations run once during the Render pre-deploy phase.

```bash
python manage.py migrate --noinput --settings=config.settings.production
```

Migration is separate from startup. Requires PostgreSQL through production settings. Does not create users, rewrite `DATABASE_URL`, or fall back to SQLite.

## Startup

The start command runs Gunicorn only. It does not migrate, collect static files, create users, or print secrets.

```bash
python -m gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --access-logfile - \
  --error-logfile -
```

## Render Blueprint

`render.yaml` defines one Python web service. The Neon PostgreSQL database is provisioned separately through the Neon dashboard.

- **Build:** `scripts/backend-build.sh`
- **Pre-deploy:** `scripts/backend-migrate.sh`
- **Start:** `scripts/backend-start.sh`
- **Health path:** `/health/`

Secret environment variables (`DJANGO_SECRET_KEY`, `DATABASE_URL`, `STEAM_WEB_API_KEY`, `ADMIN_URL_PATH`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`) are marked `sync: false`.

No Render database resource is defined. No real credentials are stored.

## Scheduled Steam Refresh (SBGC-183)

The daily scheduled Steam metadata refresh is a **separate Render Cron job**, not
part of the Gunicorn web service:

```text
Render Cron
  → python manage.py run_scheduled_steam_refresh --settings=config.settings.production
```

The job is application-implemented; the production cron itself is
**not yet provisioned** (deployment-owned work). See
[`docs/scheduled-steam-refresh.md`](scheduled-steam-refresh.md) for the
retry, audit, concurrency, and alerting contract, and
[`docs/steam-metadata-refresh.md`](steam-metadata-refresh.md) for the refresh
service it orchestrates.

Configuration:

- `STEAM_REFRESH_FALLBACK_EMAILS` — fallback alert recipients (used only when no
  valid active Superuser email exists).
- `DEFAULT_FROM_EMAIL` — sender for the operational alert email.
- Standard `EMAIL_*` settings drive `send_mail()`; no SMTP credentials are
  hardcoded.

## Environment Variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `DJANGO_SECRET_KEY` | Production | — | 50+ chars, 5+ unique, no insecure prefix |
| `DATABASE_URL` | Production | — | PostgreSQL only in production; SQLite OK in dev |
| `DJANGO_ALLOWED_HOSTS` | Production | — | Comma-separated hosts/IPv4 |
| `CSRF_TRUSTED_ORIGINS` | Production | — | `https://host[:port]`, structured parsing |
| `ADMIN_URL_PATH` | Production | `admin` (dev) | Non-default required in production |
| `DJANGO_LOG_LEVEL` | — | `INFO` | DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `DJANGO_SECURE_HSTS_SECONDS` | — | `0` | Staged: 0 → 3600 → 31536000 |
| `STEAM_WEB_API_KEY` | — | *(empty)* | Optional |
| `STEAM_REFRESH_FALLBACK_EMAILS` | — | *(empty)* | Comma-separated fallback alert recipients |
| `DEFAULT_FROM_EMAIL` | — | `webmaster@localhost` | Sender for operational alerts |
| `WEB_CONCURRENCY` | — | `2` | Gunicorn workers |

## PostgreSQL-Only Production

Production rejects every non-PostgreSQL database engine (`require_postgresql=True`):

- Missing URL → `ImproperlyConfigured`
- Blank URL → `ImproperlyConfigured`
- SQLite → `ImproperlyConfigured`
- MySQL / Oracle / unknown → `ImproperlyConfigured`

Development preserves its accepted behavior: missing URL → local SQLite.

Test settings remain in-memory SQLite.

## Secret Validation

Production secret-key validation aligns with Django `security.W009`:

- 50+ characters
- 5+ unique characters
- No `django-insecure-` or `django-secret-` prefix
- No known development placeholders

Error messages never include the rejected value. No `SECRET_KEY_FALLBACKS` without a concrete rotation process.

## Admin-Path Policy

Production requires an explicit non-default `ADMIN_URL_PATH`. `"admin"` (case-insensitive) is rejected.

- Missing → `ImproperlyConfigured`
- Blank → `ImproperlyConfigured`
- `"admin"` / `"ADMIN"` → `ImproperlyConfigured`

The custom path is defense in depth — it is not a secret and does not replace authentication or rate limiting.

Development may use `"admin"`. Test uses `"test-admin"`.

## CSRF Trusted Origins

Structured URL parsing via `urlparse`:

- **Accepted:** `https://valid-host[:port]` (port 1–65535)
- **Normalised:** scheme lowercase, hostname lowercase, root slash removed
- **Rejected:** HTTP (when HTTPS required), credentials, paths beyond `/`, query, fragment, wildcard, malformed DNS labels, port 0
- **Deduplicated** by normalised form

## Reverse-Proxy Assumptions

- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`
- Render forwards HTTPS via `X-Forwarded-Proto`
- `USE_X_FORWARDED_HOST` is not enabled
- Tests prove Django behavior; live Render forwarding remains unverified
- The application must not trust this header from arbitrary direct clients

## Deployment Checks

`scripts/backend-deploy-check.sh` runs `manage.py check --deploy` against production settings with controlled dummy values. No network or database connection. Included in the `npm run ci` chain.

## HSTS Staging

- Default: `0` (disabled)
- Stage: `3600` after HTTPS verified
- Final: `31536000` after sustained operation

## Remaining Live-Verification Work

- No Render service was created
- No Neon migration ran
- No real proxy test occurred
- No production key was generated
- No deployment readiness is claimed
- SBGC-44 remains before the Django foundation epic closes
