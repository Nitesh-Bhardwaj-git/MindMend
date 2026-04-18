from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Mind_Mend', '0016_privacy_encryption'),
    ]

    operations = [
        migrations.AddField(
            model_name='counsellorbooking',
            name='is_anonymous',
            field=models.BooleanField(default=False, help_text='If checked, the counsellor sees this booking as Anonymous Patient.'),
        ),
    ]
