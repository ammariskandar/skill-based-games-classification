"""
Derived-classification calculation service — SBGC-65.

Freezes the submission population at an epoch cutoff, runs the pure
calculation engine outside any long transaction, and persists the complete
versioned snapshot atomically.  A new snapshot becomes current only when the
engine returned READY; every other outcome leaves the previous successful
snapshot as the published fallback.

No statistical logic lives here — only the persistence/coordination
boundary around ``classifications.calculations``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
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
)
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
    """Execute one calculation attempt for one Game inside an epoch.

    Freezes inputs, computes outside any database transaction, then persists
    the complete snapshot in a short atomic block.

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
        status=CalculationAttempt.Status.FAILED,
        started_at=timezone.now(),
    )

    population, received, invalid = freeze_population(game, cutoff_at)
    boundary = stored_boundary(game)

    try:
        result = calculate_game(
            population,
            game_identifier=str(game.pk),
            stored_boundary=boundary,
            bootstrap_replicates=bootstrap_replicates,
            governance_draws=governance_draws,
        )
    except Exception as exc:
        summary = _safe_summary(exc)
        attempt.failure_category = ENGINE_FAILURE_CATEGORY
        attempt.error_summary = summary
        attempt.completed_at = timezone.now()
        attempt.save(
            update_fields=["failure_category", "error_summary", "completed_at"]
        )
        _mark_current_stale(game)
        logger.error(
            "Classification calculation failed for game %s attempt %s: %s",
            game.pk,
            attempt_number,
            summary,
        )
        _maybe_notify_exhaustion(notifier, game, epoch, attempt_number, summary)
        raise

    if result.status != READY and result.status not in DOMAIN_STATUSES:
        # Engine-level calculation defect (e.g. CALCULATION_ERROR or
        # UNIFIED_CALCULATION_ERROR): a retryable operational failure, not a
        # legitimate domain outcome.
        summary = f"calculation status {result.status}"
        attempt.failure_category = ENGINE_FAILURE_CATEGORY
        attempt.error_summary = summary
        attempt.completed_at = timezone.now()
        attempt.save(
            update_fields=["failure_category", "error_summary", "completed_at"]
        )
        _mark_current_stale(game)
        logger.error(
            "Classification calculation failed for game %s attempt %s: %s",
            game.pk,
            attempt_number,
            summary,
        )
        _maybe_notify_exhaustion(notifier, game, epoch, attempt_number, summary)
        raise RuntimeError(summary)

    # Legitimate domain outcome -> becomes the current published state.
    attempt.status = CalculationAttempt.Status.SUCCEEDED
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=["status", "completed_at"])
    _persist_snapshot(
        game=game,
        epoch=epoch,
        result=result,
        received=received,
        invalid=invalid,
        cutoff_at=cutoff_at,
        attempt_count=attempt_number,
        failure_category="" if result.status == READY else DOMAIN_OUTCOME_CATEGORY,
    )
    if result.status == READY:
        _persist_boundary(game, result)
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
    "DOMAIN_STATUSES",
    "ENGINE_FAILURE_CATEGORY",
    "MAX_ATTEMPTS_PER_GAME_EPOCH",
    "PublishedClassification",
    "freeze_population",
    "get_published_classification",
    "run_game_calculation",
    "stored_boundary",
]
