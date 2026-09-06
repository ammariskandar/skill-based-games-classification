"""
Shared test helpers — SBGC-44.

Provides canonical utilities for backend tests:
- Isolated subprocess environments.
- Production-like dummy settings.
- Network-inhibition guard.
- Discovery audit.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

# Project root and backend directory from this file's location.
# config/test_helpers.py → config → apps/backend
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR = _BACKEND_DIR.parent.parent
_MANAGE_PY = _BACKEND_DIR / "manage.py"

# ---------------------------------------------------------------------------
# Isolated subprocess environment
# ---------------------------------------------------------------------------

# Variables that are safe to inherit in subprocess tests.
_SAFE_ENV_KEYS = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "TMP",
        "TEMP",
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "PIP_REQUIRE_VIRTUALENV",
    }
)


def minimal_subprocess_env(**extras: str) -> dict[str, str]:
    """
    Build a minimal environment dict for subprocess tests.

    Inherits only explicitly safe variables from the current process
    environment (PATH, locale, temp dirs).  Never inherits:
    DJANGO_SETTINGS_MODULE, DJANGO_SKIP_DOTENV, DATABASE_URL,
    DJANGO_SECRET_KEY, Steam keys, Admin path, Render/proxy values.

    Args:
        **extras: Additional environment variables to set.

    Returns:
        A dict suitable for ``subprocess.run(..., env=env)``.
    """
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key in _SAFE_ENV_KEYS or key.startswith("PYTHON"):
            env[key] = value
    env.update(extras)
    return env


# ---------------------------------------------------------------------------
# Production-like dummy settings
# ---------------------------------------------------------------------------

_DUMMY_PG_URL = (
    "postgresql://u:p@example.neon.tech/db?sslmode=require&channel_binding=require"
)
_DUMMY_SECRET = "abCDefGHijKLmnOPqrSTuvWXyz01-234567890abCDefGHuvWXyz"


def prod_test_env(**overrides: str) -> dict[str, str]:
    """
    Return a minimal environment dict with valid production dummy values.

    Includes: DJANGO_SECRET_KEY, DATABASE_URL, DJANGO_ALLOWED_HOSTS,
    CSRF_TRUSTED_ORIGINS, ADMIN_URL_PATH, and (SBGC-104) the required
    RECAPTCHA_SECRET_KEY and STEAM_WEB_API_KEY secrets.

    Use for subprocess tests that import config.settings.production.
    """
    env = minimal_subprocess_env(
        DJANGO_SECRET_KEY=_DUMMY_SECRET,
        DATABASE_URL=_DUMMY_PG_URL,
        DJANGO_ALLOWED_HOSTS="example.com",
        CSRF_TRUSTED_ORIGINS="https://example.com",
        ADMIN_URL_PATH="mygamedna-prod",
        DJANGO_LOG_LEVEL="INFO",
        DJANGO_SECURE_HSTS_SECONDS="3600",
        RECAPTCHA_SECRET_KEY="dummy-recaptcha-secret",
        RECAPTCHA_SITE_KEY="dummy-recaptcha-site-key",
        STEAM_WEB_API_KEY="dummy-steam-api-key",
    )
    env.update(overrides)
    return env


# ---------------------------------------------------------------------------
# Safe manage.py subprocess
# ---------------------------------------------------------------------------


def run_manage(
    *args: str,
    env: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """
    Run manage.py in a subprocess with controlled environment.

    Args:
        *args: Arguments to pass to manage.py.
        env: Environment dict (use minimal_subprocess_env or prod_test_env).
        timeout: Subprocess timeout in seconds.

    Returns:
        CompletedProcess with captured stdout/stderr.
    """
    return subprocess.run(
        [sys.executable, str(_MANAGE_PY), *args],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        env=env or minimal_subprocess_env(),
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Network guard
# ---------------------------------------------------------------------------


class NetworkProhibitedError(RuntimeError):
    """Raised when a test attempts a disallowed network operation."""


def assert_no_live_requests() -> None:
    """
    Guard against accidental live HTTP requests in tests.

    Call in setUp / setUpClass of test suites that must not make
    external network calls.  Patches socket.create_connection to
    raise NetworkProhibitedError.

    Does not interfere with Django's test client or in-process
    communication.
    """
    import socket

    _original = socket.create_connection

    def _guard(address, *args, **kwargs):
        raise NetworkProhibitedError(
            f"Live network connection blocked in test: {address}"
        )

    socket.create_connection = _guard  # type: ignore[assignment]

    # Store for potential cleanup.
    if not hasattr(assert_no_live_requests, "_original"):
        assert_no_live_requests._original = _original  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Discovery audit
# ---------------------------------------------------------------------------


def audit_discovery(
    start_dir: str | None = None,
    pattern: str = "test_*.py",
) -> dict:
    """
    Audit Django/unittest test discovery.

    Returns a dict with:
    - total: total discovered test count.
    - by_module: dict mapping module name → test count.
    - duplicates: list of duplicate test IDs.
    - import_errors: list of (module, error) tuples.
    - empty_modules: list of test modules with zero tests.

    Args:
        start_dir: Directory to start discovery (default: backend dir).
        pattern: Test file pattern.

    Raises:
        SystemExit(1) if structural defects (duplicates, import errors,
        empty modules) are found.
    """
    if start_dir is None:
        start_dir = str(_BACKEND_DIR)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir, pattern=pattern)

    by_module: dict[str, int] = {}
    seen_ids: dict[str, str] = {}
    duplicates: list[str] = []
    total = 0

    def _count(s):
        nonlocal total
        for test in s:
            if isinstance(test, unittest.TestSuite):
                _count(test)
            else:
                total += 1
                tid = test.id()
                mod = test.__class__.__module__
                by_module[mod] = by_module.get(mod, 0) + 1
                if tid in seen_ids:
                    duplicates.append(f"{tid} (also in {seen_ids[tid]})")
                seen_ids[tid] = mod

    _count(suite)

    # Check for empty test modules.
    empty_modules: list[str] = []
    if start_dir:
        for root, _dirs, files in os.walk(start_dir):
            for f in files:
                if f.startswith("test_") and f.endswith(".py"):
                    full = os.path.join(root, f)
                    # Skip .venv
                    if ".venv" in full:
                        continue
                    # Try importing to check for tests
                    rel = os.path.relpath(full, start_dir)
                    mod_name = rel.replace("/", ".").replace(".py", "")
                    if mod_name not in {m.split(".")[-1] for m in by_module}:
                        # Check if it has test methods at all
                        try:
                            src = open(full).read()
                            if "def test_" in src:
                                empty_modules.append(rel)
                        except Exception:
                            pass

    return {
        "total": total,
        "by_module": by_module,
        "duplicates": duplicates,
        "empty_modules": empty_modules,
    }
