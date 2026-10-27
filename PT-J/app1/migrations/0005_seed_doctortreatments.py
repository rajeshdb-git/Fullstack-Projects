from django.db import migrations


def seed_doctor_treatments(apps, schema_editor):
    DoctorTreatment = apps.get_model('app1', 'DoctorTreatment')

    treatments = [
        ('Knee Pain', 'Whitefield Clinic'),
        ('Neck Pain', 'Brookefield Clinic'),
        ('Shoulder Pain', 'Indiranagar Clinic'),
        ('Back Pain', 'Koramangala Clinic'),
        ('Stroke Rehab', 'HSR Layout Clinic'),
        ('Posture Correction', 'Banaswadi Clinic'),
        ('Sports Injury', 'Marathahalli Clinic'),
    ]

    for treatment, location in treatments:
        DoctorTreatment.objects.get_or_create(
            treatment=treatment,
            location=location,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('app1', '0004_doctortreatment'),
    ]

    operations = [
        migrations.RunPython(seed_doctor_treatments, migrations.RunPython.noop),
    ]
