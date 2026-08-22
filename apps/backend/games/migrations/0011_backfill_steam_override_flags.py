"""
SBGC-188 — backfill Steam override flags from pre-existing manual metadata.

Existing Steam Games may already carry manually-entered metadata from before
SBGC-188, so we must not assume those values came from Steam.  A non-empty
canonical value is conservatively treated as human-owned (override = True);
empty/blank values remain Steam-managed (override = False) so the next refresh
can populate them.

Deterministic and offline — never contacts Steam, never backfills from network.
"""

from django.db import migrations


def backfill_steam_overrides(apps, schema_editor):
    Game = apps.get_model("games", "Game")

    for game in Game.objects.filter(source_type="steam"):
        updates = {}
        if game.description:
            updates["description_overridden"] = True
        if game.developer:
            updates["developer_overridden"] = True
        if game.release_date is not None:
            updates["release_date_overridden"] = True
        if updates:
            Game.objects.filter(pk=game.pk).update(**updates)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        (
            "games",
            "0010_game_description_and_steam_override_flags",
        ),
    ]

    operations = [
        migrations.RunPython(backfill_steam_overrides, noop),
    ]
