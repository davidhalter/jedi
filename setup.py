#!/usr/bin/env python

from setuptools import setup

__AUTHOR__ = 'David Halter'
__AUTHOR_EMAIL__ = 'davidhalter88@gmail.com'

readme = open('README.rst').read()

setup(name='jedi',
      version='0.5b1',
      description='An autocompletion tool for Python that can be used for text editors.',
      author=__AUTHOR__,
      author_email=__AUTHOR_EMAIL__,
      maintainer=__AUTHOR__,
      maintainer_email=__AUTHOR_EMAIL__,
      url='https://github.com/davidhalter/jedi',
      license='LGPLv3',
      keywords='python completion refactoring vim',
      long_description=readme,
      packages=['jedi'],
      platforms=['any'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Plugins',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: Text Editors :: Integrated Development Environments (IDE)',
          'Topic :: Utilities',
      ],
    )
