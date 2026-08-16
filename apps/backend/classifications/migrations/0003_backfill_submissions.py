# Generated manually for SBGC-63.

from decimal import Decimal

from django.db import migrations


def backfill_submitted_by(apps, schema_editor):
    EditorialClassification = apps.get_model(
        "classifications", "EditorialClassification"
    )

    for submission in EditorialClassification.objects.all().iterator():
        if submission.submitted_by_id is None and submission.updated_by_id is not None:
            submission.submitted_by_id = submission.updated_by_id

        # Historical rows predate the role model.  Use the safest
        # deterministic provenance: superuser if the submitter is one,
        # otherwise the Community statistical role.  This is a migration
        # default, not a guess about historical moderator/community-leader
        # status.
        user = submission.submitted_by
        if user is not None and user.is_superuser:
            submission.submitted_role = "superuser"
            submission.submitted_base_weight = Decimal("1.00")
        else:
            submission.submitted_role = "community"
            submission.submitted_base_weight = Decimal("0.20")

        submission.save(
            update_fields=[
                "submitted_by",
                "submitted_role",
                "submitted_base_weight",
            ]
        )


def reverse_backfill(apps, schema_editor):
    # submitted_by is cleared on reverse; no other reverse behavior needed.
    EditorialClassification = apps.get_model(
        "classifications", "EditorialClassification"
    )
    EditorialClassification.objects.update(submitted_by=None)


class Migration(migrations.Migration):

    dependencies = [
        ("classifications", "0002_editorialgroupprofile_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_submitted_by, reverse_code=reverse_backfill),
    ]
