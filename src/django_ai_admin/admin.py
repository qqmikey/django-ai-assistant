from django.contrib import admin
from .models import AIConfig, Chat, Message, QueryLog
from .conf import get_admin_site

admin_site = get_admin_site()


class AIConfigAdmin(admin.ModelAdmin):
    list_display = ('provider', 'model', 'updated_at')
    search_fields = ('model', 'provider')


class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner', 'title', 'current_topic', 'updated_at')
    search_fields = ('title', 'owner__username', 'owner__email', 'current_topic')
    list_filter = ('updated_at',)
    readonly_fields = ('conversation_summary', 'pending_clarification')


class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'role', 'created_at')
    search_fields = ('content',)
    list_filter = ('role', 'created_at')


class QueryLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'chat', 'route', 'intent_label', 'duration_ms', 'rows', 'truncated', 'created_at')
    search_fields = ('question', 'orm_code', 'error')
    list_filter = ('truncated', 'created_at')
    readonly_fields = ('query_meta',)


def _safe_register(model, admin_class):
    try:
        admin_site.register(model, admin_class)
    except admin.sites.AlreadyRegistered:
        pass


_safe_register(AIConfig, AIConfigAdmin)
_safe_register(Chat, ChatAdmin)
_safe_register(Message, MessageAdmin)
_safe_register(QueryLog, QueryLogAdmin)
