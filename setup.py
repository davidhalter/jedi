#!/usr/bin/env python

from setuptools import setup, find_packages

import ast
import sys

__AUTHOR__ = 'David Halter'
__AUTHOR_EMAIL__ = 'davidhalter88@gmail.com'

# Get the version from within jedi. It's defined in exactly one place now.
with open('jedi/__init__.py') as f:
    tree = ast.parse(f.read())
if sys.version_info > (3, 7):
    version = tree.body[0].value.s
else:
    version = tree.body[1].value.s

readme = open('README.rst').read() + '\n\n' + open('CHANGELOG.rst').read()
with open('requirements.txt') as f:
    install_requires = f.read().splitlines()

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
      python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*',
      install_requires=install_requires,
      extras_require={'dev': ['docopt']},
      package_data={'jedi': ['evaluate/compiled/fake/*.pym']},
      platforms=['any'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Plugins',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: Text Editors :: Integrated Development Environments (IDE)',
          'Topic :: Utilities',
      ],
      )
