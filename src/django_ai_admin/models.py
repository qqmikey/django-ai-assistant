from django.conf import settings
from django.db import models


class AIConfig(models.Model):
    api_key = models.CharField(max_length=512, blank=True, default='')
    model = models.CharField(max_length=128, blank=True, default='gpt-4o-mini')
    temperature = models.FloatField(default=0.2)
    max_tokens = models.IntegerField(default=1024)
    timeout_sec = models.IntegerField(default=30)
    provider = models.CharField(max_length=64, default='openai')
    updated_at = models.DateTimeField(auto_now=True)


class Chat(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_chats')
    title = models.CharField(max_length=255, blank=True, default='')
    conversation_summary = models.TextField(blank=True, default='')
    current_topic = models.CharField(max_length=128, blank=True, default='')
    pending_clarification = models.JSONField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['owner', '-updated_at']),
        ]


class Message(models.Model):
    ROLE_CHOICES = (
        ('system', 'system'),
        ('user', 'user'),
        ('assistant', 'assistant'),
    )
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    meta = models.JSONField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)


class QueryLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='ai_query_logs')
    chat = models.ForeignKey(Chat, null=True, on_delete=models.SET_NULL, related_name='query_logs')
    route = models.CharField(max_length=32, blank=True, default='')
    question = models.TextField()
    orm_code = models.TextField(blank=True, default='')
    query_meta = models.JSONField(null=True, blank=True, default=None)
    duration_ms = models.IntegerField(default=0)
    rows = models.IntegerField(default=0)
    truncated = models.BooleanField(default=False)
    error = models.TextField(blank=True, default='')
    intent_label = models.CharField(max_length=32, blank=True, default='')
    intent_confidence = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
