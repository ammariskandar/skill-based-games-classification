"""
Django Admin registration for editorial classifications — SBGC-46.
"""

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    RewardProfile,
)


class _RequiredSingleProfileFormSet(BaseInlineFormSet):
    """Base formset enforcing exactly one active (non-deleted, non-empty) form."""

    profile_label = "Profile"

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        active = self._active_forms()

        if len(active) != 1:
            raise ValidationError(
                f"Exactly one {self.profile_label} profile is required."
            )

    def _active_forms(self):
        """Return submitted forms that are not deleted and not empty extras."""
        result = []
        for form in self.forms:
            if not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE", False):
                continue
            if self._is_empty_extra(form):
                continue
            result.append(form)
        return result

    def _is_empty_extra(self, form):
        """True if *form* is an extra row with no user-supplied data."""
        # An existing instance always counts, even if unchanged.
        if form.instance.pk is not None:
            return False
        # A new form that has any score value counts.
        for name in ("micro_score", "mystiko_score", "macro_score"):
            if form.cleaned_data.get(name) is not None:
                return False
        return True


class ChallengeProfileInlineFormSet(_RequiredSingleProfileFormSet):
    profile_label = "Challenge"


class RewardProfileInlineFormSet(_RequiredSingleProfileFormSet):
    profile_label = "Reward"


class ChallengeProfileInline(admin.StackedInline):
    model = ChallengeProfile
    formset = ChallengeProfileInlineFormSet
    extra = 0
    max_num = 1
    min_num = 1
    can_delete = False
    verbose_name = "Challenge Profile"
    verbose_name_plural = "Challenge Profile"


class RewardProfileInline(admin.StackedInline):
    model = RewardProfile
    formset = RewardProfileInlineFormSet
    extra = 0
    max_num = 1
    min_num = 1
    can_delete = False
    verbose_name = "Reward Profile"
    verbose_name_plural = "Reward Profile"


@admin.register(EditorialClassification)
class EditorialClassificationAdmin(admin.ModelAdmin):
    inlines = [
        ChallengeProfileInline,
        RewardProfileInline,
    ]

    list_display = (
        "game",
        "updated_by",
        "updated_at",
    )

    search_fields = (
        "game__name",
        "game__slug",
        "game__external_id",
        "updated_by__username",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "updated_by",
    )

    list_select_related = (
        "game",
        "updated_by",
    )

    def save_model(self, request, obj, form, change):
        """Assign updated_by from the request before saving."""
        if not change or not obj.updated_by_id:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)
