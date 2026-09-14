# Environment Variables

Each application manages its own `.env` file. The `.env.example` templates below define the full set of expected variables per application.

## Workflow

```bash
# Copy the example file for each application
cp apps/frontend/.env.example apps/frontend/.env
cp apps/backend/.env.example apps/backend/.env

# Edit local .env files — never commit them
```

## Frontend (`apps/frontend/.env`)

| Variable                    | Scope          | Public/Secret | Local Example             | Production Provider | Required Now |
| --------------------------- | -------------- | ------------- | ------------------------- | ------------------- | ------------ |
| `DJANGO_API_URL`            | Server only    | Secret        | `http://127.0.0.1:8000`   | Vercel env vars     | Yes          |
| `PUBLIC_SITE_URL`           | Server/Client  | Public        | `http://localhost:4321`   | Vercel env vars     | Yes          |
| `PUBLIC_GOOGLE_ANALYTICS_ID`| Server/Client  | Public        | *(empty)*                 | Vercel env vars     | No (later)   |

**Rules:**

- `PUBLIC_`-prefixed variables may be accessed in browser code (Astro/Vite convention).
- Variables without `PUBLIC_` are server-only and never exposed to the browser.
- Steam and database credentials must never appear in the frontend environment.

## Backend (`apps/backend/.env`)

| Variable               | Scope    | Public/Secret | Local Example                  | Production Provider | Required Now |
| ---------------------- | -------- | ------------- | ------------------------------ | ------------------- | ------------ |
| `DJANGO_SECRET_KEY`    | Server   | Secret        | *(generate locally)*           | Render env vars     | Yes          |
| `DJANGO_ALLOWED_HOSTS` | Server   | Secret        | `127.0.0.1,localhost`          | Render env vars     | Yes          |
| `CSRF_TRUSTED_ORIGINS` | Server   | Secret        | `http://localhost:4321`        | Render env vars     | Yes          |
| `DATABASE_URL`         | Server   | Secret        | *(empty — uses SQLite locally)*| Neon dashboard      | Yes (production only) |
| `STEAM_WEB_API_KEY`          | Server   | Secret        | *(empty)*                      | Render env vars     | No (for authenticated calls) |
| `STEAM_CONNECT_TIMEOUT_SECONDS` | Server | Public    | `3.05`                         | Render env vars     | No           |
| `STEAM_READ_TIMEOUT_SECONDS`    | Server | Public    | `10`                           | Render env vars     | No           |
| `STEAM_MAX_RETRIES`             | Server | Public    | `2`                            | Render env vars     | No           |
| `STEAM_RETRY_BACKOFF_SECONDS`   | Server | Public    | `0.25`                         | Render env vars     | No           |
| `STEAM_RETRY_SLEEP_MAX_SECONDS` | Server | Public    | `5`                            | Render env vars     | No           |
| `STEAM_MAX_RESPONSE_BYTES`      | Server | Public    | `2097152`                      | Render env vars     | No           |
| `STEAM_CDN_ALLOWED_HOSTS`       | Server | Public    | *(empty)*                      | Render env vars     | No (later)   |
| `STEAM_REFRESH_FALLBACK_EMAILS` | Server | Public    | *(empty)*                      | Render env vars     | No           |
| `DEFAULT_FROM_EMAIL`            | Server | Public    | `webmaster@localhost`          | Render env vars     | No           |
| `RESEND_API_KEY`                | Server | Secret    | *(empty)*                      | Render env vars     | Yes (production) |
| `RESEND_SMTP_PORT`              | Server | Public    | `2587`                         | Render env vars     | No           |
| `ZEPTOMAIL_SEND_TOKEN`          | Server | Secret    | *(empty)*                      | Render env vars     | No (failover provider) |
| `ZEPTOMAIL_API_URL`             | Server | Public    | `https://api.zeptomail.com/v1.1/email` | Render env vars | No    |
| `SERVER_EMAIL`                  | Server | Public    | `webmaster@localhost`          | Render env vars     | No           |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | Server | Secret | *(empty)* | Render env vars | Only as a Resend alternative |
| `DJANGO_LOG_LEVEL`      | Server   | Public        | `INFO`                         | Render env vars     | No           |
| `WEB_CONCURRENCY`       | Server   | Public        | `2`                            | Render env vars     | No           |
| `ADMIN_URL_PATH`       | Server   | Secret        | `mygamedna-admin`              | Render env vars     | Yes          |

**Rules:**

- Backend secrets belong only in Django's environment or the hosting platform's secret manager.
- Never commit a real `DJANGO_SECRET_KEY`.
- `DATABASE_URL` is optional in development (SQLite is used as fallback) and **required** in production (missing value raises `ImproperlyConfigured`). Use a direct non-pooler Neon connection string — hosts containing `-pooler` are not supported for the current connection mode. See [`docs/database-connectivity.md`](database-connectivity.md).
- `DJANGO_SECRET_KEY` production requirements strengthened in SBGC-43: 50+ characters, 5+ unique characters, no `django-insecure-` or `django-secret-` prefix. See [docs/backend-security.md](backend-security.md). Sent only through the `x-webapi-key` header. Never included in query strings, logs, or errors. See [`docs/steam-integration.md`](steam-integration.md).
- Steam HTTP timeouts and retry limits use conservative defaults and are validated at construction. See [](steam-integration.md).
- `DJANGO_LOG_LEVEL` must be one of DEBUG, INFO, WARNING, ERROR, or CRITICAL (case-insensitive). Invalid values raise `ImproperlyConfigured` in production. See [](backend-operations.md). See [`docs/steam-integration.md`](steam-integration.md).
- In production, all critical secrets must be set; the application should fail safely if they are absent.
- `DEBUG` is controlled by the selected settings module (`config.settings.development` or `config.settings.production`), not by an environment variable.
  See [`docs/backend-architecture.md`](backend-architecture.md) for settings selection.
- `ADMIN_URL_PATH` controls the Django Admin route and is validated at startup. Must be a single relative path segment containing only ASCII letters, digits, hyphens, and underscores, starting with an alphanumeric character. The segment "api" is reserved. See [`docs/admin-configuration.md`](admin-configuration.md).
- `STEAM_REFRESH_FALLBACK_EMAILS` is a comma-separated list of fallback alert
  recipients used only when no valid active Django Superuser email exists
  (SBGC-183 scheduled Steam refresh). It is configuration, not a secret. See
  [`docs/scheduled-steam-refresh.md`](scheduled-steam-refresh.md).
- `DEFAULT_FROM_EMAIL` is the sender address for operational alert emails
  (scheduled Steam refresh). Uses Django's standard email settings; no SMTP
  credentials are hardcoded.
- `RESEND_API_KEY` (SBGC-239) auto-wires production email delivery: setting it
  derives `smtp.resend.com` on port `2587` (STARTTLS) with the `resend` username,
  and defaults `DEFAULT_FROM_EMAIL` to `noreply@gamedna.my` and `SERVER_EMAIL` to
  `alerts@gamedna.my`. The default port is 2587 rather than 587 because Render
  free web services block outbound SMTP on 25, 465, and 587; `RESEND_SMTP_PORT`
  overrides it, and 2465/465 switch to implicit TLS. Without `RESEND_API_KEY`,
  production falls back to an explicit `EMAIL_HOST` / `EMAIL_PORT` /
  `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` relay.
  Production raises `ImproperlyConfigured` when none of `RESEND_API_KEY`,
  `ZEPTOMAIL_SEND_TOKEN`, or `EMAIL_HOST_PASSWORD` is set, because verification
  and password-reset mail would otherwise be dropped silently. Development and
  test settings are unaffected and keep local SMTP (smtp4dev).
- `ZEPTOMAIL_SEND_TOKEN` (SBGC-239) adds ZeptoMail as an email failover provider
  over its HTTPS API on port 443 — its SMTP service supports only 465/587, both
  blocked for outbound traffic on Render free web services. With
  `RESEND_API_KEY` also set, Resend stays primary and ZeptoMail is used only when
  Resend fails; on its own, ZeptoMail becomes the sole provider. The sender
  domain must be verified separately inside the ZeptoMail Agent, and
  `ZEPTOMAIL_API_URL` selects a regional endpoint (`api.zeptomail.eu`,
  `api.zeptomail.in`).

## Variable Classification

| Category | Variables | Visibility |
|----------|-----------|------------|
| **Public frontend** (client-visible) | `PUBLIC_SITE_URL`, `PUBLIC_GOOGLE_ANALYTICS_ID` | Inspectable by users. Measurement IDs are public identifiers. |
| **Private Astro server** (server-only) | `DJANGO_API_URL` | Never exposed to browser bundles. Read only in Astro frontmatter/server endpoints. |
| **Backend-only** (Django) | `DJANGO_SECRET_KEY`, `DATABASE_URL`, `STEAM_API_KEY`, etc. | Never appear in the frontend `@theme` or Astro `PUBLIC_` schema. |

**Rules:**

- `PUBLIC_` values are inspectable by users — never put secrets here.
- Measurement IDs (`G-XXXXXXXXXX`) are public — they do not need to be treated as secrets.
- Backend credentials must never use `PUBLIC_`.
- Do not create variables like `PUBLIC_DJANGO_API_URL` or `PUBLIC_DATABASE_URL`.
