from types import SimpleNamespace

from django.conf import settings

if not settings.configured:
    settings.configure(
        ALLOWED_HOSTS=['testserver'],
        DEFAULT_CHARSET='utf-8',
        INSTALLED_APPS=[],
        ROOT_URLCONF=__name__,
        SECRET_KEY='test',
    )

import django

django.setup()

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve, reverse

from djangox.route import ModelViewSet


class ArticleViewSet(ModelViewSet):
    basename = 'article'
    url_prefix = ''
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'

    def index(self):
        return HttpResponse('index')

    def search(self):
        return HttpResponse('search')

    def new(self):
        return HttpResponse('new')

    def create(self):
        return HttpResponse('create')

    def get(self, slug):
        return HttpResponse(f'get:{slug}')

    def edit(self, slug):
        return HttpResponse(f'edit:{slug}')

    def update(self, slug):
        return HttpResponse(f'update:{slug}')


urlpatterns = ArticleViewSet.get_urls()


@override_settings(ROOT_URLCONF=__name__)
class ModelViewSetRouteTest(SimpleTestCase):
    def test_url_prefix_can_be_empty(self):
        self.assertEqual(reverse('article_index'), '/')
        self.assertEqual(reverse('article_search'), '/search/')
        self.assertEqual(reverse('article_new'), '/new/')
        self.assertEqual(reverse('article_detail', kwargs={'slug': 'hello'}),
                         '/hello/')
        self.assertEqual(reverse('article_edit', kwargs={'slug': 'hello'}),
                         '/hello/edit/')

    def test_static_actions_are_resolved_before_detail(self):
        self.assertEqual(resolve('/search/').url_name, 'article_search')
        self.assertEqual(resolve('/new/').url_name, 'article_new')
        self.assertEqual(resolve('/hello/').url_name, 'article_detail')

    def test_new_post_maps_to_create(self):
        request = RequestFactory().post('/new/')
        response = ArticleViewSet.as_view('new')(request)

        self.assertEqual(response.content, b'create')

    def test_index_post_is_not_create(self):
        request = RequestFactory().post('/')
        response = ArticleViewSet.as_view('index')(request)

        self.assertEqual(response.status_code, 405)

    def test_default_success_url_points_to_detail(self):
        view = ArticleViewSet()
        article = SimpleNamespace(slug='hello')

        self.assertEqual(view.get_success_url(article), '/hello/')
