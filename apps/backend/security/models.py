"""
Virtual (unmanaged) models backing the read-only Admin registry catalogs.

``managed = False`` means no database tables and no migrations are ever
created; each model exists purely as a Django Admin registration point so the
read-only catalog views appear under the "Security" app section of the Admin
sidebar — shared category for the error-code and tech-stack registries,
separate from the Games domain (SBGC-108).
"""

from django.db import models


class ErrorRegistryEntry(models.Model):
    """Unmanaged virtual model exposing the canonical error-code registry.

    Renders from ``games.errors.ERROR_REGISTRY`` via
    ``security.admin.ErrorRegistryAdmin`` — nothing is ever persisted.
    """

    class Meta:
        managed = False
        verbose_name = "Error Registry"
        verbose_name_plural = "Error Registry"
        # A real ``security.view_errorregistryentry`` permission is created at
        # post_migrate so superusers always pass and moderators can be granted
        # read access through the Admin group/permission picker (SBGC-108).
        default_permissions = ("view",)

    def __str__(self) -> str:
        return "Error Registry"


class DependencyRegistryEntry(models.Model):
    """Unmanaged virtual model exposing the tech-stack dependency catalog.

    Renders from ``security.dependencies.TECH_STACK_REGISTRY`` via the
    staff-guarded catalog view — nothing is ever persisted.
    """

    class Meta:
        managed = False
        verbose_name = "Tech Stack Registry"
        verbose_name_plural = "Tech Stack Registry"
        # Real ``security.view_dependencyregistryentry`` permission (SBGC-108).
        default_permissions = ("view",)

    def __str__(self) -> str:
        return "Tech Stack Registry"
