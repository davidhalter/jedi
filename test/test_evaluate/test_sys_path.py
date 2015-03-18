import os

from jedi._compatibility import unicode
from jedi.parser import Parser, load_grammar
from jedi.evaluate import sys_path, Evaluator


def test_paths_from_assignment():
    def paths(src):
        grammar = load_grammar()
        stmt = Parser(grammar, unicode(src)).module.statements[0]
        return list(sys_path._paths_from_assignment(Evaluator(grammar), stmt))

    assert paths('sys.path[0:0] = ["a"]') == ['a']
    assert paths('sys.path = ["b", 1, x + 3, y, "c"]') == ['b', 'c']
    assert paths('sys.path = a = ["a"]') == ['a']

    # Fail for complicated examples.
    assert paths('sys.path, other = ["a"], 2') == []


def test_get_sys_path(monkeypatch):
    monkeypatch.setenv('VIRTUAL_ENV', os.path.join(os.path.dirname(__file__),
                                                   'egg-link', 'venv'))
    # Mock os.listdir to test the new functionality of _get_venv_sitepackages()
    def listdir(vdir):
        # When glob.glob is used in check_virtual_env(), it calls os.listdir()
        # with the returned site-packages directory. As such, we mimic the
        # expected 'egg_link.egg-link' response. The other call is in
        # _get_venv_sitepackages() which expects a single 'pythonX.X' list.
        if vdir.endswith('packages'):
            return [os.path.join(vdir, 'egg_link.egg-link')]
        return ['python3.4']

    monkeypatch.setattr('os.listdir', listdir)

    python_path = os.path.join(os.path.dirname(__file__), 'egg-link', 'venv',
                               'lib', 'python3.4', 'site-packages')

    assert '/path/from/egg-link' in sys_path.get_sys_path()
    assert python_path in sys_path.get_sys_path()
