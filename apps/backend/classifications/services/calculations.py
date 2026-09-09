"""
Derived-classification calculation service — SBGC-65 / SBGC-197.

Runs the calculation lifecycle as three isolated phases (R4-02):

1. Claim  — transactionally allocate/lock the next attempt (or skip Games
   that already SUCCEEDED in the epoch, so a resumed epoch never collides).
2. Compute — freeze the population and run the pure engine with zero DB
   locks or transaction context held.
3. Finalize — atomically persist the snapshot, demote/promote the single
   current snapshot, persist the boundary, and mark the attempt SUCCEEDED;
   a failure rolls the whole block back and records the attempt FAILED in an
   isolated transaction.

No statistical logic lives here — only the persistence/coordination
boundary around ``classifications.calculations``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from django.db import transaction
from django.utils import timezone
from games.models import Game

from classifications.calculations.confidence import BoundaryCalibrationData
from classifications.calculations.constants import (
    BHPCM_VERSION,
    CONFIDENCE_FINAL_VERSION,
    MASTER_VERSION,
    METHODS_VERSION,
)
from classifications.calculations.engine import GameCalculationResult, calculate_game
from classifications.calculations.profiles import (
    PopulationSnapshot,
    Profile,
    SubmissionRecord,
    build_population_snapshot,
)
from classifications.calculations.results import (
    INSUFFICIENT_ANCHOR,
    INSUFFICIENT_METHOD_1,
    INSUFFICIENT_METHOD_2,
    INSUFFICIENT_METHOD_3,
    INSUFFICIENT_SAMPLE_FOR_IFOREST,
    INSUFFICIENT_SAMPLE_FOR_LOOP,
    NO_SUBMISSIONS,
    NO_SURVIVING_SUBMISSIONS,
    READY,
    UNIFIED_CALCULATION_UNSTABLE,
)
from classifications.models import (
    BoundaryCalibration,
    CalculationAttempt,
    CalculationEpoch,
    ChallengeProfile,
    ClassificationSnapshot,
    EditorialClassification,
    RewardProfile,
    UserGameScoreSubmission,
)
from classifications.roles import EditorialRole
from classifications.services.notifications import (
    CalculationFailureNotice,
    CalculationFailureNotifier,
)

logger = logging.getLogger(__name__)

# Domain outcomes are mathematical results, not infrastructure failures:
# retrying them cannot change a deterministic calculation (ticket section 9).
DOMAIN_STATUSES = frozenset(
    {
        NO_SUBMISSIONS,
        INSUFFICIENT_ANCHOR,
        INSUFFICIENT_SAMPLE_FOR_IFOREST,
        INSUFFICIENT_SAMPLE_FOR_LOOP,
        NO_SURVIVING_SUBMISSIONS,
        INSUFFICIENT_METHOD_1,
        INSUFFICIENT_METHOD_2,
        INSUFFICIENT_METHOD_3,
        UNIFIED_CALCULATION_UNSTABLE,
    }
)

ENGINE_FAILURE_CATEGORY = "engine_failure"
DOMAIN_OUTCOME_CATEGORY = "domain_outcome"
MAX_ATTEMPTS_PER_GAME_EPOCH = 4


class ClaimStatus(StrEnum):
    """Outcome of a Phase-1 transactional attempt claim (SBGC-197 / 198)."""

    CLAIMED = "claimed"
    SKIPPED_ALREADY_SUCCEEDED = "skipped_already_succeeded"
    SKIPPED_UNCHANGED = "skipped_unchanged"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True)
class PureCalculationResult:
    """Phase-2 output: the engine result plus its frozen-input diagnostics.

    Bundles everything Phase 3 needs to persist so the numerical work can run
    with zero database locks or transaction context held (SBGC-197).
    """

    result: GameCalculationResult
    received: int
    invalid: int
    cutoff_at: Any


def freeze_population(game: Game, cutoff_at) -> tuple[PopulationSnapshot, int, int]:
    """Freeze the canonical valid submission population for one Game/epoch.

    Returns ``(population, received_count, invalid_count)``.  A submission's
    effective state is committed at or before ``cutoff_at`` when its
    ``updated_at`` is at or before the cutoff (Part E.2); later edits belong
    to the next epoch.  Submissions failing the frozen input-validation
    rules are removed before N is established (Part A.4).
    """
    records = (
        EditorialClassification.objects.filter(game=game, updated_at__lte=cutoff_at)
        .select_related("challenge_profile", "reward_profile")
        .order_by("pk")
    )
    received = 0
    candidates: list[SubmissionRecord] = []
    for submission in records:
        received += 1
        try:
            challenge = submission.challenge_profile
            reward = submission.reward_profile
        except (ChallengeProfile.DoesNotExist, RewardProfile.DoesNotExist):
            continue
        candidates.append(
            SubmissionRecord(
                identifier=f"submission-{submission.pk}",
                challenge=Profile(
                    micro=float(challenge.micro_score),
                    macro=float(challenge.macro_score),
                    mystiko=float(challenge.mystiko_score),
                ),
                reward=Profile(
                    micro=float(reward.micro_score),
                    macro=float(reward.macro_score),
                    mystiko=float(reward.mystiko_score),
                ),
                role=submission.submitted_role,
            )
        )
    population = build_population_snapshot(candidates)
    invalid = len(candidates) - population.raw_n

    # 2. Pool community score submissions (SBGC-216) — same effective-state
    #    cutoff semantics (updated_at <= cutoff) and canonical ordering.
    community_records = UserGameScoreSubmission.objects.filter(
        game=game, updated_at__lte=cutoff_at
    ).order_by("pk")
    for community in community_records:
        received += 1
        candidates.append(
            SubmissionRecord(
                identifier=f"community-{community.pk}",
                challenge=Profile(
                    micro=float(community.challenge_micro),
                    macro=float(community.challenge_macro),
                    mystiko=float(community.challenge_mystiko),
                ),
                reward=Profile(
                    micro=float(community.reward_micro),
                    macro=float(community.reward_macro),
                    mystiko=float(community.reward_mystiko),
                ),
                role=EditorialRole.COMMUNITY,
            )
        )

    population = build_population_snapshot(candidates)
    invalid = len(candidates) - population.raw_n
    return population, received, invalid


def stored_boundary(game: Game) -> BoundaryCalibrationData | None:
    """The persisted static boundary constant, or None before calibration."""
    row = (
        BoundaryCalibration.objects.filter(game=game, master_version=MASTER_VERSION)
        .order_by("-calibrated_at")
        .first()
    )
    if row is None:
        return None
    return BoundaryCalibrationData(
        status=row.status or READY,
        delta=row.delta,
        calibration_population_hash=row.calibration_population_hash,
        population_size=row.population_size,
        subset_count_attempted=row.subset_count_attempted,
        subset_count_ready=row.subset_count_ready,
        sampler_version=row.sampler_version,
        seed_or_stream=row.seed_or_stream,
        version=CONFIDENCE_FINAL_VERSION,
    )


def execute_pure_calculation(
    *,
    game: Game,
    cutoff_at,
    frozen_population: tuple[PopulationSnapshot, int, int] | None = None,
    bootstrap_replicates: int | None = None,
    governance_draws: int | None = None,
) -> PureCalculationResult:
    """Phase 2 — run the engine with zero DB locks held.

    Accepts an already-frozen ``(population, received, invalid)`` triple when
    the caller computed it for a content-addressed skip check (SBGC-198), so
    the calculated result is guaranteed to match the population that was
    hash-checked; otherwise freezes at ``cutoff_at`` first.  The CPU-heavy
    numerical work runs outside any ``transaction.atomic`` context or row
    lock (SBGC-197).
    """
    if frozen_population is None:
        frozen_population = freeze_population(game, cutoff_at)
    population, received, invalid = frozen_population
    boundary = stored_boundary(game)
    result = calculate_game(
        population,
        game_identifier=str(game.pk),
        stored_boundary=boundary,
        bootstrap_replicates=bootstrap_replicates,
        governance_draws=governance_draws,
    )
    return PureCalculationResult(
        result=result, received=received, invalid=invalid, cutoff_at=cutoff_at
    )


def claim_game_calculation_attempt(
    epoch: CalculationEpoch, game_id: int
) -> tuple[ClaimStatus, CalculationAttempt | None]:
    """Phase 1 — transactionally claim the next attempt for (epoch, game).

    Serialises on the epoch row, SKIPs Games that already SUCCEEDED in the
    epoch (idempotent resume), and allocates the next free ``attempt_number``
    so re-running an interrupted epoch never collides on the
    ``(game, epoch, attempt_number)`` unique constraint (R4-02).  Returns
    EXHAUSTED once the per-Game attempt budget (max four) is consumed.
    """
    with transaction.atomic():
        CalculationEpoch.objects.select_for_update().get(pk=epoch.pk)
        existing = list(
            CalculationAttempt.objects.select_for_update()
            .filter(epoch=epoch, game_id=game_id)
            .order_by("attempt_number")
        )
        if any(
            attempt.status == CalculationAttempt.Status.SUCCEEDED
            for attempt in existing
        ):
            return ClaimStatus.SKIPPED_ALREADY_SUCCEEDED, None
        next_number = existing[-1].attempt_number + 1 if existing else 1
        if next_number > MAX_ATTEMPTS_PER_GAME_EPOCH:
            return ClaimStatus.EXHAUSTED, None
        attempt = CalculationAttempt.objects.create(
            epoch=epoch,
            game_id=game_id,
            attempt_number=next_number,
            status=CalculationAttempt.Status.RUNNING,
            started_at=timezone.now(),
        )
        return ClaimStatus.CLAIMED, attempt


def get_current_normative_versions() -> tuple[str, str, str, str]:
    """The normative algorithm-version tuple baked into every new snapshot.

    ``(master, methods, bhpcm, confidence_final)`` — the four version fields a
    ``ClassificationSnapshot`` persists.  A deliberate algorithm change bumps
    one of the constants in ``classifications.calculations.constants``, which
    forces every game to recompute (SBGC-198).
    """
    return (MASTER_VERSION, METHODS_VERSION, BHPCM_VERSION, CONFIDENCE_FINAL_VERSION)


def should_skip_unchanged_game(
    game_id: int, input_population_hash: str
) -> tuple[bool, ClassificationSnapshot | None]:
    """Content-addressed skip check (R4-03).

    Returns ``(True, snapshot)`` when the published current snapshot for the
    Game already reflects the same frozen input population hash AND the same
    normative algorithm versions — recomputation is a pure function of those
    inputs, so it would produce an identical snapshot.  Only a non-stale
    current snapshot qualifies: a stale retained fallback means a newer epoch
    attempted (and failed) to refresh, so the Game must recompute.  No rows
    are locked and no engine work runs on the skip path.
    """
    current = (
        ClassificationSnapshot.objects.filter(
            game_id=game_id, is_current=True, is_stale=False
        )
        .only(
            "input_population_hash",
            "master_version",
            "methods_version",
            "bhpcm_version",
            "confidence_final_version",
        )
        .first()
    )
    if current is None:
        return False, None
    if current.input_population_hash != input_population_hash:
        return False, None
    snapshot_versions = (
        current.master_version,
        current.methods_version,
        current.bhpcm_version,
        current.confidence_final_version,
    )
    if snapshot_versions != get_current_normative_versions():
        return False, None
    return True, current


def check_and_claim_game_calculation(
    epoch: CalculationEpoch,
    game_id: int,
    input_population_hash: str,
) -> tuple[ClaimStatus, CalculationAttempt | None, ClassificationSnapshot | None]:
    """Content-addressed skip evaluation followed by a claim (SBGC-198).

    Returns ``(SKIPPED_UNCHANGED, None, snapshot)`` when the published result
    already matches, otherwise delegates to the Phase-1 claim
    (``claim_game_calculation_attempt``) and returns its outcome with no
    snapshot.
    """
    is_unchanged, existing_snapshot = should_skip_unchanged_game(
        game_id=game_id, input_population_hash=input_population_hash
    )
    if is_unchanged:
        return ClaimStatus.SKIPPED_UNCHANGED, None, existing_snapshot
    claim_status, attempt = claim_game_calculation_attempt(epoch, game_id)
    return claim_status, attempt, None


def record_failed_calculation_attempt(
    attempt: CalculationAttempt,
    *,
    failure_category: str,
    error_summary: str,
) -> None:
    """Record an attempt as FAILED in an isolated transaction (Phase 3).

    Runs after the finalization block has fully rolled back so failure state
    persists independently of the success path (R4-02).
    """
    with transaction.atomic():
        attempt.status = CalculationAttempt.Status.FAILED
        attempt.failure_category = failure_category
        attempt.error_summary = error_summary
        attempt.completed_at = timezone.now()
        attempt.save(
            update_fields=[
                "status",
                "failure_category",
                "error_summary",
                "completed_at",
            ]
        )


def fail_engine_attempt(
    attempt: CalculationAttempt,
    error_summary: str,
    *,
    notifier: CalculationFailureNotifier | None = None,
) -> None:
    """Engine-failure orchestration: FAILED record + stale fallback + notice."""
    record_failed_calculation_attempt(
        attempt,
        failure_category=ENGINE_FAILURE_CATEGORY,
        error_summary=error_summary,
    )
    _mark_current_stale(attempt.game)
    logger.error(
        "Classification calculation failed for game %s attempt %s: %s",
        attempt.game.pk,
        attempt.attempt_number,
        error_summary,
    )
    _maybe_notify_exhaustion(
        notifier, attempt.game, attempt.epoch, attempt.attempt_number, error_summary
    )


def finalize_successful_calculation(
    attempt: CalculationAttempt, pure: PureCalculationResult
) -> ClassificationSnapshot:
    """Phase 3 — atomically publish snapshot, boundary, and SUCCEEDED state.

    Snapshot insertion, demotion/promotion of the single current snapshot,
    boundary persistence, and the attempt ``RUNNING -> SUCCEEDED`` transition
    commit in one transaction.  Any failure rolls the entire block back,
    leaving the previous current snapshot untouched and the attempt still
    recordable as FAILED in isolation (R4-02).
    """
    with transaction.atomic():
        snapshot = _persist_snapshot(
            game=attempt.game,
            epoch=attempt.epoch,
            result=pure.result,
            received=pure.received,
            invalid=pure.invalid,
            cutoff_at=pure.cutoff_at,
            attempt_count=attempt.attempt_number,
            failure_category=(
                "" if pure.result.status == READY else DOMAIN_OUTCOME_CATEGORY
            ),
        )
        if pure.result.status == READY:
            _persist_boundary(attempt.game, pure.result)
        attempt.status = CalculationAttempt.Status.SUCCEEDED
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "completed_at"])
        return snapshot


def run_game_calculation(
    *,
    game: Game,
    epoch: CalculationEpoch,
    attempt_number: int,
    cutoff_at,
    bootstrap_replicates: int | None = None,
    governance_draws: int | None = None,
    notifier: CalculationFailureNotifier | None = None,
) -> CalculationAttempt:
    """Execute one explicit-attempt calculation for one Game inside an epoch.

    Single-attempt primitive used by the admin recalculation action and direct
    test callers (which always target a fresh epoch/attempt).  The daily
    scheduler command uses the dynamic claim/allocate pipeline instead, which
    provides idempotent resume; this function drives the same
    claim -> calculate -> finalize phases for a caller-supplied attempt number.

    Freezes inputs and computes outside any database transaction, then
    finalizes the complete snapshot + boundary + SUCCEEDED state in a single
    short atomic block (R4-02).

    A legitimate mathematical/domain result — READY or a valid non-error
    status such as NO_SUBMISSIONS, INSUFFICIENT_ANCHOR, or
    INSUFFICIENT_METHOD_1 — becomes the current published domain state,
    replacing any prior READY state (which remains historical only).

    Only an unexpected engine/system failure (unhandled exception,
    CALCULATION_ERROR, or UNIFIED_CALCULATION_ERROR) retains the previous
    current snapshot as a stale fallback and is re-raised for retry.
    """
    attempt = CalculationAttempt.objects.create(
        game=game,
        epoch=epoch,
        attempt_number=attempt_number,
        status=CalculationAttempt.Status.RUNNING,
        started_at=timezone.now(),
    )

    try:
        pure = execute_pure_calculation(
            game=game,
            cutoff_at=cutoff_at,
            bootstrap_replicates=bootstrap_replicates,
            governance_draws=governance_draws,
        )
    except Exception as exc:
        fail_engine_attempt(attempt, _safe_summary(exc), notifier=notifier)
        raise

    if pure.result.status != READY and pure.result.status not in DOMAIN_STATUSES:
        # Engine-level calculation defect (e.g. CALCULATION_ERROR or
        # UNIFIED_CALCULATION_ERROR): a retryable operational failure, not a
        # legitimate domain outcome.
        summary = f"calculation status {pure.result.status}"
        fail_engine_attempt(attempt, summary, notifier=notifier)
        raise RuntimeError(summary)

    # Phase 3: atomic finalization.  A failure here rolls back the snapshot
    # + boundary writes; the attempt is then recorded FAILED in isolation.
    try:
        finalize_successful_calculation(attempt, pure)
    except Exception as exc:
        summary = _safe_summary(exc)
        record_failed_calculation_attempt(
            attempt,
            failure_category=ENGINE_FAILURE_CATEGORY,
            error_summary=summary,
        )
        logger.error(
            "Classification finalization failed for game %s attempt %s: %s",
            game.pk,
            attempt_number,
            summary,
        )
        _maybe_notify_exhaustion(notifier, game, epoch, attempt_number, summary)
        raise
    return attempt


def _maybe_notify_exhaustion(
    notifier: CalculationFailureNotifier | None,
    game: Game,
    epoch: CalculationEpoch,
    attempt_number: int,
    summary: str,
) -> None:
    if attempt_number < MAX_ATTEMPTS_PER_GAME_EPOCH:
        return
    notifier = notifier or CalculationFailureNotifier()
    notifier.notify(
        CalculationFailureNotice(
            game_id=game.pk,
            game_name=game.name,
            epoch_id=epoch.epoch_id,
            calculation_version=MASTER_VERSION,
            attempt_count=attempt_number,
            failure_category=ENGINE_FAILURE_CATEGORY,
            error_summary=summary,
            timestamp=timezone.now(),
        )
    )


def _safe_summary(exc: Exception) -> str:
    text = f"{exc.__class__.__name__}: {exc}"
    return text[:1000]


@transaction.atomic
def _mark_current_stale(game: Game) -> None:
    """Mark the retained current snapshot stale after an engine failure.

    Unlike promotion, this keeps ``is_current=True``: the previous published
    result remains the fallback, but is flagged stale because a newer epoch
    attempted (and failed) to produce a fresh result.
    """
    ClassificationSnapshot.objects.select_for_update().filter(
        game=game, is_current=True
    ).update(is_stale=True)


@transaction.atomic
def _persist_snapshot(
    *,
    game: Game,
    epoch: CalculationEpoch,
    result: GameCalculationResult,
    received: int,
    invalid: int,
    cutoff_at,
    attempt_count: int,
    failure_category: str,
) -> ClassificationSnapshot:
    snapshot = ClassificationSnapshot(
        game=game,
        epoch=epoch,
        regime=result.regime,
        status=result.status,
        input_population_hash=result.diagnostics.get("input_population_hash", ""),
        received_count=received,
        invalid_count=invalid,
        validated_count=result.raw_n,
        cutoff_at=cutoff_at,
        calculated_at=timezone.now(),
        master_version=MASTER_VERSION,
        methods_version=METHODS_VERSION,
        bhpcm_version=BHPCM_VERSION,
        confidence_final_version=CONFIDENCE_FINAL_VERSION,
        attempt_count=attempt_count,
        failure_category=failure_category,
    )
    _apply_method(snapshot, "method_1", result.method_1)
    _apply_method(snapshot, "method_2", result.method_2)
    _apply_method(snapshot, "method_3", result.method_3)

    if result.is_ready:
        snapshot.unified_raw_challenge = _profile_json(result.raw_challenge)
        snapshot.unified_raw_reward = _profile_json(result.raw_reward)
        snapshot.unified_integer_challenge = list(result.integer_challenge or ())
        snapshot.unified_integer_reward = list(result.integer_reward or ())
        if result.confidence is not None:
            snapshot.confidence_final = result.confidence.level_displayed
            snapshot.confidence_label = result.confidence.label or ""
            snapshot.confidence_provenance = result.confidence.diagnostics
        if result.bhpcm is not None:
            snapshot.conflict_classification = result.bhpcm.diagnostics.get(
                "conflict_classification", ""
            )
            snapshot.provenance = {
                "bhpcm": result.bhpcm.diagnostics,
            }
    snapshot.save()

    # Every legitimate domain outcome — READY or a valid non-error status —
    # becomes the current published state.
    _promote(snapshot)
    return snapshot


def _promote(snapshot: ClassificationSnapshot) -> None:
    """Atomically make *snapshot* the single current published result."""
    ClassificationSnapshot.objects.select_for_update().filter(
        game=snapshot.game, is_current=True
    ).update(is_current=False, is_stale=True)
    snapshot.is_current = True
    snapshot.became_current_at = timezone.now()
    snapshot.save(update_fields=["is_current", "became_current_at"])


def _apply_method(snapshot, prefix: str, method_result) -> None:
    status_field = f"{prefix}_status"
    if method_result is None:
        setattr(snapshot, status_field, "")
        return
    setattr(snapshot, status_field, method_result.status)
    if not method_result.is_ready:
        return
    setattr(
        snapshot,
        f"{prefix}_raw_challenge",
        _profile_json(method_result.raw_challenge),
    )
    setattr(
        snapshot,
        f"{prefix}_raw_reward",
        _profile_json(method_result.raw_reward),
    )
    setattr(
        snapshot,
        f"{prefix}_integer_challenge",
        list(method_result.integer_challenge or ()),
    )
    setattr(
        snapshot,
        f"{prefix}_integer_reward",
        list(method_result.integer_reward or ()),
    )
    provenance = snapshot.provenance or {}
    provenance[prefix] = method_result.diagnostics
    snapshot.provenance = provenance


def _profile_json(profile: Profile | None) -> list[float] | None:
    if profile is None:
        return None
    return list(profile.components())


def _persist_boundary(game: Game, result: GameCalculationResult) -> None:
    calibration = result.boundary_calibration
    if calibration is None:
        return
    BoundaryCalibration.objects.update_or_create(
        game=game,
        master_version=MASTER_VERSION,
        defaults={
            "status": calibration.status,
            "delta": calibration.delta,
            "calibration_population_hash": calibration.calibration_population_hash,
            "population_size": calibration.population_size,
            "subset_count_attempted": calibration.subset_count_attempted,
            "subset_count_ready": calibration.subset_count_ready,
            "sampler_version": calibration.sampler_version,
            "seed_or_stream": calibration.seed_or_stream,
        },
    )


# ---------------------------------------------------------------------------
# Read boundary for future consumers (AstroJS / API)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PublishedClassification:
    """The currently published derived classification, or an unavailable state."""

    available: bool
    status: str
    game_id: int
    calculated_at: Any | None = None
    is_stale: bool = False
    regime: str | None = None
    validated_submission_count: int | None = None
    method_1: dict[str, Any] | None = None
    method_2: dict[str, Any] | None = None
    method_3: dict[str, Any] | None = None
    unified: dict[str, Any] | None = None
    confidence: float | None = None
    confidence_label: str | None = None
    versions: dict[str, str] | None = None


def get_published_classification(game: Game) -> PublishedClassification:
    """Return the product-facing published result for one Game.

    The current snapshot — whether READY or a legitimate non-ready domain
    status (e.g. NO_SUBMISSIONS, INSUFFICIENT_ANCHOR) — is returned.  A
    non-READY current snapshot reports ``available=False`` with its exact
    status, never an obsolete READY score.  Only an engine/system failure
    retains the previous current snapshot (marked stale) as fallback.
    """
    current = (
        ClassificationSnapshot.objects.filter(game=game, is_current=True)
        .order_by("-calculated_at")
        .first()
    )
    if current is not None:
        return _published_from_snapshot(current)

    latest = (
        ClassificationSnapshot.objects.filter(game=game)
        .order_by("-calculated_at")
        .first()
    )
    if latest is not None:
        return PublishedClassification(
            available=False,
            status=latest.status,
            game_id=game.pk,
            calculated_at=latest.calculated_at,
        )
    return PublishedClassification(
        available=False,
        status="NO_SNAPSHOT",
        game_id=game.pk,
    )


def _published_from_snapshot(
    snapshot: ClassificationSnapshot,
) -> PublishedClassification:
    game_id = snapshot.game_id  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK limitation
    return PublishedClassification(
        available=snapshot.status == READY,
        status=snapshot.status,
        game_id=game_id,
        calculated_at=snapshot.calculated_at,
        is_stale=snapshot.is_stale,
        regime=snapshot.regime,
        validated_submission_count=snapshot.validated_count,
        method_1=_method_view(snapshot, "method_1"),
        method_2=_method_view(snapshot, "method_2"),
        method_3=_method_view(snapshot, "method_3"),
        unified={
            "challenge": snapshot.unified_integer_challenge,
            "reward": snapshot.unified_integer_reward,
            "conflict_classification": snapshot.conflict_classification,
        }
        if snapshot.unified_integer_challenge is not None
        else None,
        confidence=(
            float(snapshot.confidence_final)
            if snapshot.confidence_final is not None
            else None
        ),
        confidence_label=snapshot.confidence_label or None,
        versions={
            "master": snapshot.master_version,
            "methods": snapshot.methods_version,
            "bhpcm": snapshot.bhpcm_version,
            "confidence_final": snapshot.confidence_final_version,
        },
    )


def _method_view(snapshot, prefix: str) -> dict[str, Any] | None:
    status = getattr(snapshot, f"{prefix}_status")
    if not status:
        return None
    return {
        "status": status,
        "integer_challenge": getattr(snapshot, f"{prefix}_integer_challenge"),
        "integer_reward": getattr(snapshot, f"{prefix}_integer_reward"),
    }


__all__ = [
    "ClaimStatus",
    "DOMAIN_STATUSES",
    "ENGINE_FAILURE_CATEGORY",
    "MAX_ATTEMPTS_PER_GAME_EPOCH",
    "PublishedClassification",
    "PureCalculationResult",
    "check_and_claim_game_calculation",
    "claim_game_calculation_attempt",
    "execute_pure_calculation",
    "fail_engine_attempt",
    "finalize_successful_calculation",
    "freeze_population",
    "get_current_normative_versions",
    "get_published_classification",
    "record_failed_calculation_attempt",
    "run_game_calculation",
    "should_skip_unchanged_game",
    "stored_boundary",
]
