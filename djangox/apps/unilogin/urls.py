from django.conf.urls import patterns, include, url
from djangox.route import discover_controllers


urlpatterns = patterns('',
    url('', include('social.apps.django_app.urls', namespace='social')),
    (r'', discover_controllers('unilogin.controllers')),
)