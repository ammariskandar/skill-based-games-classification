"""User account security extensions — SBGC-186.

``UserSecurityProfile`` is a one-to-one extension of the auth ``User`` that
tracks the rotation engine's per-user state: the latest distinct calendar day
the user authenticated, a cumulative count of distinct login days, and the two
mutually-exclusive markers that record whether a designated superuser is
dormant or a moderator is temporarily promoted.

Login activity is buffered in cache in real time (``security.tracking``) and
flushed to this table by the nightly management command
``process_daily_logins_and_superuser_rotation``, so repeat logins within a
single calendar day never touch the database synchronously.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models


class UserSecurityProfile(models.Model):
    """Per-user rotation and login-activity state (SBGC-186)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="security_profile",
    )
    last_login_date = models.DateField(
        null=True,
        blank=True,
        help_text="Latest distinct calendar date the user authenticated.",
    )
    daily_login_count = models.PositiveIntegerField(
        default=0,
        help_text="Total distinct daily logins accumulated by this user.",
    )
    is_dormant_superuser = models.BooleanField(
        default=False,
        help_text=(
            "True if an environment-designated superuser was demoted due to inactivity."
        ),
    )
    is_temporary_superuser = models.BooleanField(
        default=False,
        help_text=(
            "True if a moderator was temporarily promoted to cover an "
            "inactive superuser."
        ),
    )

    class Meta:
        db_table = "auth_user_security_profile"
        verbose_name = "User security profile"
        verbose_name_plural = "User security profiles"

    def __str__(self) -> str:
        return f"Security profile {self.pk}"
