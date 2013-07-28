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
  sith.py [--pdb|--ipdb|--pudb] [-d] [-n=<nr>] [-f] [--record=<file>] random [<path>]
  sith.py [--pdb|--ipdb|--pudb] [-d] [-f] [--record=<file>] redo
  sith.py [--pdb|--ipdb|--pudb] [-d] [-f] run <operation> <path> <line> <column>
  sith.py show [--record=<file>]
  sith.py -h | --help

Options:
  -h --help         Show this screen.
  --record=<file>   Exceptions are recorded in here [default: record.json].
  -f, --fs-cache        By default, file system cache is off for reproducibility.
  -n, --maxtries=<nr>   Maximum of random tries [default: 100]
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

        if not lines:
            lines = ['']
        line = random.randint(1, len(lines))
        column = random.randint(0, len(lines[line - 1]))
        return cls(operation, path, line, column)

    def run(self, debugger, record=None, print_completions=False):
        try:
            with open(self.path) as f:
                self.file = f.read()
            self.script = jedi.Script(self.file, self.line, self.column,
                self.path)
            self.completions = getattr(self.script, self.operation)()
            if print_completions:
                self.show_location()
                self.show_completions()
        except jedi.NotFoundError:
            pass
        except Exception:
            self.traceback = traceback.format_exc()
            if record is not None:
                with open(record, 'w') as f:
                    json.dump(self.__dict__, f)
            self.show_errors()
            if debugger:
                einfo = sys.exc_info()
                pdb = __import__(debugger)
                if debugger == 'pudb':
                    pdb.post_mortem(einfo[2], einfo[0], einfo[1])
                else:
                    pdb.post_mortem(einfo[2])
            exit(1)

    def show_location(self):
        # Three lines ought to be enough
        show = 3
        lower = self.line - show if self.line - show > 0 else 0
        for i, line in enumerate(self.file.split('\n')[lower:self.line]):
            print(lower + i + 1, line)
        print(' '*(self.column + len(str(self.line))), '^')

    def show_completions(self):
        print("Completions:")
        print()
        for completion in self.completions:
            print(completion.name)

    def show_errors(self):
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
            t.show_errors()
        else:
            t.run(debugger)
    elif arguments['run']:
            TestCase(arguments['<operation>'], arguments['<path>'],
                int(arguments['<line>']), int(arguments['<column>'])
                ).run(debugger, print_completions=True)
    else:
        for _ in range(int(arguments['--maxtries'])):
            t = TestCase.generate(arguments['<path>'] or '.')
            t.run(debugger, record)
            print('.', end='')
            sys.stdout.flush()
        print()


if __name__ == '__main__':
    arguments = docopt(__doc__)
    main(arguments)
