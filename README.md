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
        
