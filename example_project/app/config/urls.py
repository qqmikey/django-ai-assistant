from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ai-assistant/', include('django_ai_admin.urls')),
]
