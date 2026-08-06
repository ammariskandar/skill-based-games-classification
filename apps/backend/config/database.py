"""
Database configuration helper — SBGC-39 / SBGC-43.

Parses DATABASE_URL through django-environ and produces a
Django DATABASES entry with environment-specific fallback policy
and PostgreSQL-only production enforcement.

Never opens a connection at import time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import environ
from django.core.exceptions import ImproperlyConfigured

# Known supported engine labels.
_POSTGRESQL_ENGINE = "django.db.backends.postgresql"
_SQLITE_ENGINE = "django.db.backends.sqlite3"


def build_database_config(
    database_url: str | None,
    base_dir: Path,
    *,
    allow_sqlite_fallback: bool,
    require_postgresql: bool = False,
    override_url: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Build the Django ``DATABASES["default"]`` configuration.

    Args:
        database_url: The raw DATABASE_URL value (may be empty/None).
        base_dir: Project BASE_DIR (``apps/backend/``).
        allow_sqlite_fallback: If True, a missing/blank URL selects a local
            SQLite database at ``base_dir / "db.sqlite3"``.
        require_postgresql: If True, only ``django.db.backends.postgresql``
            is accepted — missing URLs, SQLite, MySQL, Oracle, and unknown
            engines all raise ``ImproperlyConfigured``.
        override_url: If provided, use this URL instead of *database_url*.
            This enables separate runtime (pooled) and migration (direct)
            connection URLs.  Secrets are never printed.

    Returns:
        A dict suitable for ``settings.DATABASES``.

    Raises:
        ImproperlyConfigured: When the URL is missing/blank/malformed, the
            engine is unsupported, or *require_postgresql* is True and the
            resolved engine is not PostgreSQL.
    """
    # Allow override for migration URL (SBGC-52).
    effective = override_url if override_url is not None else database_url
    stripped = (effective or "").strip()

    # -- Missing / blank URL ---------------------------------------------------
    if not stripped:
        if require_postgresql:
            raise ImproperlyConfigured(
                "DATABASE_URL is required in production and must be a "
                "PostgreSQL connection URL."
            )
        if allow_sqlite_fallback:
            return {
                "default": {
                    "ENGINE": _SQLITE_ENGINE,
                    "NAME": base_dir / "db.sqlite3",
                    "CONN_MAX_AGE": 0,
                }
            }
        raise ImproperlyConfigured("DATABASE_URL is required in this environment.")

    # -- Populated URL ----------------------------------------------------------
    try:
        env = environ.Env()
        raw_config = env.db_url_config(stripped)
    except Exception as exc:
        raise ImproperlyConfigured(
            "Unable to parse DATABASE_URL. Verify the value is a valid database URL."
        ) from exc

    engine = raw_config.get("ENGINE", "")

    # -- Unsupported engine -----------------------------------------------------
    if require_postgresql:
        if engine != _POSTGRESQL_ENGINE:
            raise ImproperlyConfigured(
                f"Production requires PostgreSQL, got engine {engine!r}. "
                f"SQLite and other engines are not supported in production."
            )
    elif engine not in (_SQLITE_ENGINE, _POSTGRESQL_ENGINE):
        raise ImproperlyConfigured(
            f"Unsupported database engine: {engine!r}. "
            f"Expected {_SQLITE_ENGINE!r} or {_POSTGRESQL_ENGINE!r}."
        )

    config: dict[str, Any] = {"ENGINE": engine, "CONN_MAX_AGE": 0}

    # -- SQLite ----------------------------------------------------------------
    if engine == _SQLITE_ENGINE:
        config["NAME"] = raw_config.get("NAME", base_dir / "db.sqlite3")
        return {"default": config}

    # -- PostgreSQL -------------------------------------------------------------
    config["NAME"] = raw_config.get("NAME", "")
    config["USER"] = raw_config.get("USER", "")
    config["PASSWORD"] = raw_config.get("PASSWORD", "")
    config["HOST"] = raw_config.get("HOST", "")
    config["PORT"] = raw_config.get("PORT", "")

    # Preserve and merge OPTIONS.
    options: dict[str, Any] = dict(raw_config.get("OPTIONS", {}))

    # Enforce a connection timeout if the caller hasn't set a finite one.
    if not isinstance(options.get("connect_timeout"), (int, float)):
        options["connect_timeout"] = 10

    config["OPTIONS"] = options

    return {"default": config}
