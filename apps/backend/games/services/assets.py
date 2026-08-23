"""
Manual asset URL validation — SBGC-60.

Pure, structural validation for editor-supplied manual image references.
No network access, no fetch, no DNS, no binary handling.

This is deliberately **separate** from the Steam image policy in
``games/services/steam/cdn.py``.  Manual asset URLs are editor-provided
references and are not subject to the Steam CDN host allowlist.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Control characters are never valid in a browser-safe URL reference.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

# SBGC-190: manual image URLs must end in one of these image extensions.
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

_EXTENSION_ERROR = "Use an HTTPS image URL ending in .jpg, .jpeg, .png, or .webp."


class ManualAssetError(ValueError):
    """Domain error for an invalid manual asset reference."""


def validate_manual_image_url(value: str) -> str:
    """Validate a manual ``manual_image_url`` reference.

    Contract:

    - blank/whitespace string → ``""`` (no manual image)
    - valid HTTPS URL → returned as-is (outer whitespace stripped)
    - any other string → ``ManualAssetError``

    Enforced rules:

    - HTTPS only (rejects ``http``, ``ftp``, ``javascript``, ``file``,
      ``data``, etc.)
    - nonempty hostname required
    - no credentials/userinfo

    The field's ``URLField(max_length=500)`` additionally enforces a valid
    URL shape and length at the model layer.  This function only checks the
    project-specific manual-asset policy and never performs network I/O.
    """
    if not isinstance(value, str):
        raise ManualAssetError(
            f"Manual image URL must be a string, got {type(value).__name__}."
        )

    v = value.strip()
    if not v:
        return ""

    if _CONTROL_CHARS_RE.search(v):
        raise ManualAssetError("Manual image URL must not contain control characters.")

    parsed = urlparse(v)

    if parsed.scheme.lower() != "https":
        raise ManualAssetError(
            f"Manual image URL must use HTTPS, got {parsed.scheme or '<none>'!r}."
        )

    if parsed.username or parsed.password or "@" in parsed.netloc:
        raise ManualAssetError("Manual image URL must not contain credentials.")

    if not (parsed.hostname or "").strip():
        raise ManualAssetError("Manual image URL must have a nonempty hostname.")

    # Extension — validate the URL path (not the raw full string, because a
    # query string may follow the extension).  Case-insensitive.
    path = parsed.path or ""
    extension = path[path.rfind(".") :].lower() if "." in path else ""
    if extension not in _ALLOWED_EXTENSIONS:
        raise ManualAssetError(_EXTENSION_ERROR)

    return v


__all__ = ["ManualAssetError", "validate_manual_image_url"]
