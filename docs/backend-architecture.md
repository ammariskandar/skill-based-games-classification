# Backend Architecture

Django backend for the MyGameDNA skill-based games classification platform.

## Package Tree

```
apps/backend/
├── config/                     # Django project package (composition root)
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py         # Empty — settings modules are selected explicitly
│   │   ├── base.py             # Shared settings (all environments)
│   │   ├── development.py      # DEBUG=True, local conveniences
│   │   └── production.py       # DEBUG=False, deployment defaults
│   ├── database.py             # Database URL parser and SQLite/PostgreSQL builder
│   ├── steam.py                # Steam env → SteamClientConfig factory — SBGC-42
│   ├── security.py             # Host/origin/key validation — SBGC-41
│   ├── admin.py                # Admin URL validation and branding
│   ├── urls.py                 # Root URL configuration
│   ├── wsgi.py                 # WSGI entry point (defaults to production)
│   └── asgi.py                 # ASGI entry point (defaults to production)
├── api/                        # API routing composition (not a Django app)
│   ├── __init__.py
│   ├── urls.py                 # Mounts v1 NinjaAPI + catch-all fallback
│   ├── v1.py                   # NinjaAPI instance, handler registration, router mounting
│   ├── schemas.py              # Shared request/response/error schemas
│   ├── errors.py               # Exception handlers, error response builders
│   ├── system.py               # System router (GET /)
│   └── tests/
│       ├── __init__.py
│       ├── test_api_mounted.py # URL-level behaviour tests
│       └── test_schemas_errors.py  # Schema and error-handler tests
├── games/                      # Canonical game identity and metadata (SBGC-4)
│   ├── __init__.py
│   ├── apps.py                 # GamesConfig
│   ├── api.py                  # Games API router (no operations yet)
│   ├── models.py               # No models yet (SBGC-45)
│   ├── admin.py                # No admin registrations yet (SBGC-40)
│   ├── services/
│   │   └── steam/              # Steam Web API client — SBGC-42
│   │       ├── __init__.py     # Public re-exports
│   │       ├── config.py       # SteamClientConfig (immutable dataclass)
│   │       ├── client.py       # SteamClient (synchronous, injectable)
│   │       ├── cdn.py          # validate_steam_cdn_url()
│   │       └── errors.py       # Service-specific exception taxonomy
│   ├── tests/
│   │   └── services/steam/
│   │       └── test_steam.py   # 85 isolated Steam service tests
│   └── migrations/
│       └── __init__.py
├── classifications/            # Challenge and Reward classification records (SBGC-4)
│   ├── __init__.py
│   ├── apps.py                 # ClassificationsConfig
│   ├── api.py                  # Classifications API router (no operations yet)
│   ├── models.py               # No models yet (SBGC-46)
│   ├── admin.py                # No admin registrations yet (SBGC-40)
│   ├── tests.py                # No tests yet (SBGC-44)
│   └── migrations/
│       └── __init__.py
├── api/                        # API routing composition (not a Django app)
│   ├── __init__.py
│   └── urls.py                 # Empty urlpatterns — reserved for SBGC-38
├── manage.py                   # Development entry point
├── .env.example                # Environment variable template
├── requirements.txt            # Pinned Python dependencies
└── db.sqlite3                  # Local development database (gitignored)
```

## Composition Root (`config`)

The `config` package is the Django project composition root. It owns:

- Settings composition through environment-specific modules.
- Root URL configuration (`config/urls.py`).
- WSGI and ASGI entry points.

There is no generic `core`, `common`, `shared`, or `utils` application. Each Django app owns its concrete domain responsibility.

### Settings Modules

| Module                        | DEBUG | Entry point          |
| ----------------------------- | ----- | -------------------- |
| `config.settings.development` | True  | `manage.py`          |
| `config.settings.production`  | False | `wsgi.py`, `asgi.py` |

Settings selection occurs before the selected module loads its `.env` file. The entry points use `os.environ.setdefault()` so an explicit `DJANGO_SETTINGS_MODULE` or `--settings` flag remains authoritative.

**Explicit selection:**

```bash
# Development (default from manage.py)
python manage.py runserver

# Production check
python manage.py check --settings=config.settings.production

# Override via environment
DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check
```

### BASE_DIR

`BASE_DIR` resolves to `apps/backend/` under all settings modules. It is computed relative to `config/settings/base.py` as `Path(__file__).resolve().parent.parent.parent`.

## Application Boundaries

### `games`

**Ownership:** Canonical game identity, source-qualified game records, game metadata, catalogue concepts.

**Status:** Application scaffold only. No models or admin registrations exist yet. Models will be implemented in SBGC-4 (SBGC-45 onward). Future admin registrations belong in `games/admin.py`.

### `classifications`

**Ownership:** Separate Challenge and Reward profiles, Micro/Mystiko/Macro classification records, classification-domain concepts.

**Status:** Application scaffold only. No models or admin registrations exist yet. Models will be implemented in SBGC-4 (SBGC-46 onward). Future admin registrations belong in `classifications/admin.py`.

**Intended dependency direction:** `classifications` → `games` (classifications reference games; not circular).

### `api`

**Status:** Routing composition package — **not** a Django application and **not** registered in `INSTALLED_APPS`.

**Django Ninja 1.6.2** is configured with one `NinjaAPI` instance (`api/v1.py`) for version 1.0.0.

Mounted routers:
- `""` → System (`GET /api/v1/` — product name and version)
- `"/games/"` → Games (no operations yet)
- `"/classifications/"` → Classifications (no operations yet)

See [`docs/backend-api.md`](backend-api.md) for API contracts, error envelope, and exception handling.

**Reserved prefix:** `/api/v1/` — wired in `config/urls.py`.
- `GET /api/v1/` — API root (200)
- `GET /api/v1/openapi.json` — OpenAPI schema (200)
- `GET /api/v1/docs` — Swagger UI (development only)
- Unknown paths return standardised 404 JSON envelope.

### Database (`config/database.py`)

**Psycopg 3.3.4** is configured for PostgreSQL connectivity. The `build_database_config()` helper in `config/database.py` parses `DATABASE_URL` through `django-environ` and enforces environment-specific fallback policy.

- **Development:** SQLite fallback at `apps/backend/db.sqlite3` when `DATABASE_URL` is absent.
- **Production:** `DATABASE_URL` is **required** — missing/blank values raise `ImproperlyConfigured`.
- **Direct Neon connections only** — pooled hosts (`-pooler` in hostname) are not supported for the current connection mode.
- **SSL** (`sslmode=require`, `channel_binding=require`) and **connect_timeout=10** are enforced for PostgreSQL.
- **CONN_MAX_AGE=0** — no persistent connections or application-side pooling.

See [`docs/database-connectivity.md`](database-connectivity.md).

### Future `users`

A `users` application for final-product accounts is planned but not yet created. It is not required during the MVP foundation phase.

## Current Limitations

- **Steam service foundation** — SBGC-42 delivered the synchronous Steam HTTP client under `games/services/steam/` with immutable configuration, bounded retries, API-key header-only transmission, response-size enforcement, CDN URL validation, and an isolated test suite. Endpoint adapters and import workflows are deferred to SBGC-5.
- **No backend operations** — SBGC-43 will add logging, health endpoints, static handling, and Render startup.
- **No backend tests** — SBGC-44 will establish test settings and conventions.
- **No product models** — SBGC-4 (SBGC-45 onward) will implement domain models, constraints, and migrations.
- **Production settings are incomplete** — `config.settings.production` imports shared base settings and sets `DEBUG=False`. Full security hardening and deployment checks belong to SBGC-39 and SBGC-41.
- **`CORS_ALLOWED_ORIGINS` is inert** — it is parsed as a custom setting but does not yet control application behaviour. It is reserved for SBGC-41.
