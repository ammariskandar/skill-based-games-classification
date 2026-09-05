"""Granular admin action & anti-sabotage throttling — SBGC-106.

Writes are paced according to risk class (high-risk security actions vs.
routine editorial saves) and deletes are quota-limited per non-superuser.
The blocking check runs in ``changeform_view`` *before* form processing so a
throttled save never reaches ``save_model``/``save_related`` (which would
otherwise persist inlines and log a phantom change).  Pacing is recorded in
``save_model`` only after a successful save.
"""

from __future__ import annotations

import time

from django.conf import settings
from django.contrib import admin, messages
from django.core.cache import cache
from django.http import HttpResponseRedirect

HIGH_RISK_COOLDOWN = 30  # seconds between sensitive writes
EDITORIAL_BURST_LIMIT = 10  # editorial saves per minute
EDITORIAL_WINDOW = 60  # seconds
DELETE_LIMIT = 5
DELETE_COOLDOWN_WINDOW = 300  # 5 minutes


class HardenedModelAdminMixin:
    """Base ModelAdmin mixin enforcing write pacing and delete quotas."""

    is_high_risk = False

    # -- write pacing ---------------------------------------------------------

    def _write_pacing_key(self, user_id: int) -> str:
        if self.is_high_risk:
            return f"admin_write_pacing_high:{user_id}"
        return f"admin_write_editorial:{user_id}"

    def _check_write_pacing(self, request) -> bool:
        user_id = getattr(request.user, "pk", None)
        if user_id is None:
            return True

        if self.is_high_risk:
            key = f"admin_write_pacing_high:{user_id}"
            last_action = cache.get(key)
            if last_action and (time.time() - last_action < HIGH_RISK_COOLDOWN):
                remaining = max(
                    1, int(HIGH_RISK_COOLDOWN - (time.time() - last_action))
                )
                messages.error(
                    request,
                    "You are moving too fast. Please wait "
                    f"{remaining} seconds between administrative security actions.",
                )
                return False
            return True

        key = f"admin_write_editorial:{user_id}"
        count = cache.get(key, 0)
        if count >= EDITORIAL_BURST_LIMIT:
            messages.error(
                request,
                "Editorial rate limit reached (10 saves/min). "
                "Please pause briefly before submitting.",
            )
            return False
        return True

    def _record_write_pacing(self, request) -> None:
        user_id = getattr(request.user, "pk", None)
        if user_id is None:
            return

        if self.is_high_risk:
            cache.set(
                f"admin_write_pacing_high:{user_id}",
                time.time(),
                timeout=HIGH_RISK_COOLDOWN,
            )
            return

        key = f"admin_write_editorial:{user_id}"
        count = cache.get(key, 0)
        if count == 0:
            cache.set(key, 1, timeout=EDITORIAL_WINDOW)
        else:
            cache.incr(key)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if (
            getattr(settings, "ADMIN_THROTTLING_ENABLED", True)
            and request.method == "POST"
            and not self._check_write_pacing(request)
        ):
            return HttpResponseRedirect(request.path)
        return super().changeform_view(  # type: ignore[reportAttributeAccessIssue]
            request, object_id, form_url, extra_context
        )

    def save_model(self, request, obj, form, change):
        if getattr(settings, "ADMIN_THROTTLING_ENABLED", True):
            self._record_write_pacing(request)
        super().save_model(request, obj, form, change)  # type: ignore[reportAttributeAccessIssue]

    # -- delete quotas --------------------------------------------------------

    def _check_delete_quota(self, request, count: int = 1) -> bool:
        if getattr(request.user, "is_superuser", False):
            return True

        user_id = getattr(request.user, "pk", None)
        if user_id is None:
            return True

        key = f"admin_delete_count:{user_id}"
        cooling_key = f"admin_delete_cooling:{user_id}"

        if cache.get(cooling_key):
            messages.error(
                request,
                "Delete action blocked: A 5-minute cooling-off period is active "
                "due to excessive deletions.",
            )
            return False

        current_deletes = cache.get(key, 0)
        if current_deletes + count > DELETE_LIMIT:
            cache.set(cooling_key, True, timeout=DELETE_COOLDOWN_WINDOW)
            cache.delete(key)
            messages.error(
                request,
                "Delete threshold exceeded (>5 records). A 5-minute cooling-off "
                "period has been applied to protect catalog integrity.",
            )
            return False

        if current_deletes == 0:
            cache.set(key, count, timeout=DELETE_COOLDOWN_WINDOW)
        else:
            cache.incr(key, count)
        return True

    def delete_model(self, request, obj):
        if getattr(
            settings, "ADMIN_THROTTLING_ENABLED", True
        ) and not self._check_delete_quota(request):
            return
        super().delete_model(request, obj)  # type: ignore[reportAttributeAccessIssue]

    def delete_queryset(self, request, queryset):
        if getattr(
            settings, "ADMIN_THROTTLING_ENABLED", True
        ) and not self._check_delete_quota(request, count=queryset.count()):
            return
        super().delete_queryset(request, queryset)  # type: ignore[reportAttributeAccessIssue]


class HardenedModelAdmin(HardenedModelAdminMixin, admin.ModelAdmin):
    """Concrete hardened ModelAdmin for routine editorial models."""
