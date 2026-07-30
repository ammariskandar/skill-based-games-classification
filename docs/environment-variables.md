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
| `CORS_ALLOWED_ORIGINS` | Server   | Secret        | `http://localhost:4321`        | Render env vars     | Yes          |
| `DATABASE_URL`         | Server   | Secret        | *(empty — uses SQLite locally)*| Neon dashboard      | Yes (production only) |
| `STEAM_API_KEY`        | Server   | Secret        | *(empty)*                      | Render env vars     | No (later)   |
| `ADMIN_URL_PATH`       | Server   | Secret        | `admin`                        | Render env vars     | Yes          |

**Rules:**

- Backend secrets belong only in Django's environment or the hosting platform's secret manager.
- Never commit a real `DJANGO_SECRET_KEY`.
- `DATABASE_URL` is optional in development (SQLite is used as fallback) and **required** in production (missing value raises `ImproperlyConfigured`). Use a direct non-pooler Neon connection string — hosts containing `-pooler` are not supported for the current connection mode. See [`docs/database-connectivity.md`](database-connectivity.md).
- `STEAM_API_KEY` remains empty until the Steam integration task requires it.
- In production, all critical secrets must be set; the application should fail safely if they are absent.
- `DEBUG` is controlled by the selected settings module (`config.settings.development` or `config.settings.production`), not by an environment variable.
  See [`docs/backend-architecture.md`](backend-architecture.md) for settings selection.
- `ADMIN_URL_PATH` controls the Django Admin route and is validated at startup. Must be a single relative path segment containing only ASCII letters, digits, hyphens, and underscores, starting with an alphanumeric character. The segment "api" is reserved. See [`docs/admin-configuration.md`](admin-configuration.md).
- `CORS_ALLOWED_ORIGINS` is currently an inert reserved value. It will be wired in SBGC-41.

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
