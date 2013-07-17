#!/usr/bin/env python

"""
Sith attacks (and helps debugging) Jedi.

Randomly search Python files and run Jedi on it.  Exception and used
arguments are recorded to ``./record.json`` (specified by --record)::

    ./sith.py random /path/to/sourcecode

Redo recorded exception::

    ./sith.py redo

Show recorded exception::

    ./sith.py show

Usage:
  sith.py [--pdb|--ipdb|--pudb] [-d] [-m=<nr>] [-f] [--record=<file>] random [<path>]
  sith.py [--pdb|--ipdb|--pudb] [-d] [-f] redo
  sith.py [--pdb|--ipdb|--pudb] [-d] [-f] run <operation> <path> <line> <column>
  sith.py show
  sith.py -h | --help

Options:
  -h --help         Show this screen.
  --record=<file>   Exceptions are recorded in here [default: record.json].
  -f, --fs-cache        By default, file system cache is off for reproducibility.
  -m, --maxtries=<nr>   Maximum of random tries [default: 100]
  -d, --debug       Jedi print debugging when an error is raised.
  --pdb             Launch pdb when error is raised.
  --ipdb            Launch ipdb when error is raised.
  --pudb            Launch pudb when error is raised.
"""

from __future__ import print_function, division, unicode_literals
from docopt import docopt

import json
import os
import random
import sys
import traceback

import jedi


class SourceFinder(object):
    _files = None

    @staticmethod
    def fetch(file_path):
        for root, dirnames, filenames in os.walk(file_path):
            for name in filenames:
                if name.endswith('.py'):
                    yield os.path.join(root, name)

    @classmethod
    def files(cls, file_path):
        if cls._files is None:
            cls._files = list(cls.fetch(file_path))
        return cls._files


class TestCase(object):
    def __init__(self, operation, path, line, column, traceback=None):
        self.operation = operation
        self.path = path
        self.line = line
        self.column = column
        self.traceback = traceback

    @classmethod
    def from_cache(cls, record):
        with open(record) as f:
            dct = json.load(f)
        return cls(**dct)

    @classmethod
    def generate(cls, file_path):
        operations = [
            'completions', 'goto_assignments', 'goto_definitions', 'usages',
            'call_signatures']
        operation = random.choice(operations)

        path = random.choice(SourceFinder.files(file_path))
        with open(path) as f:
            source = f.read()
            lines = source.splitlines()

        line = random.randint(1, max(len(lines), 1))
        column = random.randint(0, len(lines[line - 1]))
        return cls(operation, path, line, column)

    def run(self, debugger, record=None):
        try:
            with open(self.path) as f:
                script = jedi.Script(f.read(), self.line, self.column,
                    self.path)
            getattr(script, self.operation)()
        except jedi.NotFoundError:
            pass
        except Exception:
            self.traceback = traceback.format_exc()
            if record is not None:
                with open(record, 'w') as f:
                    json.dump(self.__dict__, f)
            self.show()
            if debugger:
                einfo = sys.exc_info()
                pdb = __import__(debugger)
                pdb.post_mortem(einfo if debugger == 'pudb' else einfo[2])
            return False
        return True

    def show(self):
        print(self.traceback)
        print(("Error with running Script(...).{operation}() with\n"
              "\tpath:   {path}\n"
              "\tline:   {line}\n"
              "\tcolumn: {column}").format(**self.__dict__))

def main(arguments):
    debugger = 'pdb' if arguments['--pdb'] else \
               'ipdb' if arguments['--ipdb'] else \
               'pudb' if arguments['--pudb'] else None
    record = arguments['--record']

    jedi.settings.use_filesystem_cache = arguments['--fs-cache']
    if arguments['--debug']:
        jedi.set_debug_function()

    if  arguments['redo'] or arguments['show']:
        t = TestCase.from_cache(record)
        if arguments['show']:
            t.show()
        else:
            t.run(debugger)
    elif arguments['run']:
            TestCase(arguments['<operation>'], arguments['<path>'],
                arguments['<line>'], arguments['<column>']).run(debugger)
    else:
        for _ in range(int(arguments['--maxtries'])):
            t = TestCase.generate(arguments['<path>'] or '.')
            if not t.run(debugger, record):
                break
            print('.', end='')
            sys.stdout.flush()


if __name__ == '__main__':
    arguments = docopt(__doc__)
    main(arguments)
