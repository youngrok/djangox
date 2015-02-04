from django.conf.urls import include, url
import inspect
import pkgutil
import re
import sys
import types
from django.utils.decorators import classonlymethod
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View


class RESTController(object):

    @classonlymethod
    def as_view(cls):

        @csrf_exempt
        def dispatch(request, resource_id=None, action=None):
            self = cls()
            method = request.method.lower()

            if action:
                return getattr(self, action)(request, resource_id)

            elif method == 'get':
                if resource_id:
                    return self.show(request, resource_id)
                else:
                    return self.index(request)
            elif method == 'post':
                return self.create(request)
            elif method == 'put':
                return self.update(request, resource_id)
            elif method == 'delete':
                return self.delete(request, resource_id)
            elif method == 'head':
                return self.info(request)
            else:
                raise Exception('No route found: %s %s' % (method, resource_id))

        return dispatch


def discover(package, method_first=False):
    '''
    Discover controller functions within give package.
    '''
    if isinstance(package, types.ModuleType):
        package = package.__name__

    urls = []
    __import__(package)
    for module_loader, name, ispkg in pkgutil.walk_packages(sys.modules[package].__path__):
        module = module_loader.find_module(name).load_module(name)

        for member in dir(module):
            controller_class = getattr(module, member)
            if inspect.isclass(controller_class) and issubclass(controller_class, RESTController):
                resource_name = controller_class.__name__.replace('Controller', '').lower()
                urls.append(url(resource_name + '/(?P<resource_id>[^/\?\&]+)?',
                                controller_class.as_view()))

    return include(urls)
