"""
Test discovery audit — SBGC-44.

Core logic for auditing Django/unittest test discovery.  Separated from
the shell launcher so it can be tested independently with synthetic suites.
"""

from __future__ import annotations

import os
import traceback
import unittest
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DiscoveryReport:
    """Result of auditing test discovery."""

    total: int = 0
    by_module: dict[str, int] = field(default_factory=dict)
    duplicate_ids: list[str] = field(default_factory=list)
    import_errors: list[str] = field(default_factory=list)
    empty_modules: list[str] = field(default_factory=list)

    @property
    def has_defects(self) -> bool:
        return bool(
            self.duplicate_ids
            or self.import_errors
            or self.empty_modules
        )

    @property
    def success(self) -> bool:
        return not self.has_defects


def audit_discovery(
    start_dir: str | None = None,
    pattern: str = "test_*.py",
) -> DiscoveryReport:
    """
    Audit unittest test discovery for structural defects.

    Args:
        start_dir: Directory to start discovery.
        pattern: Test file glob pattern.

    Returns:
        DiscoveryReport with totals, module counts, and any defects.
        ``report.success`` is True only when zero defects were found.
    """
    if start_dir is None:
        start_dir = str(Path(__file__).resolve().parent.parent)

    loader = _AuditLoader()
    try:
        suite = loader.discover(start_dir, pattern=pattern)
    except Exception:
        report = DiscoveryReport()
        report.import_errors.append(
            f"Discovery crashed: {traceback.format_exc()}"
        )
        return report

    report = DiscoveryReport()

    # Collect loader-level import errors.
    for name, exc in getattr(loader, "import_errors", []):
        report.import_errors.append(f"{name}: {exc}")

    # Walk the suite.
    seen_ids: dict[str, str] = {}
    discovered_modules: set[str] = set()

    def _walk(s: unittest.TestSuite) -> None:
        for test in s:
            if isinstance(test, unittest.TestSuite):
                _walk(test)
            else:
                report.total += 1
                tid = test.id()
                mod = test.__class__.__module__
                report.by_module[mod] = report.by_module.get(mod, 0) + 1
                discovered_modules.add(mod)
                if tid in seen_ids:
                    report.duplicate_ids.append(
                        f"{tid} (also in {seen_ids[tid]})"
                    )
                seen_ids[tid] = mod

    _walk(suite)

    # Import-error check: test_*.py files that could not be loaded at all.
    # The loader catches exceptions internally; we detect unloaded modules
    # by checking which test_*.py files were never seen during _walk.
    for root, _dirs, files in os.walk(start_dir):
        if ".venv" in root:
            continue
        for fname in files:
            if not (fname.startswith("test_") and fname.endswith(".py")):
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, start_dir)
            mod_name = rel.replace("/", ".").replace(".py", "")
            # Check if this module was loaded.
            loaded = any(
                m == mod_name or m.endswith("." + mod_name.split(".")[-1])
                for m in discovered_modules
            )
            if loaded:
                continue
            # The module was not loaded — this is an import error.
            report.import_errors.append(
                f"{rel}: module could not be imported"
            )

    # Empty-module check: test_*.py files that look like test modules
    # (import unittest or django.test) but produced zero discovered tests.
    for root, _dirs, files in os.walk(start_dir):
        if ".venv" in root:
            continue
        for fname in files:
            if not (fname.startswith("test_") and fname.endswith(".py")):
                continue
            full = os.path.join(root, fname)
            try:
                with open(full) as fh:
                    src = fh.read()
            except Exception:
                continue
            # A test module must contain a recognisable test-framework import
            # or test-method definitions.
            is_test_module = (
                "import unittest" in src
                or "from unittest" in src
                or "django.test" in src
                or "def test_" in src
            )
            if not is_test_module:
                continue
            rel = os.path.relpath(full, start_dir)
            mod_name = rel.replace("/", ".").replace(".py", "")
            found = any(
                m == mod_name
                or m.endswith("." + mod_name.split(".")[-1])
                for m in discovered_modules
            )
            if not found:
                report.empty_modules.append(rel)

    return report


class _AuditLoader(unittest.TestLoader):
    """Loader that records import errors and excludes .venv."""

    def __init__(self):
        super().__init__()
        self.import_errors: list[tuple[str, str]] = []

    def _get_module_from_name(self, name):
        if ".venv" in name:
            raise ImportError(f"Skipping .venv module: {name}")
        return super()._get_module_from_name(name)

    def loadTestsFromName(self, name, module=None):
        try:
            return super().loadTestsFromName(name, module)
        except Exception as exc:
            self.import_errors.append((name, str(exc)))
            return self.suiteClass()

    def loadTestsFromModule(self, module, *, pattern=None):
        try:
            return super().loadTestsFromModule(module, pattern=pattern)
        except Exception as exc:
            mod_name = getattr(module, "__name__", str(module))
            self.import_errors.append((mod_name, str(exc)))
            return self.suiteClass()

    def _find_test_path(self, full_path, pattern):
        try:
            return super()._find_test_path(full_path, pattern)
        except Exception as exc:
            # Module import failed (e.g., SyntaxError).
            self.import_errors.append((full_path, str(exc)))
            return self.suiteClass(), False
