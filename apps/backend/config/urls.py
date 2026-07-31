"""
URL configuration for config project.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from config.admin import apply_admin_branding
from config.health import health

# SBGC-40 — apply MyGameDNA admin branding (safe here — apps are ready).
apply_admin_branding()

urlpatterns = [
    # SBGC-43 — health-check endpoint (public, no auth, no DB).
    path("health/", health),
    # SBGC-40 — admin route controlled by validated ADMIN_URL_PATH.
    path(f"{settings.ADMIN_URL_PATH}/", admin.site.urls),
    # SBGC-37/38 — versioned API prefix.
    path("api/v1/", include("api.urls")),
]
