# django-ai-admin

Reusable Django application with an embedded AI assistant inside Django Admin.

## Installation

1. Install package dependencies and the app:

```bash
pip install -e .
```

2. Add apps in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    "rest_framework",
    "django_ai_admin",
]
```

3. Add URLs in root `urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    # ...
    path("ai-assistant/", include("django_ai_admin.urls")),
]
```

4. Run migrations:

```bash
python manage.py migrate
```

5. Optional settings in `settings.py`:

```python
DJANGO_AI_ADMIN_URL_PREFIX = "ai-assistant"
DJANGO_AI_ADMIN_ADMIN_SITE = "backend.admin_site.admin_site"  # optional
DJANGO_AI_ADMIN_OPENAI_BASE_URL = "https://api.openai.com/v1"
```

## Usage

### 1) Configure AI in Django Admin

1. Log in as superuser.
2. Open `Admin -> Django Ai Admin -> AI configs`.
3. Create or edit the config record and fill:
   - `provider`: `openai`
   - `api_key`: your API key
   - `model`: for example `gpt-4o-mini`
   - `temperature`: for example `0.2`
   - `max_tokens`: for example `1024`
   - `timeout_sec`: for example `30`
4. Save.

### 2) Use the assistant

1. Open any Django Admin page as a staff user.
2. Click `Open AI` in the admin header.
3. Start a new chat and ask a data question about your project models.
4. Review response, result, and optional details (interpretation/explanation/code).

## Docker Demo Project

A ready-to-run example project is included in `example_project/` with simple `polls` models (`Question`, `Choice`) and admin integration.

From the repository root:

```bash
cd example_project
make dev
```

Then open:

- `http://localhost:8000/admin/`
- login: `admin` / `admin`

See [`example_project/README.md`](example_project/README.md) for details.
