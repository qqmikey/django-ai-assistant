from __future__ import annotations

import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from polls.models import Choice, Question


class Command(BaseCommand):
    help = 'Create demo superuser and demo poll data (idempotent).'

    def handle(self, *args, **options):
        self._ensure_superuser()
        self._ensure_poll_data()
        self.stdout.write(self.style.SUCCESS('Demo bootstrap finished.'))

    def _ensure_superuser(self) -> None:
        username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'admin')

        user_model = get_user_model()
        user = user_model.objects.filter(username=username).first()
        if user is None:
            user_model.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(f'Created superuser: {username}')
            return

        updated = False
        if user.email != email:
            user.email = email
            updated = True
        if not user.is_staff:
            user.is_staff = True
            updated = True
        if not user.is_superuser:
            user.is_superuser = True
            updated = True
        if password:
            user.set_password(password)
            updated = True
        if updated:
            user.save()
            self.stdout.write(f'Updated superuser: {username}')
        else:
            self.stdout.write(f'Superuser already exists: {username}')

    def _ensure_poll_data(self) -> None:
        now = timezone.now()
        payload = [
            {
                'question': 'How often do you use Django Admin?',
                'pub_date': now - timedelta(days=5),
                'choices': [
                    ('Daily', 11),
                    ('Weekly', 8),
                    ('Monthly', 3),
                ],
            },
            {
                'question': 'Which feature is most useful in this demo?',
                'pub_date': now - timedelta(days=3),
                'choices': [
                    ('AI assistant drawer', 12),
                    ('Simple poll models', 6),
                    ('Docker-based setup', 9),
                ],
            },
            {
                'question': 'Should we add more example entities?',
                'pub_date': now - timedelta(days=1),
                'choices': [
                    ('Yes', 7),
                    ('No', 1),
                    ('Maybe later', 4),
                ],
            },
        ]

        for item in payload:
            question, created = Question.objects.get_or_create(
                question_text=item['question'],
                defaults={'pub_date': item['pub_date']},
            )
            if created:
                self.stdout.write(f'Created question: {question.question_text}')
            for choice_text, votes in item['choices']:
                Choice.objects.get_or_create(
                    question=question,
                    choice_text=choice_text,
                    defaults={'votes': votes},
                )
