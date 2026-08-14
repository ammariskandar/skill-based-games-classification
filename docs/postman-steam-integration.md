# Postman Steam Integration — SBGC-57

Postman collection, environment, and test scripts that exercise the authorized
Steam import and refresh HTTP endpoints against a local Django development
server.

## Files

| File | Purpose |
|------|---------|
| `postman/Skill-Based Games Classification.postman_collection.json` | Collection |
| `postman/local.postman_environment.json` | Local environment (no secrets) |
| `postman/README.md` | Setup and usage guide |

## Collection structure

| Group | Requests |
|-------|----------|
| `00 System` | `Health` |
| `01 Authentication` | `Acquire CSRF token`, `Login (establish staff session)` |
| `10 Steam Import` | `Valid import`, `Re-import same app`, `Invalid App ID`, `Missing body`, `Unauthorized import` |
| `20 Steam Refresh` | `Refresh captured Game`, `Manual Game rejection`, `Game not found`, `Unauthorized refresh` |

## Environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `base_url` | `http://127.0.0.1:8000` | Local backend |
| `admin_url_path` | `mygamedna-admin` | Must match `ADMIN_URL_PATH` |
| `steam_app_id` | `620` | Portal 2 (from seed data) |
| `game_id` | *(empty)* | Captured from a successful import |
| `manual_game_id` | *(empty)* | An existing manual Game ID |
| `username` / `password` | *(empty)* | Local-only staff/superuser credentials |

`username` and `password` are committed as **empty placeholders**. They are
local-only and must never be filled with real values in the repository.

## Authentication flow

The mutation endpoints require an authenticated staff session (Django session
auth). The collection reuses Django's existing Admin login rather than adding a
new auth endpoint:

1. `Acquire CSRF token` — GET the Admin login page to obtain the `csrftoken`
   cookie.
2. `Login (establish staff session)` — POST the Admin login form
   (`username`, `password`, `csrfmiddlewaretoken`) to establish `sessionid`.

Django rotates the CSRF cookie on login, so each authorized request runs a
pre-request script that reads the fresh `csrftoken` from the cookie jar and
sends it as `X-CSRFToken`. CSRF is **not** disabled; no bypass header is used.

## Test scripts

Post-response scripts assert real response shapes:

- **Valid import** — status `200`/`201`; `status` is a valid import status;
  `app_id` echoes the request; when a `game` is present, `source_type ==
  "steam"` and `external_id == steam_app_id`; captures `game_id`.
- **Re-import same app** — same `game_id`; `status` is `unchanged` or
  `updated`.
- **Refresh** — `status` in `updated`/`unchanged`/`unavailable`; same game
  identity; `last_steam_refresh_at` present when not `unavailable`.
- **Error cases** — assert the expected HTTP status and `error.code`.

`UPDATED` versus `UNCHANGED` on re-import/refresh depends on whether upstream
Steam metadata changed between calls; scripts accept either where that is the
correct domain outcome.

## No secrets

No `sessionid`, `csrftoken`, real username/password, production URL, or
production token is committed. The collection only references cookie/variable
placeholders.

## Live Steam note

Running the import/refresh requests against a local server will reach live
Steam. This is an **optional local smoke test**, not the formal SBGC-58
controlled live integration validation. Do not point the collection at
production Neon or Render.
