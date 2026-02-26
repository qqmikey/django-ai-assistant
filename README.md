# django-ai-admin

Reusable Django application with an embedded AI assistant inside Django Admin.

## Recommended Repository Structure (for a reusable Django app)

```text
django-ai-admin/
  pyproject.toml
  MANIFEST.in
  README.md
  src/
    django_ai_admin/
      __init__.py
      apps.py
      conf.py
      admin.py
      admin_assets.py
      models.py
      views.py
      urls.py
      serializers.py
      permissions.py
      signals.py
      services/
      migrations/
      static/django_ai_admin/
      docs/
```

Why this layout:
- The `src/` layout prevents accidental imports from the repository root.
- Everything inside `django_ai_admin/` is packaged as a single pip-installable app.
- `static/` and `migrations/` ship with the app and work as standard Django app assets.

## Install in a Host Project

```bash
pip install -e .
```

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "rest_framework",
    "django_ai_admin",
]
```

```python
# urls.py (root)
from django.urls import include, path

urlpatterns = [
    # ...
    path("ai-assistant/", include("django_ai_admin.urls")),
]
```

## App Settings

Optional settings in `settings.py`:

```python
DJANGO_AI_ADMIN_URL_PREFIX = "ai-assistant"
DJANGO_AI_ADMIN_ADMIN_SITE = "backend.admin_site.admin_site"  # optional
DJANGO_AI_ADMIN_OPENAI_BASE_URL = "https://api.openai.com/v1"
```