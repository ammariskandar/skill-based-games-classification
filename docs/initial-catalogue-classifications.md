# Initial Catalogue Classifications — SBGC-128

Curated Challenge and Reward profiles for all 200 games in the SBGC-125
catalogue manifest.

- **Fixture:** `apps/backend/classifications/fixtures/initial_classifications_200.json`
- **Seed command:** `apps/backend/classifications/management/commands/classify_initial_catalogue.py`
- **Offline validation + divergence report:** `apps/backend/.venv/bin/python scripts/verify-initial-classifications.py`
- **Unit tests:** `apps/backend/classifications/tests/test_classify_initial_catalogue.py`
- **Input manifest:** `games/fixtures/initial_catalogue_200.json` (SBGC-125)

## How the vectors are derived

Every game in the catalogue is a *hybrid* aesthetic pair (primary != secondary),
so the instrument assembles each game's questionnaire as:

- **Challenge profile** — the primary aesthetic's set, Part 1 (Q3–Q8 plus the
  branch nodes the answers route to).
- **Reward profile** — the secondary aesthetic's set Q9–Q11, followed by the
  primary aesthetic's set Q12–Q14 (branch nodes included).

The fixture records the answer path for each game as `{node_id: option_index}`
under `challenge_answers` / `reward_answers`, alongside the
`registry_version` it was authored against. The two profiles are then
**computed**, not written by hand: the recorded path is resolved against the
game's assembled questionnaire and pushed through the canonical
`compute_raw_profile` → `normalize_profile` pipeline, so every profile is three
non-negative integers that sum to exactly 100 by construction.

This is a deliberate course-correction. An earlier revision of this fixture
derived vectors arithmetically from `sha256(slug)`, which produced numbers whose
dominant axis matched the manifest label while the remaining axes were
arbitrary — `celeste` reading `macro: 19`, `factorio` reading `micro: 17`. The
questionnaire instrument is now authoritative: answers are authored per title,
and `intended_dominant` is treated as a curation label to *report against*
rather than a target to bend answers toward.

Two consequences worth knowing:

- Only the game's own primary/secondary aesthetics decide which questions it is
  asked, so two games with different aesthetics are not compared on identical
  questions.
- Ratio normalization saturates the extremes. A game with no macro content at
  all reads `100/0/0`-ish on the axis it does have, and several pure-deduction
  titles share the same `0/100/0` Challenge profile. Distinctness is a property
  of the recorded answers, not of the rounded 100-point vector.

## Derived distribution

| Dimension | `intended_dominant` (SBGC-125) | Derived Challenge dominant |
|---|---|---|
| `micro` | 65 | 72 |
| `mystiko` | 65 | 42 |
| `macro` | 70 | 86 |
| **Total** | **200** | **200** |

The instrument reads 26 games differently from the curation label. The shift is
one-directional: the titles labelled `mystiko` split toward `macro` (preparation
and scaling decide the run) and toward `micro` (execution decides it), so
`mystiko` ends up under-represented relative to the curated third.

## Divergence report

Run `scripts/verify-initial-classifications.py` for the live list; the vectors
below are `micro/mystiko/macro`.

### Read `macro` rather than `mystiko` (18)

| Game | Challenge | Reward | Why the instrument disagrees |
|---|---|---|---|
| `slay-the-spire` | 12/14/74 | 3/30/67 | Deck and relic draft is decisive; enemy intents are fully telegraphed. |
| `inscryption` | 5/47/48 | 6/58/36 | Sacrifice-and-bones card economy and escalating boss decks make deckbuilding decisive. |
| `balatro` | 22/5/73 | 9/6/85 | Joker/multiplier stacking is the whole outcome; a bad shop run cannot be outexecuted. |
| `into-the-breach` | 18/14/68 | 3/30/67 | Perfect information and squad loadout decide each battle. |
| `ftl-faster-than-light` | 15/20/65 | 4/33/63 | Loadout and scrap routing gate progress; danger is a build check. |
| `xcom-2` | 6/19/75 | 19/0/81 | Fog of war adds some uncertainty, but squad build and pod economy dominate. |
| `monster-train` | 15/14/71 | 12/0/88 | Clan/upgrade drafting and per-floor scaling decide runs. |
| `darkest-dungeon` | 11/20/69 | 20/16/64 | Party composition and supplies outweigh torchlight uncertainty. |
| `darkest-dungeon-ii` | 12/14/74 | 13/16/71 | Hero-path and runway choices decide the run; turn-order economy is the engine. |
| `battletech` | 21/14/65 | 12/0/88 | Lance weight, heat, and pilot prep decide battles. |
| `roguebook` | 15/14/71 | 17/0/83 | Deck/gem drafting scales and the card engine wins on numbers. |
| `rimworld` | 5/21/74 | 0/51/49 | Colony systems (stockpiles, kill-boxes, mood) decide raids before combat starts. |
| `dwarf-fortress` | 15/13/72 | 0/63/37 | Collapses trace to unmanaged stockpiles and interlocking simulation systems. |
| `oxygen-not-included` | 0/27/73 | 14/30/56 | Heat/gas plumbing and resource loops decide survival, not discovery. |
| `kerbal-space-program` | 17/37/46 | 6/29/65 | Rocket design (staging, delta-v, thrust balance) and orbital mechanics gate progress. |
| `loop-hero` | 0/43/57 | 0/28/72 | Deck composition and tile adjacency resolve the auto-battles. |
| `desperados-iii` | 39/11/50 | 6/21/73 | Character ability loadouts and synchronized cover plans win missions. |
| `divinity-original-sin-2` | 14/14/72 | 0/53/47 | Armor-type matchups and elemental combos are decided in the build screen. |

### Read `micro` rather than `mystiko` (5)

| Game | Challenge | Reward | Why the instrument disagrees |
|---|---|---|---|
| `bloodborne` | 75/16/9 | 10/74/16 | No shield; sidestep spacing and rally/regain make it a reflex duel. |
| `demon-souls` | 84/5/11 | 9/31/60 | Roll i-frames and stamina timing decide fights. |
| `prey` | 50/3/47 | 0/62/38 | Typhon fights turn on real-time aim/dodge and spotting a disguised mimic. |
| `alien-isolation` | 57/3/40 | 47/34/19 | Hiding from a dynamic Xenomorph and dodging androids is movement and timing. |
| `dishonored-2` | 50/21/29 | 0/64/36 | Blink-and-parry duels and split-second stealth routing. |

### Other (3)

| Game | Intended | Challenge | Reward | Why the instrument disagrees |
|---|---|---|---|---|
| `superliminal` | `mystiko` | 50/50/0 | 17/69/14 | Truthful answers land a micro/mystiko tie; the fixed Micro tie-break decides it. The Reward profile is cleanly `mystiko`. |
| `cities-skylines-ii` | `macro` | 0/95/5 | 31/45/24 | The Sensory challenge set has no economy or area-control lever; the "reverse-engineer the simulation" load routes through the puzzle branch. `cities-skylines` itself derives `macro`. |
| `splatoon-3` | `macro` | 59/37/4 | 17/6/77 | Turf control is genuinely macro, but the Sensory challenge set has no area-control question, so the answers land on execution and movement. |

## Reproducing and re-running

```bash
# Validate the fixture, re-derive every profile, print the divergence report.
apps/backend/.venv/bin/python scripts/verify-initial-classifications.py

# CI gate.
cd apps/backend && ./.venv/bin/python manage.py test classifications.tests.test_classify_initial_catalogue --settings=config.settings.test

# Seed production (operator, local terminal, against the Neon direct URL).
cd apps/backend && DATABASE_URL="<neon direct>" ./.venv/bin/python manage.py classify_initial_catalogue --username timunlessteh
```

The seed command is idempotent — an existing submission by the same user for the
same game is updated in place — so it can be re-run after any fixture edit.

## Follow-up

The divergence is a property of the instrument, not a defect in the fixture. If
the published catalogue needs the `mystiko` share closer to the curated third so
the rankings and filters exercise all three axes evenly, the options are:

- revise the 26 `intended_dominant` labels in the SBGC-125 manifest to match what
  the instrument reads (they are curation metadata; nothing in the application
  consumes them), or
- revisit the instrument's weighting where Set A and Set D under-represent
  `mystiko` against `macro` for turn-based, information-visible games.

Both are product decisions outside SBGC-128's scope.
