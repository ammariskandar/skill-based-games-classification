# Post-Compaction Pre-SBGC-57 Context and Handover

| Field | Value |
|-------|-------|
| Generated | 2026-08-14 |
| Current branch | `SBGC-56-implement-metadata-refresh` |
| Current HEAD | `5f2c918` |
| Main/base | `e5c1871` (Merge PR #47 — SBGC-55) |
| Current Jira ticket | SBGC-56 (complete, not yet merged) |
| Next Jira ticket | SBGC-57 |
| SBGC-57 amended scope | Implement authorized HTTP API endpoints for Steam import + Steam metadata refresh, **then** Postman collection/tests against those real endpoints |
| Repository | `/home/ammaris/projects/skill-based-games-classification` |
| Python | 3.12 (venv at `apps/backend/.venv`, Python 3.12.3) |
| Django | 6.0.7 |
| State | SBGC-56 complete but not yet merged |

> **This handover is orientation context, not a substitute for inspecting the repository.**
> If this file conflicts with current code, tests, migrations, Git history, or canonical docs, the repository wins.

---

# 1. Executive Project State

## What the product is

MyGameDNA — a games database that classifies every game through two independent profiles: **Challenge** (what the game asks the player to do well) and **Reward** (what makes play satisfying). Each profile scores three dimensions — **Micro** (immediate/local), **Mystiko** (hidden/private/understood), **Macro** (accumulated/large-scale) — each profile independently totals exactly 100.

Stack: Astro + Tailwind CSS frontend (Vercel target), Django + Django Ninja backend (Render target), Neon PostgreSQL, Steam Store/Web API as external metadata source.

## What has actually been built

The backend foundation and the entire Steam domain pipeline are implemented, tested, and (for the most recent layers) concurrency-proven on PostgreSQL:

- Django backend with environment-specific settings, fail-closed production security, PostgreSQL-only production enforcement.
- Django Ninja API v1 foundation: error envelope, exception handlers, system router only.
- Django Admin with MyGameDNA branding, games + classifications registered, manual Steam refresh action (SBGC-56).
- `Game` domain model with canonical content types and listing statuses.
- Editorial classification (Challenge + Reward profiles) with DB-enforced score constraints.
- Hardened Steam transport (SBGC-42/168), Store app-details adapter (SBGC-53), import foundation (SBGC-53).
- Import persistence (SBGC-54): candidate → canonical `Game` row, deterministic slugs, concurrency-race recovery.
- Steam image URL persistence (SBGC-55): strict validation, URL-only.
- Metadata refresh (SBGC-56): service + `last_steam_refresh_at` + manual Admin action.
- BasedPyright typing baseline, discovery audit, PostgreSQL verification lane, seed data.

## The four capability boundaries — never conflate these

```text
implemented backend capability     → YES (import, refresh, images, persistence)
≠ HTTP-exposed capability          → NO (no import/refresh endpoints exist)
≠ frontend-exposed capability      → NO (no frontend import/refresh UI exists)
≠ live-Steam-verified capability   → NO (no live Steam E2E has been performed)
```

Explicit current-state checklist:

| Capability | State |
|-----------|-------|
| Steam transport (`SteamClient`) | ✅ implemented + tested |
| Steam Store adapter (`SteamAppDetailsAdapter`) | ✅ implemented + tested |
| Import foundation (`SteamImportFoundation`) | ✅ implemented + tested |
| Game persistence (`SteamGamePersistenceService`) | ✅ implemented + tested |
| Steam image URL persistence (`steam_image_url`) | ✅ implemented + tested |
| Metadata refresh (`SteamGameRefreshService`, `last_steam_refresh_at`) | ✅ implemented + tested |
| Admin manual refresh action | ✅ implemented + tested |
| **HTTP import endpoint** | ❌ does not exist |
| **HTTP refresh endpoint** | ❌ does not exist |
| Postman workflow | ❌ does not exist |
| Frontend import/refresh UI | ❌ does not exist |
| Live Steam end-to-end verification | ❌ never performed |

## Why SBGC-57 is the next architectural boundary

The entire Steam capability stack is reachable only from Python code. SBGC-57 (as human-amended) creates the HTTP application boundary that exposes the already-implemented import and refresh services, plus the Postman assets that exercise it. Everything before SBGC-57 was "capability"; SBGC-57 turns it into "interface". After SBGC-57, a human can verify against a local server and (in SBGC-58) against live Steam without writing code.

---

# 2. Full Project Architecture Map

```text
Browser / Postman
    ↓
Django URL routing (config/urls.py → /api/v1/ → api/urls.py)
    ↓
Django Ninja API (api/v1.py — one NinjaAPI instance for v1)
    ↓
API schemas / error mapping (api/schemas.py, api/errors.py)
    ↓
Application services (games/services/imports/, classifications/services/)
    ↓
Game domain / Classification domain (games/models.py, classifications/models.py)
    ↓
Django ORM
    ↓
PostgreSQL (Neon: pooled runtime URL, direct migration URL)

External Steam Store API
    ↓
SteamClient transport (games/services/steam/client.py — network)
    ↓
SteamAppDetailsAdapter (games/services/steam/adapters/app_details.py)
    ↓
SteamImportFoundation (games/services/steam/import_foundation.py)
    ↓
SteamGameImportCandidate (games/services/steam/dto.py — frozen DTO)
    ↓
SteamGamePersistenceService / SteamGameImportService (games/services/imports/steam.py)
    ↓
Game (canonical row)

Existing canonical Steam Game
    ↓
SteamGameRefreshService (games/services/imports/steam.py)
    ↓
SteamImportFoundation → fresh candidate (network, outside transaction)
    ↓
shared _apply_steam_owned_updates() (single field-mapping owner)
    ↓
Game (updated Steam-owned fields only)
```

## Layer ownership / dependency / transaction / network table

| Layer | Owns | May depend on | Forbidden | Transaction | Network |
|-------|------|---------------|-----------|-------------|---------|
| `games/models.py` | canonical identity, listing state, manual metadata, Steam-owned URL fields, timestamps | `games.types`, `classifications.skills` (enum vocabularies) | any `games.services.steam` import, requests | none (pure ORM) | never |
| `games/types.py` | canonical `ContentType` enum + choices | nothing | Django ORM, network | none | never |
| `games/services/steam/client.py` | HTTP, retries, timeouts, status classification, bounded bodies, error taxonomy | constants, config, errors | Django models, DB | none | owns all network |
| `games/services/steam/adapters/app_details.py` | structural payload validation → `SteamAppDetails` | DTOs, mapping, canonical validator | Game ORM, direct HTTP (uses `SteamClient`) | none | via `SteamClient` only |
| `games/services/steam/import_foundation.py` | App-ID validation + adapter fetch + candidate normalisation | adapter, DTOs | Game ORM, DB | none | via adapter |
| `games/services/imports/steam.py` (persistence) | candidate → Game row; identity; slug allocation; race recovery | Game ORM, DTO package, pure URL validator | Steam transport/HTTP | owns `transaction.atomic()` | never |
| `games/services/imports/steam.py` (import service) | lookup-then-persist orchestration | foundation, persistence | direct `SteamClient` | none of its own (persistence owns) | via foundation, strictly before persistence |
| `games/services/imports/steam.py` (refresh service) | eligible-Game refresh orchestration, identity invariant, refresh timestamp | foundation, persistence, shared update helper | direct `SteamClient` | owns the only transaction | via foundation, strictly before transaction |
| `api/` package | routing composition, schemas, error envelope | Ninja, routers | Steam internals, ORM mutation | none | never |
| `games/api.py`, `classifications/api.py` | domain router ownership | schemas, services | ORM mutation logic (thin handlers) | none | never (services do network) |
| `games/admin.py` | Admin presentation + manual refresh action (composition root `_build_steam_refresh_service`) | services | none | none of its own | real network in production; patched in tests |

---

# 3. Historical Ticket Progression

| Ticket | Title | Why it existed | Major output | Key constraints/decisions | Notable bugs found | Depended on by |
|--------|-------|----------------|--------------|---------------------------|--------------------|----------------|
| SBGC-44 | Establish backend testing | Needed reproducible backend test discipline | Discovery audit, subprocess isolation, reverse/shuffle/warnings commands, canonical testing doc | `SimpleTestCase` default; no live network; discovery validates structure not counts | Discovery audit later caught the `test_typing.py` import defect (SBGC-181) | all later tickets |
| SBGC-45 | Implement the Game model | First domain model | `Game`, `SourceType`, `ListingStatus`, display identity, Admin registration | Internal BigAutoField PK; external ID never the PK; manual records have NULL external ID | — | SBGC-46+ |
| SBGC-46 | Implement editorial classification | Editorial scoring domain | `EditorialClassification` + `ChallengeProfile` + `RewardProfile`, validation, atomic service, Admin inlines | Each profile totals exactly 100; DB CheckConstraints; service guarantees completeness | Direct ORM can create incomplete parent (documented limitation) | SBGC-47+ |
| SBGC-47 | Implement database constraints | Verify every invariant | Constraint inventory (8 Game + 16 classification), invalid-state matrix | Never rewrite merged migrations; expected IntegrityError isolated in nested atomics | Partial unique index later found to live in `pg_index` not `pg_constraint` (SBGC-52) | SBGC-52 |
| SBGC-48 | Implement game-type and listing rules | Normalize content types | `ContentType` 6 values, `other → unknown` reversible data migration, `publicly_listable()` | `OTHER` removed; `unknown` valid but never publicly listable; content type ≠ listing status | — | SBGC-49, SBGC-53 (canonical vocab), SBGC-54 |
| SBGC-49 | Add query and model helpers | Reusable query layer | 9 custom `GameQuerySet` methods, `SkillCategory`/`EditorialProfile` enums, dominant-skill annotations | Ties → `NULL`/`None`; SQL-level annotations; score paths allowlisted; manager delegates | Historical "11 methods" phrasing overcounted — code has 9 custom methods | SBGC-52, future API |
| SBGC-50 | Create migrations and sample data | Deterministic dev data | `seed_development_data` command, 9 games, 5 classifications, seed editor | Development-only gate; idempotent + corrective; atomic; no network | — | SBGC-51 (Admin validation used seeded data) |
| SBGC-51 | Validate models through Admin and tests | Prove Admin enforces domain | 78 Admin integration tests, manual 14/14 smoke, parity matrix | Admin saves parent+inlines directly (its own atomic), service not reused by Admin | Model `clean()` profile-labelled keys vs form-field names can 500 (pre-existing edge, documented) | SBGC-52 |
| SBGC-52 | Database hardening | PostgreSQL proof | 51 PG tests, `postgresql_test` settings, runtime-vs-migration URLs, CI service container | Isolated disposable PG only (never Neon); partial unique index is an index not a constraint; historical project-state models for migration tests | Thread connections leak → "database is being accessed by other users" (fixed in SBGC-54 concurrency test by closing per-thread) | SBGC-54+ |
| SBGC-53 | Build Steam API client / endpoint adapters | Typed Steam boundary | `SteamAppId`, DTOs, `LookupStatus`, `map_steam_product_type`, `SteamAppDetailsAdapter`, `SteamImportFoundation`, ORM-free `games/types.py`, closed `SteamEndpointOrigin` | Adapters never import ORM; transport errors propagate; `success=false` → UNAVAILABLE | `UNSUPPORTED` status appeared in docs but never in code (removed in SBGC-181) | SBGC-54 |
| SBGC-54 | Implement Steam game import workflow | Persistence boundary | `SteamGamePersistenceService`, `SteamGameImportService`, import statuses/results, deterministic `build_steam_game_slug`, identity + slug race recovery | Network strictly before transaction; identity = `(steam, app_id)` only; manual never merged; new games draft; only name/content_type refreshed on re-import | Distinct-App-ID same-name slug race failed permanently → slug-retry recovery added (audit fix) | SBGC-55, SBGC-56 |
| SBGC-55 | Handle Steam images | Image metadata boundary | `steam_image_url`, `validate_steam_image_url` (canonical), games.0004 | URL-only, no fetch/proxy/download; `manual_image_url` never populated from Steam; strict malformed-metadata semantics | Malformed nonblank URLs were silently normalized to `None` — fixed in the strict-semantics correction (`ca5de1f`) | SBGC-56 |
| SBGC-56 | Implement metadata refresh | Refresh capability | `SteamGameRefreshService`, `SteamGameRefreshResult`/`Status`, `last_steam_refresh_at` (games.0005), Admin refresh action | Shared `_apply_steam_owned_updates()` is the single field-mapping owner; stored external ID is the only App ID; identity mismatch = zero writes; UNCHANGED records timestamp via queryset update so `updated_at` stays stable | — | SBGC-57 (exposes refresh over HTTP) |
| SBGC-168 | Harden Steam transport boundaries | Close transport loopholes | Immutable origins as constants, operation budget ceiling, status-first processing, bounded drain/sleep, structured media-type regex | Closed origin enum; no arbitrary host input; error bodies never mask status classification | Numeric-host tricks (decimal/hex/octal IP forms) | SBGC-53 |
| SBGC-181 | Reconcile project state, tooling, documentation | Repair post-compaction drift | 9 stale docs corrected, `test_typing.py` → `model_typing.py`, `docs/backend-typing.md`, requirements cleanup | Repository is truth; Python 3.12 venv; BasedPyright CLI authoritative | Discovery audit falsely flagged a helper module named `test_*` | SBGC-54+ baseline |

---

# 4. Game Domain — Exact Current Contract

`apps/backend/games/models.py`. Field-by-field:

| Field | Django type | null/blank/default | Semantic owner | Source ownership | Import may change? | Refresh may change? | Admin may change? | Affects listing? |
|-------|-------------|--------------------|----------------|------------------|---------------------|---------------------|--------------------|------------------|
| `id` | `BigAutoField` PK | auto | internal identity | system | never | never | never | no (used in ordering) |
| `source_type` | `CharField(16)` choices `SourceType` | required | identity | system | set to `steam` on create only | never | editable on create; treat as immutable | indirectly (listing rule is source-agnostic) |
| `external_id` | `CharField(64)` `null=True, blank=True` | NULL for manual | Steam identity | Steam | set on create only | never | editable; must be decimal for Steam, NULL for manual | no |
| `name` | `CharField(255)` | required, duplicates allowed | display identity | Steam (import/refresh) + manual | ✅ on create/re-import | ✅ | ✅ | no |
| `slug` | `SlugField(255)` `unique=True` | required, unique | URL identity | system (deterministic allocation for Steam; manual supplies) | set on create only; **never regenerated** | never | ✅ (prepopulated convenience only) | no |
| `content_type` | `CharField(16)` choices from `games.types` | default `game` | product classification | Steam (import/refresh) + manual/editorial | ✅ on create/re-import | ✅ | ✅ | ✅ (must be `game`) |
| `listing_status` | `CharField(16)` choices `ListingStatus` | default `draft` | editorial publication state | editorial only | never (imports always draft) | never | ✅ | ✅ (must be `published`) |
| `manual_description` | `TextField(blank=True)` | empty | editorial | manual/editorial | never | never | ✅ | no |
| `manual_image_url` | `URLField(500, blank=True)` | empty | editorial | manual/editorial | never | never | ✅ | no |
| `manual_website_url` | `URLField(500, blank=True)` | empty | editorial | manual/editorial | never | never | ✅ | no |
| `steam_image_url` | `URLField(500, blank=True)` | empty | Steam-owned | Steam import/refresh only | ✅ (validated) | ✅ (SBGC-55 semantics) | readonly | no |
| `last_steam_refresh_at` | `DateTimeField(null=True, blank=True)` | NULL | Steam-owned refresh tracking | refresh service | never | ✅ (successful verifications only) | readonly | no |
| `created_at` | `DateTimeField(auto_now_add=True)` | auto | audit | system | never | never | readonly | no |
| `updated_at` | `DateTimeField(auto_now=True)` | auto | audit | system (save-triggered) | on save | on save only when fields change; **queryset updates do not trigger it** | readonly | no |

## Canonical identity

- Internal `id` is the universal PK. `source_type + external_id` is the **source identity** for Steam records (unique when `external_id` is not NULL — the `game_unique_source_external_id` conditional UniqueConstraint; a partial unique index on PostgreSQL). Slug is unique but never an identity key. Name is never an identity key.
- `display_identity` property: `steam:{external_id}` or `manual:{slug}` — deterministic, no network.
- `__str__`: `f"{name} [{display_identity}]"`.

## Constraints and indexes

- `game_source_external_id_ck` — CheckConstraint: Steam → non-null nonempty decimal ID; Manual → NULL.
- `game_unique_source_external_id` — conditional UniqueConstraint → PG partial unique index (lives in `pg_index`, not `pg_constraint`).
- `game_listing_name_idx` — index on `(listing_status, name, id)`.
- Slug uniqueness via field `unique=True`.
- `Game.clean()` enforces: non-whitespace name; Steam external ID decimal via `str.isdigit()`; manual → NULL external ID.
- Default ordering `["name", "id"]` — deterministic for duplicates.
- Deletion: no custom cascade on Game itself; classifications FK CASCADE from Game (deleting a Game deletes its classification).

---

# 5. Canonical Content-Type Vocabulary

`apps/backend/games/types.py` — ORM-free `StrEnum`:

```python
class ContentType(StrEnum):
    GAME = "game"
    DLC = "dlc"
    DEMO = "demo"
    SOFTWARE = "software"
    SOUNDTRACK = "soundtrack"
    UNKNOWN = "unknown"
```

- Moved out of `games.models` in SBGC-53 so Steam adapters can use the canonical vocabulary **without importing Django ORM models**.
- `CONTENT_TYPE_CHOICES` derives from the enum — one owner for the vocabulary.
- `unknown` never maps to `game`: unrecognized Steam types persist as `unknown` (excluded from public listing even when published).
- Default is `game`. `other` was removed in SBGC-48 with a reversible data migration (`games.0003`).

---

# 6. Listing-State Contract

```text
Game.objects.publicly_listable()
== content_type == GAME  AND  listing_status == PUBLISHED
```

- Imported Steam Games start as `draft` — imports **never publish**.
- Refresh never modifies `listing_status`.
- A Steam type transition (published GAME → DLC/unknown) keeps `published` but **leaves** `publicly_listable()` — verified by SBGC-56 tests.
- `Game.objects.all()` has no hidden filtering — the default manager returns everything.
- External metadata state and editorial publication state are intentionally independent dimensions.

---

# 7. Query Helper Architecture

`GameQuerySet` has **9 custom methods** (all chainable, SQL-evaluated):

| Method | Purpose |
|--------|---------|
| `publicly_listable()` | canonical `GAME + PUBLISHED` rule — do not reimplement |
| `steam()` / `manual()` | source-type filtering |
| `editorially_classified()` | complete classification only (parent + Challenge + Reward) |
| `with_editorial_profiles()` | `select_related` all editorial rows (N+1-safe, no filter) |
| `with_dominant_skill_categories()` | SQL `Case/When/Q/F` annotations; ties → `NULL`; missing profiles → `NULL` |
| `filter_by_dominant_skill_category(profile, category)` | strict-greater-than dominant filtering; ties excluded |
| `filter_by_editorial_score(profile, category, minimum, maximum)` | inclusive 0–100 bounds; at least one bound; booleans/floats rejected |
| `order_by_editorial_score(profile, category, descending=True)` | deterministic tie-break: score → name → id |

`GameManager` delegates all 9 (typed delegation, no duplication). Score field paths are allowlisted via `_SCORE_FIELD_PATHS`. Vocabulary enums (`SkillCategory`, `EditorialProfile`) live in `classifications/skills.py`; the pure `dominant_skill_category()` helper returns `None` on ties. Note: historical changelogs said "11 queryset methods" — the code has 9 custom methods; corrected in `docs/backend-architecture.md` during SBGC-56.

---

# 8. Editorial Classification Architecture

- `EditorialClassification` — OneToOne to `Game` (`related_name="editorial_classification"`), FK `updated_by` → User (PROTECT), `notes`, timestamps.
- `ChallengeProfile` / `RewardProfile` — each OneToOne to the parent; `micro_score` / `mystiko_score` / `macro_score` (`PositiveSmallIntegerField`).
- Each profile **independently totals exactly 100**; range 0–100 enforced by 4 DB CheckConstraints (`challenge/reward_scores_range_ck`, `challenge/reward_scores_total_100_ck` using `F()` expressions: `micro = 100 - mystiko - macro`).
- `validate_score_distribution()` is the shared pure validator (type/range/total, booleans rejected).
- Service `set_editorial_classification()` — atomic; validates both distributions before writes; creates/updates parent + both profiles; returns the parent with profiles.
- Admin uses two `StackedInline` entries with custom formsets enforcing **exactly one** active profile each (`extra=0, max_num=1, min_num=1, can_delete=False`); Admin persists directly (not through the service) inside Django's own atomic `changeform_view`.
- Known limitation: the DB guarantees at-most-one parent/profile but **not** child existence — direct ORM can create a parent without profiles (service + Admin prevent it).
- Dominant skill: strict highest score; ties → no dominant category (`None`/`NULL`), same semantics in Python and SQL.

```text
Editorial classification ≠ Questionnaire-derived classification ≠ Community/user classification
```

Questionnaire/community work remains in SBGC-171+; `QuestionnaireClassification`/`QuestionnaireResult` PG constraints deferred to SBGC-177.

---

# 9. Steam Transport — Exhaustive Contract

`games/services/steam/` (SBGC-42/168/53):

- **Immutable origins**: `STEAM_WEB_API_ORIGIN = "https://api.steampowered.com"`, `STEAM_STORE_API_ORIGIN = "https://store.steampowered.com"` — module constants in `constants.py`; never configurable.
- **`SteamEndpointOrigin`** — closed enum `WEB_API` / `STORE_API`; `_get_json()` does a runtime `isinstance` check; arbitrary URL strings are rejected. `get_web_api_json()` / `get_store_api_json()` are the entry points; `get_json()` is a backward-compat alias for the Web API.
- **Retries**: urllib3 `Retry`; GET/HEAD only; statuses 429/500/502/503/504; `total` counter is the master cap (max attempts = `1 + max_retries`, max_retries 0–3); redirects disabled (`redirect=0`, `allow_redirects=False`, `raise_on_redirect=False`); `backoff_max` and `retry_after_max` both capped at `retry_sleep_max_seconds` (int, 0–10, default 5).
- **Operation budget**: `maximum_attempts × (connect_timeout + read_timeout) + max_retries × retry_sleep_max_seconds` — default 49.15s, ceiling 120s; configurations exceeding it are rejected at construction. It is a budget ceiling, not a wall-clock deadline.
- **Config validation**: NaN/infinity/booleans rejected for numeric fields; connect timeout (0, 30], read timeout (0, 60].
- **Bounded body**: `Content-Length` precheck; streamed via `iter_content`; chunks joined once with `b"".join(chunks)`; `SteamResponseTooLargeError` over limit (default 2 MiB).
- **Status-first processing**: non-2xx statuses are classified **before** any body parse; error body bounded-drained (1 MiB) then closed; oversized/malformed error bodies never mask status classification.
- **Safe close**: response closed on every path (`finally`), close errors swallowed.
- **Media type**: regex accepts `application/json` and `application/<subtype>+json` with optional parameters; rejects `text/json`, `application/jsonx`, `application/+json`.
- **JSON contract**: root must be an object; arrays/scalars/null rejected.
- **Exception taxonomy** (15 classes under `SteamError`): `SteamConfigurationError`, `SteamRequestError` (Connection/Timeout/Redirect), `SteamResponseError` (Authentication/RateLimited/NotFound/Upstream/InvalidResponse), `SteamResponseTooLargeError`. Exceptions carry safe `code`/`message` only — never API key, URL, raw body, headers.
- **API key**: `x-webapi-key` header only; never query string, logs, errors, repr. Required only when `requires_api_key=True`.
- **This layer must never persist** anything — it returns JSON dicts to adapters.

---

# 10. Steam CDN / Image Validation Distinction

Two deliberately separate policies in `games/services/steam/cdn.py`:

## Metadata URL validation — `validate_steam_image_url(value)`

Used for `candidate.header_image_url` → `Game.steam_image_url`. Strict SBGC-53 malformed-metadata semantics:

```text
absent (None) / null / blank string     → None
valid structurally-safe HTTPS URL       → returned as-is (outer whitespace stripped)
non-string value                        → SteamMalformedPayloadError
nonblank malformed string               → SteamMalformedPayloadError
```

Rejected patterns (raise when nonblank): HTTP/non-HTTPS schemes, credentials/userinfo, missing hostname, custom port, IPv4 literal, IPv6 literal, numeric-host tricks (decimal/hex/octal — `2130706433`, `0x7f000001`, `017700000001`), `localhost` / `localhost.localdomain`, malformed URLs. **No network access — structural only.** `None` means exactly one thing: upstream did not provide a usable image field. Malformed metadata is never silently normalized to absence (that was the SBGC-55 correction).

## Backend fetch authorization — `validate_steam_cdn_url(value, allowed_hosts=...)`

The **future** strict fetch gate. Currently the allowlist is **empty → rejects every URL**. This is intentional: the repository has no authoritative evidence of real Steam CDN hostnames, and inventing hostnames is forbidden.

```text
metadata URL accepted for persistence ≠ backend authorized to fetch URL
```

No image fetching, proxying, or downloading exists anywhere. Populating the allowlist (from live verification or authoritative Steam documentation, as immutable source-controlled constants) is a prerequisite for any future fetch feature.

---

# 11. Steam DTO Architecture

`games/services/steam/dto.py` and `games/services/imports/steam.py`:

| Type | Where | Fields | Invariants | Frozen/slots | Lifecycle |
|------|-------|--------|------------|--------------|-----------|
| `SteamAppId` | steam/dto.py | `value: str` | decimal digits only; ≤ 32 chars; no whitespace; non-zero; non-string → TypeError | ✅ frozen, slots | adapter/import/refresh input validation |
| `LookupStatus` | steam/dto.py | `FOUND`, `UNAVAILABLE` | — | enum | foundation output |
| `SteamAppDetails` | steam/dto.py | `app_id, name, content_type` + optional `short_description, header_image_url, website_url, is_free, developers, publishers` | application-owned; no raw Steam JSON retained | ✅ frozen, slots | adapter output |
| `SteamGameImportCandidate` | steam/dto.py | `app_id, name, content_type` + same optionals | no Django model reference | ✅ frozen, slots | foundation output → persistence input |
| `SteamAppLookupResult` | steam/dto.py | `status: LookupStatus, app_id: str, candidate?` | FOUND ⇒ candidate present; non-FOUND ⇒ candidate absent | ✅ frozen, slots | foundation output |
| `SteamGameImportStatus` | imports/steam.py | `CREATED, UPDATED, UNCHANGED, UNAVAILABLE` | — | enum | import outcome |
| `SteamGameImportResult` | imports/steam.py | `status, app_id: SteamAppId, game_id?` | CREATED/UPDATED/UNCHANGED ⇒ game_id int; UNAVAILABLE ⇒ game_id None | ✅ frozen, slots | import outcome |
| `SteamGameRefreshStatus` | imports/steam.py | `UPDATED, UNCHANGED, UNAVAILABLE` | — | enum | refresh outcome |
| `SteamGameRefreshResult` | imports/steam.py | `status, game_id: int, changed_fields=()` | UPDATED ⇒ non-empty changed_fields; others ⇒ empty; only `name`/`content_type`/`steam_image_url` allowed; deterministic order | ✅ frozen, slots | refresh outcome |
| `SteamRefreshError` | imports/steam.py | message | domain error: eligibility/identity failures | Exception | refresh failure |

---

# 12. Steam App-Details Adapter Contract

`SteamAppDetailsAdapter.fetch(app_id: SteamAppId) -> SteamAppDetails`:

1. Calls `client.get_store_api_json("/api/appdetails", params={"appids": app_id.value})` — Store API origin only.
2. Root must be a JSON object; must contain the requested App ID as a key; wrapper must be a dict.
3. `success` must be a strict bool. `false` → `SteamAdapterError(code="STEAM_APP_UNAVAILABLE")` (foundation maps to `UNAVAILABLE`).
4. `data` must be a dict when success; `name` and `type` must be non-blank strings (else `SteamMissingRequiredFieldError`).
5. `type` → `map_steam_product_type()`: `game→GAME, dlc→DLC, demo→DEMO, software→SOFTWARE, music→SOUNDTRACK, soundtrack→SOUNDTRACK`, unrecognized nonblank → `UNKNOWN`, blank/non-string → `ValueError` (malformed).
6. Optional fields extracted type-safely (`short_description`, `is_free`, `developers`, `publishers`); malformed optional values normalize to `None` **except** `header_image` (strict `validate_steam_image_url`: non-string and nonblank malformed raise `SteamMalformedPayloadError`) and `website` (non-string raises; HTTP/HTTPS only, no credentials).
7. Structural violations → `SteamMalformedPayloadError` / `SteamMissingRequiredFieldError`. Transport exceptions propagate unchanged.

Raw Steam JSON is never persisted anywhere.

---

# 13. Steam Import Foundation

`SteamImportFoundation.prepare_candidate(app_id: str) -> SteamAppLookupResult`:

- Validates `app_id` through `SteamAppId`; invalid → `SteamAdapterError(code="STEAM_INVALID_APP_ID")`.
- Delegates to `SteamAppDetailsAdapter.fetch`.
- `STEAM_APP_UNAVAILABLE` → `LookupStatus.UNAVAILABLE`.
- Other adapter errors and all transport errors propagate unchanged.
- `FOUND` → `SteamGameImportCandidate` (mirrors details).
- No ORM, no transaction, no slugging, no listing decisions, no persistence.

---

# 14. Steam Persistence Workflow (SBGC-54)

`SteamGamePersistenceService.persist(candidate)` (no network, transaction-owning) and `SteamGameImportService.import_app(app_id)` (orchestration):

- Candidate preparation (network) happens strictly **before** `persist`'s `transaction.atomic()`.
- Identity lookup: `source_type=steam AND external_id=candidate.app_id` only — name/slug/title similarity never identity keys.
- **New Game**: `steam` source, `external_id`, `name`, `content_type`, deterministic slug, default `draft`, validated image URL or empty. Manual fields never populated from Steam.
- **Re-import**: updates `name`/`content_type` (and `steam_image_url` since SBGC-55) via the shared `_apply_steam_owned_updates()` helper; everything else preserved (slug, listing, manual metadata, classification, `created_at`). No changes → `UNCHANGED` (no save).
- **Slug allocation** (`build_steam_game_slug`): ① `slugify(name)`; ② `slugify(name)-steam-<app_id>` (suffix never truncated); ③ `steam-<app_id>` fallback; truncate to 255 without trailing hyphens; all occupied → `ValueError`. Never random; never applied to existing Games.
- **Concurrency**: same-App-ID race — loser's `IntegrityError` recovers the winner's row (nested savepoint; only when the identity row now exists); distinct-App-ID same-name slug race — loser recomputes the slug deterministically and retries once; unrelated `IntegrityError` propagates. Both verified on PostgreSQL 16 (`games/tests/test_import_concurrency.py`).
- Statuses: `CREATED` / `UPDATED` / `UNCHANGED` / `UNAVAILABLE` (import service maps foundation `UNAVAILABLE`; no writes).

---

# 15. Steam Image Persistence (SBGC-55)

- `Game.steam_image_url` (`URLField(500, blank=True)`, games.0004) — Steam-owned.
- `manual_image_url` was **not** reused: manual/editorial and Steam-owned imagery are independent.
- Valid URL updates (new import + re-import + refresh); `None`/blank preserves on re-import/refresh; malformed nonblank raises `SteamMalformedPayloadError` before any write.
- No binary storage, no proxy, no image HTTP call anywhere (tested by patching `SteamClient.__init__` to raise while persistence succeeds).
- No CDN fetch authorization exists yet (empty strict allowlist, see §10).

---

# 16. Steam Metadata Refresh Workflow (SBGC-56)

`SteamGameRefreshService.refresh(game) -> SteamGameRefreshResult`:

1. **Eligibility** (no network, no writes): must be a saved `Game`; `source_type == steam` else `SteamRefreshError`; stored `external_id` validated via `SteamAppId` — the only accepted App ID.
2. **Network**: `foundation.prepare_candidate(app_id.value)` — strictly before any transaction (proven by `TransactionTestCase` with `in_atomic_block` assertions).
3. `UNAVAILABLE` → `SteamGameRefreshResult(UNAVAILABLE, game_id)` — Game completely preserved; timestamp untouched.
4. **Identity invariant**: `lookup.app_id` and `candidate.app_id` must equal `game.external_id` — mismatch → `SteamRefreshError`, zero writes.
5. Malformed candidate image → raises before the transaction.
6. **Transaction**: re-fetch the canonical row by identity (`persistence._find_existing`); apply `_apply_steam_owned_updates()` (the single field-mapping owner shared with imports); `UPDATED` → set `last_steam_refresh_at`, `full_clean()`, `save()`; `UNCHANGED` → queryset update of `last_steam_refresh_at` only (**no `Game.save()` → `updated_at` untouched**).
7. Errors (transport/adapter) propagate unchanged, never mapped to `UNAVAILABLE`, zero writes.

Refreshed Steam-owned fields:

```text
name
content_type
steam_image_url
last_steam_refresh_at
```

`last_steam_refresh_at` semantics (verify against code):

```text
successful FOUND refresh (UPDATED)      → set via save
successful FOUND refresh (UNCHANGED)    → set via QuerySet.update; updated_at stable
UNAVAILABLE                             → unchanged (NULL if never refreshed)
technical error                         → unchanged
```

**Never refreshed**: slug, listing_status, `manual_*`, classifications, `created_at`, `source_type`, `external_id`, `id`.

**Admin action**: `GameAdmin.refresh_from_steam` ("Refresh Steam metadata from Steam") — manual games skipped without network; per-game known errors (SteamRefreshError / SteamAdapterError / SteamError) reported, others continue; unexpected exceptions propagate; composition factory `games.admin._build_steam_refresh_service()` is the patch point for tests. No endpoint, no scheduler, no bulk job.

---

# 17. Unpersisted Steam DTO Metadata — Prominent Warning

The candidate DTO carries:

```text
short_description
website_url
is_free
developers
publishers
```

**None of these are canonical `Game` fields.** They are not stored anywhere; they are never written into `manual_*`; refresh does not persist them. SBGC-56's recorded Jira scope did not require them; schema expansion is a future ticket's decision. **SBGC-57 must expose only what the backend actually persists** — do not invent response fields assuming DTO metadata is persisted. (A future HTTP GET of game details may legitimately surface them only after a schema-owning ticket adds Steam-owned fields.)

---

# 18. Current Admin Capabilities

- Games changelist: `name, source_type, external_id, content_type, listing_status, updated_at`; filters on source/content/listing; search on name/slug/external_id.
- Readonly: `display_identity`, `created_at`, `updated_at`, `steam_image_url`, `last_steam_refresh_at`.
- Manual records creatable through Admin; slug prepopulated from name (convenience only, never regenerated).
- Classifications: parent + two stacked inlines with exact-one-profile formsets; `updated_by` set from request user on create; readonly afterwards.
- Steam refresh action (SBGC-56) — see §16.
- No import Admin action exists (SBGC-57 owns the HTTP surface, not Admin).
- SBGC-51 human manual smoke: 14/14 checks passed on local dev server. **Do not expose the Admin secret URL path anywhere** (production requires non-default `ADMIN_URL_PATH`).

---

# 19. Database and Migration History

Exact current project-owned migrations (verified):

```text
games.0001_initial
games.0002_alter_game_content_type
games.0003_migrate_other_to_unknown
games.0004_game_steam_image_url
games.0005_game_last_steam_refresh_at

classifications.0001_initial
```

| Migration | Purpose | Operation | Reversible | Caveat | PG verified |
|-----------|---------|-----------|------------|--------|-------------|
| games.0001 | Game model incl. constraints/indexes | CreateModel | ✅ | content types initially 4 incl. `other` | ✅ (SBGC-52) |
| games.0002 | 4 → 6 content-type choices | AlterField | ✅ | SQLite generates no-op SQL (state only) | ✅ |
| games.0003 | `other → unknown` data migration | RunPython | ✅ (lossy reverse: `unknown → other`) | lossiness acceptable pre-deployment; historical models required in tests | ✅ |
| games.0004 | `steam_image_url` | AddField | ✅ | one-off default `""`, `preserve_default=False` | not separately PG-tested (plain nullable URL field) |
| games.0005 | `last_steam_refresh_at` | AddField | ✅ | nullable; no backfill | not separately PG-tested (plain nullable timestamp) |
| classifications.0001 | classification models + 4 CheckConstraints | CreateModel | ✅ | child-existence not DB-enforced | ✅ (SBGC-52) |

Rules:

- **Never rewrite merged migrations.**
- Migration-state tests must use **historical project-state models** (`MigrationExecutor.loader.project_state([...]).apps.get_model(...)`) — the SBGC-55 schema addition exposed two tests that used the current model at older states; both were fixed this way.
- Migration tests must restore the full project state in a `finally` (`migrate "" ""`).

---

# 20. PostgreSQL Architecture and Evidence

- PostgreSQL 16 verified (16.14 via isolated Podman container; CI uses `postgres:16` service container).
- `POSTGRES_TEST_DATABASE_URL` (disposable, isolated) for tests; **production Neon is never used for destructive testing**.
- Runtime `DATABASE_URL` may be a Neon pooled URL; `MIGRATION_DATABASE_URL` must be the direct (non-pooler) URL (`scripts/backend-migrate.sh` maps it).
- Production rejects SQLite/MySQL/Oracle/malformed URLs (`ImproperlyConfigured`).
- `game_unique_source_external_id` is implemented by PostgreSQL as a **partial unique index** — introspection must look in `pg_index`/`pg_indexes`, not `pg_constraint`.
- Transaction/savepoint lessons: expected `IntegrityError` must be isolated in nested `transaction.atomic()` blocks; service rollback and nested-savepoint recovery verified on PG.
- Thread-based tests must close **thread-local** Django connections inside each worker thread (`connections.close_all()` in the worker's `finally`), or PG test-DB teardown fails with "database is being accessed by other users".
- Import concurrency cases verified on PG (`games/tests/test_import_concurrency.py`, run by `scripts/backend-test-postgresql.sh`):

```text
same App ID race          → exactly one canonical row
different App IDs / same preferred slug race → both persist; one suffixed slug
```

Do not state current exact PG totals without verifying — the SBGC-54/55 era evidence was 53/53 (52 + 1 slug-race test).

---

# 21. Test Architecture

The revised testing philosophy (adopted from SBGC-55 onward) — use this exact model:

```text
Level 1 — inner loop
Changed/new tests only, repeated while editing.

Level 2 — affected neighborhood
Tests for the bounded context touched (e.g., steam + imports + models + listing).

Level 3 — ticket completion
Normal backend regression + static/migration checks, once near completion.

Level 4 — heavy/specialized suites
PostgreSQL, reverse, shuffle, warnings, frontend build — only when technically justified.
```

Why it changed: the full 1,300-test suite is ~6 minutes per run; reverse/shuffle/warnings were overused as ritual; tests should falsify the current change efficiently. Broad CI still exists as independent PR evidence.

When Level 4 suites are justified:

- **PostgreSQL**: new DB-specific semantics (locking, constraints, concurrency recovery, DB-specific queries, migration behavior needing PG proof).
- **Reverse/shuffle**: test-infrastructure changes, shared global fixtures/settings changes, suspected order dependence.
- **Warnings**: new network/file/stream/resource lifecycle or warning-sensitive code.
- **Frontend**: frontend code changed.
- **Live Steam**: never automatic; SBGC-58 owns that.

Commands (all use `--settings=config.settings.test --noinput`): `npm run test:backend`, `npm run test:backend:discovery`, `npm run test:backend:reverse`, `npm run test:backend:shuffle`, `npm run test:backend:warnings`, `npm run test:backend:postgresql` (requires `POSTGRES_TEST_DATABASE_URL`).

---

# 22. Current CI and Typecheck Architecture

- BasedPyright 1.32.1 (`npm run typecheck:backend` → `apps/backend/.venv/bin/basedpyright --project .`); **CLI is authoritative** — Zed LSP diagnostics are convenience only.
- `pyrightconfig.json`: `venvPath: apps/backend`, `venv: .venv`, `pythonVersion: 3.12`, include `apps/backend`, exclude `.venv`/`__pycache__`/`**/migrations`/`staticfiles`/`apps/frontend`; `extraPaths: ["apps/backend"]`; `typeCheckingMode: standard`; the **only** broad disable is `reportMissingTypeStubs: false`.
- django-stubs 6.0.2 + django-stubs-ext 6.0.2; **no django-types**; the django-stubs mypy plugin does **not** run under BasedPyright.
- Suppression policy: no global diagnostic disables; per-line `# pyright: ignore[reportXxx]` at framework boundaries only; centralized helpers (`config/env_typing.py`, `config/model_typing.py`) own framework-boundary casts.
- CI (`.github/workflows/ci.yml`): frontend job (Prettier, ESLint, astro check, vitest, design-reference isolation, build) + backend SQLite job (Ruff, format, BasedPyright, Django check, tests) + PostgreSQL 16 job.
- Discovery audit (`scripts/backend-test-discovery.sh`) validates structure (no duplicate IDs, no import errors, no empty modules) — it never hard-codes totals.
- Deploy check (`scripts/backend-deploy-check.sh`) accepts documented staging warnings W005/W021 only.
- Environment notes (agent-session specific, not repository truth): during SBGC-54/55/56 the agent terminal was sandboxed; the Python 3.12 venv lives on the host and backend commands were run via `host-spawn -cwd <repo> /bin/bash -c '...'`; frontend commands ran in the sandbox (Node 22); Podman on the host provided disposable PostgreSQL.

---

# 23. Operational / Deployment Architecture

- `render.yaml` + `scripts/backend-build.sh` (collectstatic), `scripts/backend-migrate.sh` (migrations with `MIGRATION_DATABASE_URL` mapping), `scripts/backend-start.sh` (Gunicorn only).
- Gunicorn sync workers (`WEB_CONCURRENCY` default 2); WhiteNoise serves admin static files; `/health/` is a liveness probe (no DB/Steam/migration checks).
- Start command does **not** migrate/collectstatic/seed/create users. No development seed in production (`DEVELOPMENT_SEEDING_ENABLED` false outside development).
- Production fails closed: required+validated `SECRET_KEY` (50+ chars, 5+ unique), `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` (HTTPS only), non-default `ADMIN_URL_PATH`, PostgreSQL-only DB.
- Pooled runtime DB URL vs direct migration DB URL are separate concerns.

```text
repository configuration verified ≠ live Render/Neon verified
```

No Render service, no Neon migration, no live proxy test, no production key has ever been exercised.

---

# 24. Security Invariants SBGC-57 Must Preserve

SBGC-57 must not weaken any of:

1. Immutable Steam origins — no caller-defined Steam URL.
2. No caller-defined image/CDN URL fetch — metadata validation is not fetch authorization.
3. No raw Steam payload persistence.
4. No network from models.
5. No DB transaction around a Steam network request.
6. No manual→Steam identity conversion.
7. No arbitrary App-ID override during refresh (stored external ID is authoritative).
8. No automatic publication (imports stay draft; refresh never touches listing).
9. No classification mutation by Steam operations.
10. No secret leakage (API keys, DB URLs, Admin path) in responses/logs/Postman environments.
11. No raw exception internals in API responses — everything through the error envelope.
12. No production Neon tests.
13. No unrestricted Admin-equivalent import endpoint — authorization is explicit and tested (see §26).

---

# 25. SBGC-57 Amended Scope — Exact Handoff

> **SBGC-57 has been amended by the human.**
>
> It now owns BOTH:
>
> 1. Implement authorized HTTP API endpoints for Steam import and metadata refresh.
> 2. Configure Postman and create test scripts/collections against those real endpoints.

This supersedes any older interpretation of SBGC-57 as merely a Postman configuration ticket. **Do not defer HTTP endpoint implementation to another ticket.**

---

# 26. Recommended SBGC-57 HTTP Architecture (handover recommendation — NOT yet implemented)

Recommended conceptual endpoints (final paths are SBGC-57's decision after inspecting current routing):

```text
POST /api/v1/games/steam/import
POST /api/v1/games/{game_id}/steam/refresh
```

Current routing facts SBGC-57 must respect:

- One `NinjaAPI` instance (`api/v1.py`), routers mounted at `""` (system), `"/games/"` (games — **no operations yet**), `"/classifications/"` (empty).
- Request schemas inherit `ApiRequestSchema` (`extra="forbid"`); responses are declared schemas; standard errors via `STANDARD_ERROR_RESPONSES` (`codes_4xx`/`codes_5xx` frozensets → `ApiErrorResponse`); explicit 422 must be declared separately (Ninja `codes_4xx` excludes 422); `Status(status, body)` not tuple syntax.
- Error machine codes: `VALIDATION_ERROR(422), AUTHENTICATION_ERROR(401), AUTHORIZATION_ERROR(403), NOT_FOUND(404), BAD_REQUEST(400), METHOD_NOT_ALLOWED(405), CONFLICT(409), RATE_LIMITED(429), SERVICE_UNAVAILABLE(503), HTTP_ERROR, INTERNAL_SERVER_ERROR(500)`; project code raises `ApiException`.
- **No authentication backend is configured.** The Ninja handlers for Authentication/Authorization errors exist but nothing raises them yet. Django session auth (used by Admin) exists at the Django level.

Endpoint ownership contract:

```text
HTTP request → Ninja schema validation → authorization → service invocation
→ typed domain result → response schema
```

No Steam parsing in API handlers; no ORM update logic in API handlers; handlers stay thin.

---

# 27. SBGC-57 Import Endpoint Contract Recommendation

Request (prefer string to preserve `SteamAppId` semantics):

```json
{ "app_id": "620" }
```

Result mapping candidates (final HTTP statuses are SBGC-57's decision after inspecting `api/errors.py` conventions):

```text
CREATED      → likely 201
UPDATED      → likely 200
UNCHANGED    → likely 200
UNAVAILABLE  → likely 200 with an explicit status field (Steam says success=false — not a client error)
invalid App ID / malformed body → 422 (or 400 via ApiException per existing conventions)
```

---

# 28. SBGC-57 Refresh Endpoint Contract Recommendation

Identify the Game by canonical internal Game ID (never a replacement App ID):

```text
POST /api/v1/games/{game_id}/steam/refresh
```

Handler flow:

1. resolve canonical Game by `id` (404 if missing);
2. authorize;
3. call `SteamGameRefreshService.refresh(game)`;
4. map `UPDATED`/`UNCHANGED`/`UNAVAILABLE` results.

A manual Game must produce a clear client/domain error (not 500) — `SteamRefreshError` must be mapped. Unavailable must not mutate the Game.

---

# 29. Authorization — a Required SBGC-57 Design Decision

Do not casually expose Steam mutation endpoints publicly. The ticket says **authorized** endpoints, so authorization must be explicit and tested.

Questions SBGC-57 must answer from existing infrastructure (inspect before deciding):

- Is Django session authentication (staff/superuser) the right boundary? (It exists; Admin uses it.)
- Is there any existing API auth abstraction? (Currently: none — only error handlers.)
- Are these internal/admin operations? (Import/refresh mutate canonical data; yes, treat as staff-level.)
- How will Postman authenticate — session + CSRF, or a token mechanism?

Constraints:

- Do not invent API-key infrastructure unless Jira/current architecture requires it.
- Do not disable CSRF globally to make Postman convenient.
- Do not create insecure bypass headers.

If session auth is chosen: Postman must obtain a login session cookie **and** a CSRF token; Ninja/Django behavior must be tested realistically.

---

# 30. CSRF and Postman Considerations

- With Django session auth, POSTs require CSRF; Postman flows need a login/session cookie + CSRF token exchange (e.g., GET a CSRF-token endpoint or parse the login flow).
- If a token-based auth exists (it does not today), reuse it instead.
- Never weaken `CSRF_TRUSTED_ORIGINS`, `SECURE_*` cookies, or add unsafe exemptions for Postman's sake.

---

# 31. Error Mapping Requirements for SBGC-57

The HTTP layer must translate the existing taxonomy (do not expose raw tracebacks or Steam bodies):

```text
invalid request / malformed App ID   → validation-style client error
Game not found                        → NOT_FOUND
manual Game cannot refresh            → domain/client error (SteamRefreshError mapping)
Steam app unavailable                 → explicit UNAVAILABLE result (not an error)
Steam malformed payload               → mapped Steam error (likely 502/503-class upstream data error)
Steam timeout / connection            → SERVICE_UNAVAILABLE-class
Steam rate limited                    → RATE_LIMITED (429) or SERVICE_UNAVAILABLE per conventions
Steam authentication failure          → upstream-auth mapped (never 401 of OUR endpoint)
Steam upstream failure                → SERVICE_UNAVAILABLE-class
response too large                    → SERVICE_UNAVAILABLE-class
unexpected server error               → INTERNAL_SERVER_ERROR (500)
```

Map through `api/errors.py` infrastructure (`ApiException` or registered handlers). SBGC-57 should add tests for **every** mapping that is part of its contract.

---

# 32. Idempotency Semantics Exposed Through HTTP

- Import: first import → `CREATED`; identical re-import → `UNCHANGED`; changed source metadata → `UPDATED`. **No duplicates.**
- Refresh: `UPDATED` / `UNCHANGED` / `UNAVAILABLE` (SBGC-56 statuses).
- Postman scripts should assert these states (e.g., import twice → second response is `UNCHANGED`).

---

# 33. Expected Postman Scope

Create a Postman collection/environment/test scripts against the implemented endpoints. Recommended scenarios:

**Import:** valid App ID; repeated import (idempotency); unavailable App ID; malformed App ID; authorization failure; rate-limit/upstream mapping where a mock/test environment supports it.

**Refresh:** valid Steam Game; unchanged; metadata changed (controlled fixtures); manual Game rejected; Game not found; unavailable; unauthorized.

Do not make automated CI depend on live Steam (SBGC-58 owns live integration). Postman assets should be reproducible against the local development/test API. Never commit secrets (Postman environment placeholders only).

---

# 34. SBGC-58 Handoff

`SBGC-58 — Test Steam Integration`. Recommended interpretation: controlled **live Steam integration validation** once the HTTP import endpoint, HTTP refresh endpoint, and Postman assets exist:

```text
Postman / HTTP → Django API → Steam service → live Steam → persistence → response
```

Do not perform live validation prematurely in SBGC-57 unless Jira explicitly requires it.

---

# 35. Known Architectural Gaps Entering SBGC-57

- No HTTP import endpoint.
- No HTTP refresh endpoint.
- No Postman collection.
- No live Steam verification.
- No populated backend CDN fetch allowlist (metadata validation ≠ fetch authorization).
- No image downloading/proxying.
- `short_description` / `website_url` / `is_free` / `developers` / `publishers` not persisted.
- No scheduled refresh; no bulk import/refresh.
- No frontend Steam mutation flow.

**Do not solve all of these during SBGC-57** — only what amended SBGC-57 owns (HTTP import/refresh + Postman).

---

# 36. Explicit SBGC-57 Non-Goals

Unless Jira is amended again, SBGC-57 should not add:

```text
image binary downloading
generic CDN proxy
background jobs / scheduled refresh
bulk import / bulk refresh
frontend UI
questionnaire models
community classification
normalized developer/publisher entities
automatic publication
Steam search
user Steam library import
production deployment
live destructive Neon testing
```

---

# 37. Testing Philosophy Specifically for SBGC-57

- **Level 1**: only new API endpoint tests while implementing (auth, schemas, status mapping, import endpoint, refresh endpoint).
- **Level 2**: `api` tests + Steam import/refresh service tests + Game model/listing tests only where response behavior depends on them.
- **Level 3**: one normal backend regression near completion (typecheck, discovery, normal backend tests, migration check, lint/format, deploy/system checks).
- **Level 4**: PostgreSQL probably not needed (no new DB semantics); reverse/shuffle not needed unless API test infrastructure changes materially; warnings not needed unless new resource lifecycle; frontend not needed; **live Steam — do not run automatically (SBGC-58 owns it)**. Postman manual/local validation is appropriate.

---

# 38. Historical Defects and Lessons

| Defect / lesson | Now-preferred method |
|-----------------|----------------------|
| Mutable/arbitrary Steam origins could redirect API-key traffic | Immutable origin constants + closed `SteamEndpointOrigin` with runtime check (SBGC-168/53) |
| Malformed Retry-After / unbounded sleeps | `retry_after_max` + `backoff_max` capped at `retry_sleep_max_seconds`; operation budget ceiling (SBGC-168) |
| Error bodies could mask status classification | Status-first classification, bounded drain, safe close (SBGC-168) |
| `application/*+json` media types mis-rejected | Structured regex accepting `application/<subtype>+json` with optional params (SBGC-168) |
| Numeric-host tricks (decimal/hex/octal IPs) bypassed IP checks | `_NUMERIC_HOST_RE` + `ipaddress` + localhost rejection (SBGC-168/55) |
| Malformed nonblank image metadata silently normalized to `None` (conflated "no image" with "invalid image") | Strict semantics: absent/null/blank → None; malformed nonblank → `SteamMalformedPayloadError` (SBGC-55 correction `ca5de1f`) |
| Partial unique index looked up in `pg_constraint` | Introspect `pg_index`/`pg_indexes` (SBGC-52) |
| Current model used at historical migration states (schema drift → missing column) | Historical project-state models via `MigrationExecutor.loader.project_state()` (SBGC-52; applied to two tests in SBGC-55) |
| `assertRaises` around `atomic` blocks hid savepoint semantics | Expected `IntegrityError` isolated inside nested atomic blocks (SBGC-52/54) |
| Concurrent same-App-ID imports could duplicate | Constraint authority + identity re-check recovery (SBGC-54) |
| Concurrent different-App-ID same-name imports failed permanently on slug | Slug-race recovery: recompute deterministic slug, retry once, only when slug is now occupied (SBGC-54 audit fix) |
| Threaded PG tests leaked connections → teardown failed | `connections.close_all()` inside each worker thread's `finally` (SBGC-54) |
| Discovery audit flagged helper modules named `test_*` | Test helpers must not match `test_*.py` discovery patterns (SBGC-181 rename) |
| Flatpak/host venv mismatch broke sandbox commands | Host venv is authoritative (Python 3.12); run backend commands in the environment that owns the venv (SBGC-181/54 sessions) |
| Broad BasedPyright suppressions | Per-line narrow suppressions; centralize framework-boundary casts (SBGC-53/181) |
| Full-suite-overuse made iterations slow | Four-tier testing philosophy (SBGC-55+) |
| Docs drifted from code after merges (UNSUPPORTED, "11 methods", stale pending lists) | Cross-check docs against code before relying on them (SBGC-181/56) |

---

# 39. Coding Consistency Rules for Post-Compaction Work

1. Inspect before editing — repository is source of truth.
2. DTOs before ORM — external payloads never flow directly into models.
3. One canonical enum owner (`games/types.py`); one field-mapping owner (`_apply_steam_owned_updates`).
4. No duplicate business logic across layers.
5. Models do not make network calls.
6. Network strictly before transactions.
7. Services own orchestration; persistence owns the transaction.
8. Database constraints remain the concurrency authority.
9. Do not swallow generic `IntegrityError` — catch only the expected, verifiable condition.
10. Merged migrations are append-only; never rewrite them.
11. Historical migration models for migration-state tests.
12. Narrow mocks at project-owned boundaries (service factories, adapters, `SteamClient.__init__`).
13. Explicit typed results (frozen dataclasses/enums) for service outcomes.
14. Malformed external data raises; absence is distinct from invalidity.
15. No automatic publication; manual/editorial state always preserved.
16. API handlers stay thin; errors map through centralized API infrastructure.
17. Tests proportional to changed risk; reconcile test arithmetic before reporting.

---

# 40. Hallucination-Prevention Checklist

Before implementing anything:

1. Verify branch and HEAD.
2. Read the Jira scope (registry in `context.md` §32.5 + any human amendments).
3. Read current implementation.
4. Read current tests.
5. Read current migrations.
6. Read canonical docs.
7. Verify assumptions against code.
8. Do not trust old test counts.
9. Do not assume an HTTP endpoint exists.
10. Do not assume DTO fields are persisted.
11. Do not assume Admin behavior equals API behavior.
12. Do not assume SQLite proves PostgreSQL semantics.
13. Do not assume a metadata URL is authorized for backend fetching.
14. Do not invent Steam hostnames.
15. Do not invent auth infrastructure.
16. Do not disable CSRF merely for Postman.
17. Do not expose raw Steam errors.
18. Do not contact production services without explicit human instruction.
19. If a failure occurs, classify it first: production defect / test defect / environment defect / tooling defect / documentation defect.
20. Reconcile arithmetic before final reporting.

---

# 41. Decision Log

| Decision | Chosen approach | Rejected alternative | Why | Ticket | Future consequence |
|----------|-----------------|----------------------|-----|--------|---------------------|
| Game PK | internal BigAutoField | external ID / slug as PK | duplicates, slug changes, manual records | SBGC-45 | stable identity across source changes |
| Steam identity | `(source_type, external_id)` conditional unique | name/slug matching | deterministic, source-qualified | SBGC-45/47 | PG partial unique index (pg_index) |
| Manual vs Steam metadata | separate `manual_*` and `steam_image_url` | shared image field | ownership clarity; imports never overwrite editorial data | SBGC-45/55 | refresh never touches manual fields |
| Classification model | separate Challenge + Reward, each totals 100 | combined profile | framework requires independent profiles | SBGC-46 | DB CheckConstraints own totals |
| Editorial vs questionnaire | separate domains, no shared tables | merged | different provenance/rules | SBGC-46/47 | SBGC-171+ owns questionnaire |
| Steam origins | immutable code constants | env-configurable | API-key traffic cannot be redirected | SBGC-168 | closed `SteamEndpointOrigin` |
| Payload validation | strict structural validation, malformed raises | lenient normalization | external payloads untrusted | SBGC-53/55 | `SteamMalformedPayloadError` taxonomy |
| Image persistence | URL-only, no binaries | proxy/download/storage | context.md §14.3: never store binaries | SBGC-55 | frontend hotlinks; fetch gate stays empty |
| Slug stability | deterministic allocation on create; preserved on refresh | regenerate from name | URL stability; refresh must not mutate identity | SBGC-54/56 | suffixed/fallback determinism |
| Publication | imports start draft; refresh never publishes | auto-publish | editorial control | SBGC-54/56 | type transitions can silently leave listing |
| Missing image on re-import/refresh | preserve stored URL (`None` = no usable field) | clear on absence | ambiguous upstream absence must not destroy state | SBGC-55 | SBGC-56 reuses; strict malformed→raise |
| `last_steam_refresh_at` | set on successful verifications; queryset update on UNCHANGED | always model save | keeps `updated_at` stable for no-op refreshes | SBGC-56 | refresh tracking vs edit tracking separated |
| Network/transaction boundary | network strictly before `transaction.atomic()` | network inside transaction | hold-lock minimization | SBGC-54/56 | proven by `in_atomic_block` tests |
| Testing | four-tier progressive validation | full suite per change | cost; falsification efficiency | SBGC-55+ | CI remains independent broad gate |
| SBGC-57 scope | HTTP endpoints + Postman (human-amended) | Postman only | capability needs an interface | amended 2026-08-14 | SBGC-58 does live validation |
| Live integration | SBGC-58 owns it | SBGC-57 | controlled, intentional live testing | SBGC-57/58 boundary | never automatic |

---

# 42. Current Technical Debt

Not blockers for SBGC-57: BasedPyright per-line suppressions (~90, all narrow); unpersisted Steam DTO metadata; empty CDN fetch allowlist; pre-existing third-party warnings under `-Wa`; no live Render/Neon verification; no frontend integration.

Relevant to SBGC-57 (must engage, not necessarily solve): no API auth abstraction exists — SBGC-57 must decide and implement authorization for the new endpoints; Postman needs a realistic auth + CSRF flow if session auth is chosen.

---

# 43. Exact Current Testing Evidence (SBGC-56 checkpoint — historical evidence, not permanent counts)

- New SBGC-56 tests: 37 (refresh service 30, Admin refresh action 6, model metadata 1).
- Level 2 affected neighborhood: 552 tests OK (2 PG skips).
- Level 3 normal regression: **Found 1329, Ran 1276, OK (skipped=19)**.
- BasedPyright: 0 errors, 0 warnings, 0 notes.
- `makemigrations --check --dry-run`: **No changes detected** (migrations through games.0005 synchronized).
- Discovery audit: passed. Deploy check: passed (accepted W005/W021).
- Heavy suites deliberately skipped: PostgreSQL (no new DB-specific semantics — plain nullable timestamp + standard reversible AddField), reverse/shuffle (no test-infrastructure changes), warnings (no new resource lifecycle), frontend (no frontend change).

---

# 44. Final SBGC-56 Merge Checklist

```text
SBGC-56 is ready for merge if:
- branch clean                       ✅
- pushed                            ✅
- PR CI green                       (human/CI)
- handover committed                (this commit)
- no unresolved schema drift        ✅ (makemigrations clean)
- no pending migrations beyond 0005 ✅
- refresh docs synchronized         ✅
```

---

# 45. Post-Compaction Recovery Procedure

```bash
git fetch origin
git switch main
git pull --ff-only
git status --short --branch
git log --oneline --decorate -20
```

Then read:

```text
docs/Post-Compaction Pre-SBGC-57 Context and Handover.md   ← this file
context.md
docs/backend-architecture.md
docs/backend-api.md
docs/steam-integration.md
docs/steam-import-workflow.md
docs/steam-images.md
docs/steam-metadata-refresh.md
```

Then inspect:

```text
apps/backend/api/
apps/backend/games/services/imports/
apps/backend/games/services/steam/
apps/backend/games/models.py
```

Then lightweight verification (not the full suite):

```bash
git diff --check
npm run test:backend:discovery
apps/backend/.venv/bin/python apps/backend/manage.py makemigrations --check --dry-run --settings=config.settings.test
```

Typecheck (`npm run typecheck:backend`) if the environment is healthy. Do not run the full backend suite solely to regain bearings.

---

# 46. What the Next Agent Should Do First

1. Confirm SBGC-56 is merged.
2. Create the SBGC-57 branch from latest `main`.
3. Re-read Jira — SBGC-57 scope has been human-amended (HTTP + Postman).
4. Inspect existing Django Ninja API conventions (`api/v1.py`, `api/errors.py`, `api/schemas.py`, `games/api.py`, `classifications/api.py`, `api/tests/`).
5. Inspect current auth/authorization infrastructure (none beyond handlers — decide explicitly).
6. Decide HTTP paths and schemas.
7. Decide the authentication mechanism based on existing architecture (session/staff is the most consistent with current state).
8. Implement a thin import endpoint delegating to `SteamGameImportService`.
9. Implement a thin refresh endpoint delegating to `SteamGameRefreshService`.
10. Map all service/Steam errors through the existing API error infrastructure.
11. Add focused endpoint/auth tests (Level 1).
12. Build the Postman collection/environment/test scripts (secrets as placeholders only).
13. Perform local Postman verification against a development server.
14. Run the affected API/Steam neighborhood (Level 2).
15. Run one normal backend completion regression (Level 3).
16. Do **not** perform live Steam integration unless explicitly required before SBGC-58.
17. Prepare the SBGC-58 handoff.

---

*End of handover. Repository, code, tests, migrations, Git history, and canonical docs override this document wherever they conflict.*

---

# Post-SBGC-57 Outcome Note (added 2026-08-14)

SBGC-57 has been implemented on branch
`SBGC-57-configure-postman-api-and-test-scripts`.  The handover's recommended
HTTP architecture was followed: `POST /api/v1/games/steam/import` and
`POST /api/v1/games/{game_id}/steam/refresh`, Django session auth via Ninja's
`auth=django_auth` (session + CSRF) with `is_staff` authorization, thin
handlers over the existing services, explicit schemas, and centralized error
mapping.  Postman assets live under `postman/`.  See `docs/steam-api.md`,
`docs/postman-steam-integration.md`, and the SBGC-57 changelog entry in
`context.md`.  Formal live Steam validation remains SBGC-58.
