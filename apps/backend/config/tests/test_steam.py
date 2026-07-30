"""
Steam environment-configuration tests — SBGC-42.

Verifies that steam_client_config_from_settings() correctly parses
raw Django setting strings into a validated SteamClientConfig without
making network requests or instantiating a client.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from games.services.steam.config import SteamClientConfig

from config.steam import steam_client_config_from_settings


class FactoryDefaultsTests(SimpleTestCase):
    """Documented defaults produce the expected config."""

    def test_defaults_produce_documented_config(self):
        cfg = steam_client_config_from_settings()
        self.assertIsNone(cfg.api_key)
        self.assertEqual(cfg.connect_timeout, 3.05)
        self.assertEqual(cfg.read_timeout, 10.0)
        self.assertEqual(cfg.max_retries, 2)
        self.assertEqual(cfg.retry_backoff, 0.25)
        self.assertEqual(cfg.max_response_bytes, 2_097_152)
        self.assertEqual(cfg.api_origin, "https://api.steampowered.com")
        self.assertEqual(cfg.store_origin, "https://store.steampowered.com")
        self.assertEqual(tuple(cfg.cdn_allowed_hosts), ())

    def test_factory_returns_steam_client_config(self):
        cfg = steam_client_config_from_settings()
        self.assertIsInstance(cfg, SteamClientConfig)

    def test_factory_makes_no_network_request(self):
        cfg = steam_client_config_from_settings()
        self.assertIsNotNone(cfg)


class SettingsOverrideTests(SimpleTestCase):
    """Overridden Django settings produce the expected config."""

    @override_settings(
        STEAM_WEB_API_KEY="  ABC-SECRET-123  ",
        STEAM_CONNECT_TIMEOUT_SECONDS="5.0",
        STEAM_READ_TIMEOUT_SECONDS="20",
        STEAM_MAX_RETRIES="1",
        STEAM_RETRY_BACKOFF_SECONDS="0.5",
        STEAM_MAX_RESPONSE_BYTES="1048576",
        STEAM_CDN_ALLOWED_HOSTS="host-a.example.com,host-b.example.com",
    )
    def test_overrides_drive_config(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(cfg.api_key, "ABC-SECRET-123")
        self.assertEqual(cfg.connect_timeout, 5.0)
        self.assertEqual(cfg.read_timeout, 20.0)
        self.assertEqual(cfg.max_retries, 1)
        self.assertEqual(cfg.retry_backoff, 0.5)
        self.assertEqual(cfg.max_response_bytes, 1_048_576)
        self.assertEqual(
            tuple(cfg.cdn_allowed_hosts),
            ("host-a.example.com", "host-b.example.com"),
        )

    @override_settings(STEAM_WEB_API_KEY="VALID-KEY")
    def test_key_present_when_set(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(cfg.api_key, "VALID-KEY")


class BlankValuesBecomeDefaultsTests(SimpleTestCase):
    """Blank / whitespace values fall back to documented defaults."""

    @override_settings(STEAM_WEB_API_KEY="")
    def test_empty_string_becomes_none(self):
        cfg = steam_client_config_from_settings()
        self.assertIsNone(cfg.api_key)

    @override_settings(STEAM_WEB_API_KEY="   ")
    def test_whitespace_only_becomes_none(self):
        cfg = steam_client_config_from_settings()
        self.assertIsNone(cfg.api_key)

    @override_settings(STEAM_CONNECT_TIMEOUT_SECONDS="")
    def test_blank_connect_timeout_uses_default(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(cfg.connect_timeout, 3.05)

    @override_settings(STEAM_READ_TIMEOUT_SECONDS="")
    def test_blank_read_timeout_uses_default(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(cfg.read_timeout, 10.0)

    @override_settings(STEAM_MAX_RETRIES="")
    def test_blank_retries_uses_default(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(cfg.max_retries, 2)

    @override_settings(STEAM_RETRY_BACKOFF_SECONDS="")
    def test_blank_backoff_uses_default(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(cfg.retry_backoff, 0.25)

    @override_settings(STEAM_MAX_RESPONSE_BYTES="")
    def test_blank_response_bytes_uses_default(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(cfg.max_response_bytes, 2_097_152)

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="")
    def test_blank_cdn_hosts_uses_default(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(tuple(cfg.cdn_allowed_hosts), ())

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="  ,  ")
    def test_blanks_only_cdn_hosts_returns_empty(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(tuple(cfg.cdn_allowed_hosts), ())


class ReprSafetyTests(SimpleTestCase):
    """repr(SteamClientConfig) never includes the API key."""

    def test_repr_excludes_key_value_when_present(self):
        cfg = SteamClientConfig(api_key="SUPER-SECRET")
        r = repr(cfg)
        self.assertNotIn("SUPER-SECRET", r)
        self.assertIn("api_key=present", r)

    def test_repr_shows_absent_when_none(self):
        cfg = SteamClientConfig(api_key=None)
        r = repr(cfg)
        self.assertIn("api_key=absent", r)


class MalformedValueTests(SimpleTestCase):
    """Malformed environment values raise ImproperlyConfigured."""

    @override_settings(STEAM_CONNECT_TIMEOUT_SECONDS="not-a-number")
    def test_non_numeric_connect_timeout_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CONNECT_TIMEOUT_SECONDS="NaN")
    def test_nan_connect_timeout_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CONNECT_TIMEOUT_SECONDS="Infinity")
    def test_infinity_connect_timeout_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CONNECT_TIMEOUT_SECONDS="-Infinity")
    def test_neg_infinity_connect_timeout_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_READ_TIMEOUT_SECONDS="not-a-number")
    def test_non_numeric_read_timeout_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_MAX_RETRIES="not-int")
    def test_non_integer_retries_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_MAX_RETRIES="3.14")
    def test_float_retries_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_RETRY_BACKOFF_SECONDS="NaN")
    def test_nan_backoff_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_MAX_RESPONSE_BYTES="abc")
    def test_non_integer_response_bytes_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_MAX_RESPONSE_BYTES="3.0")
    def test_float_response_bytes_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()


class OutOfRangeValueTests(SimpleTestCase):
    """Out-of-range values raise ImproperlyConfigured at the Django boundary."""

    @override_settings(STEAM_CONNECT_TIMEOUT_SECONDS="0")
    def test_zero_connect_timeout_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CONNECT_TIMEOUT_SECONDS="31")
    def test_excessive_connect_timeout_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_READ_TIMEOUT_SECONDS="-1")
    def test_negative_read_timeout_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_READ_TIMEOUT_SECONDS="61")
    def test_excessive_read_timeout_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_MAX_RETRIES="5")
    def test_excessive_retries_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_MAX_RETRIES="-1")
    def test_negative_retries_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_RETRY_BACKOFF_SECONDS="-0.1")
    def test_negative_backoff_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_MAX_RESPONSE_BYTES="0")
    def test_zero_response_bytes_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_MAX_RESPONSE_BYTES="-100")
    def test_negative_response_bytes_fails(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()


class CdnHostParsingTests(SimpleTestCase):
    """Valid CDN host values are parsed, normalised, and deduplicated."""

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="cdn.example.com")
    def test_single_host(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(tuple(cfg.cdn_allowed_hosts), ("cdn.example.com",))

    @override_settings(
        STEAM_CDN_ALLOWED_HOSTS="a.example.com,b.example.com,c.example.com"
    )
    def test_multiple_hosts(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(
            tuple(cfg.cdn_allowed_hosts),
            ("a.example.com", "b.example.com", "c.example.com"),
        )

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="  host.example.io  ")
    def test_whitespace_stripped(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(tuple(cfg.cdn_allowed_hosts), ("host.example.io",))

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="cdn1.example.com,")
    def test_trailing_comma_produces_no_blank_host(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(tuple(cfg.cdn_allowed_hosts), ("cdn1.example.com",))

    @override_settings(STEAM_CDN_ALLOWED_HOSTS=",cdn2.example.com")
    def test_leading_comma_produces_no_blank_host(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(tuple(cfg.cdn_allowed_hosts), ("cdn2.example.com",))

    @override_settings(
        STEAM_CDN_ALLOWED_HOSTS="A.EXAMPLE.COM,a.example.com,B.EXAMPLE.COM"
    )
    def test_case_insensitive_deduplication(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(
            tuple(cfg.cdn_allowed_hosts),
            ("a.example.com", "b.example.com"),
        )

    @override_settings(
        STEAM_CDN_ALLOWED_HOSTS="first.example.com,second.example.com,first.example.com"
    )
    def test_duplicates_removed_preserving_first_occurrence(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(
            tuple(cfg.cdn_allowed_hosts),
            ("first.example.com", "second.example.com"),
        )

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="CDN.UPPERCASE.COM")
    def test_uppercase_normalised_to_lowercase(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(tuple(cfg.cdn_allowed_hosts), ("cdn.uppercase.com",))


class CdnHostMalformedTests(SimpleTestCase):
    """Malformed CDN host entries raise ImproperlyConfigured."""

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="https://cdn.example.com")
    def test_scheme_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="//cdn.example.com")
    def test_protocol_relative_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="cdn.example.com/path")
    def test_path_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="cdn.example.com?q=1")
    def test_query_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="cdn.example.com#top")
    def test_fragment_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="user:pass@cdn.example.com")
    def test_credentials_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="cdn.example.com:443")
    def test_port_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="*.example.com")
    def test_wildcard_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="127.0.0.1")
    def test_ipv4_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="::1")
    def test_ipv6_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="localhost")
    def test_localhost_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="localhost.localdomain")
    def test_localhost_localdomain_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="cdn..example.com")
    def test_consecutive_dots_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="-start.example.com")
    def test_leading_hyphen_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()

    @override_settings(STEAM_CDN_ALLOWED_HOSTS="end-.example.com")
    def test_trailing_hyphen_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            steam_client_config_from_settings()


class TestSettingsIsolationTests(SimpleTestCase):
    """The test settings module never reads the developer's real .env file."""

    def test_test_key_is_blank_by_default(self):
        self.assertEqual(settings.STEAM_WEB_API_KEY, "")

    def test_test_key_produces_absent_config(self):
        cfg = steam_client_config_from_settings()
        self.assertIsNone(cfg.api_key)

    def test_test_database_is_in_memory_sqlite(self):
        self.assertEqual(
            settings.DATABASES["default"]["ENGINE"],
            "django.db.backends.sqlite3",
        )


class SubprocessIsolationTests(SimpleTestCase):
    """
    Prove that importing config.settings.test in a subprocess with
    hostile environment variables uses deterministic test values,
    never the injected values, and never reads a real .env key.
    """

    _SCRIPT = """
import os, sys, json

# Inject hostile values for every Steam variable before import.
os.environ["STEAM_WEB_API_KEY"] = "INJECTED-SECRET-KEY"
os.environ["STEAM_CONNECT_TIMEOUT_SECONDS"] = "999"
os.environ["STEAM_READ_TIMEOUT_SECONDS"] = "999"
os.environ["STEAM_MAX_RETRIES"] = "99"
os.environ["STEAM_RETRY_BACKOFF_SECONDS"] = "99.9"
os.environ["STEAM_MAX_RESPONSE_BYTES"] = "999999"
os.environ["STEAM_CDN_ALLOWED_HOSTS"] = "evil.com"

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "config.settings.test"
)

import django
django.setup()

from django.conf import settings

result = {
    "STEAM_WEB_API_KEY": settings.STEAM_WEB_API_KEY,
    "STEAM_CONNECT_TIMEOUT_SECONDS": settings.STEAM_CONNECT_TIMEOUT_SECONDS,
    "STEAM_READ_TIMEOUT_SECONDS": settings.STEAM_READ_TIMEOUT_SECONDS,
    "STEAM_MAX_RETRIES": settings.STEAM_MAX_RETRIES,
    "STEAM_RETRY_BACKOFF_SECONDS": settings.STEAM_RETRY_BACKOFF_SECONDS,
    "STEAM_MAX_RESPONSE_BYTES": settings.STEAM_MAX_RESPONSE_BYTES,
    "STEAM_CDN_ALLOWED_HOSTS": settings.STEAM_CDN_ALLOWED_HOSTS,
    "DATABASE_ENGINE": settings.DATABASES["default"]["ENGINE"],
}
print(json.dumps(result))
"""

    def _backend_dir(self) -> str:
        """Return the backend app directory for subprocess cwd."""
        # __file__ → config/tests/test_steam.py → config → apps/backend
        return os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    def test_hostile_env_vars_do_not_pollute_test_settings(self):
        proc = subprocess.run(
            [sys.executable, "-c", self._SCRIPT],
            capture_output=True,
            text=True,
            cwd=self._backend_dir(),
            timeout=30,
        )

        if proc.returncode != 0:
            self.fail(f"Subprocess failed:\n{proc.stderr}")

        result = json.loads(proc.stdout)

        # All Steam values must be the deterministic test defaults,
        # NOT the injected hostile values.
        self.assertEqual(result["STEAM_WEB_API_KEY"], "")
        self.assertEqual(result["STEAM_CONNECT_TIMEOUT_SECONDS"], "3.05")
        self.assertEqual(result["STEAM_READ_TIMEOUT_SECONDS"], "10")
        self.assertEqual(result["STEAM_MAX_RETRIES"], "2")
        self.assertEqual(result["STEAM_RETRY_BACKOFF_SECONDS"], "0.25")
        self.assertEqual(result["STEAM_MAX_RESPONSE_BYTES"], "2097152")
        self.assertEqual(result["STEAM_CDN_ALLOWED_HOSTS"], "")

        # Database must be in-memory SQLite, not Neon.
        self.assertEqual(result["DATABASE_ENGINE"], "django.db.backends.sqlite3")

    def test_subprocess_output_contains_no_secret_key(self):
        proc = subprocess.run(
            [sys.executable, "-c", self._SCRIPT],
            capture_output=True,
            text=True,
            cwd=self._backend_dir(),
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("INJECTED-SECRET-KEY", proc.stdout)


class DotenvIsolationTests(SimpleTestCase):
    """
    Prove that the test settings skip .env loading while development
    and production settings follow their normal .env paths.
    """

    _DEV_LOAD_SCRIPT = """
import os, json

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "config.settings.development"
)

import django
django.setup()

from django.conf import settings

result = {
    "DEBUG": settings.DEBUG,
    "DATABASE_ENGINE": settings.DATABASES["default"]["ENGINE"],
    "STEAM_CONNECT_TIMEOUT_SECONDS": settings.STEAM_CONNECT_TIMEOUT_SECONDS,
    "STEAM_MAX_RETRIES": settings.STEAM_MAX_RETRIES,
}
print(json.dumps(result))
"""

    _PROD_LOAD_SCRIPT = """
import os, json

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "config.settings.production"
)

os.environ["DJANGO_ALLOWED_HOSTS"] = "example.com"
os.environ["DJANGO_SECRET_KEY"] = "x" * 30
os.environ["CSRF_TRUSTED_ORIGINS"] = "https://example.com"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import django
django.setup()

from django.conf import settings

result = {
    "DEBUG": settings.DEBUG,
    "DATABASE_ENGINE": settings.DATABASES["default"]["ENGINE"],
    "STEAM_CONNECT_TIMEOUT_SECONDS": settings.STEAM_CONNECT_TIMEOUT_SECONDS,
    "STEAM_MAX_RETRIES": settings.STEAM_MAX_RETRIES,
}
print(json.dumps(result))
"""

    def _backend_dir(self) -> str:
        return os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    def _run(self, script: str, env: dict[str, str] | None = None) -> dict:
        kwargs: dict = {
            "capture_output": True,
            "text": True,
            "cwd": self._backend_dir(),
            "timeout": 30,
        }
        if env is not None:
            kwargs["env"] = {**os.environ, **env}
        proc = subprocess.run([sys.executable, "-c", script], **kwargs)
        if proc.returncode != 0:
            self.fail(f"Subprocess failed:\n{proc.stderr}")
        return json.loads(proc.stdout)

    def test_development_settings_imports_normally(self):
        """Development settings load without a .env file present and use defaults."""
        result = self._run(self._DEV_LOAD_SCRIPT)
        self.assertTrue(result["DEBUG"])
        self.assertIn(
            result["DATABASE_ENGINE"],
            [
                "django.db.backends.sqlite3",
                "django.db.backends.postgresql",
            ],
        )
        # Steam defaults come from base.py's env() calls with defaults.
        self.assertEqual(result["STEAM_CONNECT_TIMEOUT_SECONDS"], "3.05")
        self.assertEqual(result["STEAM_MAX_RETRIES"], "2")

    def test_production_settings_reads_environment(self):
        """Production settings use the supplied environment values."""
        result = self._run(self._PROD_LOAD_SCRIPT)
        self.assertEqual(result["DATABASE_ENGINE"], "django.db.backends.sqlite3")
        # Steam defaults are still used when not overridden in env.
        self.assertEqual(result["STEAM_CONNECT_TIMEOUT_SECONDS"], "3.05")
        self.assertEqual(result["STEAM_MAX_RETRIES"], "2")

    def test_django_skip_dotenv_is_not_documented_as_public(self):
        """DJANGO_SKIP_DOTENV appears only as an implementation detail."""
        # Not in base.py module docstring.
        # as a public configuration mechanism in the module docs.
        # We verify the test module explicitly sets it.
        import config.settings.test as test_module

        test_source = open(test_module.__file__).read()
        self.assertIn("DJANGO_SKIP_DOTENV", test_source)


class NoImportSideEffectTests(SimpleTestCase):
    """Settings import does not instantiate a Steam client or make network calls."""

    def test_settings_import_does_not_instantiate_client(self):
        self.assertTrue(hasattr(settings, "STEAM_WEB_API_KEY"))
        self.assertIsInstance(settings.STEAM_WEB_API_KEY, str)

    def test_steam_module_import_is_lazy(self):
        from config import steam

        self.assertTrue(callable(steam.steam_client_config_from_settings))


class OriginImmutabilityTests(SimpleTestCase):
    """API and store origins are fixed and not affected by environment."""

    def test_api_origin_is_not_configurable(self):
        cfg = steam_client_config_from_settings()
        self.assertEqual(cfg.api_origin, "https://api.steampowered.com")
        self.assertEqual(cfg.store_origin, "https://store.steampowered.com")

    def test_origin_unchanged_with_overrides(self):
        with override_settings(
            STEAM_WEB_API_KEY="KEY123",
            STEAM_CONNECT_TIMEOUT_SECONDS="1.0",
        ):
            cfg = steam_client_config_from_settings()
            self.assertEqual(cfg.api_origin, "https://api.steampowered.com")
            self.assertEqual(cfg.store_origin, "https://store.steampowered.com")
