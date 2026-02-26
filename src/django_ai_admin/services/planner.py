from __future__ import annotations


def build_query_plan(question: str, intent_decision, context: dict | None = None) -> dict:
    ctx = context or {}
    focus_models = list(intent_decision.candidate_models[:3])
    current_topic = (ctx.get('current_topic') or '').strip()
    if current_topic and current_topic not in focus_models:
        focus_models.append(current_topic)

    interpretation = question.strip()
    if focus_models:
        interpretation = f"Query focus: {', '.join(focus_models)}. Question: {question.strip()}"

    return {
        'question': question.strip(),
        'focus_models': focus_models,
        'interpretation': interpretation,
        'context_summary': (ctx.get('summary') or '').strip(),
    }
