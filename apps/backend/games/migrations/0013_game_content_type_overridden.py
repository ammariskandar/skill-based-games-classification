"""
Add Game.content_type_overridden — SBGC-96.

Existing records default to Steam-managed (False); there is no historical
provenance to backfill from, so no data migration is needed.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0012_game_manual_capsule_url_game_manual_hero_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="content_type_overridden",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "True = content type is human-owned; Steam refresh preserves it. "
                    "False = Steam-managed (Steam Games only)."
                ),
            ),
        ),
    ]
