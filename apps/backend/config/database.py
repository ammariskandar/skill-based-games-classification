"""
Database configuration helper — SBGC-39 / SBGC-43 / SBGC-104.

Parses DATABASE_URL through django-environ and produces a
Django DATABASES entry with environment-specific fallback policy
and PostgreSQL-only production enforcement.

SBGC-104 additions:
- Optional ``ssl_require`` toggle that sets PostgreSQL ``sslmode=require``.
- ``mask_database_url()`` for scrubbing connection strings in diagnostics.

Never opens a connection at import time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import environ
from django.core.exceptions import ImproperlyConfigured

# Known supported engine labels.
_POSTGRESQL_ENGINE = "django.db.backends.postgresql"
_SQLITE_ENGINE = "django.db.backends.sqlite3"


def mask_database_url(database_url: str | None) -> str:
    """Return *database_url* with any embedded password redacted.

    ``postgresql://user:hunter2@host/db`` becomes
    ``postgresql://user:[REDACTED]@host/db``.  Non-URL or malformed input is
    returned unchanged (defence in depth — never raise on untrusted input
    when building a diagnostic string).
    """
    if not database_url:
        return ""
    try:
        parts = urlsplit(database_url)
    except ValueError:
        return database_url
    if not parts.netloc:
        return database_url

    userinfo, _, host = parts.netloc.rpartition("@")
    if not host:
        return database_url
    username, _, _password = userinfo.partition(":")
    if not _password:
        return database_url

    safe_userinfo = f"{quote(username, safe='')}:[REDACTED]"
    safe_netloc = f"{safe_userinfo}@{host}"
    return urlunsplit(
        (parts.scheme, safe_netloc, parts.path, parts.query, parts.fragment)
    )


def build_database_config(
    database_url: str | None,
    base_dir: Path,
    *,
    allow_sqlite_fallback: bool,
    require_postgresql: bool = False,
    override_url: str | None = None,
    ssl_require: bool = False,
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
        ssl_require: If True and the resolved engine is PostgreSQL, add
            ``OPTIONS['sslmode'] = 'require'`` so the connection is
            encrypted (``DB_SSL_REQUIRE`` toggle).

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

    # Enforce TLS when the environment requires it (SBGC-104).
    if ssl_require and not options.get("sslmode"):
        options["sslmode"] = "require"

    config["OPTIONS"] = options

    return {"default": config}
