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

Run a specific operation

    ./sith.py run <operation> </path/to/source/file.py> <line> <col>

Where operation is one of completions, goto_assignments, goto_definitions,
usages, or call_signatures.

Note: Line numbers start at 1; columns start at 0 (this is consistent with
many text editors, including Emacs).

Usage:
  sith.py [--pdb|--ipdb|--pudb] [-d] [-n=<nr>] [-f] [--record=<file>] random [<path>]
  sith.py [--pdb|--ipdb|--pudb] [-d] [-f] [--record=<file>] redo
  sith.py [--pdb|--ipdb|--pudb] [-d] [-f] run <operation> <path> <line> <column>
  sith.py show [--record=<file>]
  sith.py -h | --help

Options:
  -h --help             Show this screen.
  --record=<file>       Exceptions are recorded in here [default: record.json].
  -f, --fs-cache        By default, file system cache is off for reproducibility.
  -n, --maxtries=<nr>   Maximum of random tries [default: 100]
  -d, --debug           Jedi print debugging when an error is raised.
  --pdb                 Launch pdb when error is raised.
  --ipdb                Launch ipdb when error is raised.
  --pudb                Launch pudb when error is raised.
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
        if not os.path.isdir(file_path):
            yield file_path
            return
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
        if operation not in self.operations:
            raise ValueError("%s is not a valid operation" % operation)

        # Set other attributes
        self.operation = operation
        self.path = path
        self.line = line
        self.column = column
        self.traceback = traceback

    @classmethod
    def from_cache(cls, record):
        with open(record) as f:
            args = json.load(f)
        return cls(*args)

    operations = [
        'completions', 'goto_assignments', 'goto_definitions', 'usages',
        'call_signatures']

    @classmethod
    def generate(cls, file_path):
        operation = random.choice(cls.operations)

        path = random.choice(SourceFinder.files(file_path))
        with open(path) as f:
            source = f.read()
            lines = source.splitlines()

        if not lines:
            lines = ['']
        line = random.randint(1, len(lines))
        column = random.randint(0, len(lines[line - 1]))
        return cls(operation, path, line, column)

    def run(self, debugger, record=None, print_result=False):
        try:
            with open(self.path) as f:
                self.script = jedi.Script(f.read(), self.line, self.column, self.path)
            self.completions = getattr(self.script, self.operation)()
            if print_result:
                self.show_location(self.line, self.column)
                self.show_operation()
        except jedi.NotFoundError:
            pass
        except Exception:
            self.traceback = traceback.format_exc()
            if record is not None:
                call_args = (self.operation, self.path, self.line, self.column, self.traceback)
                with open(record, 'w') as f:
                    json.dump(call_args, f)
            self.show_errors()
            if debugger:
                einfo = sys.exc_info()
                pdb = __import__(debugger)
                if debugger == 'pudb':
                    pdb.post_mortem(einfo[2], einfo[0], einfo[1])
                else:
                    pdb.post_mortem(einfo[2])
            exit(1)

    def show_location(self, lineno, column, show=3):
        # Three lines ought to be enough
        lower = lineno - show if lineno - show > 0 else 0
        for i, line in enumerate(self.script.source.split('\n')[lower:lineno]):
            print(lower + i + 1, line)
        print(' ' * (column + len(str(lineno))), '^')

    def show_operation(self):
        print("%s:\n" % self.operation.capitalize())
        getattr(self, 'show_' + self.operation)()

    def show_completions(self):
        for completion in self.completions:
            print(completion.name)

    # TODO: Support showing the location in other files

    # TODO: Move this printing to the completion objects themselves
    def show_usages(self):
        for completion in self.completions:
            print(completion.description)
            if os.path.abspath(completion.module_path) == os.path.abspath(self.path):
                self.show_location(completion.line, completion.column)

    def show_call_signatures(self):
        for completion in self.completions:
            # This is too complicated to print. It really should be
            # implemented in str() anyway.
            print(completion)
            # Can't print the location here because we don't have the module path

    def show_goto_definitions(self):
        for completion in self.completions:
            print(completion.desc_with_module)
            if os.path.abspath(completion.module_path) == os.path.abspath(self.path):
                self.show_location(completion.line, completion.column)

    show_goto_assignments = show_goto_definitions

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

    if arguments['redo'] or arguments['show']:
        t = TestCase.from_cache(record)
        if arguments['show']:
            t.show_errors()
        else:
            t.run(debugger)
    elif arguments['run']:
            TestCase(
                arguments['<operation>'], arguments['<path>'],
                int(arguments['<line>']), int(arguments['<column>'])
            ).run(debugger, print_result=True)
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
