"""Superuser inactivity rotation engine — SBGC-186.

Implements the dual-superuser quota lifecycle:

- The environment names exactly two designated superusers
  (``DJANGO_SUPERUSER_1`` / ``DJANGO_SUPERUSER_2``), separate from the exempt
  ``DJANGO_OWNER_USERNAME``.
- The nightly command flushes buffered daily logins and demotes any designated
  superuser whose latest login is older than ``SUPERUSER_INACTIVITY_DAYS``,
  promoting the top moderator (random tie-break) to cover the gap.
- When a dormant designated superuser logs in again, the synchronous signal
  handler atomically demotes every temporary superuser and restores the
  returning account, so the non-owner superuser count never exceeds two.
"""

from __future__ import annotations

import logging
import random
from datetime import date, timedelta

from authentication.models import UserSecurityProfile
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.db import transaction
from django.db.models.functions import Coalesce

from security.notifications import (
    dispatch_moderator_shortage_email,
    dispatch_superuser_promotion_email,
    dispatch_superuser_reversion_email,
)
from security.tracking import LOGIN_BUFFER_KEY

logger = logging.getLogger("django.security")


def get_designated_superusers() -> list[str]:
    """Return the non-empty designated superuser usernames (max two)."""
    return [
        username
        for username in (settings.DJANGO_SUPERUSER_1, settings.DJANGO_SUPERUSER_2)
        if username
    ]


def flush_login_buffer_for_date(day: date) -> int:
    """Commit a single day's buffered logins to ``UserSecurityProfile``.

    Returns the number of distinct users whose ``daily_login_count`` was
    incremented.  Uses ``select_for_update`` so concurrent flush runs cannot
    double-count a day for the same user.
    """
    buffer_key = LOGIN_BUFFER_KEY.format(date_str=day.isoformat())
    user_ids = set(cache.get(buffer_key, []) or [])
    if not user_ids:
        return 0

    flushed = 0
    with transaction.atomic():
        for user_id in user_ids:
            profile, _ = UserSecurityProfile.objects.select_for_update().get_or_create(
                user_id=user_id
            )
            if profile.last_login_date != day:
                profile.last_login_date = day
                profile.daily_login_count += 1
                profile.save(update_fields=["last_login_date", "daily_login_count"])
                flushed += 1
    cache.delete(buffer_key)
    return flushed


def evaluate_designated_superusers(today: date) -> list[User]:
    """Demote inactive designated superusers and promote replacements.

    Returns the list of designated superusers that were demoted this run.
    """
    threshold = today - timedelta(days=settings.SUPERUSER_INACTIVITY_DAYS)
    demoted: list[User] = []

    for username in get_designated_superusers():
        user = (
            User.objects.filter(username=username)
            .select_related("security_profile")
            .first()
        )
        if user is None or not user.is_superuser:
            continue

        profile, _ = UserSecurityProfile.objects.get_or_create(user=user)
        is_inactive = (
            profile.last_login_date is None or profile.last_login_date < threshold
        )
        if is_inactive:
            promote_moderator_for_inactive_superuser(user, profile)
            demoted.append(user)

    return demoted


def promote_moderator_for_inactive_superuser(
    inactive_superuser: User, profile: UserSecurityProfile
) -> str:
    """Demote *inactive_superuser* and promote the top eligible moderator.

    Returns ``"promoted"``, ``"no_group"``, or ``"no_candidates"``.
    """
    with transaction.atomic():
        inactive_superuser.is_superuser = False
        inactive_superuser.save(update_fields=["is_superuser"])
        profile.is_dormant_superuser = True
        profile.save(update_fields=["is_dormant_superuser"])

        mod_group = Group.objects.filter(name=settings.MODERATOR_GROUP_NAME).first()
        if mod_group is None:
            dispatch_moderator_shortage_email(inactive_superuser)
            return "no_group"

        candidates = list(
            User.objects.filter(
                groups=mod_group,
                is_active=True,
                is_superuser=False,
            )
            .annotate(login_count=Coalesce("security_profile__daily_login_count", 0))
            .order_by("-login_count", "id")
        )
        if not candidates:
            dispatch_moderator_shortage_email(inactive_superuser)
            return "no_candidates"

        top_count = getattr(candidates[0], "login_count", 0)
        top_tier = [
            candidate
            for candidate in candidates
            if getattr(candidate, "login_count", 0) == top_count
        ]
        chosen = random.choice(top_tier)

        chosen.is_superuser = True
        chosen.save(update_fields=["is_superuser"])
        mod_profile, _ = UserSecurityProfile.objects.get_or_create(user=chosen)
        mod_profile.is_temporary_superuser = True
        mod_profile.save(update_fields=["is_temporary_superuser"])

        dispatch_superuser_promotion_email(chosen, inactive_superuser)
        logger.warning(
            "Promoted moderator %s to temporary superuser (inactive: %s)",
            chosen.username,
            inactive_superuser.username,
        )
        return "promoted"


def restore_dormant_superuser_if_applicable(user: User) -> bool:
    """Restore a returning dormant designated superuser, demoting temps.

    Runs synchronously inside the ``user_logged_in`` signal handler and returns
    ``True`` when a restoration occurred.  The demotion + restoration happen in
    a single atomic transaction so the non-owner superuser count never exceeds
    the dual-superuser quota.
    """
    if user.username not in get_designated_superusers():
        return False

    profile = getattr(user, "security_profile", None)
    if profile is None or not profile.is_dormant_superuser:
        return False

    demoted: list[User] = []
    with transaction.atomic():
        temp_moderators = list(
            User.objects.filter(
                security_profile__is_temporary_superuser=True
            ).select_for_update()
        )
        for moderator in temp_moderators:
            moderator.is_superuser = False
            moderator.save(update_fields=["is_superuser"])
            moderator.security_profile.is_temporary_superuser = False  # type: ignore[reportAttributeAccessIssue]
            moderator.security_profile.save(  # type: ignore[reportAttributeAccessIssue]
                update_fields=["is_temporary_superuser"]
            )
            demoted.append(moderator)

        user.is_superuser = True
        user.save(update_fields=["is_superuser"])
        profile.is_dormant_superuser = False
        profile.last_login_date = date.today()
        profile.save(update_fields=["is_dormant_superuser", "last_login_date"])

    for moderator in demoted:
        dispatch_superuser_reversion_email(moderator, user)
        logger.warning(
            "Reverted temporary superuser %s (restored %s)",
            moderator.username,
            user.username,
        )
    return True
