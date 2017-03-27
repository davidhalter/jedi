import os
from textwrap import dedent

from jedi._compatibility import u
from jedi.evaluate.sys_path import (_get_parent_dir_with_file,
                                    _get_buildout_script_paths,
                                    sys_path_with_modifications,
                                    _check_module)
from jedi.evaluate import Evaluator
from jedi.evaluate.representation import ModuleContext
from jedi.parser.python import parse, load_grammar

from ..helpers import cwd_at


def check_module_test(code):
    grammar = load_grammar()
    module_context = ModuleContext(Evaluator(grammar), parse(code), path=None)
    return _check_module(module_context)


@cwd_at('test/test_evaluate/buildout_project/src/proj_name')
def test_parent_dir_with_file():
    parent = _get_parent_dir_with_file(
        os.path.abspath(os.curdir), 'buildout.cfg')
    assert parent is not None
    assert parent.endswith(os.path.join('test', 'test_evaluate', 'buildout_project'))


@cwd_at('test/test_evaluate/buildout_project/src/proj_name')
def test_buildout_detection():
    scripts = _get_buildout_script_paths(os.path.abspath('./module_name.py'))
    assert len(scripts) == 1
    curdir = os.path.abspath(os.curdir)
    appdir_path = os.path.normpath(os.path.join(curdir, '../../bin/app'))
    assert scripts[0] == appdir_path


def test_append_on_non_sys_path():
    code = dedent(u("""
        class Dummy(object):
            path = []

        d = Dummy()
        d.path.append('foo')"""))

    paths = check_module_test(code)
    assert len(paths) > 0
    assert 'foo' not in paths


def test_path_from_invalid_sys_path_assignment():
    code = dedent(u("""
        import sys
        sys.path = 'invalid'"""))

    paths = check_module_test(code)
    assert len(paths) > 0
    assert 'invalid' not in paths


@cwd_at('test/test_evaluate/buildout_project/src/proj_name/')
def test_sys_path_with_modifications():
    code = dedent("""
        import os
    """)

    path = os.path.abspath(os.path.join(os.curdir, 'module_name.py'))
    grammar = load_grammar()
    module_node = parse(code, path=path)
    module_context = ModuleContext(Evaluator(grammar), module_node, path=path)
    paths = sys_path_with_modifications(module_context.evaluator, module_context)
    assert '/tmp/.buildout/eggs/important_package.egg' in paths


def test_path_from_sys_path_assignment():
    code = dedent(u("""
        #!/usr/bin/python

        import sys
        sys.path[0:0] = [
          '/usr/lib/python3.4/site-packages',
          '/home/test/.buildout/eggs/important_package.egg'
          ]

        path[0:0] = [1]

        import important_package

        if __name__ == '__main__':
            sys.exit(important_package.main())"""))

    paths = check_module_test(code)
    assert 1 not in paths
    assert '/home/test/.buildout/eggs/important_package.egg' in paths
