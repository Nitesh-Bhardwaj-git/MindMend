from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Mind_Mend', '0010_user_memory'),
    ]

    operations = [
        migrations.AddField(
            model_name='usermemory',
            name='preferred_name',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
