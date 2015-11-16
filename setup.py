from setuptools import setup, find_packages

setup(name='djangox',
      description='Another way of using django. Convention over configuration for urls, mako template language support,'
                  'json response, REST style API, convenient scripts, ...',
      author='Youngrok Pak',
      author_email='pak.youngrok@gmail.com',
      keywords= 'rest route autodiscover django djangox mako',
      url='https://github.com/youngrok/djangox',
      version='0.1.0',
      packages=find_packages(),
      package_data={'djangox.apps.bs4templates': ['static/*', 'templates/*', 'templates/bs4templates/*'],
                    'djangox.apps.tools': ['setupstatic/*'],
                    'djangox.apps.model.templates': ['common/*', 'sample/*'],
                    'djangox.apps.deploy': ['*', 'bin/*'],
                    },

      classifiers = [
                     'Development Status :: 3 - Alpha',
                     'Topic :: Software Development :: Libraries',
                     'License :: OSI Approved :: BSD License']
      )
