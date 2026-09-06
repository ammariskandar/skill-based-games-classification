"""Template context processors — SBGC-106."""

from django.conf import settings


def recaptcha_site_key(request):
    """Expose the public reCAPTCHA site key to templates (e.g. admin login)."""
    return {"recaptcha_site_key": getattr(settings, "RECAPTCHA_SITE_KEY", "")}
