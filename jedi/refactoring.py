""" Introduce refactoring """

import api
import modules
import difflib


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
            print old_path, new_path, old_l, new_l
            if old_path:
                udiff = difflib.unified_diff(old_l, new_l)
            else:
                udiff = difflib.unified_diff(old_l, new_l, old_path, new_path)
            texts.append('\n'.join(udiff))
        return '\n'.join(texts)


def rename(new_name, source, *args, **kwargs):
    """ The `args` / `kwargs` params are the same as in `api.Script`.
    :param operation: The refactoring operation to execute.
    :type operation: str
    :type source: str
    :return: list of changed lines/changed files
    """
    dct = {}
    def process(path, old_lines, new_lines):
        if new_lines is not None:  # goto next file, save last
            dct[path] = path, old_lines, new_lines

    script = api.Script(source, *args, **kwargs)
    old_names = script.related_names()
    order = sorted(old_names, key=lambda x: (x.module_path, x.start_pos),
                            reverse=True)

    current_path = object()
    new_lines = old_lines = None
    for name in order:
        assert isinstance(name, api.api_classes.RelatedName)
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
        new_lines[nr - 1] = line[:indent] + new_name + \
                            line[indent + len(name.name_part):]

    process(current_path, old_lines, new_lines)
    return Refactoring(dct)
