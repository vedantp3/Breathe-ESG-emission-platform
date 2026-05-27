"""
core/apps.py — App config and post_save signal to auto-create UserProfile.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        import core.signals  # noqa: F401 — registers post_save signal
