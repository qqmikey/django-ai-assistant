from django.apps import AppConfig


class DjangoAiAdminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_ai_admin'

    def ready(self):
        from .admin_assets import patch_admin_asset_injection
        from . import signals

        patch_admin_asset_injection()
