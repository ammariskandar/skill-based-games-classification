# Admin Domain Validation — SBGC-51

Validates the Game and editorial-classification domain through real
Django Admin workflows and automated integration tests.

## Test Coverage

### Game Admin (`games/tests/test_admin_validation.py`)

| Area | Tests |
|------|-------|
| Access control | Unauthenticated redirect, non-staff denial, superuser access |
| Valid creation | Steam Game, Manual Game, Published DLC, Draft Game, manual metadata, timestamps |
| Edit | Name, slug, content-type/listings-status independence, manual metadata, source identity |
| Duplicate identity | Duplicate Steam external ID on create and edit, multiple manual NULL external IDs |
| Manual validation | Empty external ID succeeds; manual+external rejected; Steam missing/nondigit/blank; whitespace name; duplicate slug |
| DLC exclusion | Published DLC/Demo/Software/Soundtrack/Unknown excluded; Published Game included; Draft Game excluded |
| Changelist | Steam/manual/draft visible, all content types shown, default manager unfiltered |
| No-network | Game add GET/POST, edit GET/POST, changelist, DLC scenario |

### Classification Admin (`classifications/tests/test_admin_validation.py`)

| Area | Tests |
|------|-------|
| Valid edit | Notes, Challenge scores, Reward scores, PKs preserved, updated_by preserved, timestamps updated |
| Invalid scores (add) | Challenge total 99/101/120, Reward total 99/101, score range via total violation |
| Invalid scores (edit) | Failed edit preserves existing Challenge scores; valid opposite profile doesn't mask invalid |
| Completeness | Missing Challenge, missing Reward, duplicate Challenge, duplicate Reward, forged DELETE (silently ignored) |
| Transaction rollback | Invalid inline prevents parent save, DB failure rolls back parent, failed edit preserves state, unrelated rows unchanged |
| Changelist | Loads, contains game name, contains username |
| No-network | Add GET, valid POST, invalid POST, edit GET, changelist |

## Validation Parity Matrix

| Scenario | Model (`clean()`) | Admin form/formset | Database constraint | Service |
|----------|-------------------|--------------------|-------------------|----------|
| Duplicate Steam identity | — | ✅ (UniqueConstraint) | ✅ | — |
| Invalid source/external ID | ✅ | ✅ | ✅ (CheckConstraint) | — |
| Invalid score range (0–100) | ✅ | ✅ (via total) | ✅ (CheckConstraint) | ✅ |
| Invalid score total (≠100) | ✅ | ✅ | ✅ (CheckConstraint) | ✅ |
| Duplicate profile | — | ✅ (formset) | ✅ (OneToOneField) | ✅ |
| Missing profile | — | ✅ (formset) | —¹ | ✅ |
| Published DLC exclusion | — | — | — | —² |
| Negative score at form level | ✅³ | ✅ (PositiveSmallIntegerField) | ✅ | ✅ |

¹ Database does not enforce child existence — service and Admin both prevent it.
² Public listing exclusion is a queryset rule, not a database constraint.
³ Model `clean()` raises with profile-labeled error keys that cause Django internal
`ValueError` (500) when combined with form-field-level errors.  This is a pre-existing
edge case (not introduced by SBGC-51).  Tests target total violations which use
`__all__` key (safe).

## Pre-Existing Edge Case

`ChallengeProfile.clean()` and `RewardProfile.clean()` use
`validate_score_distribution()` with profile-labeled error keys
(e.g. `"Challenge Micro"`, `"Reward Mystiko"`).  When a score violates
both the form-field range (`PositiveSmallIntegerField` rejects negatives)
and the model `clean()` range check, the model-level `ValidationError`
keys do not match any form field name, causing Django's inline form
`_update_errors` to raise `ValueError` (500).

Tests in SBGC-51 avoid this edge case by:
- Testing range violations through total violations (which use `__all__`)
- Testing negative values through form-field rejection in isolation
- Documenting the limitation for future resolution

## No Network

All Admin paths (add GET/POST, edit GET/POST, changelist, DLC scenario)
are verified to never instantiate `SteamClient`.  The narrowest
project-owned Steam boundary (`SteamClient.__init__`) is patched to
raise `RuntimeError` during every Admin operation.

## Migration State

No schema changes required.  `makemigrations --check --dry-run` reports
"No changes detected."

## Limitations

- The database does not enforce child-profile existence — the Admin formset
  and service both prevent incomplete parents, but direct ORM can bypass.
- Content-type choices are application-level validation, not a database
  `CHECK` constraint.
- The model `clean()` edge case (profile-labeled error keys vs form field
  names) may produce 500 errors when a score is both out of range and
  the total is also wrong.
- No API endpoints consume these Admin workflows.
- No frontend UI integration.
- No bulk-action or import-action Admin tests.

## Manual Validation — August 6, 2026

A human smoke test was performed against the local Django development
server with seeded data and the configured non-default Admin route.

**14/14 checks passed:**

1. Admin URL opened successfully.
2. Existing superuser logged in.
3. Games changelist loaded.
4. Steam and manual records appeared.
5. DLC and non-game content types appeared in Admin.
6. Temporary manual Game created.
7. Manual Game with external ID rejected.
8. Duplicate Steam external ID rejected.
9. Content-type edit preserved listing status.
10. Editorial classification opened.
11. Valid Challenge/Reward score edits persisted.
12. Invalid score total redisplayed form with error.
13. No raw traceback page appeared.
14. Published DLC remains excluded from public listing.
