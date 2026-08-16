"""
Django Admin registration for editorial classification submissions and
editorial Group role metadata — SBGC-46 / SBGC-63.
"""

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    EditorialGroupProfile,
    RewardProfile,
)
from classifications.roles import BASE_WEIGHTS
from classifications.services.submissions import resolve_editorial_role


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
        if form.instance.pk is not None:
            return False
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
        "submitted_by",
        "submitted_role",
        "challenge_summary",
        "reward_summary",
        "updated_by",
        "updated_at",
    )

    search_fields = (
        "game__name",
        "game__slug",
        "game__external_id",
        "submitted_by__username",
        "updated_by__username",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "updated_by",
        "submitted_role",
        "submitted_base_weight",
    )

    list_select_related = (
        "game",
        "submitted_by",
        "updated_by",
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly.extend(("game", "submitted_by"))
        return readonly

    @admin.display(description="Challenge")
    def challenge_summary(self, obj):
        profile = getattr(obj, "challenge_profile", None)
        if profile is None:
            return "—"
        return (
            f"{profile.micro_score} / {profile.mystiko_score} / {profile.macro_score}"
        )

    @admin.display(description="Reward")
    def reward_summary(self, obj):
        profile = getattr(obj, "reward_profile", None)
        if profile is None:
            return "—"
        return (
            f"{profile.micro_score} / {profile.mystiko_score} / {profile.macro_score}"
        )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        # submitted_by defaults to the operator when not explicitly chosen.
        if "submitted_by" in form.base_fields:
            form.base_fields["submitted_by"].required = False
        return form

    def save_model(self, request, obj, form, change):
        """Record operator, default submitter, and snapshot role provenance."""
        obj.updated_by = request.user
        if obj.submitted_by_id is None:
            obj.submitted_by = request.user
        if not change:
            role = resolve_editorial_role(obj.submitted_by)  # type: ignore[reportArgumentType]
            obj.submitted_role = role
            obj.submitted_base_weight = BASE_WEIGHTS[role]
        super().save_model(request, obj, form, change)


class EditorialGroupProfileInline(admin.StackedInline):
    model = EditorialGroupProfile
    extra = 0
    max_num = 1
    verbose_name = "Editorial role"
    verbose_name_plural = "Editorial role"


class EditorialGroupAdmin(GroupAdmin):
    inlines = [EditorialGroupProfileInline]


admin.site.unregister(Group)
admin.site.register(Group, EditorialGroupAdmin)
