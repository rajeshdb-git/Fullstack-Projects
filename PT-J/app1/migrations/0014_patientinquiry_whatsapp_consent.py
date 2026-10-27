from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app1', '0013_contactquery'),
    ]

    operations = [
        migrations.AddField(
            model_name='patientinquiry',
            name='whatsapp_consent',
            field=models.BooleanField(default=False),
        ),
    ]