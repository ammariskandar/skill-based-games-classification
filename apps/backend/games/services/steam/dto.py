"""
Steam App ID value type — SBGC-53.

Immutable validated type for Steam application identifiers.
No arithmetic semantics — value is always a decimal-digit string.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

_MAX_APP_ID_LENGTH = 32


@dataclass(frozen=True, slots=True)
class SteamAppId:
    """A validated Steam application ID (decimal-digit string).

    Rejected: blank, whitespace, non-digit, signs, float/exponent,
    Boolean, None, excessive length.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError(
                f"SteamAppId value must be a string, got {type(self.value).__name__}."
            )
        stripped = self.value.strip()
        if not stripped:
            raise ValueError("SteamAppId must not be blank.")
        if stripped != self.value:
            raise ValueError(
                "SteamAppId must not contain leading or trailing whitespace."
            )
        if len(stripped) > _MAX_APP_ID_LENGTH:
            raise ValueError(
                f"SteamAppId must not exceed {_MAX_APP_ID_LENGTH} characters."
            )
        if not stripped.isdigit():
            raise ValueError(
                f"SteamAppId must consist only of decimal digits, got {stripped!r}."
            )
        if int(stripped) == 0:
            raise ValueError("SteamAppId must not be zero.")

    def __repr__(self) -> str:
        return f"SteamAppId({self.value!r})"

    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# Lookup outcomes
# ---------------------------------------------------------------------------


class LookupStatus(str, Enum):  # noqa: UP042 — Django TextChoices pattern
    """Outcome of a Steam app-details lookup."""

    FOUND = "found"
    UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# Application DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SteamAppDetails:
    """Validated application details from the Steam Store API.

    All fields are application-owned — no raw Steam JSON is retained.
    """

    app_id: str
    name: str
    content_type: str
    short_description: str | None = None
    header_image_url: str | None = None
    website_url: str | None = None
    is_free: bool | None = None
    developers: tuple[str, ...] | None = None
    publishers: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class SteamGameImportCandidate:
    """Normalised import-ready candidate produced from Steam data.

    Does not contain a Django model reference — only transport-level
    and domain-level field values.
    """

    app_id: str
    name: str
    content_type: str
    short_description: str | None = None
    header_image_url: str | None = None
    website_url: str | None = None
    is_free: bool | None = None
    developers: tuple[str, ...] | None = None
    publishers: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class SteamAppLookupResult:
    """Result of looking up a single Steam app."""

    status: LookupStatus
    app_id: str
    candidate: SteamGameImportCandidate | None = None

    def __post_init__(self) -> None:
        if self.status == LookupStatus.FOUND and self.candidate is None:
            raise ValueError(
                "SteamAppLookupResult with status=FOUND must have a candidate."
            )
        if self.status != LookupStatus.FOUND and self.candidate is not None:
            raise ValueError(
                f"SteamAppLookupResult with status={self.status.value} "
                f"must not have a candidate."
            )
