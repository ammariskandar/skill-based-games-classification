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
