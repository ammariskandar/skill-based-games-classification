"""
Django model _meta typing helpers — SBGC-53 / SBGC-181.

Narrow helpers for test code that inspects Django model field metadata
through ``_meta``.  Centralises framework-boundary casts so individual
tests do not need per-line suppressions.
"""

from __future__ import annotations

from typing import cast

from django.db import models
from django.db.models.options import Options


def model_options(model_cls: type[models.Model]) -> Options:
    """Return the ``Options`` for *model_cls* via ``_meta``."""
    return cast(Options, model_cls._meta)


def model_field(
    model_cls: type[models.Model], name: str
) -> models.Field[object, object]:
    """Return the field *name* from *model_cls* metadata."""
    return cast(
        "models.Field[object, object]",
        model_options(model_cls).get_field(name),
    )
