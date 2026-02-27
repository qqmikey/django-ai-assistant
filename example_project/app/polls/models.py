from django.db import models
from django.utils import timezone


class Question(models.Model):
    question_text = models.CharField(max_length=255)
    pub_date = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return self.question_text


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=255)
    votes = models.IntegerField(default=0)

    def __str__(self) -> str:
        return self.choice_text
