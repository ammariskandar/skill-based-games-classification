"""
API URL composition package — SBGC-38.

This is a routing composition module, not a Django application.
It is not registered in INSTALLED_APPS.

Mounts the versioned v1 NinjaAPI and provides a catch-all fallback
for unknown API paths that returns the standardised error envelope.
"""

from django.http import JsonResponse
from django.urls import path, re_path

from api.v1 import api as v1_api

urlpatterns = [
    path("", v1_api.urls),
    # Catch-all for unknown API paths under /api/v1/.
    # Must appear after Ninja patterns so it does not intercept
    # the root, docs, OpenAPI, or future router operations.
    re_path(
        r"^(?P<path>.+)$",
        lambda request, path: JsonResponse(
            {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "API resource not found.",
                    "details": [],
                }
            },
            status=404,
        ),
    ),
]
