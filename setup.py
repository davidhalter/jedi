#!/usr/bin/env python
from typing import cast

from setuptools import setup, find_packages
from setuptools.depends import get_module_constant

import os

__AUTHOR__ = 'David Halter'
__AUTHOR_EMAIL__ = 'davidhalter88@gmail.com'

# Get the version from within jedi. It's defined in exactly one place now.
version = cast(str, get_module_constant("jedi", "__version__"))

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
      project_urls={
          "Documentation": 'https://jedi.readthedocs.io/en/latest/',
      },
      license='MIT',
      keywords='python completion refactoring vim',
      long_description=readme,
      packages=find_packages(exclude=['test', 'test.*']),
      python_requires='>=3.10',
      # Python 3.13 grammars are added to parso in 0.8.4
      install_requires=['parso>=0.8.7,<0.9.0'],
      extras_require={
          'dev': [
              'pytest<9.0.0',
              # docopt for sith doctests
              'docopt',
              # coloroma for colored debug output
              'colorama',
              'Django',
              'attrs',
              'typing_extensions',
              # latest version on 2025-06-16
              'flake8==7.1.2',
              'zuban==0.7.0',
              # Arbitrary pins, latest at the time of pinning
              'types-setuptools==80.9.0.20250529',
          ],
          'docs': [
              # Just pin all of these.
              'alabaster==1.0.0',
              'babel==2.18.0',
              'certifi==2026.4.22',
              'charset-normalizer==3.4.7',
              'docutils==0.22.4',
              'idna==3.13',
              'imagesize==2.0.0',
              'iniconfig==2.3.0',
              'Jinja2==3.1.6',
              'MarkupSafe==3.0.3',
              'packaging==26.2',
              'pluggy==1.6.0',
              'Pygments==2.20.0',
              'pytest==9.0.3',
              'requests==2.33.1',
              'roman-numerals==4.1.0',
              'snowballstemmer==3.0.1',
              'Sphinx==9.1.0',
              'sphinx_rtd_theme==3.1.0',
              'sphinxcontrib-applehelp==2.0.0',
              'sphinxcontrib-devhelp==2.0.0',
              'sphinxcontrib-htmlhelp==2.1.0',
              'sphinxcontrib-jquery==4.1',
              'sphinxcontrib-jsmath==1.0.1',
              'sphinxcontrib-qthelp==2.0.0',
              'sphinxcontrib-serializinghtml==2.0.0',
              'urllib3==2.6.3',
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
          'Programming Language :: Python :: 3.10',
          'Programming Language :: Python :: 3.11',
          'Programming Language :: Python :: 3.12',
          'Programming Language :: Python :: 3.13',
          'Programming Language :: Python :: 3.14',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: Text Editors :: Integrated Development Environments (IDE)',
          'Topic :: Utilities',
      ],
      )
