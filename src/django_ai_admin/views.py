import logging
import re
import uuid

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AIConfig, Chat, Message, QueryLog
from .permissions import IsStaff
from .serializers import ChatSerializer, MessageSerializer
from .services.context_builder import build_chat_context, update_chat_memory
from .services.executor import execute
from .services.intent_router import route_intent
from .services.llm_client import answer_with_data, chat_generate_orm, suggest_chat_title
from .services.manifest import get_manifest
from .services.planner import build_query_plan
from .services.response_contract import build_envelope


def _is_retryable_error(error: str) -> bool:
    low = (error or '').lower()
    non_retryable = (
        'ai not configured',
        'llm error 400',
        'llm error 401',
        'llm error 403',
        'llm error 404',
    )
    if any(marker in low for marker in non_retryable):
        return False
    return True


def _autofix_generated_code(code: str, manifest: dict[str, list[str]]) -> str:
    """
    Best-effort fixer for common model namespace mistakes.
    Example: app.SMSVerificationCode -> SMSVerificationCode
    """
    src = (code or '').strip()
    if not src:
        return src

    pairs = []
    for key in manifest.keys():
        app_label, _, model_name = key.partition('.')
        if app_label and model_name:
            pairs.append((app_label, model_name))

    fixed = src
    for app_label, model_name in pairs:
        fixed = re.sub(rf"\b{re.escape(app_label)}\.models\.{re.escape(model_name)}\b", model_name, fixed)
        fixed = re.sub(rf"\b{re.escape(app_label)}\.{re.escape(model_name)}\b", model_name, fixed)
    return fixed


def _out_of_scope_message(intent_label: str, candidate_models: list[str]) -> tuple[str, dict]:
    if intent_label == 'GENERAL_HELP':
        msg = (
            'I can help with project data questions in Django Admin. '
            'Please phrase your request as a metric or data query, for example: '
            '"How many new users registered in the last 7 days?"'
        )
        return msg, {'how_to_rephrase': 'Specify what to count or list, and for which time period.'}
    if candidate_models:
        msg = (
            'I could not confidently map this question to project data scope. '
            f'Possible related models: {", ".join(candidate_models[:3])}. '
            'Please clarify which one your question is about.'
        )
        return msg, {'how_to_rephrase': 'Specify entity, time period, and metric.', 'candidate_models': candidate_models[:3]}
    msg = (
        'I cannot map this request to the current project models. '
        'Please clarify the entity, period, and metric.'
    )
    return msg, {'how_to_rephrase': 'Example: "Show payment count by day for the last 30 days".'}


def _safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def _is_default_title(value: str) -> bool:
    title = (value or '').strip()
    return not title or title.lower() == 'new chat'


def _prepare_first_chat_title(chat: Chat, first_question: str, candidate_models: list[str]) -> bool:
    if not _is_default_title(chat.title):
        return False
    try:
        user_message_count = chat.messages.filter(role='user').count()
    except Exception:
        user_message_count = 0
    if user_message_count != 1:
        return False

    title = ''
    try:
        title = suggest_chat_title(first_question)
    except Exception:
        title = ''

    title = (title or '').strip()
    if not title:
        if candidate_models:
            short_model = candidate_models[0].split('.')[-1]
            title = f'{short_model} analysis'
        else:
            title = 'New chat'
    title = title[:120].strip()
    if not title:
        return False
    if title == chat.title:
        return False
    chat.title = title
    return True


class ChatsView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        qs = Chat.objects.filter(owner=request.user).order_by('-updated_at')
        data = ChatSerializer(qs, many=True).data
        return Response(data)

    def post(self, request):
        title = (request.data.get('title') or '').strip() or 'New chat'
        chat = Chat.objects.create(owner=request.user, title=title)
        return Response({'id': chat.id, 'title': chat.title, 'updated_at': chat.updated_at}, status=status.HTTP_201_CREATED)


class ChatDetailView(APIView):
    permission_classes = [IsStaff]

    def get(self, request, chat_id: int):
        try:
            chat = Chat.objects.get(id=chat_id, owner=request.user)
        except Chat.DoesNotExist:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        limit = _safe_int(request.query_params.get('limit', '50'), 50)
        offset = _safe_int(request.query_params.get('offset', '0'), 0)
        msgs = chat.messages.all().order_by('created_at')[offset: offset + limit]
        data = MessageSerializer(msgs, many=True).data
        return Response({'id': chat.id, 'title': chat.title, 'messages': data})

    def delete(self, request, chat_id: int):
        try:
            chat = Chat.objects.get(id=chat_id, owner=request.user)
        except Chat.DoesNotExist:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        chat.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SettingsCheckView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        cfg = AIConfig.objects.order_by('-updated_at').first()
        ok = bool(cfg and cfg.api_key and cfg.model)
        model = cfg.model if cfg else ''
        provider = cfg.provider if cfg else ''
        timeout_sec = cfg.timeout_sec if cfg else 0
        updated_at = cfg.updated_at if cfg else None
        return Response({
            'configured': ok,
            'model': model,
            'provider': provider,
            'timeout_sec': timeout_sec,
            'updated_at': updated_at.isoformat() if updated_at else None,
            'server_time': timezone.now().isoformat(),
        })


class ChatMessageView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, chat_id: int):
        logger = logging.getLogger('app')
        try:
            chat = Chat.objects.get(id=chat_id, owner=request.user)
        except Chat.DoesNotExist:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        content = request.data.get('content', '').strip()
        if not content:
            return Response(
                build_envelope('error', 'Empty content', data={'error_code': 'empty_content'}, meta={'chat_id': chat_id}),
                status=status.HTTP_400_BAD_REQUEST,
            )

        trace_id = str(uuid.uuid4())
        started = timezone.now()
        Message.objects.create(chat=chat, role='user', content=content)

        manifest = get_manifest()
        context = build_chat_context(chat)
        decision = route_intent(
            content,
            manifest=manifest,
            pending_clarification=chat.pending_clarification,
            current_topic=chat.current_topic,
        )

        base_meta = {
            'chat_id': chat.id,
            'intent_label': decision.label,
            'intent_confidence': round(float(decision.confidence or 0.0), 4),
            'trace_id': trace_id,
            'candidate_models': decision.candidate_models[:4],
        }
        title_updated = _prepare_first_chat_title(chat, content, decision.candidate_models[:4])

        if decision.label in ('OUT_OF_SCOPE', 'GENERAL_HELP'):
            message, data = _out_of_scope_message(decision.label, decision.candidate_models)
            Message.objects.create(
                chat=chat,
                role='assistant',
                content=message,
                meta={
                    'response_type': 'out_of_scope',
                    'reason': decision.reason,
                    'candidate_models': decision.candidate_models[:4],
                    **data,
                },
            )
            update_chat_memory(chat, content, message, decision.label, clear_pending=False)
            chat.updated_at = timezone.now()
            save_fields = ['conversation_summary', 'updated_at']
            if title_updated:
                save_fields.append('title')
            chat.save(update_fields=save_fields)
            QueryLog.objects.create(
                user=request.user,
                chat=chat,
                route=decision.label,
                question=content,
                orm_code='',
                query_meta={'candidate_models': decision.candidate_models[:4], 'reason': decision.reason},
                duration_ms=int((timezone.now() - started).total_seconds() * 1000),
                rows=0,
                truncated=False,
                error='',
                intent_label=decision.label,
                intent_confidence=decision.confidence,
            )
            return Response(
                build_envelope('out_of_scope', message, data=data, meta=base_meta),
                status=status.HTTP_200_OK,
            )

        if decision.label == 'CLARIFICATION':
            options = decision.options[:4]
            if not options and decision.candidate_models:
                options = [{'id': str(idx + 1), 'label': key, 'model': key} for idx, key in enumerate(decision.candidate_models[:4])]
            clarification_id = str(uuid.uuid4())
            pending = {
                'id': clarification_id,
                'base_question': content,
                'options': options,
                'created_at': timezone.now().isoformat(),
            }
            chat.pending_clarification = pending
            chat.updated_at = timezone.now()
            save_fields = ['pending_clarification', 'updated_at']
            if decision.candidate_models:
                chat.current_topic = decision.candidate_models[0]
                save_fields.append('current_topic')
            if title_updated:
                save_fields.append('title')
            message_text = decision.clarification_question or 'Please clarify what exactly you want to know from project data.'
            Message.objects.create(
                chat=chat,
                role='assistant',
                content=message_text,
                meta={
                    'response_type': 'clarification',
                    'pending_clarification_id': clarification_id,
                    'options': options,
                    'candidate_models': decision.candidate_models[:4],
                    'reason': decision.reason,
                },
            )
            update_chat_memory(chat, content, message_text, 'CLARIFICATION', clear_pending=False)
            save_fields.append('conversation_summary')
            chat.save(update_fields=save_fields)
            QueryLog.objects.create(
                user=request.user,
                chat=chat,
                route='CLARIFICATION',
                question=content,
                orm_code='',
                query_meta={'candidate_models': decision.candidate_models[:4], 'options': options, 'reason': decision.reason},
                duration_ms=int((timezone.now() - started).total_seconds() * 1000),
                rows=0,
                truncated=False,
                error='',
                intent_label='CLARIFICATION',
                intent_confidence=decision.confidence,
            )
            meta = dict(base_meta)
            meta['pending_clarification_id'] = clarification_id
            return Response(
                build_envelope(
                    'clarification',
                    message_text,
                    data={
                        'question': message_text,
                        'options': options,
                        'pending_clarification_id': clarification_id,
                    },
                    meta=meta,
                ),
                status=status.HTTP_200_OK,
            )

        # DATA_QUERY flow
        plan = build_query_plan(decision.normalized_query or content, decision, context)
        query_text = decision.normalized_query or content
        summary = ''
        explanation = ''
        orm_code = ''
        result = None
        truncated = False
        rows = 0
        error = ''
        prev_code = None
        prev_error = None
        success = False
        final_code = ''
        retry_count = 0

        for attempt in range(3):
            retry_count = attempt
            try:
                gen = chat_generate_orm(
                    query_text,
                    prev_code=prev_code,
                    prev_error=prev_error,
                    context=context,
                    plan=plan,
                    candidate_models=decision.candidate_models,
                )
                summary = (gen.get('summary') or '').strip()
                explanation = (gen.get('explanation') or '').strip()
                orm_code = gen['code']
                logger.info('ai_admin code generated')

                candidate_codes = []
                normalized_code = _autofix_generated_code(orm_code, manifest)
                if normalized_code and normalized_code != orm_code:
                    candidate_codes.append(normalized_code)
                candidate_codes.append(orm_code)

                exec_res = None
                last_exec_error = None
                executed_code = orm_code
                for code_candidate in candidate_codes:
                    try:
                        exec_res = execute(code_candidate, max_rows=100, statement_timeout_ms=5000)
                        executed_code = code_candidate
                        break
                    except Exception as exec_exc:
                        last_exec_error = exec_exc
                        continue
                if exec_res is None:
                    raise last_exec_error or RuntimeError('Execution failed')

                result = exec_res['result']
                truncated = exec_res['truncated']
                rows = exec_res['rows']
                try:
                    final_summary = answer_with_data(content, result, truncated)
                    if final_summary:
                        summary = final_summary
                except Exception:
                    pass
                final_code = executed_code
                success = True
                break
            except Exception as exc:
                error = str(exc)
                logger.error('ai_admin error: %s', error)
                prev_code = orm_code or prev_code
                prev_error = error
                if attempt >= 2 or not _is_retryable_error(error):
                    break

        duration = int((timezone.now() - started).total_seconds() * 1000)

        if success:
            answer_text = summary or 'Done.'
            main_topic = decision.candidate_models[0] if decision.candidate_models else ''
            update_chat_memory(
                chat,
                user_message=content,
                assistant_message=answer_text,
                intent_label='DATA_QUERY',
                current_topic=main_topic,
                clear_pending=True,
            )
            chat.updated_at = timezone.now()
            chat.save(update_fields=['title', 'conversation_summary', 'current_topic', 'pending_clarification', 'updated_at'])
            Message.objects.create(
                chat=chat,
                role='assistant',
                content=answer_text,
                meta={
                    'response_type': 'answer',
                    'summary': answer_text,
                    'result': result,
                    'truncated': truncated,
                    'explanation': explanation,
                    'code': final_code,
                    'interpretation': plan.get('interpretation', ''),
                    'candidate_models': decision.candidate_models[:4],
                },
            )
            QueryLog.objects.create(
                user=request.user,
                chat=chat,
                route='DATA_QUERY',
                question=content,
                orm_code=final_code,
                query_meta={
                    'candidate_models': decision.candidate_models[:4],
                    'interpretation': plan.get('interpretation', ''),
                    'retry_count': retry_count,
                },
                duration_ms=duration,
                rows=rows,
                truncated=truncated,
                error='',
                intent_label='DATA_QUERY',
                intent_confidence=decision.confidence,
            )
            meta = dict(base_meta)
            meta['interpretation'] = plan.get('interpretation', '')
            return Response(
                build_envelope(
                    'answer',
                    answer_text,
                    data={
                        'summary': answer_text,
                        'result': result,
                        'truncated': truncated,
                        'explanation': explanation,
                        'code': final_code,
                        'interpretation': plan.get('interpretation', ''),
                    },
                    meta=meta,
                ),
                status=status.HTTP_200_OK,
            )

        err_msg = error or 'Failed to execute request.'
        Message.objects.create(
            chat=chat,
            role='assistant',
            content='I could not complete this query after multiple attempts. Please try rephrasing the request.',
            meta={'response_type': 'error', 'error_code': 'execution_failed', 'retry_count': retry_count + 1},
        )
        update_chat_memory(
            chat,
            content,
            'I could not complete this query after multiple attempts.',
            'ERROR',
            clear_pending=False,
        )
        chat.updated_at = timezone.now()
        save_fields = ['conversation_summary', 'updated_at']
        if title_updated:
            save_fields.append('title')
        chat.save(update_fields=save_fields)
        QueryLog.objects.create(
            user=request.user,
            chat=chat,
            route='ERROR',
            question=content,
            orm_code=prev_code or '',
            query_meta={'candidate_models': decision.candidate_models[:4], 'retry_count': retry_count},
            duration_ms=duration,
            rows=rows,
            truncated=truncated,
            error=err_msg,
            intent_label=decision.label,
            intent_confidence=decision.confidence,
        )
        return Response(
            build_envelope(
                'error',
                'I could not complete this query after multiple attempts. Please rephrase the request.',
                data={'error_code': 'execution_failed', 'retry_count': retry_count + 1},
                meta=base_meta,
            ),
            status=status.HTTP_200_OK,
        )
