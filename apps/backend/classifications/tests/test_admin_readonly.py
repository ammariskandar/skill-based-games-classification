"""
Derived-classification Admin read-only tests — SBGC-66 (section 12).

Calculated scores, confidence, provenance, and method results must be
read-only: no add/change/delete through the Admin, and every model field
must be in ``readonly_fields``.
"""

from __future__ import annotations

from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase

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
