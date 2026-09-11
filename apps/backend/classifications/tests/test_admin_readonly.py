"""
Derived-classification Admin read-only tests — SBGC-66 (section 12).

Calculated scores, confidence, provenance, and method results must be
read-only: no add/change/delete through the Admin, and every model field
must be in ``readonly_fields``.
"""

from __future__ import annotations

from unittest import mock

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from classifications.models import (
    BoundaryCalibration,
    CalculationEpoch,
    ClassificationSnapshot,
)

READONLY_MODELS = (ClassificationSnapshot, CalculationEpoch, BoundaryCalibration)


class DerivedAdminReadOnlyTests(SimpleTestCase):
    def _admin_class(self, model):
        model_admin = admin.site._registry.get(model)
        assert model_admin is not None, f"{model.__name__} not registered"
        return model_admin

    def test_readonly_fields_cover_every_model_field(self):
        for model in READONLY_MODELS:
            model_admin = self._admin_class(model)
            field_names = {f.name for f in model._meta.fields}
            readonly = set(model_admin.readonly_fields)
            missing = field_names - readonly
            self.assertFalse(
                missing,
                f"{model.__name__} fields missing from readonly_fields: {missing}",
            )

    def test_no_add_permission(self):
        request = RequestFactory().get("/")
        for model in READONLY_MODELS:
            model_admin = self._admin_class(model)
            self.assertFalse(model_admin.has_add_permission(request))

    def test_no_change_permission(self):
        request = RequestFactory().get("/")
        for model in READONLY_MODELS:
            model_admin = self._admin_class(model)
            self.assertFalse(model_admin.has_change_permission(request))

    def test_no_delete_permission(self):
        request = RequestFactory().get("/")
        for model in READONLY_MODELS:
            model_admin = self._admin_class(model)
            self.assertFalse(model_admin.has_delete_permission(request))


class CalculationEpochAdminTriggerTests(TestCase):
    """Regression coverage for the changelist delta-recalculation trigger.

    The custom URL must be registered under the ``classifications_calculationepoch_``
    admin prefix the changelist template reverses; a bare
    ``calculationepoch_trigger_delta`` name raises ``NoReverseMatch`` and 500s
    the whole changelist (SBGC-174 follow-up).
    """

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="epoch-trigger-admin", password="pw"
        )
        cls.member = User.objects.create_user(
            username="epoch-trigger-member", password="pw"
        )

    def test_trigger_url_reverses_under_admin_namespace(self):
        url = reverse("admin:classifications_calculationepoch_trigger_delta")
        self.assertTrue(url.endswith("/trigger-delta/"))

    def test_changelist_renders_the_trigger_button(self):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("admin:classifications_calculationepoch_changelist")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trigger delta recalculation")

    def test_superuser_trigger_queues_recalculation(self):
        self.client.force_login(self.superuser)
        with mock.patch(
            "classifications.admin.dispatch_delta_recalculation"
        ) as dispatch:
            response = self.client.get(
                reverse("admin:classifications_calculationepoch_trigger_delta")
            )
        self.assertEqual(response.status_code, 302)
        dispatch.assert_called_once()

    def test_non_editorial_member_is_denied(self):
        self.client.force_login(self.member)
        with mock.patch(
            "classifications.admin.dispatch_delta_recalculation"
        ) as dispatch:
            response = self.client.get(
                reverse("admin:classifications_calculationepoch_trigger_delta")
            )
        self.assertEqual(response.status_code, 302)
        dispatch.assert_not_called()
