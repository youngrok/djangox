import hashlib

from django.core.cache import cache
from django.templatetags.static import StaticNode
from django.contrib.staticfiles import finders


def static(path):
    if not cache.get('statichash.' + path):
        hash = hashlib.md5(open(finders.find(path), 'rb').read()).hexdigest()
        cache.set('statichash.' + path, hash)
    return StaticNode.handle_simple(path) + '?' + cache.get('statichash.' + path)