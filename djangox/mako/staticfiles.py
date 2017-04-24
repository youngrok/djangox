import hashlib

import os
from urllib.parse import urljoin

from django.core.cache import cache
from django.templatetags.static import StaticNode, PrefixNode
from django.contrib.staticfiles import finders


def static(path):
    prefixed_path = urljoin(PrefixNode.handle_simple("STATIC_URL"), path)

    if not cache.get('statichash.' + path):
        fs_path = finders.find(path)
        if not fs_path or not os.path.isfile(fs_path):
            return prefixed_path

        hash = hashlib.md5(open(fs_path, 'rb').read()).hexdigest()
        cache.set('statichash.' + path, hash)

    return prefixed_path + '?' + cache.get('statichash.' + path)