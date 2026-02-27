# Generated manually for example project.

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_text', models.CharField(max_length=255)),
                ('pub_date', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name='Choice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('choice_text', models.CharField(max_length=255)),
                ('votes', models.IntegerField(default=0)),
                (
                    'question',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='choices',
                        to='polls.question',
                    ),
                ),
            ],
        ),
    ]
