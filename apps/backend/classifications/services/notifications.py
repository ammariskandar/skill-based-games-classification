"""
Final-failure notification scaffold — SBGC-65.

A clean notification boundary only.  Actual email/delivery transport is
explicitly deferred: SBGC-65 records the failure data and logs it; a future
ticket wires a real delivery backend.  No personal addresses are hardcoded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalculationFailureNotice:
    """Everything a future notifier needs about an exhausted Game/epoch."""

    game_id: int
    game_name: str
    epoch_id: str
    calculation_version: str
    attempt_count: int
    failure_category: str
    error_summary: str
    timestamp: datetime


class CalculationFailureNotifier:
    """Delivery boundary invoked after the final (4th) failed attempt."""

    def notify(self, notice: CalculationFailureNotice) -> None:
        # Scaffold: structured logging is the current delivery behavior.
        # Email transport is deferred future work (SBGC-65 scope).
        logger.warning(
            "Classification calculation failed after %s attempts: "
            "game=%s (%s), epoch=%s, version=%s, category=%s, error=%s",
            notice.attempt_count,
            notice.game_id,
            notice.game_name,
            notice.epoch_id,
            notice.calculation_version,
            notice.failure_category,
            notice.error_summary,
        )


__all__ = ["CalculationFailureNotice", "CalculationFailureNotifier"]
