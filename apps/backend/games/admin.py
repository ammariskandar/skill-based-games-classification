"""
Django Admin registration for the Game model — SBGC-45.
"""

from django.contrib import admin

from games.models import Game


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "source_type",
        "external_id",
        "content_type",
        "listing_status",
        "updated_at",
    )

    list_filter = (
        "source_type",
        "content_type",
        "listing_status",
    )

    search_fields = (
        "name",
        "slug",
        "external_id",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    readonly_fields = (
        "display_identity",
        "created_at",
        "updated_at",
    )
