from django.db import migrations, models
import django.db.models.deletion


def move_existing_data(apps, schema_editor):
	database = schema_editor.connection.alias
	LegacyTreatment = apps.get_model('app1', 'DoctorTreatment')
	Treatment = apps.get_model('app1', 'Treatment')
	Location = apps.get_model('app1', 'Location')
	PatientInquiry = apps.get_model('app1', 'PatientInquiry')

	for legacy in LegacyTreatment.objects.using(database).all():
		treatment, _ = Treatment.objects.using(database).get_or_create(
			name=legacy.treatment,
		)
		if legacy.image and not treatment.image:
			treatment.image = legacy.image
			treatment.save(using=database, update_fields=['image'])
		Location.objects.using(database).get_or_create(name=legacy.location)

	for inquiry in PatientInquiry.objects.using(database).all():
		if inquiry.treatment:
			inquiry.treatment_new, _ = Treatment.objects.using(database).get_or_create(
				name=inquiry.treatment,
			)
		if inquiry.location:
			inquiry.location_new, _ = Location.objects.using(database).get_or_create(
				name=inquiry.location,
			)
		inquiry.save(using=database, update_fields=['treatment_new', 'location_new'])


class Migration(migrations.Migration):

	dependencies = [
		('app1', '0007_doctortreatment_image'),
	]

	operations = [
		migrations.CreateModel(
			name='Location',
			fields=[
				('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('name', models.CharField(max_length=255, unique=True)),
			],
		),
		migrations.CreateModel(
			name='Treatment',
			fields=[
				('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('name', models.CharField(max_length=150, unique=True)),
				('image', models.ImageField(blank=True, null=True, upload_to='treatments/')),
			],
		),
		migrations.AddField(
			model_name='patientinquiry',
			name='treatment_new',
			field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='app1.treatment'),
		),
		migrations.AddField(
			model_name='patientinquiry',
			name='location_new',
			field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='app1.location'),
		),
		migrations.RunPython(move_existing_data, migrations.RunPython.noop),
		migrations.RemoveField(
			model_name='patientinquiry',
			name='treatment',
		),
		migrations.RemoveField(
			model_name='patientinquiry',
			name='location',
		),
		migrations.RenameField(
			model_name='patientinquiry',
			old_name='treatment_new',
			new_name='treatment',
		),
		migrations.RenameField(
			model_name='patientinquiry',
			old_name='location_new',
			new_name='location',
		),
		migrations.AlterField(
			model_name='patientinquiry',
			name='treatment',
			field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inquiries', to='app1.treatment'),
		),
		migrations.AlterField(
			model_name='patientinquiry',
			name='location',
			field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inquiries', to='app1.location'),
		),
		migrations.AlterField(
			model_name='patientinquiry',
			name='problems',
			field=models.TextField(blank=True, default=''),
		),
		migrations.DeleteModel(
			name='DoctorTreatment',
		),
	]