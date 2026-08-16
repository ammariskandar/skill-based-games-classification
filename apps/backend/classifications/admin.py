"""
Django Admin registration for editorial classification submissions and
editorial Group role metadata — SBGC-46 / SBGC-63.
"""

import json

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    EditorialGroupProfile,
    RewardProfile,
)
from classifications.roles import BASE_WEIGHTS, EditorialRole
from classifications.services.submissions import (
    EditorialRoleError,
    resolve_editorial_role,
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


class EditorialClassificationAdminForm(forms.ModelForm):
    class Media:
        js = ("classifications/admin_role_preview.js",)

    class Meta:
        model = EditorialClassification
        fields = [
            "game",
            "submitted_by",
            "submitted_role",
            "submitted_base_weight",
            "notes",
            "updated_by",
        ]

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

    def clean(self):
        cleaned = super().clean() or {}
        game = cleaned.get("game")
        submitted_by = cleaned.get("submitted_by")
        if submitted_by is None and self.request is not None:
            submitted_by = self.request.user
        if game and submitted_by and getattr(submitted_by, "pk", None):
            qs = EditorialClassification.objects.filter(
                game=game, submitted_by=submitted_by
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                if self.request is not None and submitted_by.pk == self.request.user.pk:
                    msg = "You have already submitted scores for this game."
                else:
                    msg = "This user has already submitted scores for this game."
                self.add_error("submitted_by", msg)
        return cleaned


@admin.register(EditorialClassification)
class EditorialClassificationAdmin(admin.ModelAdmin):
    form = EditorialClassificationAdminForm

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
    )

    list_select_related = (
        "game",
        "submitted_by",
        "updated_by",
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly.extend(
                (
                    "game",
                    "submitted_by",
                    "submitted_role",
                    "submitted_base_weight",
                )
            )
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

    def get_form_kwargs(self, request, obj=None, **kwargs):
        form_kwargs = admin.ModelAdmin.get_form_kwargs(  # type: ignore[reportAttributeAccessIssue]
            self, request, obj, **kwargs
        )
        form_kwargs["request"] = request
        return form_kwargs

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        if obj is None:
            is_superuser = getattr(request.user, "is_superuser", False)
            submitter = request.user
            role = resolve_editorial_role(submitter)

            role_map = {}
            for u in User.objects.filter(is_active=True):
                try:
                    resolved = resolve_editorial_role(u)
                except EditorialRoleError:
                    resolved = EditorialRole.COMMUNITY
                role_map[str(u.pk)] = {
                    "role": resolved,
                    "weight": str(BASE_WEIGHTS[resolved]),
                }

            if "submitted_by" in form.base_fields:
                form.base_fields["submitted_by"].widget.attrs["data-role-map"] = (
                    json.dumps(role_map)
                )
                if not is_superuser:
                    form.base_fields["submitted_by"].disabled = True
                    form.base_fields["submitted_by"].required = False
                    form.base_fields["submitted_by"].initial = submitter
                else:
                    form.base_fields["submitted_by"].required = False

            if "submitted_role" in form.base_fields:
                form.base_fields["submitted_role"].disabled = True
                form.base_fields["submitted_role"].initial = role
                form.base_fields[
                    "submitted_role"
                ].help_text = (
                    "The submitter's role at the time this submission is saved."
                )
            if "submitted_base_weight" in form.base_fields:
                form.base_fields["submitted_base_weight"].disabled = True
                form.base_fields["submitted_base_weight"].initial = BASE_WEIGHTS[role]
        return form

    def save_model(self, request, obj, form, change):
        """Record operator, default submitter, and snapshot role provenance."""
        obj.updated_by = request.user
        if not getattr(request.user, "is_superuser", False):
            obj.submitted_by = request.user
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

    def changelist_view(self, request, extra_context=None):
        superusers = list(
            User.objects.filter(is_superuser=True, is_active=True)
            .order_by("username")
            .values_list("username", flat=True)
        )
        names = ", ".join(superusers) if superusers else "none"
        self.message_user(
            request,
            f"Superuser — system-defined, read-only. Current superusers: {names}. "
            "Moderator / Community Leader / Community roles are managed through "
            "the Groups below.",
            level=messages.INFO,
        )
        return super().changelist_view(request, extra_context=extra_context)


admin.site.unregister(Group)
admin.site.register(Group, EditorialGroupAdmin)
