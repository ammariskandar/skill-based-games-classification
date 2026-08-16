# Classification Submissions — SBGC-63

Canonical editorial classification submission architecture.

## Domain

```text
Game
 ├─ Submission by User A   (Challenge + Reward)
 ├─ Submission by User B   (Challenge + Reward)
 └─ Submission by User C   (Challenge + Reward)
```

- One user may submit at most once per Game (`(game, submitted_by)` unique).
- One user may submit many different Games.
- A Game may have many submissions from different users.
- `ChallengeProfile` / `RewardProfile` are one-to-one with each submission.

The existing `EditorialClassification` model now represents a **submission**.
The future computed result is **Final Classification** (SBGC-65), which is
not implemented here.

## Attribution

- `submitted_by` — whose classification/opinion this is (immutable after creation).
- `updated_by` — the operator who last changed the record (may differ).

Runtime creation is explicit: `submitted_by` is required for new records
and is **not** inferred from `updated_by`.  The migration-only backfill maps
historical rows' `submitted_by` to their existing `updated_by` because the
pre-SBGC-63 model had no separate submitter concept (see migration `0003`).

## Roles and snapshot

Editorial statistical roles (fixed product constants):

```text
SUPERUSER        1.00   (user.is_superuser only)
MODERATOR        0.95
COMMUNITY_LEADER 0.65
COMMUNITY        0.20
```

`submitted_role` and `submitted_base_weight` are snapshotted at submission
creation.  Normal edits never re-resolve or mutate the snapshot.

Group role metadata lives on `EditorialGroupProfile` (OneToOne to Django
Group) with mutually exclusive Moderator / Community Leader flags.  Neither
flag means Community.  Superuser is never a Group flag.

A user belonging to both a Moderator-designated Group and a
Community-Leader-designated Group is a **conflict**: role resolution raises
and submission creation leaves no partial row.  No "highest role wins"
fallback is applied.

## Service

`classifications/services/submissions.py`:

- `resolve_editorial_role(user)`
- `create_submission(...)`
- `update_submission(...)`

`classifications/services/editorial.py` keeps `set_editorial_classification()`
as a backward-compatible wrapper (submitted_by defaults to updated_by).

## Admin

- `EditorialClassificationAdmin` presents submissions with Game, Submitted
  by, role, Challenge/Reward summaries, Updated by, and Updated at.
- Game / submitted_by are readonly on edit.
- For ordinary (non-superuser) operators, `submitted_by` is derived from
  `request.user` and not selectable; only superusers may create on behalf of
  another user.
- The resolved role/weight preview is shown before save for the operator's
  own submission; `submitted_role` / `submitted_base_weight` are never
  operator-editable.
- Duplicate submissions and score totals surface friendly operator-facing
  messages rather than raw database constraint names.
- Group Admin exposes the Moderator / Community Leader flags via an inline.

## Not implemented in SBGC-63

No Method 1/2/3, no confidence, no weights math, no outlier rejection, no
iForest/LoOP, no Final Classification computed result.
