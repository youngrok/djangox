import os
from setuptools import setup, find_packages


def find_package_data(path):
    return [os.path.join(root[len(path) + 1:], name) for root, dirs, files in os.walk(path) for name in files if not name.endswith('.py')]


setup(name='djangox',
      description='Another way of using django. Convention over configuration for urls, mako template language support,'
                  'json response, REST style API, convenient scripts, ...',
      author='Youngrok Pak',
      author_email='pak.youngrok@gmail.com',
      keywords= 'rest route autodiscover django djangox mako',
      url='https://github.com/youngrok/djangox',
      version='0.1.14',
      packages=find_packages(),
      package_data={
          'djangox.apps.bs4tl': find_package_data('djangox/apps/bs4tl'),
          'djangox.apps.tools': find_package_data('djangox/apps/tools')
      },

      classifiers = [
                     'Development Status :: 3 - Alpha',
                     'Topic :: Software Development :: Libraries',
                     'License :: OSI Approved :: BSD License']
      )
