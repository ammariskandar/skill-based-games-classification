# Postman — Steam Import and Refresh API

Postman assets for exercising the SBGC-57 authorized Steam import and refresh
HTTP endpoints against a **local** Django development server.

- `Skill-Based Games Classification.postman_collection.json` — collection
- `local.postman_environment.json` — local environment (no secrets committed)

## What this covers

| Group | Requests |
|-------|----------|
| `00 System` | `Health` (public liveness probe) |
| `01 Authentication` | `Acquire CSRF token`, `Login (establish staff session)` |
| `10 Steam Import` | `Valid import`, `Re-import same app`, `Invalid App ID`, `Missing body`, `Unauthorized import` |
| `20 Steam Refresh` | `Refresh captured Game`, `Manual Game rejection`, `Game not found`, `Unauthorized refresh` |

The collection targets the real, implemented endpoints:

```text
GET  /health/
POST /api/v1/games/steam/import
POST /api/v1/games/{game_id}/steam/refresh
```

## Prerequisites

1. Start the Django development server locally.
2. Create a **staff** (or superuser) account if you do not have one:

   ```bash
   apps/backend/.venv/bin/python apps/backend/manage.py createsuperuser \
     --settings=config.settings.development
   ```

3. Import `local.postman_environment.json` into Postman and set the
   local-only variables:

   - `base_url` — `http://127.0.0.1:8000` by default.
   - `admin_url_path` — must match your `ADMIN_URL_PATH` (see
     `apps/backend/.env`; `mygamedna-admin` in `.env.example`, `admin` is the
     settings default).
   - `username` / `password` — your local staff/superuser credentials.
     **These are empty placeholders in this repo and must never be committed.**
   - `manual_game_id` — an existing manual (non-Steam) Game ID, used by the
     `Manual Game rejection` request. Leave empty if you only need the import
     and refresh happy paths.

4. Enable Postman's **cookie jar** for `127.0.0.1` so `sessionid` and
   `csrftoken` are captured and replayed.

## Authentication flow (session + CSRF)

These endpoints mutate canonical Games and may trigger outbound Steam calls,
so they require an **authenticated staff session**. The project uses Django
session authentication — no API keys or bearer tokens.

Run the `01 Authentication` group in order:

1. **Acquire CSRF token** — `GET /{{admin_url_path}}/login/` issues the
   `csrftoken` cookie and captures it into `{{csrf_token}}`.
2. **Login (establish staff session)** — `POST /{{admin_url_path}}/login/`
   submits `username`, `password`, and `csrfmiddlewaretoken={{csrf_token}}`,
   reusing Django's existing Admin login. This establishes the `sessionid`
   cookie.
3. **Acquire CSRF token (again)** — Django rotates the CSRF cookie on login,
   so re-run step 1 to refresh `{{csrf_token}}` with the post-login value.

Authorized mutation requests send `X-CSRFToken: {{csrf_token}}` as a static
header (no pre-request script). CSRF is **not** disabled and there is no
bypass header.

## Expected responses

### Import — `POST /api/v1/games/steam/import`

Request body (string App ID only):

```json
{ "app_id": "620" }
```

Response `200`/`201`:

```json
{
  "status": "created | updated | unchanged | unavailable",
  "app_id": "620",
  "game": {
    "id": 1,
    "source_type": "steam",
    "external_id": "620",
    "name": "Portal 2",
    "slug": "portal-2",
    "content_type": "game",
    "listing_status": "draft",
    "steam_image_url": "",
    "last_steam_refresh_at": null
  }
}
```

- `CREATED` → `201`; `UPDATED` / `UNCHANGED` / `UNAVAILABLE` → `200`.
- `UNAVAILABLE` carries `"game": null` (no Game is invented).
- Re-importing the same App ID returns the **same** `game.id`.

### Refresh — `POST /api/v1/games/{game_id}/steam/refresh`

No request body. The internal `game_id` in the path identifies the Game; the
persisted Steam identity is the only App ID used.

Response `200`:

```json
{
  "status": "updated | unchanged | unavailable",
  "game": { "...": "..." },
  "changed_fields": ["name"]
}
```

`changed_fields` is empty for `unchanged`/`unavailable`; `last_steam_refresh_at`
is set on successful (`updated`/`unchanged`) verifications.

## Status / error mapping

| Condition | HTTP | `error.code` |
|-----------|------|--------------|
| Missing/null/non-string `app_id` | 422 | `VALIDATION_ERROR` |
| Invalid Steam App ID string | 400 | `BAD_REQUEST` |
| Not authenticated | 401 | `AUTHENTICATION_ERROR` |
| Authenticated non-staff | 403 | `AUTHORIZATION_ERROR` |
| CSRF failure | 403 | framework mapping |
| Game not found | 404 | `NOT_FOUND` |
| Manual Game refresh | 400 | `BAD_REQUEST` |
| Steam rate limited | 429 | `RATE_LIMITED` |
| Steam transport/data failure | 503 | `SERVICE_UNAVAILABLE` |
| Unexpected failure | 500 | `INTERNAL_SERVER_ERROR` |

`Steam app unavailable` is a **domain outcome** (import/refresh `status` of
`unavailable`), never a `500`.

## Running the happy path

1. Run `01 Authentication` (Acquire CSRF, then Login).
2. Run `10 Steam Import > Valid import` — it captures `game_id`.
3. Run `10 Steam Import > Re-import same app` — asserts same identity.
4. Run `20 Steam Refresh > Refresh captured Game` — uses `{{game_id}}`.

The `Unauthorized import` / `Unauthorized refresh` requests must be run
**without** an established session (clear cookies first, or run before
`01 Authentication`).

## Live Steam note

The import and refresh endpoints will reach real Steam during manual testing.
That is an **optional local smoke test**, not the formal SBGC-58 controlled
live integration validation. Do not run this collection against production
Neon or Render.
