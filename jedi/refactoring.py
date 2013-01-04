""" Introduce refactoring """

import api


class Refactoring(object):
    def __init__(self, changed_lines, renamed_files):
        self.changed_lines = changed_lines
        self.renamed_files = renamed_files

    def diff(self):
        return ''


def rename(new_name, *args, **kwargs):
    """ The `args` / `kwargs` params are the same as in `api.Script`.
    :param operation: The refactoring operation to execute.
    :type operation: str
    :return: list of changed lines/changed files
    """
    script = api.Script(*args, **kwargs)
    old_names = script.related_names()
    return []
