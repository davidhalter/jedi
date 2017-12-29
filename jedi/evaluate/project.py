from jedi._compatibility import force_unicode
from jedi.evaluate.sys_path import detect_additional_paths
from jedi.cache import memoize_method


class Project(object):
    def __init__(self, sys_path=None):
        self._script_path = None

        self._base_sys_path = sys_path

    def add_script_path(self, script_path):
        self._script_path = script_path

    def add_evaluator(self, evaluator):
        self._evaluator = evaluator

    @property
    @memoize_method
    def sys_path(self):
        sys_path = self._base_sys_path
        if sys_path is None:
            sys_path = self._evaluator.environment.get_sys_path()

        sys_path = list(sys_path)
        try:
            sys_path.remove('')
        except ValueError:
            pass

        if self._script_path is None:
            return sys_path

        added_paths = map(
            force_unicode,
            detect_additional_paths(self._evaluator, self._script_path)
        )
        return sys_path + added_paths
