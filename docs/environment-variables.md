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
| `DJANGO_DEBUG`         | Server   | Secret        | `true`                         | Render env vars     | Yes          |
| `DJANGO_ALLOWED_HOSTS` | Server   | Secret        | `127.0.0.1,localhost`          | Render env vars     | Yes          |
| `CSRF_TRUSTED_ORIGINS` | Server   | Secret        | `http://localhost:4321`        | Render env vars     | Yes          |
| `CORS_ALLOWED_ORIGINS` | Server   | Secret        | `http://localhost:4321`        | Render env vars     | Yes          |
| `DATABASE_URL`         | Server   | Secret        | *(empty — uses SQLite locally)*| Neon dashboard      | No (later)   |
| `STEAM_API_KEY`        | Server   | Secret        | *(empty)*                      | Render env vars     | No (later)   |
| `ADMIN_URL_PATH`       | Server   | Secret        | `admin/`                       | Render env vars     | No (later)   |

**Rules:**

- Backend secrets belong only in Django's environment or the hosting platform's secret manager.
- Never commit a real `DJANGO_SECRET_KEY`.
- `DATABASE_URL` is optional until PostgreSQL is configured.
- `STEAM_API_KEY` remains empty until the Steam integration task requires it.
- In production, all critical secrets must be set; the application should fail safely if they are absent.
