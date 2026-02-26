from django.apps import apps

_manifest = {}


def build_manifest():
    m = {}
    for model in apps.get_models():
        app_label = model._meta.app_label
        model_name = model.__name__
        fields = [
            f.name
            for f in model._meta.get_fields()
            if getattr(f, 'concrete', False) and not getattr(f, 'many_to_many', False)
        ]
        m[f'{app_label}.{model_name}'] = fields
    return m


def refresh_manifest():
    global _manifest
    _manifest = build_manifest()


def get_manifest():
    global _manifest
    if not _manifest:
        try:
            refresh_manifest()
        except Exception:
            return {}
    return dict(_manifest)
