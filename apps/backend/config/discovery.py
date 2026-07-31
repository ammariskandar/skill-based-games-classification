"""
Test discovery audit — SBGC-44.

Core logic for auditing Django test discovery.  Separated from the
shell launcher so it can be tested independently with synthetic suites.
"""

from __future__ import annotations

import os
import unittest
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DiscoveryReport:
    """Result of auditing test discovery."""

    total: int = 0
    by_module: dict[str, int] = field(default_factory=dict)
    duplicate_ids: list[str] = field(default_factory=list)
    import_errors: list[tuple[str, str]] = field(default_factory=list)
    empty_modules: list[str] = field(default_factory=list)

    @property
    def has_defects(self) -> bool:
        return bool(self.duplicate_ids or self.import_errors or self.empty_modules)


def audit_discovery(
    start_dir: str | None = None,
    pattern: str = "test_*.py",
) -> DiscoveryReport:
    """
    Audit unittest test discovery for structural defects.

    Args:
        start_dir: Directory to start discovery (default: cwd).
        pattern: Test file glob pattern.

    Returns:
        DiscoveryReport with totals, module counts, and any defects.
    """
    if start_dir is None:
        start_dir = str(Path(__file__).resolve().parent.parent)

    # Filter out .venv from discovery if present.
    loader = _CleanLoader()
    try:
        suite = loader.discover(start_dir, pattern=pattern)
    except Exception as exc:
        report = DiscoveryReport()
        report.import_errors.append((start_dir, str(exc)))
        return report

    report = DiscoveryReport()
    seen_ids: dict[str, str] = {}

    def _walk(s: unittest.TestSuite) -> None:
        for test in s:
            if isinstance(test, unittest.TestSuite):
                _walk(test)
            else:
                report.total += 1
                tid = test.id()
                mod = test.__class__.__module__
                report.by_module[mod] = report.by_module.get(mod, 0) + 1
                if tid in seen_ids:
                    report.duplicate_ids.append(f"{tid} (also in {seen_ids[tid]})")
                seen_ids[tid] = mod

    _walk(suite)

    # Empty-module check: find test_*.py files with test methods
    # that produced zero discovered tests.
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
            if "def test_" not in src:
                continue
            rel = os.path.relpath(full, start_dir)
            mod_name = rel.replace("/", ".").replace(".py", "")
            # Check if this module has any discovered tests.
            found = any(
                m == mod_name or m.endswith("." + mod_name.split(".")[-1])
                for m in report.by_module
            )
            if not found:
                report.empty_modules.append(rel)

    return report


class _CleanLoader(unittest.TestLoader):
    """Loader that excludes .venv from discovery."""

    def _get_module_from_name(self, name):
        if ".venv" in name:
            raise ImportError(f"Skipping .venv module: {name}")
        return super()._get_module_from_name(name)
