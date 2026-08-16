"""
Shared editorial-classification validation — SBGC-46.

Pure functions — no database access, no network access.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_score_distribution(
    micro: object,
    mystiko: object,
    macro: object,
    *,
    profile_label: str,
) -> None:
    """Validate three integer scores that must sum to exactly 100.

    Each score must be an int (not bool), 0–100, and the three must
    total 100.  *profile_label* is used in error messages so Challenge
    and Reward validation errors are context-specific.

    Field errors are keyed by the concrete model field name
    (``micro_score`` / ``mystiko_score`` / ``macro_score``) so they attach
    to the matching form field; the human-readable label lives only inside
    the message text.
    """
    errors: dict[str, list[str]] = {}

    for field_name, label, value in (
        ("micro_score", f"{profile_label} Micro", micro),
        ("mystiko_score", f"{profile_label} Mystiko", mystiko),
        ("macro_score", f"{profile_label} Macro", macro),
    ):
        # Reject booleans (bool is a subclass of int).
        if isinstance(value, bool):
            errors.setdefault(field_name, []).append(
                _("%(label)s must be an integer, not a boolean.") % {"label": label}
            )
            continue

        if not isinstance(value, int):
            errors.setdefault(field_name, []).append(
                _("%(label)s must be an integer.") % {"label": label}
            )
            continue

        if value < 0 or value > 100:
            errors.setdefault(field_name, []).append(
                _("%(label)s must be between 0 and 100 (got %(got)d).")
                % {"label": label, "got": value}
            )

    # Only check the total when every value is a valid int (not bool/other).
    if not errors:
        total = micro + mystiko + macro  # type: ignore[operator]
        if total != 100:
            errors.setdefault("__all__", []).append(
                _("%(label)s scores must total exactly 100 (got %(got)d).")
                % {"label": profile_label, "got": total}
            )

    if errors:
        raise ValidationError(errors)
