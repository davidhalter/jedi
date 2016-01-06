"""
Introduce some basic refactoring functions to |jedi|. This module is still in a
very early development stage and needs much testing and improvement.

.. warning:: I won't do too much here, but if anyone wants to step in, please
             do. Refactoring is none of my priorities

It uses the |jedi| `API <plugin-api.html>`_ and supports currently the
following functions (sometimes bug-prone):

- rename
- extract variable
- inline variable
"""
import difflib

from itertools import groupby
from jedi import common
from jedi.evaluate import helpers
from jedi.parser import tree as pt
from common import content, source_to_unicode, splitlines


class Pos(object):
    def __init__(self, line, column):
        self.line = line
        self.column = column
        self.real_line = line - 1


class PosRange(object):
    def __init__(self, start, stop):
        self.start = start
        self.stop = stop


class Content(object):
    def __init__(self, lines=()):
        self.lines = list(lines)

    def __getitem__(self, index):
        start_line_slice_start = index.start.column
        start_line_slice_stop = None
        first_line = []
        whole_lines = []
        end_line = []
        if index.start.real_line < index.stop.real_line:
            whole_lines.extend(
                    self.lines[index.start.real_line + 1: index.stop.real_line]
            )
            end_line = [
                self.lines[index.stop.real_line][:index.stop.column]
            ]
        else:
            start_line_slice_stop = index.stop.column
        fst_selected_line = self.lines[index.start.real_line]
        first_line.append(
                fst_selected_line[start_line_slice_start:start_line_slice_stop]
        )
        return first_line + whole_lines + end_line

    def __delitem__(self, index):
        fst_affected_line = self.lines[index.start.real_line]
        lst_affected_line = self.lines[index.stop.real_line]
        fst_ln_slice_start = index.start.column
        fst_ln_slice_stop = len(fst_affected_line)
        lst_ln_remainder = ''
        if index.start.real_line == index.stop.real_line:
            fst_ln_slice_stop = index.stop.column
        else:
            del self.lines[index.start.real_line + 1: index.stop.real_line]
            del self.lines[index.stop.real_line]
            lst_ln_remainder = lst_affected_line[index.stop.column:]
        p1 = fst_affected_line[:fst_ln_slice_start]
        p2 = fst_affected_line[fst_ln_slice_stop:]
        fst_ln_remainder = p1 + p2
        self.lines[index.start.real_line] = fst_ln_remainder + lst_ln_remainder
        if self.lines[index.start.real_line] == '':
            del self.lines[index.start.real_line]

    def __setitem__(self, index, value):
        del self[index]
        line = self.lines[index.start.real_line]
        part_1 = line[:index.start.column]
        part_2 = line[index.start.column:]
        self.lines[index.start.real_line] = ''.join((part_1, value, part_2))

    @classmethod
    def from_file(cls, path):
        return cls(splitlines(source_to_unicode(content(path))))


class Refactoring(object):
    def __init__(self, change_dct):
        """ """ """ """ """ """  """
        .__init__(self)

        :param change_dct: dict(old_path=(new_path, old_lines, new_lines))
        """
        self.change_dct = change_dct

    def old_files(self):
        dct = {}
        for old_path, (new_path, old_l, new_l) in self.change_dct.items():
            dct[new_path] = '\n'.join(new_l)
        return dct

    def new_files(self):
        dct = {}
        for old_path, (new_path, old_l, new_l) in self.change_dct.items():
            dct[new_path] = '\n'.join(new_l)
        return dct

    def diff(self):
        texts = []
        for old_path, (new_path, old_l, new_l) in self.change_dct.items():
            if old_path:
                udiff = difflib.unified_diff(old_l, new_l)
            else:
                udiff = difflib.unified_diff(old_l, new_l, old_path, new_path)
            texts.append('\n'.join(udiff))
        return '\n'.join(texts)


def rename(script, new_name):
    def by_module_path(script):
        return script.module_path

    usages = (u for u in sorted(script.usages(), key=by_module_path)
              if not u.in_builtin_module())
    usages_by_file = groupby(usages, by_module_path)
    out = [(m_path, change_for_rename(m_path, usages, new_name))
           for m_path, usages in usages_by_file]
    return Refactoring(dict(out))


def change_for_rename(path, usages, new_name):
    c = Content.from_file(path)
    old_lines = c.lines[:]
    for u in usages:
        start_pos = Pos(u.line, u.column)
        end_pos = Pos(u.line, u.column + len(u.name))
        c[PosRange(start_pos, end_pos)] = new_name
    return path, old_lines, c.lines


def extract(script, new_name):
    """ The `args` / `kwargs` params are the same as in `api.Script`.
    :param operation: The refactoring operation to execute.
    :type operation: str
    :type source: str
    :return: list of changed lines/changed files
    """
    new_lines = common.splitlines(common.source_to_unicode(script.source))
    old_lines = new_lines[:]

    user_stmt = script._parser.user_stmt()

    # TODO care for multiline extracts
    dct = {}
    if user_stmt:
        pos = script._pos
        line_index = pos[0] - 1
        arr, index = helpers.array_for_pos(user_stmt, pos)
        if arr is not None:
            start_pos = arr[index].start_pos
            end_pos = arr[index].end_pos

            # take full line if the start line is different from end line
            e = end_pos[1] if end_pos[0] == start_pos[0] else None
            start_line = new_lines[start_pos[0] - 1]
            text = start_line[start_pos[1]:e]
            for l in range(start_pos[0], end_pos[0] - 1):
                text += '\n' + l
            if e is None:
                end_line = new_lines[end_pos[0] - 1]
                text += '\n' + end_line[:end_pos[1]]

            # remove code from new lines
            t = text.lstrip()
            del_start = start_pos[1] + len(text) - len(t)

            text = t.rstrip()
            del_end = len(t) - len(text)
            if e is None:
                new_lines[end_pos[0] - 1] = end_line[end_pos[1] - del_end:]
                e = len(start_line)
            else:
                e = e - del_end
            start_line = start_line[:del_start] + new_name + start_line[e:]
            new_lines[start_pos[0] - 1] = start_line
            new_lines[start_pos[0]:end_pos[0] - 1] = []

            # add parentheses in multiline case
            open_brackets = ['(', '[', '{']
            close_brackets = [')', ']', '}']
            if '\n' in text and not (text[0] in open_brackets and text[-1] ==
                close_brackets[open_brackets.index(text[0])]):
                text = '(%s)' % text

            # add new line before statement
            indent = user_stmt.start_pos[1]
            new = "%s%s = %s" % (' ' * indent, new_name, text)
            new_lines.insert(line_index, new)
    dct[script.path] = script.path, old_lines, new_lines
    return Refactoring(dct)


def inline(script):
    """
    :type script: api.Script
    """
    new_lines = common.splitlines(common.source_to_unicode(script.source))

    dct = {}

    definitions = script.goto_assignments()
    with common.ignored(AssertionError):
        assert len(definitions) == 1
        stmt = definitions[0]._definition
        usages = script.usages()
        inlines = [r for r in usages
                   if not stmt.start_pos <= (r.line, r.column) <= stmt.end_pos]
        inlines = sorted(inlines, key=lambda x: (x.module_path, x.line, x.column),
                         reverse=True)
        expression_list = stmt.expression_list()
        # don't allow multiline refactorings for now.
        assert stmt.start_pos[0] == stmt.end_pos[0]
        index = stmt.start_pos[0] - 1

        line = new_lines[index]
        replace_str = line[expression_list[0].start_pos[1]:stmt.end_pos[1] + 1]
        replace_str = replace_str.strip()
        # tuples need parentheses
        if expression_list and isinstance(expression_list[0], pr.Array):
            arr = expression_list[0]
            if replace_str[0] not in ['(', '[', '{'] and len(arr) > 1:
                replace_str = '(%s)' % replace_str

        # if it's the only assignment, remove the statement
        if len(stmt.get_defined_names()) == 1:
            line = line[:stmt.start_pos[1]] + line[stmt.end_pos[1]:]

        dct = _rename(inlines, replace_str)
        # remove the empty line
        new_lines = dct[script.path][2]
        if line.strip():
            new_lines[index] = line
        else:
            new_lines.pop(index)

    return Refactoring(dct)
