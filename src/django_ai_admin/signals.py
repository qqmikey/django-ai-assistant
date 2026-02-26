from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .services.manifest import refresh_manifest


@receiver(post_migrate)
def _refresh_manifest(sender, **kwargs):
    try:
        refresh_manifest()
    except Exception:
        pass
