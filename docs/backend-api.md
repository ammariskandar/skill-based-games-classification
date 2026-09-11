# Backend API

Django Ninja API for the MyGameDNA skill-based games classification platform.

## API Version

| Attribute       | Value             |
| --------------- | ----------------- |
| Product name    | MyGameDNA API     |
| Version         | 1.0.0             |
| URL prefix      | `/api/v1/`        |
| OpenAPI schema  | `/api/v1/openapi.json` |
| Interactive docs| `/api/v1/docs` (development only) |

One `NinjaAPI` instance is created per major API version. The current v1
instance lives at `api/v1.py`.

## Architecture

```
Browser  →  Astro SSR  →  frontend transport  →  /api/v1/  →  Django Ninja
```

- **One server API path.** Browser code never calls Django directly.
- **One `NinjaAPI` per major version.** New major versions create a new instance;
  minor additions extend the existing routers.

## Router Ownership

| Router            | Module                          | Tag              | Status            |
| ----------------- | ------------------------------- | ---------------- | ----------------- |
| System            | `api/system.py`                 | System           | `GET /` active    |
| Games             | `games/api.py`                  | Games            | Steam import + refresh (SBGC-57); public game detail (SBGC-71); homepage carousel (SBGC-189); similar Games (SBGC-227) |
| Classifications   | `classifications/api.py`        | Submissions      | Community score submission (SBGC-216); delta recalculation trigger (SBGC-174) |
| Questionnaire     | `classifications/questionnaire/api.py` | Questionnaire | Aesthetic resolution (SBGC-172) |

Routers own domain-specific endpoints.  Domain models and services are
implemented (SBGC-45 through SBGC-56).  SBGC-57 added authorized Steam
import and refresh mutations on the Games router:
`POST /api/v1/games/steam/import` and
`POST /api/v1/games/{game_id}/steam/refresh` — see `docs/steam-api.md`.
SBGC-71 added the public read endpoint `GET /api/v1/games/{slug}` — see the
Game detail section below. SBGC-189 added `GET /api/v1/games/homepage` for the
homepage Steam carousel — see the Homepage Carousel section below. SBGC-216
added the community score submission endpoint, SBGC-172 added questionnaire
aesthetic resolution — see the Questionnaire sections below — and SBGC-174
added the delta recalculation trigger. SBGC-227 added
`GET /api/v1/games/{slug}/similar` — see the Similar Games section below.

## Request Schemas

All request schemas inherit from `ApiRequestSchema`, which configures
Pydantic v2 to **reject unknown/extra fields** (`extra="forbid"`).
Misspelled or unsupported keys produce a `VALIDATION_ERROR` rather than
being silently ignored.

## Response Schemas

Every endpoint explicitly declares its response schema. No endpoint returns
untyped `dict` or raw Django models. Use `ninja.Schema` subclasses, not
`ModelSchema`, until database models exist.

### Standard Error Responses

All endpoint operations must include standard error-response declarations:

```python
from api.errors import STANDARD_ERROR_RESPONSES

@router.get("/path", response={200: SomeSchema, **STANDARD_ERROR_RESPONSES})
```

`STANDARD_ERROR_RESPONSES` maps Django Ninja's grouped `codes_4xx` and
`codes_5xx` status-code sets (`frozenset` objects from `ninja.responses`)
to `ApiErrorResponse`, producing correct OpenAPI error documentation with
concrete HTTP status codes (400, 401, 403, 404, 500, 503, etc.) rather than
invalid group keys "4" and "5" — SBGC-167.

**Note:** Django Ninja's `codes_4xx` does **not** include 422 (Unprocessable
Entity).  Endpoints that return explicit 422 responses must declare it
separately alongside `STANDARD_ERROR_RESPONSES`:

```python
@router.get("/endpoint", response={
    200: SuccessSchema,
    **STANDARD_ERROR_RESPONSES,
    422: ApiErrorResponse,
})
```

The explicit int key `422` does not collide with the `codes_4xx` frozenset
key — they are distinct dictionary keys.  Framework validation-error handlers
return 422 directly through the Ninja exception-handler path and do not rely
on the operation response declaration.

### Response Status Codes

Use `Status(status, body)` from `ninja` for explicit non-default statuses.
Do not use the deprecated `(status, body)` tuple syntax.

## Game Catalogue — `GET /api/v1/games/`

Returns a deterministic, paginated list of publicly-listed base Games
(`content_type == game AND listing_status == published`).  It is **read-only**:
it never contacts Steam, never probes images, and never recalculates
classification.  Draft/archived and non-game content (DLC, demo, software,
soundtrack, unknown) are excluded from both `results` and `count`.

### Query parameters

| Parameter | Type | Default | Meaning |
|-----------|------|---------|---------|
| `q` | string | — | case-insensitive `name` substring search (trimmed; whitespace-only is no filter) |
| `source` | `steam` / `manual` | — | restrict to one source; omitted means both |
| `classified` | boolean | — | `true` = has a current published READY classification; `false` = no displayable scores |
| `sort` | `name_asc` / `name_desc` / `recent` / `micro` / `mystiko` / `macro` | `name_asc` | primary sort (see below) |
| `profile` | `challenge` / `reward` | `challenge` | explicit profile for `micro`/`mystiko`/`macro` sort and the `dominant` filter |
| `dominant` | `micro` / `mystiko` / `macro` | — | dominant-category filter against the published current READY snapshot (strictly-highest wins; top-score ties match none) |
| `coverless_last` | boolean | `true` | outer partition before pagination: Games without an effective Capsule go after Games with one |
| `page` | positive int | `1` | 1-based page number |
| `page_size` | positive int | `24` | results per page (max `100`) |

Filters are AND-composed.  `classified=true` means the Game currently has a
current `ClassificationSnapshot` with `status == READY` (including a stale
READY result retained after an engine/system failure); every other state —
`NO_SNAPSHOT`, a current non-READY domain status, etc. — is `classified=false`.
This matches the published-read semantics of the Game-detail endpoint and is
driven by persisted state, never by a recalculation.

### Primary sort

`sort` selects the primary order; deterministic tie-breakers always apply.

- `name_asc` (default) → `name ASC, id ASC`.
- `name_desc` → `name DESC, id ASC`.
- `recent` → `created_at DESC, name ASC, id ASC` (`recent` keys off
  `Game.created_at`, **not** `release_date`).
- `micro` / `mystiko` / `macro` → the selected `profile`'s published current
  READY unified-integer score, highest first; Games without a usable READY
  score sort after scored Games, then `name ASC, id ASC`.

Score sorting reads `ClassificationSnapshot.unified_integer_{challenge,reward}`
(canonical order `[micro, macro, mystiko]`) from the current READY snapshot only
— never the editorial submission tables, never raw Method 1/2/3 results.

### Dominant-category filter

`dominant` filters against the selected `profile`'s published current READY
snapshot.  Dominance is **strictly highest** (the canonical
`classifications.skills.dominant_skill_category` rule): a top-score tie has no
dominant category and therefore matches no `micro`/`mystiko`/`macro` filter.

### Cover-last partition

When `coverless_last=true` (the default), Games with an effective Capsule URL
(Steam manual-override-else-Library-Capsule; Manual manual Capsule — SBGC-190)
come before Games without one, **before** the count/pagination slice, so the
policy is globally correct across pages.  This outer partition is applied on top
of whichever primary sort is selected.  A general/header image is **not** a
Capsule.  `coverless_last=false` removes the partition and lets the primary sort
govern the whole population.

### Response envelope

```json
{
  "count": 42,
  "page": 1,
  "page_size": 24,
  "total_pages": 2,
  "results": [
    {
      "slug": "hades",
      "name": "Hades",
      "source": "steam",
      "image_url": "https://...",
      "library_capsule_url": "https://...",
      "classification": {
        "status": "READY",
        "challenge": {"micro": 51, "macro": 31, "mystiko": 18},
        "reward": {"micro": 17, "macro": 29, "mystiko": 54},
        "confidence_level": 85.5,
        "confidence_label": "High",
        "is_stale": false
      }
    }
  ]
}
```

`count` is the filtered count; `total_pages` is `0` when `count` is `0`.
Ordering is deterministic: the default primary sort is `name ASC, id ASC`;
skill sorts order by the published READY score descending with unscored Games
last; and `coverless_last=true` applies a cover-last outer partition before
pagination.  A page beyond the final page returns `200` with `results: []`.
`image_url` and `library_capsule_url` are effective values (manual override
first, Steam fallback — SBGC-190); the frontend never resolves override
precedence.  `classification` is `null` when the Game has no displayable scores
(no fake zero vectors).

## Game Rankings — `GET /api/v1/rankings/`

Returns a deterministic, paginated ranking of publicly-listed base Games that
have a current READY `ClassificationSnapshot` with the score data required for
the requested profile.  It is **read-only**: never contacts Steam, never probes
images, never recalculates classification.  Draft/archived and non-game content,
Games without a current READY snapshot, and Games missing the required score
data are excluded from both `results` and `count`.  Missing Hero artwork does
not exclude an otherwise rankable Game.

### Query parameters

| Parameter | Type | Default | Meaning |
|-----------|------|---------|---------|
| `profile` | `unified` / `challenge` / `reward` | `unified` | ranking profile (see below) |
| `dimension` | `micro` / `mystiko` / `macro` | `micro` | skill dimension to rank by |
| `direction` | `desc` / `asc` | `desc` | score order (high→low or low→high) |
| `dominant` | `micro` / `mystiko` / `macro` | — | dominant-category filter (strictly-highest; top-score ties match none) |
| `page` | positive int | `1` | 1-based page number |
| `page_size` | positive int | `24` | results per page (max `100`) |

### Profile semantics

- `challenge` — the selected dimension of
  `ClassificationSnapshot.unified_integer_challenge`.
- `reward` — the selected dimension of
  `ClassificationSnapshot.unified_integer_reward`.
- `unified` — a presentation-only profile equal to
  `(challenge + reward) / 2` for the selected dimension.  It is **not** a
  separate persisted classification.

The canonical vector order is `[micro, macro, mystiko]`.  Unified scores may be
a whole number (e.g. `80 + 60 → 70`) or `.5` (e.g. `80 + 55 → 67.5`); `.5` is
never rounded away.  Database-side ordering uses the doubled integer
`challenge + reward`, so Unified ordering is integer-exact; the public `score`
is halved only when serialized.

### Dominant-category filter

`dominant` filters against the selected `profile`'s published current READY
snapshot.  For `challenge`/`reward`, dominance is the strictly-highest of the
three dimensions; for `unified`, dominance is the strictly-highest of the three
summed dimensions (`challenge_micro + reward_micro`, and so on).  A top-score
tie has no dominant category and matches no filter.  Filtering happens before
ordering and pagination.

### Response envelope

```json
{
  "count": 30,
  "page": 1,
  "page_size": 24,
  "total_pages": 2,
  "results": [
    {"slug": "hades", "name": "Hades", "hero_url": "https://...", "score": 70},
    {"slug": "portal-2", "name": "Portal 2", "hero_url": "", "score": 67.5}
  ]
}
```

- `score` is the selected profile's dimension score: an integer for
  `challenge`/`reward`, and `(challenge + reward) / 2` for `unified` (an
  integer or a `.5` value).
- `hero_url` is the effective Hero artwork (Steam
  `manual_hero_url || library_hero_url`; Manual `manual_hero_url` — SBGC-190).
  It is an empty string for a Game with no Hero; such Games are still ranked.
- Ordering is deterministic: `score` (selected direction) → `name ASC` → `id ASC`.
  Only the score reverses for `asc`; name/id tie-breakers stay ascending.
- `count` is the filtered count; `total_pages` is `0` when `count` is `0`.
  A page beyond the final page returns `200` with `results: []`.

## Public Game Detail — `GET /api/v1/games/{slug}`

Returns the normalized public identity and persisted metadata for one
publicly-listed base Game, plus its currently persisted Final Classification
(if any).  It is a **read-only** endpoint: it never contacts Steam, never
refreshes metadata, and never recalculates classification.

### Public eligibility

A Game resolves only when it is **publicly listable** — the canonical
`Game.objects.publicly_listable()` policy:

```text
content_type == game AND listing_status == published
```

Steam and Manual Games are both canonical Games and share this endpoint.
Slug is the lookup key (`Game.slug` is globally unique).

### 404 behavior

Unknown slug, hidden/draft, archived, and non-game content (dlc, demo,
software, soundtrack, unknown) all return identically:

```json
404 GAME_NOT_FOUND
```

A hidden record is indistinguishable from a missing one publicly.

### Game payload

The `game` object exposes the public subset: `id`, `slug`, `name`, `source`
(`steam` / `manual`), `external_id` (Steam App ID, or `null` for Manual),
`content_type`, `description` (Steam-populated for Steam Games unless
overridden in Admin; manual for Manual Games), `release_date`, `developer`,
`image_url`, and `metadata_updated_at`.

The three artwork fields are **effective** values (SBGC-190) — Django resolves
manual-override precedence, so the frontend never does `manual ?? steam`:

- `image_url` — effective general/header image (`manual_image_url` overrides
  `steam_image_url` for Steam Games);
- `library_hero_url` — effective Hero (`manual_hero_url` overrides the Steam
  Library Hero);
- `library_capsule_url` — effective Capsule (`manual_capsule_url` overrides the
  Steam Library Capsule).

These are `null` when no effective value exists (for example, a Manual Game
with no manual Hero/Capsule, or a Steam Game with neither Steam nor manual
Library artwork).

### Classification payload

`classification` is `null` when no Final Classification record exists.
Otherwise it exposes the persisted current published result:

- `status` — the canonical calculation status (`READY`, `NO_SUBMISSIONS`,
  `INSUFFICIENT_ANCHOR`, …);
- `regime` — `provisional`, `unified`, or `none`;
- `challenge` / `reward` — `{micro, macro, mystiko}` when published, `null`
  when the status is a legitimate non-ready domain outcome;
- `confidence_level` / `confidence_label`;
- `submission_count`, `calculation_version`, `calculated_at`, `is_stale`.

No scores are fabricated for non-ready statuses, and a non-ready result is
returned as-is (never converted to `404` and never replaced by a stale score).

### Human verification

Completed on local SQLite (no live Steam, no engine run). All three checks
passed: a public classified Game returned 200 with normalized fields and the
persisted READY Challenge/Reward + confidence; a public Game without
classification returned `classification: null` (no fake zeros); and
hidden/non-game/unknown slugs returned `404 GAME_NOT_FOUND` with no
hidden-record disclosure.

## Similar Games — `GET /api/v1/games/{slug}/similar`

Returns the precomputed similar-Game recommendations for one publicly-listed
base Game (SBGC-227). It is **read-only**: it reads persisted `GameSimilarity`
rows only and never recalculates similarity.

### Eligibility & ordering

The slug must resolve under the canonical `publicly_listable()` policy;
otherwise `404 GAME_NOT_FOUND`. Results are ordered by descending similarity
score (ties broken by target name, then id). A target Game is still filtered
for current public eligibility, so a Game unpublished since the last engine run
cannot leak into the list.

### Query parameters

- `limit` — 1–24 (default `6`); values outside the range are rejected `422`.

### Response

```json
{
  "count": 4,
  "results": [
    {
      "slug": "dead-cells",
      "name": "Dead Cells",
      "capsule_url": "https://assets.mygamedna.com/capsules/dead-cells.webp",
      "similarity_score": 78
    }
  ]
}
```

- `capsule_url` — effective Capsule (`manual_capsule_url` overrides the Steam
  Library Capsule — SBGC-190), or `null` when absent;
- `similarity_score` — the persisted integer percentage (0–100).

Scores are produced by the `compute_similarities [--delta | --full]` management
command (see `docs/backend-architecture.md`).

## Game Search Index — `GET /api/v1/games/search-index`

Returns the **complete** compact public Game search index used by the frontend
header autocomplete (SBGC-78). It is **read-only**: it never contacts Steam,
never probes images, and never recalculates classification.

### Eligibility & ordering

A Game is included only when it is **publicly listable** — the canonical
`Game.objects.publicly_listable()` policy (`content_type == game AND
listing_status == published`). Both Steam and Manual Games are included;
draft/archived and non-game content (dlc, demo, software, soundtrack, unknown)
are excluded. A Game with no Capsule is still included (the autocomplete falls
back to a placeholder). Ordering is deterministic (`name ASC, id ASC`).

### Response

```json
{
  "games": [
    {
      "slug": "hades",
      "name": "Hades",
      "capsule_url": "https://...",
      "image_url": "https://..."
    }
  ]
}
```

- `capsule_url` — effective Capsule (`manual_capsule_url` overrides the Steam
  Library Capsule — SBGC-190), or `null` when absent;
- `image_url` — effective general image (thumbnail fallback), or `null` when
  absent.

Only the fields needed to render a suggestion are returned — no classification,
description, Hero, raw source fields, or override provenance.

## Homepage Carousel — `GET /api/v1/games/homepage`

Returns up to 10 randomly selected Games for the homepage Steam carousel. It is
**read-only**: it never contacts Steam and never recalculates classification.

### Eligibility

A Game is eligible only when it is:

```text
publicly_listable AND source_type == steam AND library_capsule_url != ""
```

`publicly_listable` is the canonical `content_type == game AND listing_status
== published` policy. Manual Games, non-game Steam content, hidden/draft/
archived Games, and Steam Games without a Library Capsule are excluded.

### Selection

Selection is a single `ORDER BY RANDOM()` limited to 10 rows. Random ordering
happens per request; if fewer than 10 eligible Games exist, the available count
is returned.

### Response

```json
{
  "games": [
    { "slug": "hades", "name": "Hades", "library_capsule_url": "https://..." }
  ]
}
```

Only the carousel card fields are returned — `slug`, `name`,
`library_capsule_url`. No classification objects are included.

Every error response follows this structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": [
      {
        "location": ["body", "field"],
        "message": "Field required",
        "type": "missing"
      }
    ]
  }
}
```

- **`code`** — machine-readable uppercase snake_case identifier.
- **`message`** — safe human-readable description. Never contains stack
  traces, exception class names, input values, or internal paths.
- **`details`** — always an array (empty `[]` when no per-field detail
  exists).

### Machine Codes

| Code                    | HTTP | Source                                    |
| ----------------------- | ---- | ----------------------------------------- |
| `VALIDATION_ERROR`      | 422  | Schema validation failure                 |
| `AUTHENTICATION_ERROR`  | 401  | Missing or invalid credentials            |
| `AUTHORIZATION_ERROR`   | 403  | Insufficient permissions                  |
| `NOT_FOUND`             | 404  | Resource not found                        |
| `GAME_NOT_FOUND`        | 404  | Public game not found (hidden/non-game/unknown) |
| `BAD_REQUEST`           | 400  | Generic client error                      |
| `METHOD_NOT_ALLOWED`    | 405  | HTTP method not supported                 |
| `CONFLICT`              | 409  | Resource conflict                         |
| `RATE_LIMITED`          | 429  | Too many requests                         |
| `SERVICE_UNAVAILABLE`   | 503  | Upstream or transient failure             |
| `HTTP_ERROR`            | 4xx/5xx | Unmapped HTTP error                  |
| `INTERNAL_SERVER_ERROR` | 500  | Unexpected exception                      |

Project code can raise `ApiException` with any custom code and status.

## Questionnaire — `POST /api/v1/questionnaire/resolve-aesthetic`

Resolves a publicly-listed Game's dominant and secondary aesthetics from its
Q1/Q2 answers and returns the Part 1 (Challenge) / Part 2 (Reward) question-set
dispatch contract (SBGC-172).  It is a **pure resolver**: it never writes
`Game.aesthetic` or any submission record — canonical persistence and
precedence handling belong to SBGC-175 / SBGC-176.

### Request

```json
{
  "game_slug": "hades",
  "q1_option_id": "OPT_S1",
  "q2_option_id": "OPT_F1"
}
```

### Eligibility

The Game must be publicly listable (`content_type == game` and
`listing_status == published`).  Unknown, hidden, non-game, and non-existent
slugs return `404 NOT_FOUND`.

### Resolution

- `SENSORY` / `FANTASY` / `NARRATIVE` / `CHALLENGE` in Q1 and Q2 form either a
  **true aesthetic** (identical categories, or a Collaborative/None collapse)
  or a **hybrid aesthetic** (two different categories; Q1 dominates).
- Hybrid Part 2 splits: `q9_to_q11_set` comes from the secondary aesthetic and
  `q12_to_q14_set` from the dominant one.
- `OPT_COL` + `OPT_NONE` resolves to the reserved `SPECIAL_FLOW` outcome (all
  sets `SPECIAL`).

### Response

```json
{
  "game_slug": "hades",
  "game_name": "Hades",
  "dominant_aesthetic": "SENSORY",
  "secondary_aesthetic": "FANTASY",
  "is_true_aesthetic": false,
  "part1_challenge_set": "1A",
  "part2_reward_config": {
    "is_split": true,
    "q9_to_q11_set": "2B",
    "q12_to_q14_set": "2A"
  }
}
```

Unknown options, `OPT_NONE` in Q1, and replaying the Q1 option in Q2 return
`422 VALIDATION_ERROR`.  See `docs/questionnaire-epic-sbgc-171.md`.

## Questionnaire — `POST /api/v1/questionnaire/assemble-tree`

Resolves the same Q1/Q2 aesthetics and additionally returns the concrete
versioned (`v1.0.0`) question graph for that session (SBGC-173).  It is a
**pure read**: it never writes `Game.aesthetic` or any submission.

### Request

```json
{
  "game_slug": "hades",
  "q1_option_id": "OPT_S1",
  "q2_option_id": "OPT_F1"
}
```

### Eligibility & routing

The Game must be publicly listable (`content_type == game` and
`listing_status == published`); otherwise `404 NOT_FOUND`.

- **Part 1 (`part1_challenge_nodes`)** — always the dominant set's Q3–Q8 plus
  child branch nodes.
- **Part 2 (`part2_reward_nodes`)** — the dominant set's Q9–Q14 for a true
  aesthetic, or a 50/50 split for a hybrid: Q9–Q11 from the secondary set and
  Q12–Q14 from the dominant set.  Child branch nodes always stay with their
  root.

### Response

```json
{
  "version": "v1.0.0",
  "game_slug": "hades",
  "game_name": "Hades",
  "dominant_aesthetic": "SENSORY",
  "secondary_aesthetic": "FANTASY",
  "is_true_aesthetic": false,
  "part1_challenge_nodes": [
    {
      "id": "Q3",
      "root_id": "Q3",
      "text": "How much does precise physical input affect what happens?",
      "target": "CHALLENGE",
      "options": [
        {
          "id": "Q3_a_lot_missing_a_dodge_shot_combo_jump_or_timing_window_can_quickly_cause_failure_or_heavy_damage",
          "text": "A lot: Missing a dodge, shot, combo, jump, or timing window can quickly cause failure or heavy damage.",
          "modifiers": { "micro": 20, "macro": 0, "mystiko": 0 },
          "next_question_id": null
        }
      ],
      "is_branch": false,
      "parent_id": null,
      "helper_text": null
    }
  ],
  "part2_reward_nodes": []
}
```

Unknown options return `422 VALIDATION_ERROR`; the reserved
`SPECIAL_FLOW` outcome cannot be assembled and also returns `422`.  See
`docs/questionnaire-epic-sbgc-171.md` for the full registry layout.

## Questionnaire Session & Submission

Authenticated persistence endpoints (SBGC-176).  Both require a session and a
publicly-listed Game (otherwise `401` / `404`).

### `GET /api/v1/questionnaire/{slug}/session`

Returns the Game identity plus manual-conflict metadata and the viewer's
previous questionnaire result (if any):

```json
{
  "game_slug": "hades",
  "game_name": "Hades",
  "canonical_aesthetic": "SENSORY",
  "precedence": {
    "has_conflict": true,
    "requires_user_choice": true,
    "manual_submission_id": 12,
    "manual_created_at": "2026-09-07T00:00:00+00:00",
    "age_days": 3
  },
  "previous_result": null
}
```

### `POST /api/v1/questionnaire/{slug}/submit`

Validates the traversal against the active `v1.0.0` registry, **recomputes**
raw/normalized profiles server-side (client values are never trusted), enforces
Q15 quality-delta bounds, then persists through the SBGC-175 precedence engine.

```json
{
  "version": "v1.0.0",
  "q1_option_id": "OPT_S1",
  "q2_option_id": "OPT_NONE",
  "answers": { "Q3": "Q3_a_lot_missing_a_dodge_shot_combo_jump_or_timing_window_can_quickly_cause_failure_or_heavy_damage" },
  "q15_rating": 7,
  "adjusted_challenge": { "micro": 40, "macro": 30, "mystiko": 30 },
  "adjusted_reward": { "micro": 35, "macro": 35, "mystiko": 30 }
}
```

Status codes:

- `201` — created (direct promotion, ≥10-day auto-overwrite, staff editorial
  routing, or `KEEP_MANUAL` archival).
- `200` — `OVERWRITE` of a recent manual submission.
- `409` — a recent manual submission exists and `conflict_resolution` is
  missing.  The body is `{ "error": "conflict_resolution_required",
  "message": ..., "precedence": {...} }` and **no records are written**.
- `422` — invalid aesthetic options, unknown question node / option, an
  adjusted profile that does not sum to 100, or an exceeded Q15 delta bound.

See `docs/questionnaire-epic-sbgc-171.md` for the full pipeline.

## Delta Recalculation — `POST /api/v1/classifications/recalculate-delta`

Queues a global delta recalculation for every published Game whose submissions
changed since its most recent completed calculation (SBGC-174).  The CPU-heavy
work runs on a daemon thread; the request returns immediately with `202`.

### Authorization

- Unauthenticated → `401 AUTHENTICATION_ERROR`.
- Authenticated non-Superuser/non-Moderator → `403 AUTHORIZATION_ERROR`.
- Superuser or Moderator → `202`.  The operator's email (when present) receives
  a completion report once the worker finishes.

### Response

```json
{
  "status": "queued",
  "message": "Delta recalculation worker started successfully.",
  "recipient_email": "admin@example.com"
}
```

See `docs/questionnaire-epic-sbgc-171.md` for the staleness rule
(`latest submission updated_at > latest snapshot calculated_at`) and the email
report format.

## Exception Handling

Exception handlers are registered once per `NinjaAPI` instance via
`api.errors.register_handlers()`. All handlers produce the standard
error envelope.

### Validation Errors

`ninja.errors.ValidationError` → 422 `VALIDATION_ERROR`. Details are
sanitised: only `location`, `message`, and `type` are returned. Input
values, Pydantic context, and documentation URLs are stripped.

### Authentication / Authorization

- `AuthenticationError` → 401 `AUTHENTICATION_ERROR`
- `AuthorizationError` → 403 `AUTHORIZATION_ERROR`

Generic safe messages are returned.  No global authentication backend or
middleware is configured; the SBGC-57 Steam mutation endpoints opt in to
Django session authentication via Ninja's `auth=django_auth` (session + CSRF)
and enforce `is_staff` authorization in the handler.

### Http404

Django's `Http404` → 404 `NOT_FOUND`. The requested path is not echoed.

### HttpError

`ninja.errors.HttpError` status codes are mapped to the corresponding
machine code. Unmapped 4xx/5xx statuses fall back to `HTTP_ERROR`.

### Unexpected Exceptions

All unhandled exceptions produce 500 `INTERNAL_SERVER_ERROR`. The full
exception and traceback are logged server-side. Exception class names,
messages, and stack traces are never returned to the client.

### Project ApiException

`api.errors.ApiException` allows endpoint code to raise deliberate,
safe errors with a custom code, message, status, and optional details.

## Unknown-Route Fallback

Requests to `/api/v1/<unknown>` return a standardised 404 envelope:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "API resource not found.",
    "details": []
  }
}
```

The submitted path is not echoed in the response.

## Method-Not-Allowed Behavior

HTTP method mismatches (e.g., `POST /api/v1/`) are handled by Django's
built-in URL routing layer before Ninja's dispatcher runs. The response
is Django's default 405 HTML page, not the standard JSON error envelope.

This is a documented framework limitation for Django Ninja 1.6.2. It is
not addressed through private Ninja internals or broad middleware.

## Interactive Documentation

- **Development:** Swagger UI is available at `/api/v1/docs` using
  self-hosted static assets from the `ninja` Django app. No external
  CDN dependencies.
- **Production:** Interactive docs are disabled (`docs_url=None`).
  The OpenAPI schema remains available at `/api/v1/openapi.json`.

Controlled by `NINJA_API_DOCS_ENABLED` in the settings module:
- `config.settings.development` → `True`
- `config.settings.production` → `False`
- `config.settings.base` → `False` (safe default)

## OpenAPI Schema

Available at `/api/v1/openapi.json` in both development and production.
Contains all registered endpoints, request/response schemas, tags,
and standard error-response declarations.

## Limitations

- **No global authentication backend.** Session auth is opt-in per operation
  via `auth=django_auth`; there is no project-wide auth middleware.
- **Method-not-allowed returns HTML.** Documented framework limitation
  for Django Ninja 1.6.2.
- **CORS deny-by-default** — No browser-to-Django CORS configuration
  exists; architecture uses Astro SSR as intermediary.
