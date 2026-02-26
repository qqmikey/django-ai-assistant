from __future__ import annotations

import json
from functools import wraps

from django.contrib.admin.sites import AdminSite
from django.templatetags.static import static

from .conf import get_api_base_path


def _inject_assets(response):
    content_type = (response.get('Content-Type') or '').lower()
    if 'text/html' not in content_type:
        return response
    if getattr(response, 'streaming', False):
        return response

    def _mutate(resp):
        content = getattr(resp, 'content', b'')
        if not content:
            return resp
        if b'django_ai_admin/js/drawer.js' in content:
            return resp
        marker = b'</head>'
        lower = content.lower()
        idx = lower.find(marker)
        if idx < 0:
            return resp
        base_path = json.dumps(get_api_base_path())
        snippet = (
            '\n<link rel="stylesheet" href="{css}">\n'
            '<script>window.DJANGO_AI_ADMIN_BASE_PATH = {base_path};</script>\n'
            '<script defer src="{js}"></script>\n'
        ).format(
            css=static('django_ai_admin/css/drawer.css'),
            base_path=base_path,
            js=static('django_ai_admin/js/drawer.js'),
        ).encode('utf-8')
        resp.content = content[:idx] + snippet + content[idx:]
        return resp

    if hasattr(response, 'add_post_render_callback') and hasattr(response, 'render'):
        if not getattr(response, 'is_rendered', True):
            response.add_post_render_callback(_mutate)
            return response
    return _mutate(response)


def patch_admin_asset_injection():
    if getattr(AdminSite, '_django_ai_admin_assets_patched', False):
        return

    original_admin_view = AdminSite.admin_view

    @wraps(original_admin_view)
    def patched_admin_view(self, view, cacheable=False):
        wrapped_view = original_admin_view(self, view, cacheable=cacheable)

        @wraps(wrapped_view)
        def wrapped_with_assets(request, *args, **kwargs):
            response = wrapped_view(request, *args, **kwargs)
            return _inject_assets(response)

        return wrapped_with_assets

    AdminSite.admin_view = patched_admin_view
    AdminSite._django_ai_admin_assets_patched = True
