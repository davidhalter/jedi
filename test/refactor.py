#!/usr/bin/env python
"""
Refactoring tests work a little bit similar to Black Box tests. But the idea is
here to compare two versions of code. **Note: Refactoring is currently not in
active development (and was never stable), the tests are therefore not really
valuable - just ignore them.**
"""
from __future__ import with_statement
import os
import re

from functools import reduce
import jedi
from .helpers import test_dir


class RefactoringCase(object):

    def __init__(self, name, code, line_nr, index, path,
                 args, desired_diff):
        self.name = name
        self._code = code
        self._line_nr = line_nr
        self._index = index
        self._path = path
        self._args = args
        self.desired_diff = desired_diff

    @property
    def refactor_type(self):
        f_name = os.path.basename(self._path)
        return f_name.replace('.py', '')

    def calculate_diff(self):
        project = jedi.Project(os.path.join(test_dir, 'refactor'))
        script = jedi.Script(self._code, path=self._path, project=project)
        refactor_func = getattr(script, self.refactor_type)
        refactor_object = refactor_func(self._line_nr, self._index, *self._args)
        return refactor_object.get_diff()

    def __repr__(self):
        return '<%s: %s:%s>' % (self.__class__.__name__,
                                self.name, self._line_nr - 1)


def _collect_file_tests(code, path, lines_to_execute):
    r = r'^# -{5} ?([^\n]*)\n((?:(?!\n# \+{5}).)*\n)' \
        r'# \+{5}\n((?:(?!\n# -{5}).)*\n)'
    for match in re.finditer(r, code, re.DOTALL | re.MULTILINE):
        name = match.group(1).strip()
        first = match.group(2)
        second = match.group(3)

        # get the line with the position of the operation
        p = re.match(r'((?:(?!#\?).)*)#\? (\d*) ?([^\n]*)', first, re.DOTALL)
        if p is None:
            print("Please add a test start.")
            continue
        until = p.group(1)
        index = int(p.group(2))
        new_name = p.group(3)
        args = (new_name,) if new_name else ()

        line_nr = until.count('\n') + 2
        if lines_to_execute and line_nr - 1 not in lines_to_execute:
            continue

        yield RefactoringCase(name, first, line_nr, index, path, args, second)


def collect_dir_tests(base_dir, test_files):
    for f_name in os.listdir(base_dir):
        files_to_execute = [a for a in test_files.items() if a[0] in f_name]
        lines_to_execute = reduce(lambda x, y: x + y[1], files_to_execute, [])
        if f_name.endswith(".py") and (not test_files or files_to_execute):
            path = os.path.join(base_dir, f_name)
            with open(path) as f:
                code = f.read()
            for case in _collect_file_tests(code, path, lines_to_execute):
                yield case
