# Postmortem — Unified Rankings 500 (PostgreSQL `jsonb` arithmetic)

- **Status:** fixed
- **Related feature:** SBGC-81 (public ranking API), SBGC-199 (centralized dominant-category expression)
- **Scope:** engineering incident record, not a product decision

## 1. Incident

Every request to `/api/v1/rankings/` in production returned
`500 INTERNAL_SERVER_ERROR`, which the Astro rankings page renders as:

> Rankings are temporarily unavailable. Please try again in a moment.
> Code: SERVICE_UNAVAILABLE

The message reads as a transient outage, so it presented as intermittent
unavailability rather than a permanent defect.

Directly probing the backend localised it immediately:

| Request | Result |
|---|---|
| `/api/v1/rankings/` (defaults — `profile=unified`) | 500 |
| `/api/v1/rankings/?profile=challenge` | 200 |
| `/api/v1/rankings/?profile=reward` | 200 |
| `/api/v1/rankings/?dominant=micro&profile=challenge` | 200 |
| `/api/v1/games/`, `/health/` | 200 |

Only the **Unified** profile failed, and the frontend's error surface turned a
deterministic bug into a "try again in a moment" message.

## 2. Root cause

`published_score()` extracts one element from the snapshot's score vector:

```python
.values(f"{field}__{index}")[:1]        # compiles to: ("unified_integer_challenge" -> 0)
```

`unified_integer_challenge` / `unified_integer_reward` are `JSONField`s, so the
`->` operator yields **`jsonb`**.  The Unified profile then adds two of those
expressions together:

```python
return published_score("challenge", dimension) + published_score("reward", dimension)
```

PostgreSQL has no `jsonb + jsonb` operator:

```sql
((SELECT ("unified_integer_challenge" -> 0) ... LIMIT 1)
 + (SELECT ("unified_integer_reward"    -> 0) ... LIMIT 1)) AS "_score"
-- ERROR: operator does not exist: jsonb + jsonb
```

Challenge and Reward survived because they only need `IS NOT NULL` filtering and
`ORDER BY`, both of which `jsonb` supports — which is why the failure looked
profile-specific.

`Subquery(..., output_field=IntegerField())` declared an integer while emitting
`jsonb`.  `output_field` is compiler metadata, not a cast: nothing enforces it.

## 3. Why it was not caught

1. The default suite runs on **in-memory SQLite** (`config.settings.test`).
   SQLite extracts JSON into an untyped value and happily evaluates `+`, so the
   same expression returns correct numbers there.
2. The PostgreSQL CI job ran only constraint, migration, and concurrency
   modules — never a read path.
3. The tests that *would* have failed already existed
   (`api/tests/test_game_rankings.py` has 59 references to unified scores,
   including `test_unified_equals_average_and_differs_from_both`), but only ever
   executed on SQLite.

The defect has been present since the original SBGC-81 commit (`d3598ed`), and
`unified` is the *default* ranking profile — so the endpoint 500s on PostgreSQL
whenever the Unified profile is requested, independently of the data.

## 4. Resolution

`published_score()` now extracts the element as text and casts it to an integer,
so every score is a real integer on every backend:

```sql
((SELECT (("unified_integer_challenge" ->> 0))::integer ... LIMIT 1)
 + (SELECT (("unified_integer_reward"    ->> 0))::integer ... LIMIT 1)) AS "_score"
```

The cast also makes ordering and `_cat_*` dominance comparisons numeric rather
than JSON-ordering, which is what the code always intended.

## 5. Adopted controls

- **Read paths that build SQL arithmetic over a JSON column must run on the
  production vendor.** A new `games.tests.test_pg_read_paths` module executes the
  Unified ranking arithmetic (sum, `.5` preservation, summed dominant filter,
  unclassified exclusion, single-profile typing) against real PostgreSQL, and is
  wired into `scripts/backend-test-postgresql.sh`.
- **`output_field` is a declaration, not a guarantee.** A JSONField extraction
  decorated with `IntegerField` is still `jsonb` in the query. Treat the SQL type
  of any expression used in arithmetic or comparisons as unverified until it has
  been compiled for, or executed against, the target vendor.
- **Error surfaces must not invent transience.** The rankings page maps every
  SSR failure to a 503 `SERVICE_UNAVAILABLE` panel whose copy implies "try
  again". A permanent server defect should be diagnosable from the response
  without probing the backend directly.
