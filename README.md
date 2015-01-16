# djangox

프로젝트 생성

requirements.txt 만들기

    Django>=1.7
    Mako
    django-extensions
    django-reset
    python-social-auth
    djangox-mako
    djangox-route
    ipython
    uwsgi

설치

    pip install -r requirements

bower 설정
.bowerrc

    {
      "directory":"app/static/packages"
    }

bower.json

    {
      "name": "springnote",
      "dependencies": {
        "bootstrap": "",
        "jquery": "",
        "font-awesome": ""
      }
    }

설치

    bower install
    
settings.py

    INSTALLED_APPS = (
        'social.apps.django_app.default',
        'django_extensions',
        'unilogin',
        'myapp',
    )
    
urls.py

    url(r'~', include('unilogin.urls')),
    url(r'~', discover_controllers(dashboard.controllers)),
    
myapp/controllers package

first index

    from djangox.mako.shortcuts import render_to_response


    def index(request):
        return render_to_response('index.html', locals())
        

myapp/templates

layout.html

    <!DOCTYPE html>
    <html>
    <head>
    <meta http-equiv="Content-Type" content="text/xhtml; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><%block name="title">Pepper</%block></title>
    <link rel="stylesheet" type="text/css" href="${static('packages/bootstrap/dist/css/bootstrap.css')}"/>
    <link rel="stylesheet" type="text/css" href="${static('packages/font-awesome/css/font-awesome.min.css')}">
    <script type="text/javascript" src="${static('packages/jquery/dist/jquery.js')}"></script>
    <script type="text/javascript" src="${static('packages/bootstrap/dist/js/bootstrap.js')}"></script>
    
    <link rel="stylesheet" type="text/css" href="${static('style.css')}"/>
    <script type="text/javascript" src="${static('common.js')}"></script>
    <script type="text/javascript">
    	$(document.body).ready(function() {
    	})
    </script>
    <%block name="head">
    </%block>
    </head>
    <body class="pepper">
    <%namespace name="nav" file="/common/nav.html" inheritable="True"/>
    <%namespace name="pf" file="/common/profile.html" inheritable="True"/>
    <div class="navbar navbar-default">
        <div class="navbar-header">
            <button type="button" class="navbar-toggle" data-toggle="collapse" data-target=".navbar-menu">
                <span class="sr-only">Toggle navigation</span>
                <span class="icon-bar"></span>
                <span class="icon-bar"></span>
                <span class="icon-bar"></span>
            </button>
            <a href="/" class="navbar-brand">Pepper</a>
        </div>
        <div class="collapse navbar-collapse navbar-menu">
            <ul class="nav navbar-nav">
    
            </ul>
            <ul class="nav navbar-nav navbar-right">
                % if request.user.is_authenticated():
                    <li>
                        <a href="/~profile">${pf.show_profile(request.user)}</a>
                    </li>
                    <li><a href="${url('accounts.logout')}">logout</a></li>
                % else:
                    <li><a href="${url('accounts.login') + '?next=' + request.build_absolute_uri()}">login</a></li>
                % endif
            </ul>
            <form id="search-form" class="navbar-form navbar-right" role="search">
              <div class="form-group">
                <input type="text" class="form-control page-search" id="search-query" placeholder="Go">
              </div>
            </form>
        </div>
    </div>
    
    <div class="container">
        % if messages:
            % for message in messages:
                <div class="alert alert-${message.tags}">
                    ${message}
                </div>
            % endfor
        % endif
    
        ${next.body()}
    </div>
    
    </body>
    </html>

index.html

    <%inherit file="layout.html"/>

    <h1>Hello</h1>
