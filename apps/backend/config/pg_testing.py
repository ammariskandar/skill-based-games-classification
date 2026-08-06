"""
PostgreSQL integration tests — SBGC-52.

Verifies database constraints, indexes, transactions, and migration
behaviour on an isolated PostgreSQL instance.  These tests require
``POSTGRES_TEST_DATABASE_URL`` and the ``config.settings.postgresql_test``
settings module.

Run with::

    POSTGRES_TEST_DATABASE_URL='postgresql://...' \\
    apps/backend/.venv/bin/python manage.py test \\
    games.tests.test_pg_constraints \\
    classifications.tests.test_pg_constraints \\
    --settings=config.settings.postgresql_test \\
    --noinput
"""

from __future__ import annotations

import os
from unittest import SkipTest

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase


def require_postgres_test_url():
    """Fail early if POSTGRES_TEST_DATABASE_URL is not configured."""
    url = os.environ.get("POSTGRES_TEST_DATABASE_URL", "").strip()
    if not url:
        raise ImproperlyConfigured(
            "POSTGRES_TEST_DATABASE_URL is required for PostgreSQL tests."
        )
    return url


class PostgreSQLTestCase(TestCase):
    """Base for tests that must run against a real PostgreSQL database.

    Skips on SQLite so the default test suite remains clean.
    """

    @classmethod
    def setUpClass(cls):
        from django.db import connection

        if connection.vendor != "postgresql":
            raise SkipTest(
                f"PostgreSQL tests require a PostgreSQL database. "
                f"Got vendor {connection.vendor!r}. "
                f"Use --settings=config.settings.postgresql_test."
            )
        super().setUpClass()
