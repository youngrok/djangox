from django.core.management.base import BaseCommand
from djangox.apps import import_app


class Command(BaseCommand):
    help = 'setup deploy environment'

    def handle(self, *args, **options):
        import_app('djangox.deploy', edit_settings=False)