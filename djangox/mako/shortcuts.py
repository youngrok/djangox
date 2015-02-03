import traceback
import warnings
import djangox.mako
from django.conf import settings
from django.http import HttpResponse, HttpResponseServerError
from mako import exceptions


def render_to_response(filename, dictionary, context_instance=None):
    '''
    :param filename:
    :param dictionary:
    :param context_instance:
    :return: rendered django HttpResponse

    .. deprecated:: 1.07
       Use :djangox.mako.render_to_response: instead.
    '''
    warnings.warn('use djangox.mako.render_to_response', DeprecationWarning)

    dictionary.update(djangox.mako.default_context)
    
    if context_instance:
        for context_dict in context_instance.dicts:
            dictionary.update(context_dict)
    
    if hasattr(settings, 'MAKO_DEFAULT_CONTEXT'):
        dictionary.update(settings.MAKO_DEFAULT_CONTEXT)

    try:
        template = djangox.mako.template_lookup.get_template(filename)
        return HttpResponse(template.render(**dictionary))
    except:
        traceback.print_exc()
        return HttpResponseServerError(exceptions.html_error_template().render())
