import logging
import os
import sys
import traceback
import types
from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponseServerError
from django.shortcuts import render
from django.template import TemplateDoesNotExist, Origin
from django.template.backends.base import BaseEngine
from django.template.backends.utils import csrf_input_lazy, csrf_token_lazy
from django.template.engine import Engine
from django.templatetags import static
from django.urls import reverse, get_resolver, get_urlconf
from django.utils.translation import gettext
from mako import exceptions
from mako.exceptions import TemplateLookupException
from mako.lookup import TemplateLookup
from mako.template import Template

from djangox.mako import staticfiles


def url(view_name, *args, **kwargs):
    try:
        return reverse(view_name, args=args, kwargs=kwargs)
    except:
        resolver = get_resolver(get_urlconf())
        for key in resolver.reverse_dict.keys():
            if isinstance(key, types.FunctionType):
                name = key.__module__ + '.' + key.__name__
            else:
                name = key

            if name.endswith(view_name):
                return reverse(key, args=args, kwargs=kwargs)
        
        raise
        

default_context = {
    'url' : url,
    'static': staticfiles.static,
    '_': gettext,
}

default_charset = getattr(settings, 'DEFAULT_CHARSET', 'utf8')

app_template_dirs = []
fs_encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()

for app in settings.INSTALLED_APPS:
    try:
        mod = import_module(app)
    except ImportError as e:
        raise ImproperlyConfigured('ImportError %s: %s' % (app, e.args[0]))
    template_dir = os.path.join(os.path.dirname(mod.__file__), 'templates')
    if os.path.isdir(template_dir):
        app_template_dirs.append(template_dir)


template_lookup = TemplateLookup(directories=app_template_dirs, 
                                 input_encoding=default_charset, 
                                 output_encoding=default_charset, 
                                 )

def render_to_response(filename, dictionary, context_instance=None):
    '''
    :param filename:
    :param dictionary:
    :param context_instance:
    :return: rendered django HttpResponse
    '''

    dictionary.update(default_context)

    if context_instance:
        return render(context_instance.request, filename, dictionary)

    if hasattr(settings, 'MAKO_DEFAULT_CONTEXT'):
        dictionary.update(settings.MAKO_DEFAULT_CONTEXT)

    try:
        template = template_lookup.get_template(filename)
        return HttpResponse(template.render(**dictionary))
    except exceptions.TopLevelLookupException:
        raise
    except:
        traceback.print_exc()
        return HttpResponseServerError(exceptions.html_error_template().render())


class MakoTemplateEngine(BaseEngine):

    app_dirname = 'templates'

    def __init__(self, params):
        params = params.copy()
        options = params.pop('OPTIONS').copy()
        options.setdefault('debug', settings.DEBUG)
        super().__init__(params)

        self.context_processors = options.pop('context_processors', [])

        self.apps = options.get('apps', None)
        self.app_dirs = []
        for app in self.apps:
            app_module = import_module(app)
            self.app_dirs.append(os.path.abspath(app_module.__path__[0]))

    def from_string(self, template_code):
        return MakoTemplateWrapper(Template(text=template_code))

    def get_template(self, template_name, dirs=None):
        try:
            mt = template_lookup.get_template(template_name)
        except TemplateLookupException as e:
            raise TemplateDoesNotExist(str(e))

        for d in self.app_dirs:
            if os.path.abspath(os.path.join(d, 'templates', template_name)) == os.path.abspath(mt.filename):
                return MakoTemplateWrapper(mt)

        raise TemplateDoesNotExist("template does not exists in templates directories in specified apps: %s", str(self.apps))


class MakoTemplateWrapper(object):

    def __init__(self, template):
        self.template = template
        self.backend = Engine.get_default()
        self.origin = Origin(
            name=template.filename, template_name=template.filename,
        )

    def render(self, context=None, request=None):
        if context is None:
            context = {}
        if request is not None:
            context['request'] = request
            context['csrf_input'] = csrf_input_lazy(request)
            context['csrf_token'] = csrf_token_lazy(request)
            for context_processor in self.backend.template_context_processors:
                context.update(context_processor(request))

        context.update(default_context)
        if hasattr(settings, 'MAKO_DEFAULT_CONTEXT'):
            context.update(settings.MAKO_DEFAULT_CONTEXT)

        try:
            return self.template.render(**context)
        except exceptions.TopLevelLookupException:
            raise
        except Exception as e:
            logging.error('Template Error\n request: %s\n context: %s', request, context, exc_info=e)
            if settings.DEBUG:
                return exceptions.html_error_template().render()
            else:
                raise e
