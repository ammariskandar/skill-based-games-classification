"""
Game Admin/ModelForm — SBGC-62.

Provides the manual release-date input formats for the Admin form while
keeping the underlying model field a plain ``DateField``.
"""

from __future__ import annotations

from django import forms

from games.models import Game

MANUAL_RELEASE_DATE_INPUT_FORMATS = [
    "%Y-%m-%d",  # 2026-08-16
    "%d-%m-%Y",  # 16-08-2026
    "%d/%m/%Y",  # 16/08/2026
    "%Y/%m/%d",  # 2026/08/16
]

MANUAL_RELEASE_DATE_HELP_TEXT = (
    "Release date for manually managed game metadata. Accepted formats: "
    "YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, or YYYY/MM/DD."
)


class GameForm(forms.ModelForm):
    """ModelForm used by ``GameAdmin`` for create/edit."""

    release_date = forms.DateField(
        required=False,
        input_formats=MANUAL_RELEASE_DATE_INPUT_FORMATS,
        help_text=MANUAL_RELEASE_DATE_HELP_TEXT,
    )

    class Meta:
        model = Game
        fields = [
            "source_type",
            "external_id",
            "name",
            "slug",
            "content_type",
            "listing_status",
            "release_date",
            "developer",
            "manual_description",
            "manual_image_url",
            "manual_website_url",
            "steam_image_url",
            "last_steam_refresh_at",
        ]
