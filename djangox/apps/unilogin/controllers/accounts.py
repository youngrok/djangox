import urllib.parse
from django.conf import settings
from django.contrib import auth
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.models import User
from django.core.context_processors import csrf
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.context import RequestContext
from django.template.defaulttags import csrf_token, CsrfTokenNode
from djangox.mako import render_to_response


def login(request):
    request.session['login_error_url'] = request.build_absolute_uri()

    next = request.GET.get('next', '/')

    social_auth_providers = settings.SOCIAL_AUTH_PROIVDERS
    print('rc', RequestContext(request))
    return render(request, 'unilogin/login.html', locals())


def provider_authorize(request):
    request.session['state'] = request.GET['state']
    request.session['host'] = request.GET['host']

    next = reverse(provider_complete)

    if request.user.is_authenticated() and not request.GET['connect_more']:
        return HttpResponseRedirect(next)

    social_auth_providers = settings.SOCIAL_AUTH_PROIVDERS
    return render_to_response('accounts/login.html', locals(), RequestContext(request))


def provider_complete(request):
    if not request.user.is_authenticated():
        raise Exception('authentication failed')

    host = request.session['host']
    state = request.session['state']

    del request.session['host']
    del request.session['state']

    return HttpResponseRedirect('http://%s%s?%s' % (
        host,
        reverse(consumer_complete),
        urllib.parse.urlencode({
            'user': request.user.id,
            'state': state
        }))
    )


def consumer_complete(request):
    user = User.objects.get(id=request.GET['user'])
    next = request.session['next']
    state = request.session['state']

    request.session.clear()

    if state != request.GET['state']:
        raise Exception('state token mismatch: %s != %s' % (state, request.GET['state']))

    user.backend = 'django.contrib.auth.backends.ModelBackend'
    auth.login(request, user)
    return HttpResponseRedirect(next)


def logout(request):
    """Logs out user"""
    auth_logout(request)

    return HttpResponseRedirect(request.GET.get('next', '/'))
    