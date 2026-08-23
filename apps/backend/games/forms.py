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

    # Form-only "resume Steam sync" controls (SBGC-188).  These are not model
    # fields — ``GameAdmin.save_model`` reads them to clear the per-field
    # override flags.  They are hidden for Manual Games and new records.
    _RESUME_HELP = "Clear the override; the next Steam refresh repopulates this field."
    resume_release_date = forms.BooleanField(
        required=False,
        label="Resume Steam sync for release date",
        help_text=_RESUME_HELP,
    )
    resume_developer = forms.BooleanField(
        required=False,
        label="Resume Steam sync for developer",
        help_text=_RESUME_HELP,
    )
    resume_description = forms.BooleanField(
        required=False,
        label="Resume Steam sync for description",
        help_text=_RESUME_HELP,
    )

    STEAM_RESUME_FIELDS = (
        "resume_release_date",
        "resume_developer",
        "resume_description",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance
        if instance is None or not instance.is_steam:
            for name in self.STEAM_RESUME_FIELDS:
                self.fields.pop(name, None)
            # Manual Games have no Steam source underneath — no override wording.
            self.fields["manual_image_url"].help_text = "Optional general/header image."
            self.fields["manual_hero_url"].help_text = "Optional wide background image."
            self.fields[
                "manual_capsule_url"
            ].help_text = "Optional portrait key-art image."
        else:
            self.fields[
                "manual_image_url"
            ].help_text = "Overrides the Steam Header image when supplied."
            self.fields[
                "manual_hero_url"
            ].help_text = "Overrides the Steam Library Hero when supplied."
            self.fields[
                "manual_capsule_url"
            ].help_text = "Overrides the Steam Library Capsule when supplied."

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
            "description",
            "manual_image_url",
            "manual_hero_url",
            "manual_capsule_url",
            "manual_website_url",
            "steam_image_url",
            "last_steam_refresh_at",
        ]
