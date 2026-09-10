"""
Bidirectional migration verification — SBGC-177.

Exercises the real migration graph through Django's ``MigrationExecutor``:
roll the questionnaire migrations back to the pre-SBGC-175 schema and then
forward to the latest revision.  Any non-reversible operation (or a dangling
catalog object) surfaces here.
"""

from __future__ import annotations

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

LATEST_MIGRATION = "0011_questionnaire_db_constraints"
QUESTIONNAIRE_MIGRATION = (
    "0010_usergamescoresubmission_source_questionnaireresult_and_more"
)
PREVIOUS_MIGRATION = "0009_usergamescoresubmission"


class MigrationReversibilityTests(TransactionTestCase):
    def tearDown(self):
        # Restore the latest schema even if an assertion failed mid-test.
        call_command("migrate", "classifications", verbosity=0)
        super().tearDown()

    def test_questionnaire_migrations_are_reversible(self):
        executor = MigrationExecutor(connection)
        applied = set(executor.loader.applied_migrations)
        self.assertIn(("classifications", LATEST_MIGRATION), applied)

        # Roll back to the pre-questionnaire schema (undoes 0010 and 0011).
        executor.migrate([("classifications", PREVIOUS_MIGRATION)])
        executor = MigrationExecutor(connection)
        rolled_back = set(executor.loader.applied_migrations)
        self.assertNotIn(("classifications", QUESTIONNAIRE_MIGRATION), rolled_back)
        self.assertNotIn(("classifications", LATEST_MIGRATION), rolled_back)

        # Roll forward to the latest schema.
        call_command("migrate", "classifications", verbosity=0)
        executor = MigrationExecutor(connection)
        forward = set(executor.loader.applied_migrations)
        self.assertIn(("classifications", QUESTIONNAIRE_MIGRATION), forward)
        self.assertIn(("classifications", LATEST_MIGRATION), forward)
