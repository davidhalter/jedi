import os

from jedi.plugins import typeshed
from jedi.evaluate.context import TreeInstance, BoundMethod, FunctionContext
from parso.utils import PythonVersionInfo
from jedi.evaluate.filters import TreeNameDefinition

TYPESHED_PYTHON3 = os.path.join(typeshed._TYPESHED_PATH, 'stdlib', '3')


def test_get_typeshed_directories():
    def get_dirs(version_info):
        return {
            d.replace(typeshed._TYPESHED_PATH, '').lstrip(os.path.sep)
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
    if environment.version_info.major == 2:
        # In Python 2, the definitions are a bit weird in typeshed. Therefore
        # it's for now a FunctionContext.
        expected = FunctionContext
    else:
        expected = typeshed.StubFunctionContext

    code = 'import threading; threading.current_thread'
    def_, = Script(code).goto_definitions()
    context = def_._name._context
    assert isinstance(context, expected), context

    def_, = Script(code + '()').goto_definitions()
    context = def_._name._context
    assert isinstance(context, TreeInstance)
    assert isinstance(context.class_context, typeshed.StubOnlyClass), context

    def_, = Script('import threading; threading.Thread').goto_definitions()
    assert isinstance(def_._name._context, typeshed.StubClassContext), def_


def test_keywords_variable(Script):
    code = 'import keyword; keyword.kwlist'
    def_, = Script(code).goto_definitions()
    assert def_.name == 'Sequence'
    # This points towards the typeshed implementation
    assert typeshed._TYPESHED_PATH in def_.module_path


def test_class(Script):
    def_, = Script('import threading; threading.Thread').goto_definitions()
    context = def_._name._context
    assert isinstance(context, typeshed.StubClassContext), context


def test_instance(Script):
    def_, = Script('import threading; threading.Thread()').goto_definitions()
    context = def_._name._context
    assert isinstance(context, TreeInstance)
    assert isinstance(context.class_context, typeshed.StubClassContext), context


def test_class_function(Script):
    def_, = Script('import threading; threading.Thread.getName').goto_definitions()
    context = def_._name._context
    assert isinstance(context, typeshed.StubFunctionContext), context


def test_method(Script):
    code = 'import threading; threading.Thread().getName'
    def_, = Script(code).goto_definitions()
    context = def_._name._context
    assert isinstance(context, BoundMethod), context
    assert isinstance(context._wrapped_context, typeshed.StubFunctionContext), context

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
    # This should only exist on Windows, but cmpletion should happen
    # everywhere.
    def_, = Script('import sys; sys.getwindowsversion().major').goto_definitions()
    if environment.version_info.major == 2:
        assert def_.name == 'ellipsis'
    else:
        assert def_.name == 'int'


def test_sys_hexversion(Script):
    script = Script('import sys; sys.hexversion')
    def_, = script.completions()
    assert isinstance(def_._name, typeshed.CompiledStubName), def_._name
    assert isinstance(def_._name._wrapped_name, TreeNameDefinition)
    assert typeshed._TYPESHED_PATH in def_.module_path
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
