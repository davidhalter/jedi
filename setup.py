#!/usr/bin/env python

from __future__ import with_statement
try:
    from setuptools import setup
except ImportError:
    # Distribute is not actually required to install
    from distutils.core import setup

__AUTHOR__ = 'David Halter'
__AUTHOR_EMAIL__ = 'davidhalter88@gmail.com'

readme = open('README.rst').read() + '\n\n' + open('CHANGELOG.rst').read()

import jedi
VERSION = '.'.join(str(x) for x in jedi.__version__)

setup(name='jedi',
      version=VERSION,
      description='An autocompletion tool for Python that can be used for text editors.',
      author=__AUTHOR__,
      author_email=__AUTHOR_EMAIL__,
      maintainer=__AUTHOR__,
      maintainer_email=__AUTHOR_EMAIL__,
      url='https://github.com/davidhalter/jedi',
      license='MIT',
      keywords='python completion refactoring vim',
      long_description=readme,
      packages=['jedi', 'jedi.parser'],
      package_data={'jedi': ['mixin/*.pym']},
      platforms=['any'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Plugins',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.2',
          'Programming Language :: Python :: 3.3',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: Text Editors :: Integrated Development Environments (IDE)',
          'Topic :: Utilities',
      ],
    )
