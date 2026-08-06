"""
Django base settings shared by all environments.

Generated from 'django-admin startproject' using Django 6.0.7 and
subsequently split into environment-specific modules under SBGC-37.
"""

import os
from pathlib import Path

import environ

from config.admin import validate_admin_url_path
from config.env_typing import env_str

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# config/settings/base.py -> config/settings -> config -> apps/backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read .env from the backend app root (apps/backend/)
# Skip when DJANGO_SKIP_DOTENV is set (used by test settings to avoid
# reading the developer's real .env file).
env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists() and not os.environ.get("DJANGO_SKIP_DOTENV"):
    env.read_env(str(env_file))


# ---------------------------------------------------------------------------
# Security-sensitive values are set by environment-specific modules.
# base.py does NOT provide production defaults for SECRET_KEY, ALLOWED_HOSTS,
# or CSRF_TRUSTED_ORIGINS — those are owned by development / production.
# ---------------------------------------------------------------------------

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG is set by the environment-specific module.
DEBUG = False

# ADMIN_URL_PATH — SBGC-40
# Validated single relative path segment (no leading/trailing slash).
# Controls the Django Admin route.  The configured value is validated at
# settings-import time and the URLconf appends the trailing slash.
#
# Fails startup with ImproperlyConfigured for:
#   missing, blank, slashes, backslashes, dots, query/fragment, URL forms,
#   and the reserved segment "api".
_ADMIN_URL_PATH_RAW = env_str(env, "ADMIN_URL_PATH", default="admin")
ADMIN_URL_PATH = validate_admin_url_path(_ADMIN_URL_PATH_RAW)


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ninja",
    # SBGC-37 — application boundaries (no models yet)
    "games.apps.GamesConfig",
    "classifications.apps.ClassificationsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # SBGC-43 — WhiteNoise for production static files (Admin CSS/JS).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# SBGC-50 — development-only seed-data gate.
# Enabled only in config.settings.development.
DEVELOPMENT_SEEDING_ENABLED = False

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database — SBGC-39
# Raw DATABASE_URL is read here but not connected.
# Environment-specific modules use config.database.build_database_config
# to produce the final DATABASES entry with the correct fallback policy.
DATABASE_URL = env_str(env, "DATABASE_URL", default="")


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Password hashing — SBGC-41
# PBKDF2-SHA256 only.  No legacy hashers, no Argon2/bcrypt/scrypt.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"

# SBGC-43 — collected static root for WhiteNoise production serving.
STATIC_ROOT = BASE_DIR / "staticfiles"

# SBGC-43 — WhiteNoise compressed manifest storage.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/6.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Request-size limits — SBGC-41
# Conservative values for JSON API payloads and Admin forms.
# No public file uploads; Steam images are hotlinked.
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_621_440  # 2.5 MiB
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440  # 2.5 MiB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1_000
DATA_UPLOAD_MAX_NUMBER_FILES = 20

# Django Ninja — SBGC-38
# Interactive API docs are disabled by default.
# Development overrides this to True; production keeps it False.
NINJA_API_DOCS_ENABLED = False

# Steam — SBGC-42
# Raw values read from the environment.  Use steam_client_config_from_settings()
# to build a validated SteamClientConfig — never instantiate it directly from
# these raw strings.
STEAM_WEB_API_KEY = env_str(env, "STEAM_WEB_API_KEY", default="")
STEAM_CONNECT_TIMEOUT_SECONDS = env_str(
    env, "STEAM_CONNECT_TIMEOUT_SECONDS", default="3.05"
)
STEAM_READ_TIMEOUT_SECONDS = env_str(env, "STEAM_READ_TIMEOUT_SECONDS", default="10")
STEAM_MAX_RETRIES = env_str(env, "STEAM_MAX_RETRIES", default="2")
STEAM_RETRY_BACKOFF_SECONDS = env_str(
    env, "STEAM_RETRY_BACKOFF_SECONDS", default="0.25"
)
STEAM_MAX_RESPONSE_BYTES = env_str(env, "STEAM_MAX_RESPONSE_BYTES", default="2097152")
STEAM_CDN_ALLOWED_HOSTS = env_str(env, "STEAM_CDN_ALLOWED_HOSTS", default="")
STEAM_RETRY_SLEEP_MAX_SECONDS = env_str(
    env, "STEAM_RETRY_SLEEP_MAX_SECONDS", default="5"
)

# Logging — SBGC-43
# DJANGO_LOG_LEVEL controls the root Django logger threshold.
# Production default: INFO.  Development may use DEBUG.
# Valid: DEBUG, INFO, WARNING, ERROR, CRITICAL.
_LOG_LEVEL_RAW = env_str(env, "DJANGO_LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{asctime} [{levelname}] {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": _LOG_LEVEL_RAW,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": _LOG_LEVEL_RAW,
            "propagate": False,
        },
    },
}
