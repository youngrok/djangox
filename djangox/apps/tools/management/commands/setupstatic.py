import os
from django.conf import settings
from django.core.management.base import BaseCommand
from mako.template import Template
from djangox.apps import import_app, tools


class Command(BaseCommand):
    args = 'app name'
    help = '''Setup static folder for specified app.
 - create static folder
 - ready to use bower
   - generate .bowerrc and bower.json
   - bower packages will be installed in static/lib
   - bootstrap, font-awesome, jquery will be included in bower.json by default.
'''

    def handle(self, *args, **options):
        app_name = args[0]
        os.makedirs(app_name + '/' + 'static/lib', exist_ok=True)

        template_path = filename=tools.__path__[0] + '/setupstatic/'
        with open(app_name + '/../.bowerrc', 'w') as f:
            f.write(Template(filename=template_path + '.bowerrc').render(app_name=app_name))

        with open(app_name + '/../bower.json', 'w') as f:
            f.write(Template(filename=template_path + 'bower.json').render(app_name=app_name))

        print('Now you can use bower command. Try `bower install`.')

