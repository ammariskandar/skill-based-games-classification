"""
Health-check view — SBGC-43.

Minimal liveness/startup probe.  No database query, no Steam call,
no migration check, no filesystem write, no authentication.
"""

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "HEAD"])
def health(request: HttpRequest) -> JsonResponse:
    """Return a minimal 200 JSON liveness response."""
    return JsonResponse({"status": "ok"})
