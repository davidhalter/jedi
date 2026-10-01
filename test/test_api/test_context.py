import os
import subprocess
import sys

import pytest


def _iter_hierarchy(context):
    def iter(context):
        while context is not None:
            yield context
            context = context.parent()

    return reversed(list(iter(context)))


func_code = '''\
def func1(x, y):
    pass

def func2():
 what ?
i = 3

def func3():
    1'''
cls_code = '''\
class Foo:
    def x():
        def y():
            pass
'''
cls_nested = '''\
class C:
    class D:
        def f():
            pass
'''
lambda_ = '''\
def x():
    (lambda x:
     lambda: y
    )
'''
comprehension = '''
def f(x):
    [x
    for
    x
    in x
    ]'''

with_brackets = '''\
def x():
    [

    ]
'''

async_code = '''\
async def coro():
    return None
'''
async_method = '''\
class C:
    async def coro(self):
        return None
'''
async_nested = '''\
async def outer():
    async def inner():
        return None
'''


@pytest.mark.parametrize(
    'code, line, column, full_name, expected_parents', [
        ('', None, None, 'myfile', []),
        (' ', None, 0, 'myfile', []),

        (func_code, 1, 0, 'myfile', []),
        (func_code, 1, None, 'myfile.func1', ['func1']),
        (func_code, 1, 1, 'myfile.func1', ['func1']),
        (func_code, 1, 4, 'myfile.func1', ['func1']),
        (func_code, 1, 10, 'myfile.func1', ['func1']),

        (func_code, 3, 0, 'myfile', []),
        (func_code, 5, None, 'myfile.func2', ['func2']),
        (func_code, 6, None, 'myfile', []),
        (func_code, 7, None, 'myfile', []),
        (func_code, 9, None, 'myfile.func3', ['func3']),

        (cls_code, None, None, 'myfile', []),
        (cls_code + ' ', None, None, 'myfile.Foo', ['Foo']),
        (cls_code + ' ' * 3, None, None, 'myfile.Foo', ['Foo']),
        (cls_code + ' ' * 4, None, None, 'myfile.Foo', ['Foo']),
        (cls_code + ' ' * 5, None, None, 'myfile.Foo.x', ['Foo', 'x']),
        (cls_code + ' ' * 8, None, None, 'myfile.Foo.x', ['Foo', 'x']),
        (cls_code + ' ' * 12, None, None, None, ['Foo', 'x', 'y']),

        (cls_code, 4, 0, 'myfile', []),
        (cls_code, 4, 3, 'myfile.Foo', ['Foo']),
        (cls_code, 4, 4, 'myfile.Foo', ['Foo']),
        (cls_code, 4, 5, 'myfile.Foo.x', ['Foo', 'x']),
        (cls_code, 4, 8, 'myfile.Foo.x', ['Foo', 'x']),
        (cls_code, 4, 12, None, ['Foo', 'x', 'y']),
        (cls_code, 1, 1, 'myfile.Foo', ['Foo']),

        (cls_nested, 4, None, 'myfile.C.D.f', ['C', 'D', 'f']),
        (cls_nested, 4, 3, 'myfile.C', ['C']),

        (lambda_, 2, 9, 'myfile.x', ['x']),  # the lambda keyword
        (lambda_, 2, 13, 'myfile.x', ['x']),  # the lambda param
        (lambda_, 3, 0, 'myfile', []),  # Within brackets, but they are ignored.
        (lambda_, 3, 8, 'myfile.x', ['x']),
        (lambda_, 3, None, 'myfile.x', ['x']),

        (comprehension, 2, None, 'myfile.f', ['f']),
        (comprehension, 3, None, 'myfile.f', ['f']),
        (comprehension, 4, None, 'myfile.f', ['f']),
        (comprehension, 5, None, 'myfile.f', ['f']),
        (comprehension, 6, None, 'myfile.f', ['f']),

        # Brackets are just ignored.
        (with_brackets, 3, None, 'myfile', []),
        (with_brackets, 4, 4, 'myfile.x', ['x']),
        (with_brackets, 4, 5, 'myfile.x', ['x']),

        (async_code, 2, 0, 'myfile', []),
        (async_code, 2, 4, 'myfile.coro', ['coro']),
        (async_code, 2, 5, 'myfile.coro', ['coro']),
        (async_code, 2, None, 'myfile.coro', ['coro']),
        ('@decorator\n' + async_code, 3, 0, 'myfile', []),
        ('@decorator\n' + async_code, 3, 4, 'myfile.coro', ['coro']),
        ('@decorator\n' + async_code, 3, 5, 'myfile.coro', ['coro']),
        (async_method, 3, 4, 'myfile.C', ['C']),
        (async_method, 3, 8, 'myfile.C.coro', ['C', 'coro']),
        (async_method, 3, 9, 'myfile.C.coro', ['C', 'coro']),
        (async_nested, 3, 0, 'myfile', []),
        (async_nested, 3, 4, 'myfile.outer', ['outer']),
        (async_nested, 3, 8, None, ['outer', 'inner']),
        (async_nested, 3, 9, None, ['outer', 'inner']),
    ]
)
def test_context(Script, code, line, column, full_name, expected_parents):
    context = Script(code, path='/foo/myfile.py').get_context(line, column)
    assert context.full_name == full_name
    parent_names = [d.name for d in _iter_hierarchy(context)]
    assert parent_names == ['myfile'] + expected_parents


_REPRO_CACHE_PY = """\
import os


def deco1(maxsize):
    def func_wrapper(func):
        def wrapper(*args, **kwargs):
            print('deco1')
            retval = func(*args, **kwargs)
            return retval
        return wrapper
    return func_wrapper


def deco2(func):
    print('deco2')
    return func


if os.getenv('CHOICE') == "deco1":
    deco = deco1(1000)
else:
    deco = deco2
"""

_REPRO_MAIN_PY = """\
from cache import deco

class Expr:
    flag = True

    __slots__ = []

    def __new__(cls, expr, *args, **kwargs):
        obj = object.__new__(cls)
        obj.args = args
        return obj

    @property
    def func(self):
        return self.__class__

    @deco
    def contains(self, expr):
        if expr.flag:
            pass
        obj = self.func(expr, *self.args[1:])
        return self.contains(obj)

    def __contains__(self, other):
        result = self.contains(other)
        return result
"""

_REPRO_RUNNER = """\
import os
import sys
import tempfile

import jedi

jedi.settings.cache_directory = tempfile.mkdtemp()

project_path = sys.argv[1]
main_path = os.path.join(project_path, 'main.py')
with open(main_path) as f:
    code = f.read()
project = jedi.Project(path=project_path, environment_path=None)
script = jedi.Script(code=code, path=main_path, project=project)
for _ in range(100):
    try:
        definitions = script.goto(19, 17, follow_imports=True)
        definitions[0].full_name
    except AttributeError:
        raise
    except Exception:
        continue
"""

_REPO_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.skipif(sys.version_info >= (3, 13), reason=(
    'this reproduction does not crash on the unfixed code on Python 3.13, '
    'so it cannot catch the regression there'))
def test_goto_does_not_walk_past_module_root(tmpdir):
    # Regression test for #2077. Script.goto() on this decorated method used
    # to crash with AttributeError: 'NoneType' object has no attribute
    # 'type': while resolving dynamic parameters, a name inside one method
    # gets evaluated from a sibling method's execution context, and the
    # additional knowledge walk climbs past the module root.
    #
    # In a single process the crash cannot be triggered deterministically:
    # which inference interleaving runs depends on hash randomization and on
    # environment subprocess timing. The reproduction below only uses the
    # public API (the exact script from the issue), so it is run in fresh
    # subprocesses with fixed hash seeds. On the unfixed code most of them
    # crash on Python 3.12 (measured roughly two out of three). A green run
    # on a Python version where the reproduction is silent does not prove
    # the bug is absent there.
    tmpdir.join('cache.py').write(_REPRO_CACHE_PY)
    tmpdir.join('main.py').write(_REPRO_MAIN_PY)
    env = dict(os.environ)
    pythonpath = [_REPO_ROOT]
    if env.get('PYTHONPATH'):
        pythonpath.append(env['PYTHONPATH'])
    env['PYTHONPATH'] = os.pathsep.join(pythonpath)
    for seed in range(10):
        env['PYTHONHASHSEED'] = str(seed)
        result = subprocess.run(
            [sys.executable, '-c', _REPRO_RUNNER, str(tmpdir)],
            env=env, capture_output=True, text=True)
        assert result.returncode == 0, (
            'reproduction crashed with PYTHONHASHSEED=%s:\n%s'
            % (seed, result.stderr))
