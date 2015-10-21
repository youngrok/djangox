import distutils
from distutils.dir_util import copy_tree
from django.conf import settings
import importlib
import os
import re
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Install app specified by module name, and copy it's files into this project"

    def add_arguments(self, parser):
        parser.add_argument('app_name')

    def handle(self, app_name, *args, **options):
        import_app(app_name)


def import_app(app_name, edit_settings=True):
    print(app_name)
    try:
        app_module = importlib.import_module(app_name)
    except:
        print('cannot import %s' % app_name)
        return

    module_name_only = app_module.__name__.split('.')[-1]
    if edit_settings:
        insert_app_to_settings(app_name)

    copy_tree(app_module.__path__[0], settings.BASE_DIR + '/' + module_name_only)
    print('copied %s into %s' % (app_module.__path__[0], settings.BASE_DIR + '/' + module_name_only))


def insert_app_to_settings(app_name):
    project_path = os.path.dirname(os.path.normpath(os.sys.modules[settings.SETTINGS_MODULE].__file__))
    settings_edit = CodeEditor(project_path + os.sep + 'settings.py')
    settings_edit.insert_line("    '%s'," % app_name.split('.')[-1], after='INSTALLED_APPS')
    settings_edit.commit()
    print("edited " + project_path + os.sep + 'settings.py')


class CodeEditor(object):

    def __init__(self, filename):
        self.filename = filename
        source = open(filename, 'r').read()
        self.lines = source.splitlines()
        self.cursor = 0

    def insert_tuple_element(self, name, value):
        for index, line in enumerate(self.lines):
            if line.strip().startswith(name):
                insert_index = index + 1
                break

        self.lines.insert(insert_index, '    ' + repr(value) + ',')

    def go_line(self, expr):
        for index, l in enumerate(self.lines[self.cursor:], self.cursor):
            if expr in l:
                self.cursor = index
                break

    def replace_all(self, expr, replacement):
        for index, l in enumerate(self.lines, self.cursor):
            if expr in l:
                self.lines[index] = l.replace(expr, replacement)

    def replace_line(self, expr, replacement):
        for index, l in enumerate(self.lines[self.cursor:], self.cursor):
            if expr in l:
                self.cursor = index
                break

        self.lines[self.cursor] = self.lines[self.cursor].replace(expr, replacement)

    def insert_line(self, line, after):
        if line in self.lines: return

        insert_index = 0
        for index, l in enumerate(self.lines[self.cursor:], self.cursor):
            if re.match(after, l):
                insert_index = index + 1
                break;
        self.lines.insert(insert_index, line)

    def append_line(self, line):
        self.lines.append(line)

    def to_source(self):
        return '\n'.join(self.lines)

    def commit(self):
        open(self.filename, 'w').write(self.to_source())