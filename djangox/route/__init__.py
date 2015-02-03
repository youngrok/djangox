from django.conf.urls import include, url
import inspect
import pkgutil
import re
import sys
import types

def discover_controllers(package, method_first=False):
    '''
    Discover controller functions within give package.
    '''
    if isinstance(package, types.ModuleType):
        package = package.__name__
        
    urls = []
    __import__(package)

    if hasattr(sys.modules[package], 'index'):
        urls.append(url('^$', getattr(sys.modules[package], 'index')))
    
    for _, name, _ in pkgutil.iter_modules([sys.modules[package].__path__[0]]):
        __import__(package + '.' + name)
        
        controller = sys.modules[package + '.' + name]
        
        for member in dir(controller):
            func = getattr(controller, member)
            if not inspect.isfunction(func): continue
            args = inspect.getargspec(func).args
            
            # TODO filter request functions
            # if len(args) == 0 or args[0] != 'request': continue

            if method_first:
                urls.append(url('^' + name + '/' + member + '/(?P<resource_id>[^/\?\&]+)/?$', func))
            else:
                urls.append(url('^' + name + '/(?P<resource_id>[^/\?\&]+)/' + member + '/?$', func))

            urls.append(url('^' + name + '/' + member + '/?$', func))

        if 'show' in dir(controller):
            urls.append(url('^' + name + '/(?P<resource_id>[^/\?\&]+)/?$', getattr(controller, 'show')))
        if 'index' in dir(controller):
            urls.append(url('^' + name + '$', getattr(controller, 'index')))
                
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
