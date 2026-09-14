#!/usr/bin/env python3
"""
Production-settings verification harness — SBGC-17 deployment readiness.

Exercises ``config.settings.production`` with the exact environment contract the
Render service must provide, without touching a database or the network.  Loads
settings (which runs every fail-fast validator) and then executes
``manage.py check --deploy``.

Credentials below are deliberately NON-SECRET placeholders.  The Neon password
is intentionally redacted (``CENSORED``) — ``check --deploy`` never opens a
connection, so the value only needs to parse.

Usage:
    apps/backend/.venv/bin/python scripts/verify-production-env.py

Exit code 0 when settings load and the deploy check completes; non-zero when a
validator raises ``ImproperlyConfigured`` or a Django error check fails.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend"))

# Never read a developer's local apps/backend/.env.
os.environ["DJANGO_SKIP_DOTENV"] = "1"
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"

# ── Values the operator must substitute (placeholders) ──────────────────────
BACKEND_HOST = "skill-based-games-classification.onrender.com"  # verified Render URL
FRONTEND_ORIGIN = "https://gamedna.my"  # public site (Vercel custom domain)
SCOPED_DB_USER = "app_django"  # least-privilege runtime role
# Provisioned by scripts/db-provision-app-role.sql; DML only, no DDL.
NEON_POOLED = (
    f"postgresql://{SCOPED_DB_USER}:CENSORED@"
    "ep-damp-dust-azgkwrol-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)
NEON_DIRECT = (
    "postgresql://neondb_owner:CENSORED@"
    "ep-damp-dust-azgkwrol.c-3.ap-southeast-1.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)

# A 64-character, high-entropy placeholder that satisfies validate_secret_key.
# Replace with: python -c "from django.core.management.utils import \
#   get_random_secret_key as g; print(g())"
SECRET_PLACEHOLDER = (
    "Zx4Qm!9Tv2Lp7Rs1Kd8Wy3Nb6Hj0Ua5Ce2Gr7Mt4Pz9Xv1Bs6Lq3Df8Nw5Ry2Tc7Uj4"
)

ENV = {
    # -- Required, fail-fast in production.py / base.py ----------------------
    "DJANGO_DEBUG": "False",
    "DJANGO_SECRET_KEY": SECRET_PLACEHOLDER,
    "ADMIN_URL_PATH": "mygamedna-admin",
    "DJANGO_ALLOWED_HOSTS": BACKEND_HOST,
    "CSRF_TRUSTED_ORIGINS": (
        f"https://{BACKEND_HOST},{FRONTEND_ORIGIN},"
        "https://www.gamedna.my,https://skill-based-games-classification-fr.vercel.app"
    ),
    "DATABASE_URL": NEON_POOLED,
    "RECAPTCHA_SECRET_KEY": "placeholder-recaptcha-secret",
    "RECAPTCHA_SITE_KEY": "6LdU_bktAAAAANW2tjirQlPRvKmHjuryTSkgLpN0",
    "STEAM_WEB_API_KEY": "placeholder-steam-web-api-key",
    "DJANGO_OWNER_USERNAME": "your_owner_username",
    "DJANGO_SUPERUSER_1": "superuser_one",
    "DJANGO_SUPERUSER_2": "superuser_two",
    # -- Release-phase only (read by scripts/backend-migrate.sh) -------------
    "MIGRATION_DATABASE_URL": NEON_DIRECT,
    # -- Optional (documented defaults) --------------------------------------
    "DB_SSL_REQUIRE": "true",
    "DJANGO_LOG_LEVEL": "INFO",
    "DJANGO_SECURE_HSTS_SECONDS": "31536000",
    "PUBLIC_SITE_URL": FRONTEND_ORIGIN,
    "DEFAULT_FROM_EMAIL": "noreply@gamedna.my",
    "WEB_CONCURRENCY": "2",
}

os.environ.update(ENV)


def main() -> int:
    import django

    django.setup()

    from django.conf import settings
    from django.core.management import call_command

    print("─" * 68)
    print("config.settings.production loaded successfully (all validators passed)")
    print("─" * 68)
    print(f"DEBUG                 : {settings.DEBUG}")
    print(f"ADMIN_URL_PATH        : {settings.ADMIN_URL_PATH}")
    print(f"ALLOWED_HOSTS         : {settings.ALLOWED_HOSTS}")
    print(f"CSRF_TRUSTED_ORIGINS  : {settings.CSRF_TRUSTED_ORIGINS}")
    print(f"DB ENGINE             : {settings.DATABASES['default']['ENGINE']}")
    print(f"DB USER               : {settings.DATABASES['default']['USER']}")
    print(f"DB HOST               : {settings.DATABASES['default']['HOST']}")
    print(f"DB CONN_MAX_AGE       : {settings.DATABASES['default']['CONN_MAX_AGE']}")
    print(f"DB OPTIONS            : {settings.DATABASES['default']['OPTIONS']}")
    print(f"NINJA_API_DOCS_ENABLED: {settings.NINJA_API_DOCS_ENABLED}")
    print(f"HSTS                  : {settings.SECURE_HSTS_SECONDS}")
    print(f"SESSION_COOKIE_SECURE : {settings.SESSION_COOKIE_SECURE}")
    print(f"CSRF_COOKIE_SECURE    : {settings.CSRF_COOKIE_SECURE}")
    print("─" * 68)

    call_command("check", "--deploy")
    print("─" * 68)
    print("check --deploy completed.")
    return 0


def probe_expected_failures() -> int:
    """Prove the exact validation rules (the failure modes of earlier attempts)."""
    from config.admin import validate_admin_url_path
    from config.security import (
        parse_allowed_hosts,
        parse_trusted_origins,
        validate_secret_key,
    )
    from django.core.exceptions import ImproperlyConfigured

    checks: list[tuple[str, bool]] = []

    def expect_reject(label: str, fn) -> None:
        try:
            fn()
        except ImproperlyConfigured as exc:
            checks.append((f"REJECTED {label}: {exc}", True))
        else:
            checks.append((f"NOT REJECTED {label}", False))

    def expect_accept(label: str, fn) -> None:
        try:
            value = fn()
        except ImproperlyConfigured as exc:
            checks.append((f"WRONGLY REJECTED {label}: {exc}", False))
        else:
            checks.append((f"ACCEPTED {label} -> {value}", True))

    # ADMIN_URL_PATH rules (segment validator)
    expect_reject(
        "ADMIN_URL_PATH='my/admin' (slash)", lambda: validate_admin_url_path("my/admin")
    )
    expect_reject(
        "ADMIN_URL_PATH='api' (reserved)", lambda: validate_admin_url_path("api")
    )
    expect_accept(
        "ADMIN_URL_PATH='mygamedna-admin'",
        lambda: validate_admin_url_path("mygamedna-admin"),
    )

    # ALLOWED_HOSTS rules
    expect_reject(
        "ALLOWED_HOSTS='.example.com' (leading dot)",
        lambda: parse_allowed_hosts(".example.com"),
    )
    expect_reject("ALLOWED_HOSTS='*' (wildcard)", lambda: parse_allowed_hosts("*"))
    expect_reject(
        "ALLOWED_HOSTS='example.com:8000' (port)",
        lambda: parse_allowed_hosts("example.com:8000"),
    )
    expect_reject(
        "ALLOWED_HOSTS='https://example.com' (scheme)",
        lambda: parse_allowed_hosts("https://example.com"),
    )
    expect_accept(
        "ALLOWED_HOSTS='skill-based-games-classification.onrender.com'",
        lambda: parse_allowed_hosts("skill-based-games-classification.onrender.com"),
    )

    # CSRF origins
    expect_reject(
        "CSRF http origin under require_https",
        lambda: parse_trusted_origins("http://example.com", require_https=True),
    )
    expect_accept(
        "CSRF 'https://gamedna.my'",
        lambda: parse_trusted_origins("https://gamedna.my", require_https=True),
    )

    # Secret key
    expect_reject("SECRET_KEY short", lambda: validate_secret_key("short"))
    expect_reject(
        "SECRET_KEY dev placeholder",
        lambda: validate_secret_key("django-insecure-dev-key-do-not-use-in-production"),
    )
    expect_reject(
        "SECRET_KEY insecure prefix",
        lambda: validate_secret_key(
            "django-insecure-" + "aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5a"
        ),
    )
    expect_accept(
        "SECRET_KEY 64-char high entropy",
        lambda: validate_secret_key(SECRET_PLACEHOLDER),
    )

    # Settings-layer probes: these rules live in config/settings/production.py
    # and are the ones earlier manual attempts tripped over.
    def settings_case(overrides: dict[str, str | None]) -> tuple[bool, str]:
        import subprocess

        env = dict(os.environ)
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import django; django.setup()",
            ],
            env=env,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT / "apps" / "backend"),
        )
        message = (proc.stderr or proc.stdout or "").strip().splitlines()
        return proc.returncode == 0, (message[-1] if message else "")

    def expect_settings_reject(label: str, overrides: dict[str, str | None]) -> None:
        ok, detail = settings_case(overrides)
        checks.append(
            (
                ("REJECTED" if not ok else "NOT REJECTED")
                + f" {label}"
                + ("" if not ok else " (settings loaded)"),
                not ok,
            )
        )

    def expect_settings_accept(label: str) -> None:
        ok, detail = settings_case({})
        checks.append((f"{'ACCEPTED' if ok else 'WRONGLY REJECTED'} {label}", ok))
        if not ok:
            print(f"    detail: {detail}")

    expect_settings_accept("production settings load with the documented env contract")
    expect_settings_reject("ADMIN_URL_PATH='admin'", {"ADMIN_URL_PATH": "admin"})
    expect_settings_reject(
        "DJANGO_ALLOWED_HOSTS='.example.com'", {"DJANGO_ALLOWED_HOSTS": ".example.com"}
    )
    expect_settings_reject(
        "CSRF_TRUSTED_ORIGINS=http://example.com",
        {"CSRF_TRUSTED_ORIGINS": "http://example.com"},
    )
    expect_settings_reject("DJANGO_DEBUG=true", {"DJANGO_DEBUG": "true"})
    expect_settings_reject(
        "missing DJANGO_OWNER_USERNAME", {"DJANGO_OWNER_USERNAME": None}
    )
    expect_settings_reject("missing DJANGO_SUPERUSER_1", {"DJANGO_SUPERUSER_1": None})
    expect_settings_reject(
        "duplicate superuser handles", {"DJANGO_SUPERUSER_2": "superuser_one"}
    )
    expect_settings_reject("missing STEAM_WEB_API_KEY", {"STEAM_WEB_API_KEY": None})
    expect_settings_reject("missing RECAPTCHA_SITE_KEY", {"RECAPTCHA_SITE_KEY": None})
    expect_settings_reject("blank DATABASE_URL", {"DATABASE_URL": ""})

    print("─" * 68)
    print("Validator probes (config/security.py, config/admin.py)")
    print("─" * 68)
    for entry in checks:
        label, ok = entry[0], entry[1]
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    failed = [label for label, ok in checks if not ok]
    print("─" * 68)
    print(f"{len(checks) - len(failed)}/{len(checks)} probes passed")
    return 1 if failed else 0


if __name__ == "__main__":
    if "--probe" in sys.argv:
        sys.exit(probe_expected_failures())
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - surface the exact validator failure
        from django.core.exceptions import ImproperlyConfigured

        if isinstance(exc, ImproperlyConfigured):
            print(f"\nSETTINGS VALIDATION FAILED: {exc}", file=sys.stderr)
        else:
            import traceback

            traceback.print_exc()
        sys.exit(1)
