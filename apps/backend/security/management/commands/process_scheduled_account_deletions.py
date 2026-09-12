"""
``process_scheduled_account_deletions`` management command — SBGC-223.

Executes the three-hour hard purge for every permaban whose ``scheduled_for``
window has elapsed: dispatches the reporter gratitude notices, cascades the
account deletion, and marks the schedule executed.  Intended to run every five
minutes from a scheduler.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from security.emails import send_reporter_gratitude_email
from security.models import ScheduledAccountDeletion, UserReport


class Command(BaseCommand):
    help = "Execute due permanent-ban account deletions (T + 3 hours)."

    def handle(self, **options):
        due = list(
            ScheduledAccountDeletion.objects.filter(
                executed=False,
                scheduled_for__lte=timezone.now(),
            ).select_related("user")
        )

        processed = 0
        for record in due:
            with transaction.atomic():
                user = record.user
                reporter_emails = {
                    email
                    for email in UserReport.objects.filter(
                        offending_user=user
                    ).values_list("reporting_user__email", flat=True)
                    if email
                }
                for email in reporter_emails:
                    send_reporter_gratitude_email(recipient_email=email)

                record.executed = True
                record.save(update_fields=["executed"])
                # Cascade-deletes the user's profile, submissions, and this
                # schedule row; the pre-delete `executed` write is retained only
                # for the (unlikely) partial-failure window.
                user.delete()

            processed += 1
            self.stdout.write(self.style.SUCCESS(f"Purged account for {record.pk}."))

        self.stdout.write(
            self.style.SUCCESS(f"{processed} scheduled deletion(s) processed.")
        )
