"""Authentication signal receivers — SBGC-186.

Connects the ``user_logged_in`` signal to the two real-time security hooks:

- buffer the daily login for the nightly batch;
- synchronously restore a dormant designated superuser and demote temporary
  moderators within an atomic transaction.
"""

from __future__ import annotations

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from security.tracking import record_user_login_activity


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs) -> None:  # noqa: ANN001
    record_user_login_activity(user.pk)

    # Imported lazily to avoid a module-load cycle with security.tracking.
    from security.superuser_rotation import restore_dormant_superuser_if_applicable

    restore_dormant_superuser_if_applicable(user)
