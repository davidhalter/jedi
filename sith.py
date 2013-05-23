#!/usr/bin/env python

"""
Sith attacks (and helps debugging) Jedi.

Randomly search Python files and run Jedi on it.  Exception and used
arguments are recorded to ``./record.json`` (specified by --record)::

    %(prog)s random

Redo recorded exception::

    %(prog)s redo

Fallback to pdb (or ipdb if available) when error is raised::

    %(prog)s --pdb random
    %(prog)s --pdb redo

"""

from __future__ import print_function
import json
import os
import random
import sys
import traceback

try:
    from itertools import izip as zip
except ImportError:
    pass

import jedi


class SourceCode(object):

    def __init__(self, path):
        self.path = path
        with open(path) as f:
            self.source = f.read()
        self.lines = self.source.splitlines()
        self.maxline = len(self.lines)

    def choose_script_args(self):
        line = random.randint(1, self.maxline)
        column = random.randint(0, len(self.lines[line - 1]))
        return (self.source, line, column, self.path)


class SourceFinder(object):

    def __init__(self, rootpath):
        self.rootpath = rootpath
        self.files = list(self.search_files())

    def search_files(self):
        for root, dirnames, filenames in os.walk(self.rootpath):
            for name in filenames:
                if name.endswith('.py'):
                    yield os.path.join(root, name)

    def choose_source(self):
        # FIXME: try same file for several times
        return SourceCode(random.choice(self.files))


class BaseAttacker(object):

    def __init__(self):
        self.record = {'data': []}

    def attack(self, operation, *args):
        script = jedi.Script(*args)
        op = getattr(script, operation)
        op()

    def add_record(self, exc_info, operation, args):
        (_type, value, tb) = exc_info
        self.record['data'].append({
            'traceback': traceback.format_tb(tb),
            'error': repr(value),
            'operation': operation,
            'args': args,
        })

    def get_record(self, recid):
        return self.record['data'][recid]

    def save_record(self, path):
        with open(path, 'w') as f:
            json.dump(self.record, f)

    def load_record(self, path):
        with open(path) as f:
            self.record = json.load(f)
            return self.record

    def add_arguments(self, parser):
        parser.set_defaults(func=self.do_run)

    def get_help(self):
        for line in self.__doc__.splitlines():
            line = line.strip()
            if line:
                return line


class MixinPrinter(object):

    def print_record(self, recid=-1):
        data = self.get_record(recid)
        print(*data['traceback'], end='')
        print("""
{error} is raised by running Script(...).{operation}() with
line  : {args[1]}
column: {args[2]}
path  : {args[3]}
""".format(**data))


class MixinLoader(object):

    def add_arguments(self, parser):
        super(MixinLoader, self).add_arguments(parser)
        parser = parser.add_argument(
            'recid', default=0, nargs='?', type=int, help="""
            This option currently has no effect as random attack record
            only one error.
            """)

    def do_run(self, record, recid):
        self.load_record(record)


class AttackReporter(object):

    def __init__(self):
        self.tries = 0
        self.errors = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.tries += 1
        sys.stderr.write('.')
        sys.stderr.flush()
        return self.tries

    next = __next__

    def error(self):
        self.errors += 1
        sys.stderr.write('\n')
        sys.stderr.flush()
        print('{0}th error is encountered after {1} tries.'
              .format(self.errors, self.tries))


class RandomAtaccker(MixinPrinter, BaseAttacker):

    """
    Randomly run Script().<method>() against files under <rootpath>.
    """

    operations = [
        'completions', 'goto_assignments', 'goto_definitions', 'usages',
        'call_signatures']

    def choose_operation(self):
        return random.choice(self.operations)

    def generate_attacks(self, maxtries, finder):
        for _ in range(maxtries):
            src = finder.choose_source()
            operation = self.choose_operation()
            yield (operation, src.choose_script_args())

    def do_run(self, record, rootpath, maxtries):
        finder = SourceFinder(rootpath)
        reporter = AttackReporter()
        for (operation, args) in self.generate_attacks(maxtries, finder):
            reporter.next()
            try:
                self.attack(operation, *args)
            except jedi.NotFoundError:
                pass
            except Exception:
                self.add_record(sys.exc_info(), operation, args)
                reporter.error()
                self.print_record()
                raise
            finally:
                self.save_record(record)

    def add_arguments(self, parser):
        super(RandomAtaccker, self).add_arguments(parser)
        parser.add_argument(
            '--maxtries', '-l', default=10000, type=int)
        parser.add_argument(
            'rootpath', default='.', nargs='?',
            help='root directory to look for Python files.')


class RedoAttacker(MixinLoader, BaseAttacker):

    """
    Redo recorded attack.
    """

    def do_run(self, record, recid):
        super(RedoAttacker, self).do_run(record, recid)
        data = self.get_record(recid)
        self.attack(data['operation'], *data['args'])


class ShowRecord(MixinLoader, MixinPrinter, BaseAttacker):

    """
    Show recorded errors.
    """

    def do_run(self, record, recid):
        super(ShowRecord, self).do_run(record, recid)
        self.print_record()


class AttackApp(object):

    def __init__(self):
        self.parsers = []
        self.attackers = []

    def run(self, args=None):
        parser = self.get_parser()
        self.do_run(**vars(parser.parse_args(args)))

    def do_run(self, func, debugger, **kwds):
        try:
            func(**kwds)
        except:
            exc_info = sys.exc_info()
            if debugger == 'pdb':
                try:
                    import ipdb as debugger
                except ImportError:
                    import pdb as debugger
                debugger.post_mortem(exc_info[2])

    def add_parser(self, attacker_class, *args, **kwds):
        attacker = attacker_class()
        parser = self.subparsers.add_parser(
            *args,
            help=attacker.get_help(),
            description=attacker.__doc__,
            **kwds)
        attacker.add_arguments(parser)

        # Not required, just fore debugging:
        self.parsers.append(parser)
        self.attackers.append(attacker)

    def get_parser(self):
        import argparse
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=__doc__)
        parser.add_argument(
            '--record', '-R', default='record.json',
            help='Exceptions are recorded in here (default: %(default)s).')
        parser.add_argument(
            '--pdb', dest='debugger', const='pdb', action='store_const',
            help="Launch pdb or ipdb (if available) when error is raised.")

        self.subparsers = parser.add_subparsers()
        self.add_parser(RandomAtaccker, 'random')
        self.add_parser(RedoAttacker, 'redo')
        self.add_parser(ShowRecord, 'show')

        return parser


if __name__ == '__main__':
    app = AttackApp()
    app.run()
