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
│   ├── models.py               # Game model + GameQuerySet (SBGC-45/48/49/55/56)
│   ├── admin.py                # GameAdmin + Steam refresh action (SBGC-45/56)
│   ├── types.py                # ContentType, CONTENT_TYPE_CHOICES (ORM-free) — SBGC-53
│   ├── services/
│   │   ├── steam/              # Steam service package — SBGC-42/168/53
│   │   │   ├── __init__.py     # Public re-exports
│   │   │   ├── constants.py    # Immutable origins — SBGC-168
│   │   │   ├── config.py       # SteamClientConfig (immutable dataclass)
│   │   │   ├── client.py       # SteamClient (synchronous, injectable)
│   │   │   ├── cdn.py          # validate_steam_image_url / validate_steam_cdn_url
│   │   │   ├── errors.py       # Service-specific exception taxonomy
│   │   │   ├── dto.py          # SteamAppId, DTOs, LookupStatus — SBGC-53
│   │   │   ├── mapping.py      # map_steam_product_type() — SBGC-53
│   │   │   ├── import_foundation.py  # SteamImportFoundation — SBGC-53
│   │   │   └── adapters/
│   │   │       ├── __init__.py      # Adapter error taxonomy
│   │   │       └── app_details.py   # SteamAppDetailsAdapter
│   │   └── imports/            # Steam import persistence + refresh — SBGC-54/56
│   │       ├── __init__.py     # Public re-exports
│   │       └── steam.py        # Persistence/import/refresh services, slug helper, results
│   │   └── manual.py           # Manual Game create/edit service — SBGC-59
│   ├── tests/
│   │   ├── services/steam/
│   │   │   ├── test_steam.py   # Steam transport tests
│   │   │   ├── test_dto.py
│   │   │   ├── test_mapping.py
│   │   │   ├── test_app_details_adapter.py
│   │   │   ├── test_import_foundation.py
│   │   │   └── test_image_validation.py  # SBGC-55
│   │   ├── services/imports/
│   │   │   ├── test_steam_persistence.py
│   │   │   ├── test_steam_import.py
│   │   │   └── test_steam_refresh.py   # SBGC-56
│   │   ├── test_steam_slugging.py
│   │   ├── test_admin_refresh.py       # SBGC-56 Admin action
│   │   └── test_import_concurrency.py  # PostgreSQL-only race verification
│   └── migrations/
│       ├── 0001_initial.py
│       ├── 0002_alter_game_content_type.py
│       ├── 0003_migrate_other_to_unknown.py
│       ├── 0004_game_steam_image_url.py     # SBGC-55
│       ├── 0005_game_last_steam_refresh_at.py  # SBGC-56
│       └── 0006_game_developer_game_release_date.py  # SBGC-59
├── classifications/            # Challenge and Reward classification records (SBGC-4)
│   ├── __init__.py
│   ├── apps.py                 # ClassificationsConfig
│   ├── api.py                  # Classifications API router (no operations yet)
│   ├── models.py               # EditorialClassification, ChallengeProfile, RewardProfile (SBGC-46)
│   ├── admin.py                # EditorialClassificationAdmin with inlines (SBGC-46)
│   ├── skills.py               # SkillCategory, EditorialProfile, dominant helper (SBGC-49)
│   ├── validation.py           # validate_score_distribution (SBGC-46)
│   ├── tests/                  # Test package with 5 modules
│   └── migrations/
│       └── __init__.py
├── api/                        # API routing composition (not a Django app)
│   ├── __init__.py
│   ├── urls.py                 # Mounts v1 NinjaAPI + catch-all fallback (SBGC-38)
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

**Ownership:** Canonical game identity, source-qualified game records, game metadata, catalogue concepts, Steam integration.

**Status (SBGC-45 through SBGC-59):** `Game` model, `GameQuerySet` (9 custom query methods), `GameAdmin` (with the manual Steam refresh action and source-identity protection), `ContentType` vocabulary, canonical listing rules, and query helpers.  Steam transport (`SteamClient` with hardened retry/CDN/error taxonomy), endpoint adapters (`SteamAppDetailsAdapter`), and import-foundation DTOs (`SteamImportFoundation.prepare_candidate()`) are implemented.  SBGC-54 added the persistence boundary (`SteamGameImportService` / `SteamGamePersistenceService`) — see `docs/steam-import-workflow.md`.  SBGC-55 added validated Steam image-URL persistence (`steam_image_url`) — see `docs/steam-images.md`.  SBGC-56 added metadata refresh (`SteamGameRefreshService`, `last_steam_refresh_at`, Admin action) — see `docs/steam-metadata-refresh.md`.  SBGC-57 added authorized HTTP import and refresh endpoints — see `docs/steam-api.md`.  SBGC-59 added manual Game create/edit (`release_date`, `developer`, source identity protection) — see `docs/manual-game-management.md`.  Periodic/background refresh is not implemented.

### `classifications`

**Ownership:** Separate Challenge and Reward profiles, Micro/Mystiko/Macro classification records, classification-domain concepts.

**Status:** `EditorialClassification`, `ChallengeProfile`, and `RewardProfile` models implemented in SBGC-46 — one editorial classification per Game with independent Challenge/Reward score profiles, Admin with two inlines, and an atomic service layer.  Admin validation completed in SBGC-51.  Community classifications and API endpoints remain unimplemented.

**Intended dependency direction:** `classifications` → `games` (classifications reference games; not circular).

### Query Layer (`games/models.py` — `GameQuerySet`)

Reusable queryset helpers live on `GameQuerySet` (SBGC-48 / SBGC-49):
- `publicly_listable()` — canonical public listing rule
- `steam()` / `manual()` — source-type filtering
- `editorially_classified()` — requires complete parent + both profiles
- `with_editorial_profiles()` — `select_related` for N+1-safe joins
- `with_dominant_skill_categories()` — SQL-level dominant-skill annotations
- `filter_by_dominant_skill_category()` — dominant-category filtering
- `filter_by_editorial_score()` / `order_by_editorial_score()` — score
  range filtering and deterministic sorting

Skill vocabularies and pure helpers live in `classifications/skills.py`
(SBGC-49).  See `docs/game-query-helpers.md` for the canonical inventory.

### `api`

**Status:** Routing composition package — **not** a Django application and **not** registered in `INSTALLED_APPS`.

**Django Ninja 1.6.2** is configured with one `NinjaAPI` instance (`api/v1.py`) for version 1.0.0.

Mounted routers:
- `""` → System (`GET /api/v1/` — product name and version)
- `"/games/"` → Games (Steam import + refresh mutations — SBGC-57)
- `"/classifications/"` → Classifications (no operations yet)

See [`docs/backend-api.md`](backend-api.md) for API contracts, error envelope, and exception handling, and [`docs/steam-api.md`](steam-api.md) for the Steam import/refresh endpoints.

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

- **Steam service foundation** — SBGC-42 delivered the synchronous Steam HTTP client with immutable configuration, bounded retries, API-key header-only transmission, response-size enforcement, CDN URL validation, and an isolated test suite. SBGC-168 hardened transport boundaries (immutable origins, operation budget ceiling, status-first error processing). SBGC-53 delivered Store endpoint adapters (`SteamAppDetailsAdapter`) and import-foundation DTOs (`SteamImportFoundation.prepare_candidate()`). SBGC-54 delivered candidate-to-Game persistence (`games/services/imports/`). SBGC-55 delivered validated Steam image-URL persistence. SBGC-56 delivered metadata refresh (service + Admin action). SBGC-57 delivered authorized HTTP import/refresh endpoints. Public read endpoints, periodic refresh, and the remaining DTO metadata persistence are not implemented.
- **Backend operations** — SBGC-43 delivered Gunicorn/WhiteNoise, health endpoint, production logging, PostgreSQL-only enforcement, strengthened secret/CSRF validation, Render Blueprint, deployment checks, and operational scripts. See docs/backend-operations.md.
- **Backend testing** — SBGC-44 established test conventions, discovery audit, subprocess isolation, and canonical testing documentation. See docs/backend-testing.md.
- **SBGC-4 domain models complete** — SBGC-45 through SBGC-50 implemented the Game model, editorial classification, database constraints, content types, listing rules, query helpers, and development seed data.  SBGC-51 added Admin validation tests.
- **No public game read endpoints** — Public game/classification read endpoints and pages are deferred to SBGC-9 and SBGC-10.  SBGC-57 added the authorized Steam import/refresh mutation endpoints.
- **Steam persistence exists, import/refresh API exists** — Candidate-to-Game persistence is complete (SBGC-54, `games/services/imports/`), Steam image URLs persist (SBGC-55), manual metadata refresh exists as a service + Admin action (SBGC-56), and authorized HTTP import/refresh endpoints exist (SBGC-57).  Periodic/background refresh and the remaining DTO metadata persistence are deferred to later tickets.
