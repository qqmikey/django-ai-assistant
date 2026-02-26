import json
import re

import requests
from django.utils import timezone

from ..conf import get_openai_chat_completions_url
from ..models import AIConfig
from .manifest import get_manifest


def _manifest_snippet() -> str:
    manifest = get_manifest()
    lines = []
    for model_key, fields in sorted(manifest.items()):
        lines.append(f"{model_key}: {', '.join(fields[:30])}")
    # Important: currently clipped to 200 models / 30 fields per model.
    return '\n'.join(lines[:200])


def _context_snippet(context: dict | None) -> str:
    if not context:
        return ''
    summary = (context.get('summary') or '').strip()
    turns = context.get('turns') or []
    current_topic = (context.get('current_topic') or '').strip()
    parts = []
    if summary:
        parts.append(f"Conversation summary: {summary}")
    if current_topic:
        parts.append(f"Current topic hint: {current_topic}")
    if turns:
        tail = turns[-6:]
        rendered = '\n'.join(f"- {t.get('role')}: {t.get('content')}" for t in tail)
        parts.append(f"Recent turns:\n{rendered}")
    return '\n'.join(parts).strip()


def _plan_snippet(plan: dict | None) -> str:
    if not plan:
        return ''
    try:
        payload = json.dumps(plan, ensure_ascii=False)
    except Exception:
        payload = str(plan)
    return f"Execution plan:\n{payload}"


def _system_prompt(context: dict | None = None, plan: dict | None = None, candidate_models: list[str] | None = None) -> str:
    rules = (
        'You are a Python/Django ORM expert. '
        'Answer in three parts: first line is a concise summary without hedging, then an explanation paragraph, then a fenced Python code block that assigns a variable named result. '
        'Use read-only ORM operations only (filter, annotate, aggregate, values, values_list, count). '
        'Never write to the database. '
        'Use only model and field names that exist in the manifest exactly; never invent fields. '
        'For categorical fields, derive categories from data using distinct/annotate rather than inventing values. '
        'Limit rows to 100 by default.'
    )
    focus = ''
    if candidate_models:
        focus = f"\nPreferred models based on routing: {', '.join(candidate_models[:5])}"
    manifest_text = _manifest_snippet()
    ctx = _context_snippet(context)
    plan_text = _plan_snippet(plan)
    parts = [
        rules + focus,
        'Models and fields available:\n' + manifest_text,
    ]
    if ctx:
        parts.append(ctx)
    if plan_text:
        parts.append(plan_text)
    return '\n\n'.join(parts)


def _extract_parts(content: str) -> tuple[str, str, str]:
    code = ''
    block = re.search(r"```(?:python)?\n([\s\S]*?)```", content or '')
    if block:
        code = block.group(1).strip()
    elif 'result' in (content or ''):
        # Fallback: if model forgot code fences, salvage likely executable tail.
        salvage = re.search(r"(result\s*=.*)", content, flags=re.S)
        if salvage:
            code = salvage.group(1).strip()

    head = content[: block.start()] if block else (content or '')
    lines = [x for x in head.strip().split('\n') if x.strip()]
    summary = lines[0] if lines else ''
    explanation = '\n'.join(lines[1:]) if len(lines) > 1 else ''
    return summary, explanation, code


def _post_chat_completion(payload: dict, cfg: AIConfig) -> dict:
    headers = {
        'Authorization': f'Bearer {cfg.api_key}',
        'Content-Type': 'application/json',
    }
    response = requests.post(
        get_openai_chat_completions_url(),
        headers=headers,
        data=json.dumps(payload),
        timeout=cfg.timeout_sec,
    )
    if response.status_code != 200:
        raise RuntimeError(f'LLM error {response.status_code}')
    return response.json()


def chat_generate_orm(
    question: str,
    prev_code: str | None = None,
    prev_error: str | None = None,
    *,
    context: dict | None = None,
    plan: dict | None = None,
    candidate_models: list[str] | None = None,
) -> dict:
    cfg = AIConfig.objects.order_by('-updated_at').first()
    if not cfg or not cfg.api_key or not cfg.model:
        raise RuntimeError('AI not configured')

    messages = [{'role': 'system', 'content': _system_prompt(context=context, plan=plan, candidate_models=candidate_models)}]

    if prev_error or prev_code:
        hint = 'Previous attempt failed. Fix the issue and regenerate.\n'
        if prev_error:
            hint += f'Error: {prev_error}\n'
        if prev_code:
            hint += f'Previous code:\n```python\n{prev_code}\n```\n'
        if prev_error and ('Unsupported lookup' in prev_error or 'join on the field not permitted' in prev_error):
            hint += 'Avoid reverse relations. Prefer forward queries and __in filters.\n'
        if prev_error and "is not defined" in prev_error:
            hint += (
                'A variable/name was not defined. '
                'Do not reference models as app_label.Model (for example app.User). '
                'Use model classes directly by name (for example User.objects...).\n'
            )
        if prev_code and re.search(r"\b\w+\.[A-Z][A-Za-z0-9_]*\b", prev_code):
            hint += (
                'Detected app namespace model reference pattern. '
                'Replace app_label.Model with Model class name directly.\n'
            )
        messages.append({'role': 'user', 'content': hint})

    messages.append({'role': 'user', 'content': question})
    payload = {
        'model': cfg.model,
        'temperature': cfg.temperature,
        'max_tokens': cfg.max_tokens,
        'messages': messages,
    }
    data = _post_chat_completion(payload, cfg)
    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
    summary, explanation, code = _extract_parts(content)
    if not code:
        raise RuntimeError('No code produced')
    return {
        'summary': summary,
        'explanation': explanation,
        'code': code,
        'raw': content,
        'created_at': timezone.now().isoformat(),
    }


def answer_with_data(question, result, truncated=False):
    cfg = AIConfig.objects.order_by('-updated_at').first()
    if not cfg or not cfg.api_key or not cfg.model:
        raise RuntimeError('AI not configured')
    sys = (
        'You are an analytics summarizer. '
        'Given a user question and JSON data, produce a concise, confident answer in plain language. '
        'Do not invent fields; rely only on provided data. '
        'If data is truncated, mention that totals may be limited. '
        'Return only the final short answer, no code.'
    )
    try:
        data_str = json.dumps(result, ensure_ascii=False)[:6000]
    except Exception:
        data_str = str(result)[:6000]
    payload = {
        'model': cfg.model,
        'temperature': max(0.0, min(0.5, cfg.temperature)),
        'max_tokens': min(512, cfg.max_tokens),
        'messages': [
            {'role': 'system', 'content': sys},
            {'role': 'user', 'content': f'Question: {question}\nData: {data_str}\nTruncated: {bool(truncated)}'},
        ],
    }
    data = _post_chat_completion(payload, cfg)
    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
    return content.strip()


def _normalize_title(value: str, max_len: int = 80) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    text = text.split('\n')[0].strip()
    text = text.strip('`"\' ')
    text = re.sub(r'^\s*title\s*:\s*', '', text, flags=re.I).strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.rstrip(' .,:;|-')
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


def suggest_chat_title(first_user_message: str) -> str:
    cfg = AIConfig.objects.order_by('-updated_at').first()
    if not cfg or not cfg.api_key or not cfg.model:
        return ''
    system = (
        'Generate a concise English chat title for analytics conversation. '
        'Use 2 to 6 words, no quotes, no trailing punctuation. '
        'Return title text only.'
    )
    payload = {
        'model': cfg.model,
        'temperature': 0.1,
        'max_tokens': 24,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': f'First user message: {first_user_message}'},
        ],
    }
    try:
        data = _post_chat_completion(payload, cfg)
    except Exception:
        return ''
    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
    return _normalize_title(content, max_len=80)
