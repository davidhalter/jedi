import os

import pytest
from parso.utils import PythonVersionInfo

from jedi.api.project import Project
from jedi.evaluate.gradual import typeshed, stub_context
from jedi.evaluate.context import TreeInstance, BoundMethod, FunctionContext, \
    MethodContext, ClassContext
from test.helpers import root_dir

TYPESHED_PYTHON3 = os.path.join(typeshed.TYPESHED_PATH, 'stdlib', '3')


def test_get_typeshed_directories():
    def get_dirs(version_info):
        return {
            d.replace(typeshed.TYPESHED_PATH, '').lstrip(os.path.sep)
            for d in typeshed._get_typeshed_directories(version_info)
        }

    def transform(set_):
        return {x.replace('/', os.path.sep) for x in set_}

    dirs = get_dirs(PythonVersionInfo(2, 7))
    assert dirs == transform({'stdlib/2and3', 'stdlib/2', 'third_party/2and3', 'third_party/2'})

    dirs = get_dirs(PythonVersionInfo(3, 4))
    assert dirs == transform({'stdlib/2and3', 'stdlib/3', 'third_party/2and3', 'third_party/3'})

    dirs = get_dirs(PythonVersionInfo(3, 5))
    assert dirs == transform({'stdlib/2and3', 'stdlib/3', 'stdlib/3.5',
                              'third_party/2and3', 'third_party/3', 'third_party/3.5'})

    dirs = get_dirs(PythonVersionInfo(3, 6))
    assert dirs == transform({'stdlib/2and3', 'stdlib/3', 'stdlib/3.5',
                              'stdlib/3.6', 'third_party/2and3',
                              'third_party/3', 'third_party/3.5', 'third_party/3.6'})


def test_get_stub_files():
    def get_map(version_info):
        return typeshed._create_stub_map(version_info)

    map_ = typeshed._create_stub_map(TYPESHED_PYTHON3)
    assert map_['functools'] == os.path.join(TYPESHED_PYTHON3, 'functools.pyi')


def test_function(Script, environment):
    code = 'import threading; threading.current_thread'
    def_, = Script(code).goto_definitions()
    context = def_._name._context
    assert isinstance(context, FunctionContext), context

    def_, = Script(code + '()').goto_definitions()
    context = def_._name._context
    assert isinstance(context, TreeInstance)

    def_, = Script('import threading; threading.Thread').goto_definitions()
    assert isinstance(def_._name._context, ClassContext), def_


def test_keywords_variable(Script):
    code = 'import keyword; keyword.kwlist'
    for seq in Script(code).goto_definitions():
        assert seq.name == 'Sequence'
        # This points towards the typeshed implementation
        stub_seq, = seq.goto_assignments(only_stubs=True)
        assert typeshed.TYPESHED_PATH in stub_seq.module_path


def test_class(Script):
    def_, = Script('import threading; threading.Thread').goto_definitions()
    context = def_._name._context
    assert isinstance(context, ClassContext), context


def test_instance(Script):
    def_, = Script('import threading; threading.Thread()').goto_definitions()
    context = def_._name._context
    assert isinstance(context, TreeInstance)


def test_class_function(Script):
    def_, = Script('import threading; threading.Thread.getName').goto_definitions()
    context = def_._name._context
    assert isinstance(context, MethodContext), context


def test_method(Script):
    code = 'import threading; threading.Thread().getName'
    def_, = Script(code).goto_definitions()
    context = def_._name._context
    assert isinstance(context, BoundMethod), context
    assert isinstance(context._wrapped_context, MethodContext), context

    def_, = Script(code + '()').goto_definitions()
    context = def_._name._context
    assert isinstance(context, TreeInstance)
    assert context.class_context.py__name__() == 'str'


def test_sys_exc_info(Script):
    code = 'import sys; sys.exc_info()'
    none, def_ = Script(code + '[1]').goto_definitions()
    # It's an optional.
    assert def_.name == 'BaseException'
    assert def_.type == 'instance'
    assert none.name == 'NoneType'

    none, def_ = Script(code + '[0]').goto_definitions()
    assert def_.name == 'BaseException'
    assert def_.type == 'class'


def test_sys_getwindowsversion(Script, environment):
    # This should only exist on Windows, but type inference should happen
    # everywhere.
    definitions = Script('import sys; sys.getwindowsversion().major').goto_definitions()
    if environment.version_info.major == 2:
        assert not definitions
    else:
        def_, = definitions
        assert def_.name == 'int'


def test_sys_hexversion(Script):
    script = Script('import sys; sys.hexversion')
    def_, = script.completions()
    assert isinstance(def_._name, stub_context._StubName), def_._name
    assert typeshed.TYPESHED_PATH in def_.module_path
    def_, = script.goto_definitions()
    assert def_.name == 'int'


def test_math(Script):
    def_, = Script('import math; math.acos()').goto_definitions()
    assert def_.name == 'float'
    context = def_._name._context
    assert context


def test_type_var(Script):
    def_, = Script('import typing; T = typing.TypeVar("T1")').goto_definitions()
    assert def_.name == 'TypeVar'
    assert def_.description == 'TypeVar = object()'


@pytest.mark.parametrize(
    'code, full_name', (
        ('import math', 'math'),
        ('from math import cos', 'math.cos')
    )
)
def test_math_is_stub(Script, code, full_name):
    s = Script(code)
    cos, = s.goto_definitions()
    wanted = os.path.join('typeshed', 'stdlib', '2and3', 'math.pyi')
    assert cos.module_path.endswith(wanted)
    assert cos.is_stub() is True
    assert cos.goto_assignments(only_stubs=True) == [cos]
    assert cos.full_name == full_name

    cos, = s.goto_assignments()
    assert cos.module_path.endswith(wanted)
    assert cos.goto_assignments(only_stubs=True) == [cos]
    assert cos.is_stub() is True
    assert cos.full_name == full_name


def test_goto_stubs(Script):
    s = Script('import os; os')
    os_module, = s.goto_definitions()
    assert os_module.full_name == 'os'
    assert os_module.is_stub() is False
    stub, = os_module.goto_assignments(only_stubs=True)
    assert stub.is_stub() is True

    os_module, = s.goto_assignments()


def _assert_is_same(d1, d2):
    assert d1.name == d2.name
    assert d1.module_path == d2.module_path
    assert d1.line == d2.line
    assert d1.column == d2.column


@pytest.mark.parametrize('type_', ['goto', 'infer'])
@pytest.mark.parametrize(
    'code', [
        'import os; os.walk',
        'from collections import Counter; Counter',
        'from collections import Counter; Counter()',
        'from collections import Counter; Counter.most_common',
    ])
def test_goto_stubs_on_itself(Script, code, type_):
    """
    If goto_stubs is used on an identifier in e.g. the stdlib, we should goto
    the stub of it.
    """
    s = Script(code)
    if type_ == 'infer':
        def_, = s.goto_definitions()
    else:
        def_, = s.goto_assignments(follow_imports=True)
    stub, = def_.goto_assignments(only_stubs=True)

    script_on_source = Script(
        path=def_.module_path,
        line=def_.line,
        column=def_.column
    )
    if type_ == 'infer':
        definition, = script_on_source.goto_definitions()
    else:
        definition, = script_on_source.goto_assignments()
    same_stub, = definition.goto_assignments(only_stubs=True)
    _assert_is_same(same_stub, stub)
    _assert_is_same(definition, def_)
    assert same_stub.module_path != def_.module_path

    # And the reverse.
    script_on_stub = Script(
        path=same_stub.module_path,
        line=same_stub.line,
        column=same_stub.column
    )

    if type_ == 'infer':
        same_definition, = script_on_stub.goto_definitions()
        same_definition2, = same_stub.infer()
    else:
        same_definition, = script_on_stub.goto_assignments()
        same_definition2, = same_stub.goto_assignments()

    _assert_is_same(same_definition, definition)
    _assert_is_same(same_definition, same_definition2)


@pytest.mark.parametrize('way', ['direct', 'indirect'])
@pytest.mark.parametrize(
    'kwargs', [
        dict(only_stubs=False, prefer_stubs=False),
        dict(only_stubs=False, prefer_stubs=True),
        dict(only_stubs=True, prefer_stubs=False),
    ]
)
@pytest.mark.parametrize(
    ('code', 'full_name', 'has_stub', 'has_python'), [
        ['import os; os.walk', 'os.walk', True, True],
        ['from collections import Counter', 'collections.Counter', True, True],
        ['from collections', 'collections', True, True],
        ['from collections import Counter; Counter', 'collections.Counter', True, True],
        ['from collections import Counter; Counter()', 'collections.Counter', True, True],
        ['from collections import Counter; Counter.most_common',
         'collections.Counter.most_common', True, True],

        ['from keyword import kwlist; kwlist', 'typing.Sequence', True, True],
        #['from keyword import kwlist', 'typing.Sequence', True, True],

        ['import with_stub', 'with_stub', True, True],
        ['import with_stub', 'with_stub', True, True],
        ['import with_stub_folder.python_only', 'with_stub_folder.python_only', False, True],
        ['import stub_only', 'stub_only', True, False],
    ])
def test_infer_and_goto(Script, code, full_name, has_stub, has_python, way, kwargs):
    project = Project(os.path.join(root_dir, 'test', 'completion', 'stub_folder'))
    s = Script(code, _project=project)
    if way == 'direct':
        defs = s.goto_definitions(**kwargs)
    else:
        goto_defs = s.goto_assignments()
        defs = [d for goto_def in goto_defs for d in goto_def.infer(**kwargs)]

    only_stubs = kwargs['only_stubs']
    prefer_stubs = kwargs['prefer_stubs']
    if not has_stub and only_stubs:
        assert not defs
    else:
        assert defs

    for d in defs:
        if prefer_stubs and has_stub:
            assert d.is_stub()
        if only_stubs:
            assert d.is_stub()
        assert d.full_name == full_name
