# Development Seed Data — SBGC-50

Deterministic sample data for local development.  A management command
creates representative Games, editorial classifications, and a seed
editor user.

## Quick Start

```bash
apps/backend/.venv/bin/python \
  apps/backend/manage.py migrate \
  --settings=config.settings.development

apps/backend/.venv/bin/python \
  apps/backend/manage.py seed_development_data \
  --settings=config.settings.development
```

Rerunning is safe — the command is idempotent.

## Safety Gate

`DEVELOPMENT_SEEDING_ENABLED` is `True` only in
`config.settings.development`.  Every other settings module
(`test`, `production`) keeps it `False`.  The command raises
`CommandError` before any writes when the gate is disabled.

There is no production force flag.  There is no environment variable.

## Seed Editor

- **Username:** `development-editor`
- **Email:** `development-editor@example.invalid`
- **Privileges:** none (`is_staff=False`, `is_superuser=False`)
- **Password:** unusable (no login possible)
- **Re-run:** restores email and unusable-password state

The command never creates a superuser.  If a privileged account already
uses the seed username, the command raises `CommandError`.

## Sample Coverage

9 Games spanning Steam and manual sources, public and draft states,
Game and non-game content types, classified and unclassified records.

5 Games have complete editorial classifications created through
`set_editorial_classification()`.

### Steam Samples

| Slug | App ID | Name | Content | Status |
|------|--------|------|---------|--------|
| portal-2 | 620 | Portal 2 | Game | Published |
| hades | 1145360 | Hades | Game | Published |
| dev-demo-sample | 220 | Development Demo Sample | Demo | Published |
| dev-soundtrack-sample | 323190 | Development Soundtrack Sample | Soundtrack | Published |

**Important:** Steam App IDs are deterministic local identifiers only.
They have not been remotely verified through the Steam Web API.  Names
for demo and soundtrack samples are explicitly marked as development
samples to avoid confusion with remotely verified metadata.

### Manual Samples

| Slug | Name | Content | Status |
|------|------|---------|--------|
| chess | Chess | Game | Published |
| go | Go | Game | Published |
| sample-productivity-tool | Sample Productivity Tool | Software | Published |
| unresolved-sample | Unresolved Sample | Unknown | Draft |
| tied-challenge-sample | Tied Challenge Sample | Game | Published |

### Classification Samples

| Game | Challenge | Reward | Notes |
|------|-----------|--------|-------|
| portal-2 | 50/20/30 | 10/30/60 | Classic puzzle-platformer |
| hades | 60/25/15 | 20/50/30 | Roguelike action |
| chess | 30/50/20 | 10/10/80 | Abstract strategy |
| go | 20/70/10 | 5/80/15 | Deep strategy |
| tied-challenge-sample | 50/50/0 | 25/25/50 | Challenge tie example |

All profiles total exactly 100.  The tied-challenge sample demonstrates
dominant-skill tie → `NULL` behavior.

## Idempotency

Re-running produces identical results — no duplicates, stable primary
keys, restored canonical values.

## Corrective Reruns

If seeded data is modified (name, listing status, scores, notes,
metadata, user email), re-running restores the canonical values
without affecting unrelated records.

## Non-Destructive Behavior

Only records identified by stable lookup keys (Steam: `source_type` +
`external_id`; Manual: `slug`) are touched.  Unrelated user accounts,
Games, and classifications are left unchanged.

## Conflicts

- Manual slug occupied by a Steam record → `CommandError`
- Seed username occupied by a privileged account → `CommandError`
- Steam identity collision on slug → `CommandError`

No source identity is silently changed.

## Transaction Atomicity

The full seed operation runs inside `transaction.atomic()`.  Any
failure rolls back all command-owned writes.  Pre-existing records
are restored to their pre-run state.

## No Network

The seed command never contacts Steam, fetches CDN images, verifies
App IDs, or makes any external network request.  All data is locally
deterministic.

## What SBGC-50 Does Not Include

- JSON or YAML fixture files — the management command is the canonical
  seed mechanism
- Sample data in migrations
- Production seeding capability
- A superuser
- Usable passwords
- Questionnaire or community classification samples
- Automatic execution from build, migration, start, Render, or CI scripts
- Hundreds of records — the sample is representative, not exhaustive
