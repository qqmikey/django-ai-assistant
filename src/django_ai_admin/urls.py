from django.urls import path
from .views import ChatsView, ChatDetailView, SettingsCheckView, ChatMessageView

urlpatterns = [
    path('api/chats', ChatsView.as_view()),
    path('api/chats/<int:chat_id>', ChatDetailView.as_view()),
    path('api/chats/<int:chat_id>/message', ChatMessageView.as_view()),
    path('api/settings/check', SettingsCheckView.as_view()),
]
