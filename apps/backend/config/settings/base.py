"""
Django base settings shared by all environments.

Generated from 'django-admin startproject' using Django 6.0.7 and
subsequently split into environment-specific modules under SBGC-37.
"""

from pathlib import Path

import environ

from config.admin import validate_admin_url_path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# config/settings/base.py -> config/settings -> config -> apps/backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read .env from the backend app root (apps/backend/)
env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
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
_ADMIN_URL_PATH_RAW = env("ADMIN_URL_PATH", default="admin")
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
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

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
DATABASE_URL = env("DATABASE_URL", default="")


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
