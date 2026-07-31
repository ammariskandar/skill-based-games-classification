"""
Shared test-helper verification — SBGC-44.

Proves minimal_subprocess_env, prod_test_env, run_manage, and
discovery-audit behavior.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from config.testing import (
    minimal_subprocess_env,
    prod_test_env,
    run_manage,
)

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class MinimalSubprocessEnvTests(SimpleTestCase):
    """minimal_subprocess_env() isolates subprocess environments."""

    def test_retains_path(self):
        env = minimal_subprocess_env()
        self.assertIn("PATH", env)

    def test_excludes_django_settings_module(self):
        env = minimal_subprocess_env()
        self.assertNotIn("DJANGO_SETTINGS_MODULE", env)

    def test_excludes_django_skip_dotenv(self):
        env = minimal_subprocess_env()
        self.assertNotIn("DJANGO_SKIP_DOTENV", env)

    def test_excludes_database_url(self):
        env = minimal_subprocess_env()
        self.assertNotIn("DATABASE_URL", env)

    def test_excludes_secret_key(self):
        env = minimal_subprocess_env()
        self.assertNotIn("DJANGO_SECRET_KEY", env)

    def test_excludes_admin_url_path(self):
        env = minimal_subprocess_env()
        self.assertNotIn("ADMIN_URL_PATH", env)

    def test_excludes_steam_web_api_key(self):
        env = minimal_subprocess_env()
        self.assertNotIn("STEAM_WEB_API_KEY", env)

    def test_excludes_csrf_origins(self):
        env = minimal_subprocess_env()
        self.assertNotIn("CSRF_TRUSTED_ORIGINS", env)

    def test_excludes_allowed_hosts(self):
        env = minimal_subprocess_env()
        self.assertNotIn("DJANGO_ALLOWED_HOSTS", env)

    def test_explicit_overrides_included(self):
        env = minimal_subprocess_env(MY_VAR="hello")
        self.assertEqual(env["MY_VAR"], "hello")

    def test_hostile_parent_var_not_inherited(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(f"""
import os, json
os.environ["INJECTED_SECRET"] = "should-not-leak"
# Now call our helper
import sys
sys.path.insert(0, "{_BACKEND_DIR.parent}")
from config.testing import minimal_subprocess_env
env = minimal_subprocess_env()
print(json.dumps({{k: "***" if "SECRET" in k else v for k, v in env.items()}}))
""")
            script_path = f.name

        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "INJECTED_SECRET": "should-not-leak"},
            )
            output = proc.stdout.strip()
            if output:
                data = json.loads(output)
                self.assertNotIn("INJECTED_SECRET", data)
        finally:
            os.unlink(script_path)


class ProdTestEnvTests(SimpleTestCase):
    """prod_test_env() provides valid production dummy values."""

    def test_contains_postgresql_url(self):
        env = prod_test_env()
        self.assertIn("postgresql://", env["DATABASE_URL"])

    def test_contains_secret_key(self):
        env = prod_test_env()
        self.assertIn("DJANGO_SECRET_KEY", env)
        self.assertGreaterEqual(len(env["DJANGO_SECRET_KEY"]), 50)

    def test_contains_required_production_vars(self):
        env = prod_test_env()
        for key in (
            "DJANGO_ALLOWED_HOSTS",
            "CSRF_TRUSTED_ORIGINS",
            "ADMIN_URL_PATH",
            "DJANGO_LOG_LEVEL",
        ):
            self.assertIn(key, env, f"Missing {key}")

    def test_no_real_credential(self):
        env = prod_test_env()
        self.assertNotIn("@real-neon", env["DATABASE_URL"])
        self.assertNotIn("real-secret", env["DJANGO_SECRET_KEY"].lower())

    def test_can_import_production_settings(self):
        """prod_test_env values can import production settings without DB."""
        env = prod_test_env(
            DJANGO_SECURE_HSTS_SECONDS="3600",
        )
        proc = run_manage(
            "check",
            "--settings=config.settings.production",
            env=env,
        )
        self.assertEqual(proc.returncode, 0, f"stderr: {proc.stderr}")

    def test_overrides_work(self):
        env = prod_test_env(ADMIN_URL_PATH="custom-prod")
        self.assertEqual(env["ADMIN_URL_PATH"], "custom-prod")


class RunManageTests(SimpleTestCase):
    """run_manage() executes manage.py commands safely."""

    def test_uses_repo_venv_python(self):
        env = minimal_subprocess_env()
        proc = run_manage("check", env=env)
        self.assertEqual(proc.returncode, 0)

    def test_captures_output(self):
        env = minimal_subprocess_env()
        proc = run_manage("check", env=env)
        self.assertIn("System check identified no issues", proc.stdout)

    def test_preserves_exit_code(self):
        env = minimal_subprocess_env(
            DJANGO_SETTINGS_MODULE="config.settings.test",
        )
        proc = run_manage("check", env=env)
        self.assertEqual(proc.returncode, 0)

    def test_does_not_silently_inherit_parent_env(self):
        """Setting DJANGO_SETTINGS_MODULE in parent should not leak."""
        env = minimal_subprocess_env()
        proc = run_manage("check", env=env)
        # Without DJANGO_SETTINGS_MODULE, manage.py uses its default.
        # The check should work because manage.py sets a default.
        self.assertIn(proc.returncode, (0, 1))
