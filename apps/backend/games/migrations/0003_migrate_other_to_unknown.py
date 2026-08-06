"""SBGC-48 — migrate legacy ``other`` content-type rows to ``unknown``."""

from django.db import migrations


def _other_to_unknown(apps, schema_editor):
    Game = apps.get_model("games", "Game")
    updated = Game.objects.filter(content_type="other").update(content_type="unknown")
    # No-op if zero rows — safe to call repeatedly.


def _unknown_to_other(apps, schema_editor):
    Game = apps.get_model("games", "Game")
    updated = Game.objects.filter(content_type="unknown").update(content_type="other")
    # Lossy for legitimate Unknown records created after forward migration.
    # This is acceptable because the project has not been deployed.


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0002_alter_game_content_type"),
    ]

    operations = [
        migrations.RunPython(
            _other_to_unknown,
            _unknown_to_other,
        ),
    ]
