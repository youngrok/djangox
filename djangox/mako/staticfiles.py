import hashlib

import os
from django.core.cache import cache
from django.templatetags.static import StaticNode
from django.contrib.staticfiles import finders


def static(path):
    if not cache.get('statichash.' + path):
        fs_path = finders.find(path)
        if not os.path.isfile(fs_path): return StaticNode.handle_simple(path)

        hash = hashlib.md5(open(fs_path, 'rb').read()).hexdigest()
        cache.set('statichash.' + path, hash)

    return StaticNode.handle_simple(path) + '?' + cache.get('statichash.' + path)