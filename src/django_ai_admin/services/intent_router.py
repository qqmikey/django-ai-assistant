from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import requests

from ..conf import get_openai_chat_completions_url
from ..models import AIConfig


VALID_LABELS = {'DATA_QUERY', 'CLARIFICATION', 'OUT_OF_SCOPE', 'GENERAL_HELP'}
INTERNAL_APP_LABEL = AIConfig._meta.app_label


@dataclass
class IntentDecision:
    label: str
    confidence: float
    reason: str = ''
    candidate_models: list[str] = field(default_factory=list)
    clarification_question: str = ''
    options: list[dict] = field(default_factory=list)
    normalized_query: str = ''


def _manifest_snippet(manifest: dict[str, list[str]], max_models: int = 200, max_fields: int = 30) -> str:
    lines = []
    for model_key in sorted(manifest.keys())[:max_models]:
        fields = manifest.get(model_key) or []
        lines.append(f"{model_key}: {', '.join(fields[:max_fields])}")
    return '\n'.join(lines)


def _extract_json_object(text: str) -> dict:
    raw = (text or '').strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _normalize_models(values, manifest_keys: set[str], limit: int = 4) -> list[str]:
    if not isinstance(values, list):
        return []
    out = []
    for item in values:
        key = str(item or '').strip()
        if not key or key not in manifest_keys:
            continue
        if key in out:
            continue
        out.append(key)
        if len(out) >= limit:
            break
    return out


def _normalize_options(values, manifest_keys: set[str], limit: int = 4) -> list[dict]:
    if not isinstance(values, list):
        return []
    out = []
    idx = 1
    for item in values:
        if not isinstance(item, dict):
            continue
        model = str(item.get('model') or '').strip()
        if not model or model not in manifest_keys:
            continue
        label = str(item.get('label') or model).strip()
        out.append({
            'id': str(item.get('id') or idx),
            'label': label,
            'model': model,
        })
        idx += 1
        if len(out) >= limit:
            break
    return out


def _split_model_key(model_key: str) -> tuple[str, str]:
    if '.' not in model_key:
        return model_key, ''
    app_label, model_name = model_key.split('.', 1)
    return app_label, model_name


def _contains_token(text: str, token: str) -> bool:
    return bool(re.search(rf'(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])', text))


def _camel_to_words(value: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', value).lower()


def _app_variants(app_label: str) -> list[str]:
    lowered = app_label.lower()
    variants = {
        lowered,
        lowered.replace('_', ' '),
        lowered.replace('_', '-'),
        lowered.replace('_', '.'),
    }
    return [v for v in variants if v]


def _extract_mentioned_apps(question: str, manifest_keys: list[str]) -> list[str]:
    text = (question or '').lower()
    app_labels = sorted({_split_model_key(key)[0] for key in manifest_keys})
    mentioned = []
    for app_label in app_labels:
        for variant in _app_variants(app_label):
            if _contains_token(text, variant):
                mentioned.append(app_label)
                break
    return mentioned


def _is_explicit_internal_request(question: str) -> bool:
    text = (question or '').lower()
    hints = set(_app_variants(INTERNAL_APP_LABEL))
    hints.update({
        'ai admin',
        'assistant internals',
        'querylog',
        'query log',
        'router log',
    })
    return any(_contains_token(text, h) for h in hints)


def _score_model_match(question: str, model_key: str, mentioned_apps: list[str]) -> int:
    text = (question or '').lower()
    app_label, model_name = _split_model_key(model_key)
    app_lower = app_label.lower()
    model_lower = model_name.lower()
    camel_words = _camel_to_words(model_name)
    score = 0

    full_key_variants = (
        model_key.lower(),
        model_key.lower().replace('.', '_'),
        model_key.lower().replace('.', '-'),
        model_key.lower().replace('.', ' '),
    )
    if any(_contains_token(text, variant) for variant in full_key_variants):
        score += 120
    if _contains_token(text, model_lower) or _contains_token(text, f'{model_lower}s'):
        score += 40
    if camel_words != model_lower and (_contains_token(text, camel_words) or _contains_token(text, f'{camel_words}s')):
        score += 35
    if camel_words:
        for part in [p.strip() for p in camel_words.split(' ') if p.strip()]:
            if len(part) < 4:
                continue
            if _contains_token(text, part) or _contains_token(text, f'{part}s'):
                score += 28
                break
    if app_label in mentioned_apps:
        score += 55
    elif any(_contains_token(text, variant) for variant in _app_variants(app_label)):
        score += 20

    if app_lower == INTERNAL_APP_LABEL:
        score -= 50
        if _is_explicit_internal_request(question):
            score += 60
        if mentioned_apps and INTERNAL_APP_LABEL not in mentioned_apps and not _is_explicit_internal_request(question):
            score -= 90
    return score


def _prioritize_candidate_models(question: str, candidate_models: list[str], manifest: dict[str, list[str]], limit: int = 4) -> list[str]:
    manifest_keys = sorted(manifest.keys())
    if not manifest_keys:
        return candidate_models[:limit]
    mentioned_apps = _extract_mentioned_apps(question, manifest_keys)

    ranked_manifest = sorted(
        manifest_keys,
        key=lambda key: (_score_model_match(question, key, mentioned_apps), key),
        reverse=True,
    )
    boosted = [key for key in ranked_manifest if _score_model_match(question, key, mentioned_apps) >= 25][:limit]

    ordered = []
    for key in boosted + list(candidate_models):
        if key in manifest and key not in ordered:
            ordered.append(key)
    if not ordered:
        ordered = list(candidate_models)
    return ordered[:limit]


def _prioritize_options(options: list[dict], candidate_models: list[str], limit: int = 4) -> list[dict]:
    if not options:
        options = []
    by_model = {}
    for item in options:
        model = str(item.get('model') or '').strip()
        if model and model not in by_model:
            by_model[model] = item
    ordered = []
    for model in candidate_models:
        if model in by_model:
            if by_model[model] not in ordered:
                ordered.append(by_model[model])
            continue
        ordered.append({'id': str(len(ordered) + 1), 'label': model, 'model': model})
    for item in options:
        if item not in ordered:
            ordered.append(item)
    return ordered[:limit]


def _fallback_decision(question: str, reason: str = 'router_fallback') -> IntentDecision:
    text = (question or '').strip()
    if not text:
        return IntentDecision(
            label='CLARIFICATION',
            confidence=0.55,
            reason=reason,
            clarification_question='Please clarify what you want to measure or list from project data.',
            options=[],
            normalized_query='',
        )
    return IntentDecision(
        label='DATA_QUERY',
        confidence=0.51,
        reason=reason,
        candidate_models=[],
        normalized_query=text,
    )


def _post_router_completion(cfg: AIConfig, messages: list[dict]) -> str:
    payload = {
        'model': cfg.model,
        'temperature': 0.0,
        'max_tokens': min(420, max(180, cfg.max_tokens)),
        'messages': messages,
    }
    headers = {
        'Authorization': f'Bearer {cfg.api_key}',
        'Content-Type': 'application/json',
    }
    response = requests.post(
        get_openai_chat_completions_url(),
        headers=headers,
        data=json.dumps(payload),
        timeout=min(cfg.timeout_sec, 20),
    )
    if response.status_code != 200:
        raise RuntimeError(f'router llm error {response.status_code}')
    data = response.json()
    return data.get('choices', [{}])[0].get('message', {}).get('content', '') or ''


def _build_router_messages(
    question: str,
    manifest: dict[str, list[str]],
    pending_clarification: dict | None = None,
    current_topic: str = '',
) -> list[dict]:
    internal_app_label = INTERNAL_APP_LABEL
    system = (
        'You are an intent router for a Django Admin data assistant.\n'
        'Classify the user message into exactly one label: DATA_QUERY, CLARIFICATION, OUT_OF_SCOPE, GENERAL_HELP.\n'
        'Use manifest models/fields as project scope.\n'
        'Rules:\n'
        '1) DATA_QUERY when user likely asks for metrics/listing/filter over project data.\n'
        '2) CLARIFICATION when likely in-scope but ambiguous; ask a concise clarification question.\n'
        '3) OUT_OF_SCOPE only when clearly unrelated to project data.\n'
        '4) GENERAL_HELP for generic assistant usage/help requests.\n'
        '5) Prefer CLARIFICATION over OUT_OF_SCOPE if uncertain.\n'
        '6) All generated text fields MUST be in English.\n'
        '7) candidate_models and options.model must use exact keys from manifest.\n'
        f'8) Prefer domain models over internal assistant models. Use {internal_app_label}.* only if user explicitly asks about assistant internals/logs.\n'
        '9) If user mentions an app label, prioritize models from that app in candidate_models/options.\n'
        'Return strict JSON only with this schema:\n'
        '{'
        '"label":"...",'
        '"confidence":0.0,'
        '"reason":"...",'
        '"candidate_models":["app.Model"],'
        '"clarification_question":"...",'
        '"options":[{"id":"1","label":"app.Model","model":"app.Model"}],'
        '"normalized_query":"..."'
        '}\n'
        'If no clarification is needed, use empty clarification_question/options.\n'
        'If normalized_query is not needed, repeat the original question.'
    )
    user_payload = {
        'question': (question or '').strip(),
        'current_topic': current_topic or '',
        'pending_clarification': pending_clarification or None,
        'manifest_note': 'Manifest is clipped to 200 models and 30 fields per model.',
        'manifest': _manifest_snippet(manifest, max_models=200, max_fields=30),
    }
    return [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': json.dumps(user_payload, ensure_ascii=False)},
    ]


def _normalize_decision(raw: dict, question: str, manifest: dict[str, list[str]]) -> IntentDecision:
    manifest_keys = set(manifest.keys())
    label = str(raw.get('label') or '').strip().upper()
    if label not in VALID_LABELS:
        label = 'DATA_QUERY'
    try:
        confidence = float(raw.get('confidence', 0.55))
    except Exception:
        confidence = 0.55
    confidence = max(0.0, min(1.0, confidence))
    reason = str(raw.get('reason') or '').strip()
    candidate_models = _normalize_models(raw.get('candidate_models'), manifest_keys, limit=4)
    options = _normalize_options(raw.get('options'), manifest_keys, limit=4)
    candidate_models = _prioritize_candidate_models(question, candidate_models, manifest, limit=4)
    options = _prioritize_options(options, candidate_models, limit=4)
    clarification_question = str(raw.get('clarification_question') or '').strip()
    normalized_query = str(raw.get('normalized_query') or '').strip() or (question or '').strip()

    if label == 'CLARIFICATION' and not clarification_question:
        clarification_question = 'Please clarify which model or metric your question is about.'
    if label == 'CLARIFICATION' and not options and candidate_models:
        options = [{'id': str(idx + 1), 'label': model, 'model': model} for idx, model in enumerate(candidate_models)]
    if label == 'OUT_OF_SCOPE' and not reason:
        reason = 'classified_out_of_scope'

    return IntentDecision(
        label=label,
        confidence=confidence,
        reason=reason,
        candidate_models=candidate_models,
        clarification_question=clarification_question,
        options=options,
        normalized_query=normalized_query,
    )


def _classify_with_ai(
    question: str,
    manifest: dict[str, list[str]],
    pending_clarification: dict | None = None,
    current_topic: str = '',
) -> dict:
    cfg = AIConfig.objects.order_by('-updated_at').first()
    if not cfg or not cfg.api_key or not cfg.model:
        raise RuntimeError('router ai not configured')
    messages = _build_router_messages(
        question=question,
        manifest=manifest,
        pending_clarification=pending_clarification,
        current_topic=current_topic,
    )
    content = _post_router_completion(cfg, messages)
    return _extract_json_object(content)


def route_intent(
    question: str,
    manifest: dict[str, list[str]],
    pending_clarification: dict | None = None,
    current_topic: str = '',
    classifier=None,
) -> IntentDecision:
    text = (question or '').strip()
    try:
        raw = (
            classifier(question=text, manifest=manifest, pending_clarification=pending_clarification, current_topic=current_topic)
            if classifier
            else _classify_with_ai(
                question=text,
                manifest=manifest,
                pending_clarification=pending_clarification,
                current_topic=current_topic,
            )
        )
        if not isinstance(raw, dict):
            return _fallback_decision(text, reason='router_non_dict_result')
        return _normalize_decision(raw, text, manifest)
    except Exception as exc:
        return _fallback_decision(text, reason=f'router_error:{type(exc).__name__}')
