from __future__ import annotations

import re


def _shorten(text: str, limit: int = 220) -> str:
    value = re.sub(r'\s+', ' ', (text or '').strip())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + '…'


def build_chat_context(chat, history_limit: int = 8) -> dict:
    msgs = list(chat.messages.order_by('-created_at')[:history_limit])
    msgs.reverse()
    turns = []
    for msg in msgs:
        role = msg.role
        if role not in ('user', 'assistant'):
            continue
        turns.append({
            'role': role,
            'content': _shorten(msg.content, limit=600),
        })

    summary = (chat.conversation_summary or '').strip()
    if not summary and turns:
        pieces = [f"{t['role']}: {_shorten(t['content'], 120)}" for t in turns[-4:]]
        summary = ' | '.join(pieces)

    return {
        'summary': summary,
        'turns': turns,
        'current_topic': (chat.current_topic or '').strip(),
        'pending_clarification': chat.pending_clarification,
    }


def update_chat_memory(
    chat,
    user_message: str,
    assistant_message: str,
    intent_label: str,
    current_topic: str = '',
    clear_pending: bool = False,
) -> None:
    prev = (chat.conversation_summary or '').strip()
    event = (
        f"intent={intent_label}; "
        f"user={_shorten(user_message, 180)}; "
        f"assistant={_shorten(assistant_message, 180)}"
    )
    merged = f"{prev}\n{event}".strip() if prev else event
    if len(merged) > 4000:
        merged = merged[-4000:]
    chat.conversation_summary = merged
    if current_topic:
        chat.current_topic = current_topic
    if clear_pending:
        chat.pending_clarification = None


def generate_chat_title(question: str, model_hint: str = '') -> str:
    base = _shorten(question, limit=80)
    if not base:
        return ''
    if model_hint:
        short_model = model_hint.split('.')[-1]
        return _shorten(f"{short_model}: {base}", limit=120)
    return _shorten(base, limit=120)
