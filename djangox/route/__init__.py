import inspect
import pkgutil
import sys
import types

from django.conf.urls import include
from django.urls import re_path


def discover_controllers(package, method_first=False):
    '''
    Discover controller functions within give package.
    '''
    if isinstance(package, types.ModuleType):
        package = package.__name__
        
    urls = []
    __import__(package)

    if hasattr(sys.modules[package], 'index'):
        urls.append(re_path('^$', getattr(sys.modules[package], 'index')))
    
    for _, name, _ in pkgutil.iter_modules([sys.modules[package].__path__[0]]):
        __import__(package + '.' + name)
        
        controller = sys.modules[package + '.' + name]
        
        for member in dir(controller):
            func = getattr(controller, member)
            if not inspect.isfunction(func): continue
            args = inspect.getfullargspec(func).args
            
            # TODO filter request functions
            # if len(args) == 0 or args[0] != 'request': continue

            if method_first:
                urls.append(re_path('^' + name + '/' + member + '/(?P<resource_id>[^/\?\&]+)/?$', func))
            else:
                urls.append(re_path('^' + name + '/(?P<resource_id>[^/\?\&]+)/' + member + '/?$', func))

            urls.append(re_path('^' + name + '/' + member + '/?$', func))

        if 'show' in dir(controller):
            urls.append(re_path('^' + name + '/(?P<resource_id>[^/\?\&]+)/?$', getattr(controller, 'show')))
        if 'index' in dir(controller):
            urls.append(re_path('^' + name + '$', getattr(controller, 'index')))
                
    return include(urls)


class SubdomainMiddleware(object):
    def process_request(self, request):
        hostname = request.get_host().split(':')[0]
        
        name_parts = hostname.split('.')
        
        if len(name_parts) < 2:
            request.subdomain = None
        else:
            request.subdomain = name_parts[0]
            
        return None
