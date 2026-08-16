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
- For superuser on-behalf creation, the preview follows the selected
  `submitted_by` via a backend-supplied role map (no operator-editable
  role/weight fields).
- Superuser is shown on the Group/editorial-role management screen as a
  system-defined, read-only role with the current superusers listed
  dynamically; no fake Superuser Group is created.
- Duplicate submissions and score totals surface friendly operator-facing
  messages rather than raw database constraint names.
- Non-superusers may only edit their own submissions; superusers may edit
  any submission under standard Django change-permission policy.
- Group Admin exposes the Moderator / Community Leader flags via an inline.

## Validation record

Final human Admin validation passed on local SQLite (2026-08-16).  All prior
SBGC-63 checks remain green, and the final pass fixed one production crash
found during human testing.

- **Regression:** an out-of-range score (e.g. `200`) raised
  `ValueError: 'ChallengeProfileForm' has no field named 'Challenge Mystiko'`.
  `validate_score_distribution()` was keying `ValidationError` by
  human-readable labels instead of real field names, so Django inline form
  validation crashed (HTTP 500).
- **Fix:** field errors are now keyed by the concrete model/form field names
  `micro_score` / `mystiko_score` / `macro_score`; human-readable labels stay
  inside the message text (e.g. `"Challenge Mystiko must be between 0 and 100
  (got 200)."`).  Total errors remain on `__all__`.
- `DEBUG=True` only exposed the traceback; it was **not** the cause and was
  not changed.  With `DEBUG=False` the same input was a 500.
- Duplicate-submission wording is contextual: self-submission says
  `"You have already submitted scores for this game."`; privileged on-behalf
  says `"This user has already submitted scores for this game."`.
- PostgreSQL cardinality/uniqueness verification was **not** freshly run for
  this pass (no disposable PostgreSQL 16 image in the sandbox; not Neon).
  The fix is application-level validation only and changes no DB semantics.

Final human retest (local SQLite): Challenge `20 / 200 / 60` and Reward
`20 / 200 / 60` showed friendly range errors without traceback; in-range but
wrong totals showed friendly exact-total errors; duplicate self-submission
showed the exact friendly wording.  All prior SBGC-63 checks remain passed.

## Validation hardening (SBGC-64)

- Role/weight snapshot consistency is enforced at three layers: the service
  always derives the pair, `EditorialClassification.clean()` rejects
  mismatches, and the `CheckConstraint`
  `editorial_submission_role_weight_ck` provides last-resort DB protection
  for raw saves that bypass `full_clean()`.
- Model-level duplicate validation now translates the
  `(game, submitted_by)` uniqueness violation into friendly wording instead
  of Django's generated "already exists" sentence.
- `create_submission()` translates a lost uniqueness race (pre-check passed,
  but the DB `UniqueConstraint` fired) into `EditorialSubmissionError`
  without swallowing unrelated `IntegrityError`s.
- Admin `has_change_permission()` restricts non-superusers to editing only
  their own submissions.
- Score range/total, uniqueness, identity immutability, role conflict, and
  group mutual exclusion remain enforced at their existing layers (model,
  service, Admin, DB).

## Not implemented in SBGC-63

No Method 1/2/3, no confidence, no weights math, no outlier rejection, no
iForest/LoOP, no Final Classification computed result.
