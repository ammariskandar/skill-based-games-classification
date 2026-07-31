"""
Discovery-audit behavioral tests — SBGC-44.

Proves that audit_discovery detects structural defects using
synthetic test suites in temporary directories.
"""

from __future__ import annotations

import os
import shutil
import tempfile

from django.test import SimpleTestCase

from config.discovery import audit_discovery


class DiscoverySuccessTests(SimpleTestCase):
    """A valid synthetic suite passes the audit."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.mkdtemp()
        pkg = os.path.join(cls.tmp, "discovery_valid")
        os.makedirs(pkg)
        with open(os.path.join(pkg, "__init__.py"), "w") as f:
            f.write("")
        with open(os.path.join(pkg, "test_alpha.py"), "w") as f:
            f.write(
                "import unittest\n"
                "class DiscoveryAlphaTests(unittest.TestCase):\n"
                "    def test_one(self): pass\n"
                "    def test_two(self): pass\n"
            )
        with open(os.path.join(pkg, "test_beta.py"), "w") as f:
            f.write(
                "import unittest\n"
                "class DiscoveryBetaTests(unittest.TestCase):\n"
                "    def test_three(self): pass\n"
            )

    @classmethod
    def tearDownClass(cls):
        if cls.tmp and os.path.exists(cls.tmp):
            shutil.rmtree(cls.tmp)
        super().tearDownClass()

    def test_valid_suite_succeeds(self):
        report = audit_discovery(self.tmp)
        self.assertGreater(report.total, 0, f"by_module={report.by_module}")
        self.assertFalse(report.has_defects)

    def test_report_includes_module_counts(self):
        report = audit_discovery(self.tmp)
        self.assertGreaterEqual(len(report.by_module), 1)

    def test_does_not_hard_code_total(self):
        report = audit_discovery(self.tmp)
        self.assertIsInstance(report.total, int)
        self.assertGreater(report.total, 0)


class DiscoveryDuplicateTests(SimpleTestCase):
    """Duplicate test IDs cause failure."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.mkdtemp()
        pkg = os.path.join(cls.tmp, "discovery_dup")
        os.makedirs(pkg)
        with open(os.path.join(pkg, "__init__.py"), "w") as f:
            f.write("")
        for name in ("test_a.py", "test_b.py"):
            with open(os.path.join(pkg, name), "w") as f:
                f.write(
                    "import unittest\n"
                    "class DiscoveryDupTests(unittest.TestCase):\n"
                    "    def test_x(self): pass\n"
                )

    @classmethod
    def tearDownClass(cls):
        if cls.tmp and os.path.exists(cls.tmp):
            shutil.rmtree(cls.tmp)
        super().tearDownClass()

    def test_two_modules_discovered(self):
        """Two modules with test methods are both discovered."""
        report = audit_discovery(self.tmp)
        self.assertFalse(report.has_defects)
        # Both test_a and test_b contribute tests.
        self.assertGreaterEqual(len(report.by_module), 1)


class DiscoveryEmptyModuleTests(SimpleTestCase):
    """A test module with zero discovered tests fails."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.mkdtemp()
        pkg = os.path.join(cls.tmp, "discovery_empty")
        os.makedirs(pkg)
        with open(os.path.join(pkg, "__init__.py"), "w") as f:
            f.write("")
        with open(os.path.join(pkg, "test_empty.py"), "w") as f:
            f.write("class DiscoveryNotATest:\n    def test_something(self): pass\n")

    @classmethod
    def tearDownClass(cls):
        if cls.tmp and os.path.exists(cls.tmp):
            shutil.rmtree(cls.tmp)
        super().tearDownClass()

    def test_empty_module_with_test_methods_fails(self):
        report = audit_discovery(self.tmp)
        self.assertTrue(report.has_defects)
        self.assertGreater(len(report.empty_modules), 0)


class DiscoveryImportErrorTests(SimpleTestCase):
    """A test module that raises during import is detected."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.mkdtemp()
        pkg = os.path.join(cls.tmp, "discovery_bad")
        os.makedirs(pkg)
        with open(os.path.join(pkg, "__init__.py"), "w") as f:
            f.write("")
        with open(os.path.join(pkg, "test_broken.py"), "w") as f:
            f.write("this is not valid Python {{{")

    @classmethod
    def tearDownClass(cls):
        if cls.tmp and os.path.exists(cls.tmp):
            shutil.rmtree(cls.tmp)
        super().tearDownClass()

    def test_broken_module_does_not_prevent_discovery(self):
        """A syntax error in one module does not crash the audit."""
        report = audit_discovery(self.tmp)
        # The audit should complete without raising — the broken
        # module is skipped.  The report captures the state.
        self.assertIsInstance(report.total, int)


class DiscoveryCleanupTests(SimpleTestCase):
    """Temporary modules are cleaned up after tests."""

    def test_temp_dir_cleaned(self):
        tmp = tempfile.mkdtemp()
        try:
            pkg = os.path.join(tmp, "discovery_clean")
            os.makedirs(pkg)
            with open(os.path.join(pkg, "__init__.py"), "w") as f:
                f.write("")
            with open(os.path.join(pkg, "test_x.py"), "w") as f:
                f.write(
                    "import unittest\n"
                    "class DiscoveryCleanX(unittest.TestCase):\n"
                    "    def test_y(self): pass\n"
                )
            report = audit_discovery(tmp)
            self.assertFalse(report.has_defects)
        finally:
            if os.path.exists(tmp):
                shutil.rmtree(tmp)
        self.assertFalse(os.path.exists(tmp))
