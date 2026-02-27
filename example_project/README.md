# Example Project

This folder contains a minimal Django project that integrates `django_ai_admin` with simple poll models.

## Quick Start

From the `example_project` directory:

```bash
cd example_project
make dev
```

Or from repository root:

```bash
make -C example_project dev
```

Then open:

- Admin: http://localhost:8000/admin/
- AI Assistant API base: http://localhost:8000/ai-assistant/

Default credentials:

- Username: `admin`
- Password: `admin`

## Demo Data

On startup, the container runs:

1. `python manage.py migrate`
2. `python manage.py bootstrap_demo`

`bootstrap_demo` creates:

- a superuser (idempotent)
- sample `Question` and `Choice` records for the `polls` app
