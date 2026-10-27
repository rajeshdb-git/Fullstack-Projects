from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app1', '0014_patientinquiry_whatsapp_consent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patientinquiry',
            name='phone_number',
            field=models.CharField(db_index=True, max_length=20),
        ),
        migrations.AddField(
            model_name='contactquery',
            name='status',
            field=models.CharField(
                choices=[
                    ('new', 'New'),
                    ('reviewed', 'Reviewed'),
                    ('closed', 'Closed'),
                ],
                default='new',
                max_length=12,
            ),
        ),
    ]
