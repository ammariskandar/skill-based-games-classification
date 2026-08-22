"""
Django Admin registration for editorial classification submissions and
editorial Group role metadata — SBGC-46 / SBGC-63 / SBGC-69.
"""

import json

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.shortcuts import redirect
from django.utils import timezone
from games.models import Game

from classifications.calculations.constants import MASTER_VERSION
from classifications.models import (
    BoundaryCalibration,
    CalculationEpoch,
    ChallengeProfile,
    ClassificationSnapshot,
    EditorialClassification,
    EditorialGroupProfile,
    RewardProfile,
)
from classifications.roles import BASE_WEIGHTS
from classifications.services.submissions import (
    EditorialRoleError,
    group_set_has_role_conflict,
    resolve_editorial_role,
)


def _format_integer_profile(value) -> str:
    """Format a ``[micro, macro, mystiko]`` JSON profile for display."""
    if not value or len(value) != 3:
        return "—"
    micro, macro, mystiko = value
    return f"{micro} / {macro} / {mystiko}"


def _method_summary(obj, prefix: str) -> str:
    """Format one method's status plus Challenge/Reward integer profiles."""
    status = getattr(obj, f"{prefix}_status")
    if not status:
        return "—"
    challenge = _format_integer_profile(getattr(obj, f"{prefix}_integer_challenge"))
    reward = _format_integer_profile(getattr(obj, f"{prefix}_integer_reward"))
    return f"{status} · C {challenge} · R {reward}"


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
    readonly_fields = ("total", "dominant_display")
    fields = (
        "micro_score",
        "mystiko_score",
        "macro_score",
        "total",
        "dominant_display",
    )


class RewardProfileInline(admin.StackedInline):
    model = RewardProfile
    formset = RewardProfileInlineFormSet
    extra = 0
    max_num = 1
    min_num = 1
    can_delete = False
    verbose_name = "Reward Profile"
    verbose_name_plural = "Reward Profile"
    readonly_fields = ("total", "dominant_display")
    fields = (
        "micro_score",
        "mystiko_score",
        "macro_score",
        "total",
        "dominant_display",
    )


class EditorialClassificationAdminForm(forms.ModelForm):
    # Set by EditorialClassificationAdmin.get_form() before the form is
    # instantiated.  Django 6.x Admin no longer forwards extra kwargs to the
    # ModelForm constructor, so request cannot be injected via get_form_kwargs.
    request = None

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

    def clean(self):
        cleaned = super().clean() or {}
        game = cleaned.get("game")
        submitted_by = cleaned.get("submitted_by")
        request_user = getattr(getattr(self, "request", None), "user", None)

        # Non-superusers cannot choose the submitter (the field is disabled),
        # so cleaned_data has no submitted_by; fall back to the operator.
        if submitted_by is None:
            submitted_by = request_user

        # Reject a submitter whose editorial role is conflicted.
        if submitted_by is not None and getattr(submitted_by, "pk", None):
            try:
                resolve_editorial_role(submitted_by)
            except EditorialRoleError:
                if request_user is not None and submitted_by.pk == request_user.pk:
                    msg = (
                        "Your account has conflicting classification roles. An "
                        "administrator must remove either the Moderator or "
                        "Community Leader role before you can submit scores."
                    )
                    self.add_error(None, msg)
                else:
                    msg = (
                        "This user has conflicting classification roles and "
                        "cannot be selected as a submitter."
                    )
                    self.add_error("submitted_by", msg)

        if game and submitted_by and getattr(submitted_by, "pk", None):
            qs = EditorialClassification.objects.filter(
                game=game, submitted_by=submitted_by
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                if request_user is not None and submitted_by.pk == request_user.pk:
                    msg = "You have already submitted scores for this game."
                else:
                    msg = "This user has already submitted scores for this game."
                self.add_error("submitted_by", msg)
        return cleaned


@admin.register(EditorialClassification)
class EditorialClassificationAdmin(admin.ModelAdmin):
    form = EditorialClassificationAdminForm

    # A native FK <select> renders its option list full-width, so an absurdly
    # long Game name overflows the viewport when the dropdown is expanded.  The
    # autocomplete widget is searchable and keeps its results bounded.
    autocomplete_fields = ["game"]

    class Media:
        css = {"all": ("classifications/admin.css",)}

    inlines = [
        ChallengeProfileInline,
        RewardProfileInline,
    ]

    list_display = (
        "game",
        "submitted_by",
        "submitted_role",
        "challenge_dominant",
        "challenge_total",
        "reward_dominant",
        "reward_total",
        "updated_at",
    )

    list_filter = (
        "submitted_role",
        "game__source_type",
        "game__content_type",
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
        "challenge_profile",
        "reward_profile",
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

    def has_change_permission(self, request, obj=None):
        """Non-superusers may only edit their own submissions."""
        if not super().has_change_permission(request, obj):
            return False
        if obj is not None and not getattr(request.user, "is_superuser", False):
            return obj.submitted_by_id == request.user.pk
        return True

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        """Deny the Add page to an operator whose editorial role is conflicted."""
        if object_id is None:
            try:
                resolve_editorial_role(request.user)
            except EditorialRoleError:
                messages.error(
                    request,
                    "Your account has conflicting classification roles. An "
                    "administrator must remove either the Moderator or Community "
                    "Leader role before you can submit scores.",
                )
                return redirect(
                    "admin:classifications_editorialclassification_changelist"
                )
        return super().changeform_view(request, object_id, form_url, extra_context)

    @admin.display(description="Challenge dominant")
    def challenge_dominant(self, obj):
        profile = getattr(obj, "challenge_profile", None)
        if profile is None:
            return "—"
        return profile.dominant_display

    @admin.display(description="Challenge total")
    def challenge_total(self, obj):
        profile = getattr(obj, "challenge_profile", None)
        if profile is None:
            return "—"
        return profile.total

    @admin.display(description="Reward dominant")
    def reward_dominant(self, obj):
        profile = getattr(obj, "reward_profile", None)
        if profile is None:
            return "—"
        return profile.dominant_display

    @admin.display(description="Reward total")
    def reward_total(self, obj):
        profile = getattr(obj, "reward_profile", None)
        if profile is None:
            return "—"
        return profile.total

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        # Django 6.x Admin instantiates the ModelForm without forwarding
        # extra kwargs, so expose the request as a class attribute for the
        # form's clean() duplicate/conflict-wording logic.
        form.request = request  # type: ignore[reportAttributeAccessIssue]
        if obj is None:
            is_superuser = getattr(request.user, "is_superuser", False)
            submitter = request.user
            try:
                role = resolve_editorial_role(submitter)
            except EditorialRoleError:
                role = None

            role_map = {}
            for u in User.objects.filter(is_active=True):
                try:
                    resolved = resolve_editorial_role(u)
                    role_map[str(u.pk)] = {
                        "role": resolved,
                        "weight": str(BASE_WEIGHTS[resolved]),
                    }
                except EditorialRoleError:
                    role_map[str(u.pk)] = {"role": None, "weight": None}

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
                form.base_fields["submitted_base_weight"].initial = (
                    BASE_WEIGHTS[role] if role is not None else None
                )
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

    actions = ("recalculate_classifications",)

    @admin.action(description="Recalculate classifications")
    def recalculate_classifications(self, request, queryset):
        """Recalculate the selected Games once each via the canonical engine.

        Duplicate selected submissions for the same Game are deduplicated so
        each affected Game is calculated exactly once.  This is an
        operator-triggered single attempt — it does not replicate the
        scheduled-job retry framework.
        """
        from classifications.services.calculations import run_game_calculation

        game_ids = list(queryset.values_list("game_id", flat=True).distinct())
        if not game_ids:
            self.message_user(request, "No games selected.", level=messages.WARNING)
            return

        cutoff = timezone.now()
        epoch = CalculationEpoch.objects.create(
            epoch_id=f"manual-{cutoff:%Y%m%d-%H%M%S-%f}",
            cutoff_at=cutoff,
            master_version=MASTER_VERSION,
            status=CalculationEpoch.Status.RUNNING,
        )

        ready = non_ready = failed = 0
        for game in Game.objects.filter(pk__in=game_ids):
            try:
                run_game_calculation(
                    game=game,
                    epoch=epoch,
                    attempt_number=1,
                    cutoff_at=cutoff,
                )
            except Exception:
                failed += 1
                continue
            snapshot = ClassificationSnapshot.objects.filter(
                game=game, epoch=epoch, is_current=True
            ).first()
            if snapshot is not None and snapshot.status == "READY":
                ready += 1
            else:
                non_ready += 1
            self.log_change(request, game, "Classification recalculated")

        epoch.status = CalculationEpoch.Status.COMPLETED
        epoch.games_attempted = len(game_ids)
        epoch.games_succeeded = ready + non_ready
        epoch.games_failed = failed
        epoch.completed_at = timezone.now()
        epoch.save(
            update_fields=[
                "status",
                "games_attempted",
                "games_succeeded",
                "games_failed",
                "completed_at",
            ]
        )

        parts = [f"{ready} ready", f"{non_ready} non-ready"]
        if failed:
            parts.append(f"{failed} failed")
        level = messages.SUCCESS if not failed else messages.WARNING
        self.message_user(
            request,
            f"Recalculation complete: {', '.join(parts)}.",
            level=level,
        )


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


class EditorialUserChangeForm(BaseUserChangeForm):
    def clean_groups(self):
        groups = self.cleaned_data.get("groups")
        if groups is not None and group_set_has_role_conflict(groups):
            raise ValidationError(
                "This user cannot belong to both Moderator and Community "
                "Leader classification roles."
            )
        return groups


class EditorialUserAdmin(BaseUserAdmin):
    form = EditorialUserChangeForm


admin.site.unregister(User)
admin.site.register(User, EditorialUserAdmin)


# ---------------------------------------------------------------------------
# Derived-classification read-only inspection — SBGC-65
#
# Calculated scores, confidence, and provenance are mathematical outputs.
# They are readonly: no admin, superuser, or form may edit them.
# ---------------------------------------------------------------------------


@admin.register(ClassificationSnapshot)
class ClassificationSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "game",
        "status",
        "regime",
        "validated_count",
        "final_challenge",
        "final_reward",
        "confidence_final",
        "confidence_label",
        "calculated_at",
        "is_current",
    )
    list_filter = ("regime", "status", "is_current", "is_stale")
    search_fields = ("game__name",)
    list_select_related = ("game",)
    readonly_fields = [field.name for field in ClassificationSnapshot._meta.fields] + [
        "final_challenge",
        "final_reward",
        "method_1_summary",
        "method_2_summary",
        "method_3_summary",
    ]

    fieldsets = (
        (
            "Final Classification",
            {
                "fields": (
                    "game",
                    "status",
                    "regime",
                    "validated_count",
                    "final_challenge",
                    "final_reward",
                    "confidence_final",
                    "confidence_label",
                ),
            },
        ),
        (
            "Method diagnostics",
            {
                "fields": (
                    "method_1_summary",
                    "method_2_summary",
                    "method_3_summary",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timing & provenance",
            {
                "fields": (
                    "calculated_at",
                    "cutoff_at",
                    "is_current",
                    "is_stale",
                    "master_version",
                    "methods_version",
                    "bhpcm_version",
                    "confidence_final_version",
                    "input_population_hash",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Final Challenge")
    def final_challenge(self, obj):
        return _format_integer_profile(obj.unified_integer_challenge)

    @admin.display(description="Final Reward")
    def final_reward(self, obj):
        return _format_integer_profile(obj.unified_integer_reward)

    @admin.display(description="Method 1")
    def method_1_summary(self, obj):
        return _method_summary(obj, "method_1")

    @admin.display(description="Method 2")
    def method_2_summary(self, obj):
        return _method_summary(obj, "method_2")

    @admin.display(description="Method 3")
    def method_3_summary(self, obj):
        return _method_summary(obj, "method_3")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CalculationEpoch)
class CalculationEpochAdmin(admin.ModelAdmin):
    list_display = (
        "epoch_id",
        "cutoff_at",
        "status",
        "games_attempted",
        "games_succeeded",
        "games_failed",
        "completed_at",
    )
    list_filter = ("status",)
    readonly_fields = [field.name for field in CalculationEpoch._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BoundaryCalibration)
class BoundaryCalibrationAdmin(admin.ModelAdmin):
    list_display = (
        "game",
        "master_version",
        "status",
        "delta",
        "population_size",
        "calibrated_at",
    )
    list_filter = ("status",)
    readonly_fields = [field.name for field in BoundaryCalibration._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
