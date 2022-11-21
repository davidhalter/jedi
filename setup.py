#!/usr/bin/env python

from setuptools import setup, find_packages
from setuptools.depends import get_module_constant

import os

__AUTHOR__ = 'David Halter'
__AUTHOR_EMAIL__ = 'davidhalter88@gmail.com'

# Get the version from within jedi. It's defined in exactly one place now.
version = get_module_constant("jedi", "__version__")

readme = open('README.rst').read() + '\n\n' + open('CHANGELOG.rst').read()

assert os.path.isfile("jedi/third_party/typeshed/LICENSE"), \
    "Please download the typeshed submodule first (Hint: git submodule update --init)"
assert os.path.isfile("jedi/third_party/django-stubs/LICENSE.txt"), \
    "Please download the django-stubs submodule first (Hint: git submodule update --init)"

setup(name='jedi',
      version=version,
      description='An autocompletion tool for Python that can be used for text editors.',
      author=__AUTHOR__,
      author_email=__AUTHOR_EMAIL__,
      include_package_data=True,
      maintainer=__AUTHOR__,
      maintainer_email=__AUTHOR_EMAIL__,
      url='https://github.com/davidhalter/jedi',
      license='MIT',
      keywords='python completion refactoring vim',
      long_description=readme,
      packages=find_packages(exclude=['test', 'test.*']),
      python_requires='>=3.6',
      install_requires=['parso>=0.8.0,<0.9.0'],
      extras_require={
          'testing': [
              'pytest<7.0.0',
              # docopt for sith doctests
              'docopt',
              # coloroma for colored debug output
              'colorama',
              'Django<3.1',  # For now pin this.
              'attrs',
          ],
          'qa': [
              'flake8==3.8.3',
              'mypy==0.782',
          ],
          'docs': [
              # Just pin all of these.
              'Jinja2==2.11.3',
              'MarkupSafe==1.1.1',
              'Pygments==2.8.1',
              'alabaster==0.7.12',
              'babel==2.9.1',
              'chardet==4.0.0',
              'commonmark==0.8.1',
              'docutils==0.17.1',
              'future==0.18.2',
              'idna==2.10',
              'imagesize==1.2.0',
              'mock==1.0.1',
              'packaging==20.9',
              'pyparsing==2.4.7',
              'pytz==2021.1',
              'readthedocs-sphinx-ext==2.1.4',
              'recommonmark==0.5.0',
              'requests==2.25.1',
              'six==1.15.0',
              'snowballstemmer==2.1.0',
              'sphinx==1.8.5',
              'sphinx-rtd-theme==0.4.3',
              'sphinxcontrib-serializinghtml==1.1.4',
              'sphinxcontrib-websupport==1.2.4',
              'urllib3==1.26.4',
          ],
      },
      package_data={'jedi': ['*.pyi', 'third_party/typeshed/LICENSE',
                             'third_party/typeshed/README']},
      platforms=['any'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Plugins',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9',
          'Programming Language :: Python :: 3.10',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: Text Editors :: Integrated Development Environments (IDE)',
          'Topic :: Utilities',
      ],
      )
