"""
Django Admin registration for editorial classifications — SBGC-46.
"""

from django.contrib import admin

from classifications.models import (
    ChallengeProfile,
    EditorialClassification,
    RewardProfile,
)


class ChallengeProfileInline(admin.StackedInline):
    model = ChallengeProfile
    extra = 0
    max_num = 1
    min_num = 1
    can_delete = False
    verbose_name = "Challenge Profile"
    verbose_name_plural = "Challenge Profile"


class RewardProfileInline(admin.StackedInline):
    model = RewardProfile
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
