# djangox
Another way of using django. Convention over configuration for urls, mako template language, json response, REST style API, convenient scripts, ...

This package was originated from [djangox-mako](http://github.com/youngrok/djangox-mako) and [djangox-route](http://github.com/youngrok/djangox-route). The namespace package of python sucks, so I integrated two packages into one, and planned to add other features.

[TOC]

## Install

	pip install djangox

## djangox.route
[Django said tying URLs to Python functions is Bad thing.](https://docs.djangoproject.com/en/dev/misc/design-philosophies/#id8) But registering every view functions in urls.py is not so cool. Even django admin uses autodiscover, what's the reason we don't use autodiscover for normal view functions?


### discover_controllers
Register all controller functions to urlpatterns.

    url(r'', discover_controllers(your_app.controllers))

Recommended controller directory structure is like this:

* your_project
  * your_app
    * controllers
      * \__init__.py
      * hello.py
  * your_project
    * urls.py
    
\__init__.py

	def index(request):
		...	

hello.py

	def index(request):
		...
		
	def world(request):
		...

	def show(request, resource_id):
		...		

	def great(request, resource_id):
		...

Now urls will be dispatched like these:

* / -> controllers.__init__.index(request)
* /hello -> controllers.hello.index(request)
* /hello/great -> controllers.hello.great(request)
* /hello/5 -> controllers.hello.show(request, 5)
* /hello/5/world -> controllers.hello.world(request, 5)

You can also use string of package name.

    url(r'', discover_controllers('your_app.controllers'))
    
Other features of django url system are available, too.

    url(r'api/', discover_controllers(your_app.controllers))

url above will dispatch /api/hello to hello.index(request)


### Notes
* `discover_controllers` doesn't intercept django's url dispatching. It just registers every controllers to urlconf. So every decorators for django views works fine.

* I don't like the naming, `views`. Every other web frameworks are consist of MVC(model, view, controller), but only django uses the concept of model-view-template. The view of MVC and the view of django are different. It's more like controller in MVC, but not exactly same. Django intend template should be dull, and views should supply all data template needed. View in django are abstract layer for view in MVC. However I didn't find any advantages in django's approach, so I prefer MVC. This is why I name the autodiscover function as `discover_controllers`, not `discover_views`.

* As I said above, I don't like powerless template engine in django. I think template should have full functionality as programming language. Therefore I recommend mako rather than django template. With [djangox-mako](https://github.com/youngrok/djangox-mako) you can use mako easily.


## djangox.mako
django mako adapter. Now support backend for django template engine (django >= 1.8).

### template loader
Currently djangox.mako supports only app directories loader. You can put template file in your app directory's subdirectory named 'templates', djangox-mako can access that.

### usage
#### django 1.8 render

	def someview(request):
	    ...
	    ...
        return render(request, 'dir/file.html', locals())
	
#### render_to_response (*deprecated in django 1.8*)


	def someview(request):
	    ...
	    ...
        return render_to_response('dir/file.html', locals())
        
#### render_to_response with RequestContext (*deprecated in django 1.8*)

	def someview(request):
	    ...
	    ...
        return render_to_response('dir/file.html', locals(), RequestContext(request))

With RequestContext, you can use context variables related to request, such as csrf_token.

#### django template tags
##### url
django template

    {% url 'path.to.some_view' arg1=v1 arg2=v2 %}
    
mako

    ${url('path.to.some_view', v1, v2)}

##### csrf_token
django template
	
	{% csrf_token %}

The code above will be rendered as:

    <input type="hidden" name="csrfmiddlewaretoken" value="26ec0b9f301f077da66f7aa2d2ae11cd" />	
    
mako

    <input type="hidden" name="csrfmiddlewaretoken" value="${csrf_token}" />

and planning to make the code below possible. Not implemented yet.
    
    ${csrf_token_tag()}

##### static
django template

	{% static 'path/to/style.css' %}

mako

	${static('path/to/style.css')}

#### encoding
Django settings variable DEFAULT_CHARSET will be used for input & output of templates. if None, 'utf8' will be default.

#### default context
You can inject default context with django settings MAKO_DEFAULT_CONTEXT. It's dict type. It also possible to use TEMPLATES config in settings.py.

### TODO
* csrf_token_tag()
* settings.TEMPLATE_DEBUG support
* render_to_string
* support filesystem loader (settings.TEMPLATE_DIR)
* any other feature that is supported by django template but not supported by djangox-mako.

