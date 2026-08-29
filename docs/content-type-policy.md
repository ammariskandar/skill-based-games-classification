# Content-Type Policy — SBGC-94

Canonical product-content classification, Steam mapping, and public
eligibility policy.  This document is the **policy contract**; the queryset
mechanics live in `game-listing-rules.md` (SBGC-48), and the contract tests
live in `games/tests/test_content_type_policy.py` (SBGC-94).

## Canonical Taxonomy

Six normalized content types (`games/types.py`, SBGC-53) classify every
canonical `Game` record.  `GAME` is the default and the **only** publicly
listable type.

| Value | Python member | Label | Meaning | Publicly listable |
|-------|---------------|-------|---------|-------------------|
| `game` | `ContentType.GAME` | Game | A full, standalone, playable video game | ✅ |
| `dlc` | `ContentType.DLC` | Downloadable content | Expansion, season pass, add-on, cosmetic pack | ❌ |
| `demo` | `ContentType.DEMO` | Demo | Free trial or slice of a game | ❌ |
| `software` | `ContentType.SOFTWARE` | Software | Non-game application (tool, SDK, engine, benchmark) | ❌ |
| `soundtrack` | `ContentType.SOUNDTRACK` | Soundtrack | Standalone music / OST product | ❌ |
| `unknown` | `ContentType.UNKNOWN` | Unknown | Type not determinable or unmapped | ❌ |

`UNKNOWN` replaced the former `OTHER` value (SBGC-48) and is the fallback for
anything the Steam pipeline cannot map.

## Steam Type Mapping

`map_steam_product_type(raw)` (`games/services/steam/mapping.py`, SBGC-53) is
the deterministic pure mapping used by the Steam import/refresh pipeline
(SBGC-54/56).  It is case-insensitive and trims whitespace.

| Raw Steam `type` | Canonical type |
|------------------|----------------|
| `game` | `GAME` |
| `dlc` | `DLC` |
| `demo` | `DEMO` |
| `software` | `SOFTWARE` |
| `music`, `soundtrack` | `SOUNDTRACK` |
| Any other nonblank string — `application`, `tool`, `hardware`, `video`, `series`, `episode`, `mod`, `advertising`, … | `UNKNOWN` |
| Blank, whitespace-only, or non-string input | Raises `ValueError` (malformed payload) |

> **Note on `application`:** Steam uses the literal `application` type for
> software, tools, and benchmarks.  The current mapping sends `application`
> to `UNKNOWN` — only the literal string `software` maps to `SOFTWARE`.  This
> is the existing contract; a finer-grained bucket (e.g. `application` →
> `SOFTWARE`) is a deliberate future decision and is *not* current behavior.

Because `UNKNOWN` is never publicly listable, every unmapped or ambiguous
Steam product is excluded from the public game surface by default — the
mapping is fail-closed by construction.

## Public Eligibility Gate

The single source of truth for public visibility is the queryset method:

```python
Game.objects.publicly_listable()
```

which requires **both**:

1. `content_type = ContentType.GAME`
2. `listing_status = ListingStatus.PUBLISHED`

Every other combination is excluded from the public surface — catalogue,
rankings, search index, game detail, and homepage carousel:

- Published `DLC` / `DEMO` / `SOFTWARE` / `SOUNDTRACK` / `UNKNOWN`
- `DRAFT` or `ARCHIVED` `GAME`

`content_type` and `listing_status` are independent dimensions: changing one
never mutates the other.  A type transition alone removes a record from the
public listing while leaving its status untouched (and vice versa).

## Ambiguous Case Guidelines (owner overrides)

- **Standalone expansions / DLC**: may be reclassified as `GAME` when the
  product runs fully standalone (its own executable, no base-game dependency)
  and carries independent skill profiles.  This is an owner decision; today
  it is expressed by registering the product as a Manual `GAME` (see
  `manual-game-management.md`) — Steam-sourced types remain Steam-owned until
  an owner-override mechanism exists (SBGC-96).
- **Bundles / GOTY / Deluxe editions**: classify as `GAME` when the package
  contains the base playable game client (base game + bundled DLC).  Classify
  as `DLC` when it is only an add-on package without the base client.
- **Remasters / re-releases**: `GAME` when they are a playable game client.
- **Mods / advertising / hardware / video**: no dedicated type exists; they
  map to `UNKNOWN` and stay excluded from the public listing.

## Contract Tests

`games/tests/test_content_type_policy.py` (SBGC-94) pins this policy:

- `TaxonomyContractTests` — exactly six canonical values; `CONTENT_TYPE_CHOICES`
  covers every enum value with clean labels.
- `SteamMappingContractTests` — the full mapping truth table (mapped types,
  unrecognized → `UNKNOWN` including `application`, malformed input →
  `ValueError`).
- `PublicEligibilityContractTests` — among six PUBLISHED records spanning all
  content types, only the `GAME` appears in `publicly_listable()`; a `GAME`
  in `DRAFT` or `ARCHIVED` status is excluded.
