""" Introduce refactoring """

from __future__ import with_statement

import modules
import difflib
import helpers


class Refactoring(object):
    def __init__(self, change_dct):
        """
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
    """ The `args` / `kwargs` params are the same as in `api.Script`.
    :param operation: The refactoring operation to execute.
    :type operation: str
    :type source: str
    :return: list of changed lines/changed files
    """
    return Refactoring(_rename(script.related_names(), new_name))


def _rename(names, replace_str):
    """ For both rename and inline. """
    order = sorted(names, key=lambda x: (x.module_path, x.start_pos),
                            reverse=True)
    def process(path, old_lines, new_lines):
        if new_lines is not None:  # goto next file, save last
            dct[path] = path, old_lines, new_lines

    dct = {}
    current_path = object()
    new_lines = old_lines = None
    for name in order:
        if name.in_builtin_module():
            continue
        if current_path != name.module_path:
            current_path = name.module_path

            process(current_path, old_lines, new_lines)
            if current_path is not None:
                # None means take the source that is a normal param.
                with open(current_path) as f:
                    source = f.read()

            new_lines = modules.source_to_unicode(source).splitlines()
            old_lines = new_lines[:]

        nr, indent = name.start_pos
        line = new_lines[nr - 1]
        new_lines[nr - 1] = line[:indent] + replace_str + \
                            line[indent + len(name.name_part):]
    process(current_path, old_lines, new_lines)
    return dct


def extract(script, new_name):
    """ The `args` / `kwargs` params are the same as in `api.Script`.
    :param operation: The refactoring operation to execute.
    :type operation: str
    :type source: str
    :return: list of changed lines/changed files
    """
    new_lines = modules.source_to_unicode(script.source).splitlines()
    old_lines = new_lines[:]

    user_stmt = script._parser.user_stmt

    # TODO care for multiline extracts
    dct = {}
    if user_stmt:
        pos = script.pos
        line_index = pos[0] - 1
        arr, index = helpers.array_for_pos(user_stmt.get_assignment_calls(),
                                            pos)
        if arr:
            s = arr.start_pos[0], arr.start_pos[1] + 1
            positions = [s] + arr.arr_el_pos + [arr.end_pos]
            start_pos = positions[index]
            end_pos = positions[index + 1][0], positions[index + 1][1] - 1

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
            new_lines[start_pos[0]:end_pos[0]-1] = []

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
    dct[script.source_path] = script.source_path, old_lines, new_lines
    return Refactoring(dct)


def inline(script):
    """
    :type script: api.Script
    """
    new_lines = modules.source_to_unicode(script.source).splitlines()

    dct = {}

    definitions = script.goto()
    try:
        assert len(definitions) == 1
        stmt = definitions[0].definition
        related_names = script.related_names()
        inlines = [r for r in related_names
                        if not stmt.start_pos <= r.start_pos <= stmt.end_pos]
        inlines = sorted(inlines, key=lambda x: (x.module_path, x.start_pos),
                                                reverse=True)
        ass = stmt.get_assignment_calls()
        # don't allow multiline refactorings for now.
        assert ass.start_pos[0] == ass.end_pos[0]
        index = ass.start_pos[0] - 1

        line = new_lines[index]
        replace_str = line[ass.start_pos[1]:ass.end_pos[1] + 1]
        replace_str = replace_str.strip()
        # tuples need parentheses
        if len(ass.values) > 1:
            replace_str = '(%s)' % replace_str

        # if it's the only assignment, remove the statement
        if len(stmt.set_vars) == 1:
            line = line[:stmt.start_pos[1]] + line[stmt.end_pos[1]:]


        dct = _rename(inlines, replace_str)
        # remove the empty line
        new_lines = dct[script.source_path][2]
        if line.strip():
            new_lines[index] = line
        else:
            new_lines.pop(index)

    except AssertionError:
        pass

    return Refactoring(dct)
