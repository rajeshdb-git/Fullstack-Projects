from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create the project role groups if they do not already exist.'

    def handle(self, *args, **options):
        for group_name in ('Administrators', 'Doctors'):
            group, created = Group.objects.get_or_create(name=group_name)
            status = 'created' if created else 'already exists'
            self.stdout.write(f'{group_name}: {status}')