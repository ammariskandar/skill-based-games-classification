"""
Discovery-audit behavioral tests — SBGC-44.

Proves that audit_discovery detects structural defects using
synthetic test suites in temporary directories.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from config.discovery import audit_discovery

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class DiscoverySuccessTests(SimpleTestCase):
    """A valid synthetic suite passes the audit."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.mkdtemp()
        pkg = os.path.join(cls.tmp, "discovery_ok")
        os.makedirs(pkg)
        with open(os.path.join(pkg, "__init__.py"), "w") as f:
            f.write("")
        with open(os.path.join(pkg, "test_alpha.py"), "w") as f:
            f.write(
                "import unittest\n"
                "class OkAlpha(unittest.TestCase):\n"
                "    def test_one(self): pass\n"
            )

    @classmethod
    def tearDownClass(cls):
        if cls.tmp and os.path.exists(cls.tmp):
            shutil.rmtree(cls.tmp)
        super().tearDownClass()

    def test_valid_suite_succeeds(self):
        report = audit_discovery(self.tmp)
        self.assertTrue(report.success)
        self.assertGreater(report.total, 0)

    def test_report_includes_module_counts(self):
        report = audit_discovery(self.tmp)
        self.assertGreaterEqual(len(report.by_module), 1)

    def test_does_not_hard_code_total(self):
        report = audit_discovery(self.tmp)
        self.assertIsInstance(report.total, int)
        self.assertGreater(report.total, 0)


class DiscoveryDuplicateIdTests(SimpleTestCase):
    """Two tests with identical fully qualified IDs cause failure."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.mkdtemp()
        pkg = os.path.join(cls.tmp, "duplicate_ids")
        os.makedirs(pkg)
        with open(os.path.join(pkg, "__init__.py"), "w") as f:
            f.write("")
        # A module whose load_tests returns the same test twice.
        with open(os.path.join(pkg, "test_dup.py"), "w") as f:
            f.write(
                "import unittest\n"
                "class DupTest(unittest.TestCase):\n"
                "    def test_x(self): pass\n"
                "def load_tests(loader, tests, pattern):\n"
                "    t = DupTest('test_x')\n"
                "    suite = unittest.TestSuite()\n"
                "    suite.addTest(t)\n"
                "    suite.addTest(t)  # same object, same id()\n"
                "    return suite\n"
            )

    @classmethod
    def tearDownClass(cls):
        if cls.tmp and os.path.exists(cls.tmp):
            shutil.rmtree(cls.tmp)
        super().tearDownClass()

    def test_duplicate_ids_reported(self):
        report = audit_discovery(self.tmp)
        self.assertTrue(report.has_defects)
        self.assertFalse(report.success)
        self.assertGreater(len(report.duplicate_ids), 0,
                           f"Expected duplicate IDs, got: {report}")

    def test_duplicate_diagnostic_identifies_the_id(self):
        report = audit_discovery(self.tmp)
        self.assertTrue(
            any("test_x" in d for d in report.duplicate_ids),
            f"Duplicate info should mention 'test_x': {report.duplicate_ids}",
        )


class DiscoveryImportErrorTests(SimpleTestCase):
    """A module with a syntax error fails the audit."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.mkdtemp()
        pkg = os.path.join(cls.tmp, "import_err")
        os.makedirs(pkg)
        with open(os.path.join(pkg, "__init__.py"), "w") as f:
            f.write("")
        with open(os.path.join(pkg, "test_broken.py"), "w") as f:
            f.write("this is not valid Python {")

    @classmethod
    def tearDownClass(cls):
        if cls.tmp and os.path.exists(cls.tmp):
            shutil.rmtree(cls.tmp)
        super().tearDownClass()

    def test_import_error_is_a_defect(self):
        report = audit_discovery(self.tmp)
        self.assertTrue(report.has_defects,
                        f"Expected defects, got: {report}")
        self.assertFalse(report.success)
        self.assertGreater(
            len(report.import_errors), 0,
            f"Expected import errors, got: {report}",
        )

    def test_import_error_diagnostic_identifies_module(self):
        report = audit_discovery(self.tmp)
        combined = " ".join(report.import_errors)
        self.assertTrue(
            "test_broken" in combined or "SyntaxError" in combined
            or "invalid" in combined.lower(),
            f"Diagnostic should identify the broken module: {report.import_errors}",
        )


class DiscoveryZeroTestModuleTests(SimpleTestCase):
    """A test_*.py module with no discoverable tests fails."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.mkdtemp()
        pkg = os.path.join(cls.tmp, "zero_tests")
        os.makedirs(pkg)
        with open(os.path.join(pkg, "__init__.py"), "w") as f:
            f.write("")
        # A module that imports unittest but has no TestCase subclass.
        with open(os.path.join(pkg, "test_empty.py"), "w") as f:
            f.write(
                "import unittest\n"
                "class NotATestCase:\n"
                "    def test_something(self):\n"
                "        pass\n"
            )

    @classmethod
    def tearDownClass(cls):
        if cls.tmp and os.path.exists(cls.tmp):
            shutil.rmtree(cls.tmp)
        super().tearDownClass()

    def test_zero_test_module_is_a_defect(self):
        report = audit_discovery(self.tmp)
        self.assertTrue(report.has_defects)
        self.assertFalse(report.success)
        self.assertGreater(len(report.empty_modules), 0)

    def test_zero_test_diagnostic_identifies_module(self):
        report = audit_discovery(self.tmp)
        self.assertTrue(
            any("test_empty" in m for m in report.empty_modules),
            f"Empty module should be listed: {report.empty_modules}",
        )

    def test_helpers_without_test_prefix_are_ignored(self):
        """A helper.py without test_ prefix is not flagged."""
        pkg = os.path.join(self.tmp, "zero_tests")
        with open(os.path.join(pkg, "helper.py"), "w") as f:
            f.write(
                "import unittest\n"
                "class NotATestCase:\n"
                "    def test_something(self): pass\n"
            )
        report = audit_discovery(self.tmp)
        # helper.py does not match test_*.py, should not be flagged.
        self.assertFalse(
            any("helper.py" in m for m in report.empty_modules),
            f"helper.py should not be in empty_modules: {report.empty_modules}",
        )


class DiscoveryShellLauncherTests(SimpleTestCase):
    """The shell launcher exit code reflects DiscoveryReport.success."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        if self.tmp and os.path.exists(self.tmp):
            shutil.rmtree(self.tmp)
        super().tearDown()

    def _make_pkg(self, name, modules=None):
        pkg = os.path.join(self.tmp, name)
        os.makedirs(pkg, exist_ok=True)
        with open(os.path.join(pkg, "__init__.py"), "w") as f:
            f.write("")
        if modules:
            for mod_name, content in modules.items():
                with open(os.path.join(pkg, mod_name), "w") as f:
                    f.write(content)
        return pkg

    def test_valid_suite_exits_zero(self):
        self._make_pkg("valid_shell", {
            "test_a.py": (
                "import unittest\n"
                "class ShellA(unittest.TestCase):\n"
                "    def test_x(self): pass\n"
            ),
        })
        report = audit_discovery(self.tmp)
        self.assertTrue(report.success)

    def test_duplicate_ids_exits_nonzero(self):
        self._make_pkg("dup_shell", {
            "test_dup.py": (
                "import unittest\n"
                "class DupS(unittest.TestCase):\n"
                "    def test_x(self): pass\n"
                "def load_tests(loader, tests, pattern):\n"
                "    t = DupS('test_x')\n"
                "    s = unittest.TestSuite()\n"
                "    s.addTest(t)\n"
                "    s.addTest(t)\n"
                "    return s\n"
            ),
        })
        report = audit_discovery(self.tmp)
        self.assertFalse(report.success)
        self.assertGreater(len(report.duplicate_ids), 0)

    def test_import_error_exits_nonzero(self):
        self._make_pkg("importerr_shell", {
            "test_bad.py": "syntax error {{{",
        })
        report = audit_discovery(self.tmp)
        self.assertFalse(report.success)
        self.assertGreater(len(report.import_errors), 0)

    def test_zero_tests_exits_nonzero(self):
        self._make_pkg("zero_shell", {
            "test_empty.py": (
                "import unittest\n"
                "# No TestCase subclass — zero discoverable tests.\n"
            ),
        })
        report = audit_discovery(self.tmp)
        self.assertFalse(report.success)
        self.assertGreater(len(report.empty_modules), 0)


class DiscoveryCleanupTests(SimpleTestCase):
    """Temporary modules are cleaned up after tests."""

    def test_temp_dir_cleaned(self):
        tmp = tempfile.mkdtemp()
        try:
            pkg = os.path.join(tmp, "clean")
            os.makedirs(pkg)
            with open(os.path.join(pkg, "__init__.py"), "w") as f:
                f.write("")
            with open(os.path.join(pkg, "test_x.py"), "w") as f:
                f.write(
                    "import unittest\n"
                    "class CleanX(unittest.TestCase):\n"
                    "    def test_y(self): pass\n"
                )
            report = audit_discovery(tmp)
            self.assertTrue(report.success)
        finally:
            if os.path.exists(tmp):
                shutil.rmtree(tmp)
        self.assertFalse(os.path.exists(tmp))
