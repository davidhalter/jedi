import os
import sys

from jedi.evaluate.sys_path import get_venv_path


class Project(object):
    def __init__(self, sys_path=None):
        if sys_path is None:
            venv = os.getenv('VIRTUAL_ENV')
            if venv:
                sys_path = get_venv_path(venv)

        if sys_path is None:
            sys_path = sys.path

        sys_path = list(sys_path)

        try:
            sys_path.remove('')
        except ValueError:
            pass

        self.sys_path = sys_path
