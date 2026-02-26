from __future__ import annotations

from typing import Any


def build_envelope(
    response_type: str,
    message: str,
    *,
    data: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        'type': response_type,
        'message': message,
        'data': data or {},
        'meta': meta or {},
    }
