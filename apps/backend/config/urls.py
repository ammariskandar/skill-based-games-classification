"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from config.admin import apply_admin_branding

# SBGC-40 — apply MyGameDNA admin branding (safe here — apps are ready).
apply_admin_branding()

urlpatterns = [
    # SBGC-40 — admin route controlled by validated ADMIN_URL_PATH.
    path(f"{settings.ADMIN_URL_PATH}/", admin.site.urls),
    # SBGC-37/38 — versioned API prefix.
    path("api/v1/", include("api.urls")),
]
