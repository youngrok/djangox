from django.core.management.base import BaseCommand
from djangox.apps import import_app


class Command(BaseCommand):
    args = 'package name of app'
    help = 'copy specified app files into this project.'

    def handle(self, *args, **options):
        import_app(args[0])