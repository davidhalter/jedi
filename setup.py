#!/usr/bin/env python

import fnmatch
import os
from setuptools import setup, find_packages

import ast


def rglob(top, pat, strip=0):
    matches = []

    for root, dirnames, filenames in os.walk(top):
        if strip:
            stripped_root = os.path.sep.join(root.split(os.path.sep)[strip:])
        else:
            stripped_root = root

        for filename in fnmatch.filter(filenames, pat):
            matches.append(os.path.join(stripped_root, filename))

    return matches


__AUTHOR__ = 'David Halter'
__AUTHOR_EMAIL__ = 'davidhalter88@gmail.com'

# Get the version from within jedi. It's defined in exactly one place now.
with open('jedi/__init__.py') as f:
    tree = ast.parse(f.read())
version = tree.body[int(not hasattr(tree, 'docstring'))].value.s

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
      python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*',
      install_requires=install_requires,
      extras_require={
          'testing': [
              'pytest>=3.1.0',
              # docopt for sith doctests
              'docopt',
              # coloroma for colored debug output
              'colorama',
          ],
      },
      package_data={
          'jedi': ['evaluate/compiled/fake/*.pym'] + rglob('jedi/third_party/typeshed', '*.pyi', 1)
      },
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
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: Text Editors :: Integrated Development Environments (IDE)',
          'Topic :: Utilities',
      ],
      )
