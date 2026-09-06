from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    name = "authentication"
    verbose_name = "Authentication"

    def ready(self) -> None:
        # Register the ``user_logged_in`` receiver for login tracking and
        # dormant-superuser restoration (SBGC-186).
        from authentication import signals  # noqa: F401
