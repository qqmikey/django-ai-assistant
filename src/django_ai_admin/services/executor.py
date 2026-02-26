import json
import builtins as _builtins
from datetime import date, datetime, time, timedelta
from django.db import connection, transaction
from django.apps import apps
from django.db.models.query import QuerySet
from django.utils import timezone
from django.db.models import Q, F, Count
from django.db.models.functions import TruncMonth, ExtractMonth, ExtractYear


def _safe_builtins():
    return {
        'len': len,
        'min': min,
        'max': max,
        'sum': sum,
        'sorted': sorted,
        'range': range,
        'list': list,
        'dict': dict,
        'set': set,
        'tuple': tuple,
        'enumerate': enumerate,
        'zip': zip,
        'any': any,
        'all': all,
        '__import__': _builtins.__import__,
    }


def _model_globals():
    g = {}
    for m in apps.get_models():
        g[m.__name__] = m
    return g


def _normalize(obj):
    if isinstance(obj, (datetime, date, time)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_normalize(x) for x in list(obj)]
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)


def _to_jsonable(value, max_rows):
    truncated = False
    if isinstance(value, QuerySet):
        try:
            probe = list(value[: max_rows + 1])
        except Exception:
            probe = []
        data = None
        if probe:
            first = probe[0]
            if isinstance(first, dict):
                data = probe
            elif isinstance(first, (list, tuple)):
                data = probe
            else:
                try:
                    data = list(value.values()[: max_rows + 1])
                except Exception:
                    data = [getattr(o, 'pk', None) for o in probe]
        else:
            data = []
        if len(data) > max_rows:
            data = data[:max_rows]
            truncated = True
        return _normalize(data), truncated
    if isinstance(value, list):
        if len(value) > max_rows:
            value = value[:max_rows]
            truncated = True
        return _normalize(value), truncated
    if isinstance(value, dict):
        return _normalize(value), truncated
    return _normalize(value), truncated


def execute(code, max_rows=100, statement_timeout_ms=5000):
    safe_globals = {'__builtins__': _safe_builtins()}
    safe_globals.update(_model_globals())
    safe_globals.update({
        'timezone': timezone,
        'date': date,
        'timedelta': timedelta,
        'Q': Q,
        'F': F,
        'Count': Count,
        'TruncMonth': TruncMonth,
        'ExtractMonth': ExtractMonth,
        'ExtractYear': ExtractYear,
    })
    safe_locals = {}
    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute('SET LOCAL transaction_read_only = on')
            cur.execute(f'SET LOCAL statement_timeout = {int(statement_timeout_ms)}')
        exec(code, safe_globals, safe_locals)
    result = safe_locals.get('result')
    jsonable, truncated = _to_jsonable(result, max_rows)
    rows = 1
    if isinstance(jsonable, list):
        rows = len(jsonable)
    if isinstance(jsonable, dict):
        rows = len(jsonable)
    return {'result': jsonable, 'rows': rows, 'truncated': truncated}
