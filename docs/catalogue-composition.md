# Initial Catalogue Composition — SBGC-125

Curated source of truth for the first 200 games that populate MyGameDNA.

- **Manifest:** `apps/backend/games/fixtures/initial_catalogue_200.json`
- **Offline validation:** `apps/backend/.venv/bin/python scripts/verify-initial-catalogue.py`
- **Live AppID validation:** `apps/backend/.venv/bin/python scripts/verify-initial-catalogue.py --online`
- **Unit tests:** `apps/backend/games/tests/test_initial_catalogue_manifest.py`

## Purpose

The manifest is the authoritative input for the two SBGC-20 population steps:

- **SBGC-126** bulk-imports the 175 `STEAM` entries through the Steam adapter.
- **SBGC-127** creates the 25 `MANUAL` entries directly.

Defining it here, ahead of any import, keeps curation reviewable as data and
lets the AppID set be proven against Valve before a single network import runs.

## Distribution

| Split | Count | Share |
|---|---|---|
| `STEAM` | 175 | 87.5% |
| `MANUAL` | 25 | 12.5% |
| **Total** | **200** | **100%** |

### Skill bias (`intended_dominant`)

| Dimension | Count | Character |
|---|---|---|
| `micro` | 65 | mechanical execution, precision, reaction, timing |
| `mystiko` | 65 | uncertainty, adaptation, hidden information, deduction |
| `macro` | 70 | planning, resource economies, long-term positioning |

Each dimension dominates roughly a third of the catalogue so the rankings,
filters, search index, and radar charts exercise the full analytical range
rather than clustering on one axis.

> `intended_dominant` is curation metadata for this spread. Nothing in the
> application consumes it, and it is not a target for the editorial
> classifications: SBGC-128 derives those profiles from the questionnaire
> instrument and reports where the instrument reads a title differently. See
> [`initial-catalogue-classifications.md`](initial-catalogue-classifications.md).

### Primary aesthetic

| Aesthetic | Count |
|---|---|
| `CHALLENGE` | 67 |
| `FANTASY` | 54 |
| `SENSORY` | 40 |
| `NARRATIVE` | 39 |

All four aesthetics appear as a primary driver, and no title repeats the same
aesthetic as both primary and secondary.

## Source split

### Steam (175)

Chosen for recognisable, mechanically distinct design across all three
dimensions. Every `steam_appid` was resolved live against the Steam Store API
and asserted to return `type: "game"` — no DLC, demos, soundtracks, software,
or delisted base games.

Four entries were rejected by that gate and corrected during curation:

| Title | Rejected AppID | Reason | Resolution |
|---|---|---|---|
| Paradise Killer | 1166720 | `type: "music"` (soundtrack) | corrected to 1160220 |
| Darkest Dungeon II | 1608650 | `success: false` | corrected to 1940340 |
| Per Aspera | 803180 | `success: false` | corrected to 803050 |
| Metal Gear Rising: Revengeance | 235460 | `success: false` (delisted) | replaced with Nine Sols (1809540) |

### Manual / non-Steam (25)

Console and first-party titles with no Steam release, which is why they are
seeded rather than imported. Coverage spans Nintendo Switch and legacy
Nintendo, PlayStation, and retro hardware.

Every manual entry carries `developer` and `release_date`; `steam_appid` is
always `null` so the Steam adapter can never claim them.

## Schema

```json
{
  "slug": "hades",
  "name": "Hades",
  "source": "STEAM",
  "steam_appid": 1145360,
  "primary_aesthetic": "CHALLENGE",
  "secondary_aesthetic": "NARRATIVE",
  "intended_dominant": "micro"
}
```

Manual entries replace `steam_appid` with `null` and add `developer` and
`release_date`:

```json
{
  "slug": "the-legend-of-zelda-breath-of-the-wild",
  "name": "The Legend of Zelda: Breath of the Wild",
  "source": "MANUAL",
  "steam_appid": null,
  "developer": "Nintendo EPD",
  "release_date": "2017-03-03",
  "primary_aesthetic": "FANTASY",
  "secondary_aesthetic": "SENSORY",
  "intended_dominant": "mystiko"
}
```

### Field contract

| Field | Notes |
|---|---|
| `slug` | unique; becomes `Game.slug` |
| `name` | display name; becomes `Game.name` |
| `source` | `STEAM` or `MANUAL` — maps to `SourceType.STEAM` / `SourceType.MANUAL` (lowercase) at import time |
| `steam_appid` | positive integer for `STEAM`; `null` for `MANUAL`; becomes `Game.external_id` (decimal string) |
| `primary_aesthetic` / `secondary_aesthetic` | canonical `games.models.Aesthetic` values |
| `intended_dominant` | canonical `Dimension` value from the questionnaire registry |
| `developer` / `release_date` | `MANUAL` only; `STEAM` values are Steam-managed |

## Invariants enforced

`scripts/verify-initial-catalogue.py` and the unit tests both assert:

1. exactly 200 entries, split 175 `STEAM` / 25 `MANUAL`
2. slugs are unique and non-null `steam_appid` values are unique
3. every `STEAM` AppID is a positive integer and resolves to a standalone game
4. every `MANUAL` entry has `steam_appid: null` plus `developer` and `release_date`
5. aesthetics and `intended_dominant` match the canonical enums
6. primary and secondary aesthetics differ

The offline checks run without network access. `--online` additionally queries
`store.steampowered.com` per AppID and is intended to gate a bulk import, not
to run in CI — the Store API rate-limits bursts, so a single `success: false`
should be re-checked before a title is treated as invalid.
