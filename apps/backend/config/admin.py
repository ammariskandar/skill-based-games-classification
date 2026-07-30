"""
Django Admin configuration — SBGC-40.

Provides:

- validate_admin_url_path  — validates ADMIN_URL_PATH against the
  project's canonical path-segment contract.
- apply_admin_branding      — applies conservative MyGameDNA labels to
  the default Django AdminSite.

Does not register models (future registrations live in
games/admin.py and classifications/admin.py).
"""

from __future__ import annotations

import re

from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured

# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

# Accept: ASCII alphanumeric, hyphen, underscore; first char alphanumeric.
_ADMIN_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

# Reserved segments that must not be used as the admin path.
_RESERVED_SEGMENTS = frozenset({"api"})


def validate_admin_url_path(raw: str | None) -> str:
    """
    Validate and normalise *raw* into a canonical relative path segment.

    Returns a non-empty segment suitable for use in a URL pattern
    (``path(f"{value}/", ...)``).

    Raises ``ImproperlyConfigured`` for any value that does not meet
    the project's admin-path contract.
    """
    if raw is None:
        raise ImproperlyConfigured("ADMIN_URL_PATH must not be missing.")

    if not isinstance(raw, str):
        raise ImproperlyConfigured("ADMIN_URL_PATH must be a string.")

    stripped = raw.strip()

    if not stripped:
        raise ImproperlyConfigured("ADMIN_URL_PATH must not be blank.")

    # Reject any value that looks like a URL, contains a scheme, or has
    # path separators beyond the single segment.
    if "://" in stripped:
        raise ImproperlyConfigured("ADMIN_URL_PATH must be a single path segment.")
    if "/" in stripped:
        raise ImproperlyConfigured("ADMIN_URL_PATH must not contain a slash.")
    if "\\" in stripped:
        raise ImproperlyConfigured("ADMIN_URL_PATH must not contain a backslash.")
    if "?" in stripped:
        raise ImproperlyConfigured("ADMIN_URL_PATH must not contain a query string.")
    if "#" in stripped:
        raise ImproperlyConfigured("ADMIN_URL_PATH must not contain a fragment.")

    # Dot / dot-dot segments.
    if stripped in (".", ".."):
        raise ImproperlyConfigured("ADMIN_URL_PATH must not be a dot segment.")
    if stripped.startswith("./") or stripped.startswith("../"):
        raise ImproperlyConfigured("ADMIN_URL_PATH must not be a dot segment.")

    # Reserved segments (case-insensitive).
    if stripped.lower() in _RESERVED_SEGMENTS:
        raise ImproperlyConfigured(
            f"The segment {stripped!r} is reserved and cannot be used as "
            "ADMIN_URL_PATH."
        )

    # Character-level validation.
    if not _ADMIN_PATH_RE.match(stripped):
        raise ImproperlyConfigured(
            "ADMIN_URL_PATH must be a single relative path segment "
            "containing only ASCII letters, digits, hyphens, and underscores, "
            "starting with a letter or digit."
        )

    return stripped


# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------


def apply_admin_branding() -> None:
    """Apply MyGameDNA labels to the default Django AdminSite."""
    admin.site.site_header = "MyGameDNA Administration"
    admin.site.site_title = "MyGameDNA Admin"
    admin.site.index_title = "Content administration"
