from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.utils.module_loading import import_string


def _get_setting(name: str, default):
    return getattr(settings, f'DJANGO_AI_ADMIN_{name}', default)


def get_url_prefix() -> str:
    raw = str(_get_setting('URL_PREFIX', 'ai-assistant') or '').strip()
    prefix = raw.strip('/')
    return prefix or 'ai-assistant'


def get_api_base_path() -> str:
    return f'/{get_url_prefix()}'


def get_openai_base_url() -> str:
    raw = str(_get_setting('OPENAI_BASE_URL', 'https://api.openai.com/v1') or '').strip()
    return raw.rstrip('/') or 'https://api.openai.com/v1'


def get_openai_chat_completions_url() -> str:
    return f'{get_openai_base_url()}/chat/completions'


def get_admin_site() -> AdminSite:
    site_ref = _get_setting('ADMIN_SITE', '')
    if not site_ref:
        return admin.site
    try:
        loaded = import_string(site_ref)
    except Exception:
        return admin.site
    if isinstance(loaded, AdminSite):
        return loaded
    return admin.site
