from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Mind_Mend', '0009_contactmessage'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserMemory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(blank=True, max_length=100)),
                ('stress_topics', models.JSONField(blank=True, default=list)),
                ('helpful_activities', models.JSONField(blank=True, default=list)),
                ('last_emotion', models.CharField(blank=True, max_length=50)),
                ('last_context', models.CharField(blank=True, max_length=50)),
                ('preferred_name', models.CharField(blank=True, max_length=100)),
                ('last_prompted_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
