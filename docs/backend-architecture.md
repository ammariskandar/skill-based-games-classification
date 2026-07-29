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
│   ├── urls.py                 # Root URL configuration
│   ├── wsgi.py                 # WSGI entry point (defaults to production)
│   └── asgi.py                 # ASGI entry point (defaults to production)
├── games/                      # Canonical game identity and metadata (SBGC-4)
│   ├── __init__.py
│   ├── apps.py                 # GamesConfig
│   ├── models.py               # No models yet (SBGC-45)
│   ├── admin.py                # No admin registrations yet (SBGC-40)
│   ├── tests.py                # No tests yet (SBGC-44)
│   └── migrations/
│       └── __init__.py
├── classifications/            # Challenge and Reward classification records (SBGC-4)
│   ├── __init__.py
│   ├── apps.py                 # ClassificationsConfig
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

**Status:** Application scaffold only. No models, admin registrations, or tests exist yet. Models will be implemented in SBGC-4 (SBGC-45 onward).

### `classifications`

**Ownership:** Separate Challenge and Reward profiles, Micro/Mystiko/Macro classification records, classification-domain concepts.

**Status:** Application scaffold only. No models, admin registrations, or tests exist yet. Models will be implemented in SBGC-4 (SBGC-46 onward).

**Intended dependency direction:** `classifications` → `games` (classifications reference games; not circular).

### `api`

**Status:** Routing composition package — **not** a Django application and **not** registered in `INSTALLED_APPS`.

**Reserved prefix:** `/api/v1/` — wired in `config/urls.py`. All requests currently return 404 because no endpoints exist.

SBGC-38 will install and configure Django Ninja routers here.

### Future `users`

A `users` application for final-product accounts is planned but not yet created. It is not required during the MVP foundation phase.

## Current Limitations

- **No Django Ninja** — installation and configuration belongs to SBGC-38.
- **No PostgreSQL connectivity** — SBGC-39 will add a PostgreSQL driver and configure Neon connectivity.
- **No Admin configuration** — SBGC-40 will create superuser access, model registration patterns, and wire `ADMIN_URL_PATH`.
- **No security hardening** — SBGC-41 will enforce production secrets, hosts, CSRF, cookies, and request limits.
- **No Steam integration** — SBGC-42 will create the Steam service/client.
- **No backend operations** — SBGC-43 will add logging, health endpoints, static handling, and Render startup.
- **No backend tests** — SBGC-44 will establish test settings and conventions.
- **No product models** — SBGC-4 (SBGC-45 onward) will implement domain models, constraints, and migrations.
- **Production settings are incomplete** — `config.settings.production` imports shared base settings and sets `DEBUG=False`. Full security hardening and deployment checks belong to SBGC-39 and SBGC-41.
- **`ADMIN_URL_PATH` and `CORS_ALLOWED_ORIGINS` are inert** — they are parsed as custom settings but do not yet control application behaviour. They are reserved for SBGC-40 and SBGC-41 respectively.
