from django.contrib import admin

from .models import Choice, Question


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'question_text', 'pub_date')
    search_fields = ('question_text',)
    list_filter = ('pub_date',)
    inlines = [ChoiceInline]


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'choice_text', 'votes')
    search_fields = ('choice_text', 'question__question_text')
    list_filter = ('question',)
