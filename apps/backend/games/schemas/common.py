"""
Shared request validation for public game endpoints — SBGC-99.

Path-parameter constraints shared by the games routers.  Slug validation
happens at the Ninja/Pydantic boundary so malformed slugs never reach the
query layer.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

ValidGameSlug = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=255,
        pattern=SLUG_PATTERN,
        strip_whitespace=True,
    ),
]
