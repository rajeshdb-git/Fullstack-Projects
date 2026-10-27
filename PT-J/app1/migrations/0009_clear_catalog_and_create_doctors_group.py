from django.db import migrations


def clear_catalog_and_create_doctors_group(apps, schema_editor):
	database = schema_editor.connection.alias
	Treatment = apps.get_model('app1', 'Treatment')
	Location = apps.get_model('app1', 'Location')
	Group = apps.get_model('auth', 'Group')

	for treatment in Treatment.objects.using(database).all():
		if treatment.image:
			treatment.image.delete(save=False)

	Treatment.objects.using(database).all().delete()
	Location.objects.using(database).all().delete()
	Group.objects.using(database).get_or_create(name='Doctors')


class Migration(migrations.Migration):

	dependencies = [
		('app1', '0008_normalize_treatments_and_locations'),
		('auth', '0001_initial'),
	]

	operations = [
		migrations.RunPython(clear_catalog_and_create_doctors_group, migrations.RunPython.noop),
	]