import inspect
import pkgutil
import re
import sys
import types
from urllib.parse import urlencode

from django.db.models import Q
from django.http import HttpResponseNotAllowed, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import include, path, re_path, reverse
from django.utils.decorators import classonlymethod
from django.views import View
from django_filters.filterset import filterset_factory


class MethodNotAllowed(Exception): pass


class BasicRoutingViewSet(View):
    url_prefix = None
    basename = None
    lookup_field = 'pk'
    lookup_url_kwarg = None
    lookup_path_converter = 'str'

    @classonlymethod
    def as_view(cls, endpoint, **initkwargs):
        def view(request, *args, **kwargs):
            self = cls(**initkwargs)
            self.endpoint = endpoint
            self.setup(request, *args, **kwargs)

            return self.dispatch(request, *args, **kwargs)

        view.view_class = cls
        view.view_initkwargs = initkwargs

        return view

    def dispatch(self, request, *args, **kwargs):
        try:
            method = request.method.lower()
            if method == 'head':
                method = 'get'
            self.action = None

            if self.endpoint == 'index':
                if method == 'get':
                    self.action = self.index
            elif self.endpoint == 'new':
                if method == 'get':
                    self.action = self.new
                if method == 'post':
                    self.action = self.create
            elif self.endpoint == 'detail':
                if method == 'get':
                    self.action = self.get
                if method == 'put':
                    self.action = self.update
                if method == 'patch':
                    self.action = self.update
                if method == 'delete':
                    self.action = self.delete
            elif self.endpoint == 'edit':
                if method == 'get':
                    self.action = self.edit
                if method == 'post':
                    self.action = self.update
            elif self.endpoint == 'delete':
                if method == 'post':
                    self.action = self.delete

            if self.action is None:
                raise MethodNotAllowed()

            if self.endpoint in ['detail', 'edit', 'delete']:
                lookup_url_kwarg = self.__class__.get_lookup_url_kwarg()
                return self.action(kwargs[lookup_url_kwarg])
            return self.action()
        except MethodNotAllowed:
            return HttpResponseNotAllowed([])

    @classonlymethod
    def get_urls(cls):
        url_prefix = cls.get_url_prefix()
        url_basename = cls.get_url_basename()
        lookup_url_kwarg = cls.get_lookup_url_kwarg()
        lookup_path_converter = cls.lookup_path_converter
        base_path = f'{url_prefix}/' if url_prefix else ''
        lookup_path = f'<{lookup_path_converter}:{lookup_url_kwarg}>/'
        object_path = f'{base_path}{lookup_path}'

        return [
            path(base_path, cls.as_view('index'), name=f'{url_basename}_index'),
            path(f'{base_path}new/',
                 cls.as_view('new'),
                 name=f'{url_basename}_new'),
            path(object_path,
                 cls.as_view('detail'),
                 name=f'{url_basename}_detail'),
            path(f'{object_path}edit/',
                 cls.as_view('edit'),
                 name=f'{url_basename}_edit'),
            path(f'{object_path}delete/',
                 cls.as_view('delete'),
                 name=f'{url_basename}_delete'),
        ]

    @classonlymethod
    def get_url_prefix(cls):
        if cls.url_prefix is not None:
            return cls.url_prefix

        class_name = re.sub(r'(ViewSet|Controller)$', '', cls.__name__)
        return re.sub(r'(?<!^)(?=[A-Z])', '-', class_name).lower()

    @classonlymethod
    def get_url_basename(cls):
        return cls.basename or cls.get_url_prefix().replace('/', '_')

    @classonlymethod
    def get_lookup_url_kwarg(cls):
        return cls.lookup_url_kwarg or cls.lookup_field

    def index(self):
        raise MethodNotAllowed()

    def new(self):
        raise MethodNotAllowed()

    def get(self, pk):
        raise MethodNotAllowed()

    def create(self):
        raise MethodNotAllowed()

    def edit(self, pk):
        raise MethodNotAllowed()

    def update(self, pk):
        raise MethodNotAllowed()

    def delete(self, pk):
        raise MethodNotAllowed()


BasicRouteViewSet = BasicRoutingViewSet


class ModelViewSet(BasicRoutingViewSet):
    queryset = None
    form_class = None
    filterset_class = None
    filterset_fields = None
    search_fields = []
    index_limit = None

    @classonlymethod
    def get_urls(cls):
        url_prefix = cls.get_url_prefix()
        url_basename = cls.get_url_basename()
        lookup_url_kwarg = cls.get_lookup_url_kwarg()
        lookup_path_converter = cls.lookup_path_converter
        base_path = f'{url_prefix}/' if url_prefix else ''
        lookup_path = f'<{lookup_path_converter}:{lookup_url_kwarg}>/'
        object_path = f'{base_path}{lookup_path}'

        return [
            path(base_path, cls.as_view('index'), name=f'{url_basename}_index'),
            path(f'{base_path}search/',
                 cls.as_view('search'),
                 name=f'{url_basename}_search'),
            path(f'{base_path}new/',
                 cls.as_view('new'),
                 name=f'{url_basename}_new'),
            path(object_path,
                 cls.as_view('detail'),
                 name=f'{url_basename}_detail'),
            path(f'{object_path}edit/',
                 cls.as_view('edit'),
                 name=f'{url_basename}_edit'),
            path(f'{object_path}delete/',
                 cls.as_view('delete'),
                 name=f'{url_basename}_delete'),
        ]

    def dispatch(self, request, *args, **kwargs):
        method = request.method.lower()
        if method == 'head':
            method = 'get'

        if self.endpoint == 'search' and method == 'get':
            self.action = self.search
            return self.action()
        if self.endpoint == 'search':
            return HttpResponseNotAllowed([])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.all()

    def get_form(self, *args, **kwargs):
        return self.form_class(*args, **kwargs)

    def get_form_data(self):
        if self.request.method == 'POST':
            return self.request.POST

        return QueryDict(self.request.body, encoding=self.request.encoding)

    def get_initial(self):
        return self.request.GET.dict()

    def get_index_url(self):
        return reverse(f'{type(self).get_url_basename()}_index')

    def get_detail_url(self, obj):
        lookup_url_kwarg = type(self).get_lookup_url_kwarg()
        kwargs = {lookup_url_kwarg: getattr(obj, self.lookup_field)}
        return reverse(f'{type(self).get_url_basename()}_detail',
                       kwargs=kwargs)

    def get_new_url(self):
        return reverse(f'{type(self).get_url_basename()}_new')

    def get_edit_url(self, obj):
        lookup_url_kwarg = type(self).get_lookup_url_kwarg()
        kwargs = {lookup_url_kwarg: getattr(obj, self.lookup_field)}
        return reverse(f'{type(self).get_url_basename()}_edit',
                       kwargs=kwargs)

    def get_success_url(self, obj=None):
        if obj is not None:
            return self.get_detail_url(obj)
        return self.get_index_url()

    def get_filtered_queryset(self):
        queryset = self.get_queryset()
        filterset_class = self.filterset_class

        if filterset_class is None and self.filterset_fields is not None:
            filterset_class = filterset_factory(self.get_queryset().model,
                                                fields=self.filterset_fields)
        if filterset_class is None:
            return queryset
        return filterset_class(data=self.request.GET,
                               queryset=queryset,
                               request=self.request).qs

    def get_object(self, pk):
        return get_object_or_404(self.get_filtered_queryset(),
                                 **{self.lookup_field: pk})

    def index(self):
        object_list = self.get_filtered_queryset()
        if self.index_limit is not None:
            object_list = object_list[:self.index_limit]

        template = f'{type(self).get_url_basename()}/index.html'
        return render(self.request, template, locals())

    def search(self):
        q = self.request.GET.get('q', '').strip()
        object_list = self.get_filtered_queryset()

        if q:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f'{field}__icontains': q})
            object_list = object_list.filter(query)
        if not q and not self.request.GET:
            object_list = self.get_queryset().none()

        new_url = f"{self.get_new_url()}?{urlencode({'title': q})}"

        template = f'{type(self).get_url_basename()}/search.html'
        return render(self.request, template, locals())

    def new(self):
        form = self.get_form(initial=self.get_initial())
        form_action = self.get_new_url()
        cancel_url = self.get_index_url()
        submit_label = '저장'

        template = f'{type(self).get_url_basename()}/new.html'
        return render(self.request, template, locals())

    def get(self, pk):
        obj = self.get_object(pk)

        template = f'{type(self).get_url_basename()}/detail.html'
        return render(self.request, template, locals())

    def create(self):
        form = self.get_form(data=self.get_form_data(),
                             files=self.request.FILES)

        if form.is_valid():
            obj = form.save()
            self.object_saved(obj)
            return redirect(self.get_success_url(obj))

        form_action = self.get_new_url()
        cancel_url = self.get_index_url()
        submit_label = '저장'

        template = f'{type(self).get_url_basename()}/new.html'
        return render(self.request, template, locals())

    def edit(self, pk):
        obj = self.get_object(pk)
        form = self.get_form(instance=obj)
        form_action = self.get_edit_url(obj)
        cancel_url = self.get_detail_url(obj)
        submit_label = '수정'

        template = f'{type(self).get_url_basename()}/edit.html'
        return render(self.request, template, locals())

    def update(self, pk):
        obj = self.get_object(pk)
        form = self.get_form(data=self.get_form_data(),
                             files=self.request.FILES,
                             instance=obj)

        if form.is_valid():
            obj = form.save()
            self.object_saved(obj)
            return redirect(self.get_success_url(obj))

        form_action = self.get_edit_url(obj)
        cancel_url = self.get_detail_url(obj)
        submit_label = '수정'

        template = f'{type(self).get_url_basename()}/edit.html'
        return render(self.request, template, locals())

    def delete(self, pk):
        obj = self.get_object(pk)
        obj.delete()

        return redirect(self.get_success_url(obj))

    def object_saved(self, obj):
        pass


def discover_viewsets(controller):
    urls = []

    for member in dir(controller):
        viewset_class = getattr(controller, member)

        if not inspect.isclass(viewset_class):
            continue

        if viewset_class in [BasicRoutingViewSet, ModelViewSet]:
            continue

        if issubclass(viewset_class, BasicRoutingViewSet):
            urls.extend(viewset_class.get_urls())

    return urls


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

    urls.extend(discover_viewsets(sys.modules[package]))
    
    for _, name, _ in pkgutil.iter_modules([sys.modules[package].__path__[0]]):
        __import__(package + '.' + name)
        
        controller = sys.modules[package + '.' + name]

        urls.extend(discover_viewsets(controller))
        
        for member in dir(controller):
            func = getattr(controller, member)
            if not inspect.isfunction(func): continue

            if method_first:
                urls.append(re_path(r'^' + name + r'/' + member + r'/(?P<resource_id>[^/?&]+)/?$', func))
            else:
                urls.append(re_path(r'^' + name + r'/(?P<resource_id>[^/?&]+)/' + member + r'/?$', func))

            urls.append(re_path('^' + name + '/' + member + '/?$', func))

        if 'show' in dir(controller):
            urls.append(re_path(r'^' + name + r'/(?P<resource_id>[^/?&]+)/?$', getattr(controller, 'show')))
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
