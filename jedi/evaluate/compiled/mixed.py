"""
Used only for REPL Completion.
"""

import inspect
import os

from jedi.parser.python import parse
from jedi.evaluate import compiled
from jedi.cache import underscore_memoization
from jedi.evaluate import imports
from jedi.evaluate.context import Context
from jedi.evaluate.cache import memoize_default


class MixedObject(object):
    """
    A ``MixedObject`` is used in two ways:

    1. It uses the default logic of ``parser.python.tree`` objects,
    2. except for getattr calls. The names dicts are generated in a fashion
       like ``CompiledObject``.

    This combined logic makes it possible to provide more powerful REPL
    completion. It allows side effects that are not noticable with the default
    parser structure to still be completeable.

    The biggest difference from CompiledObject to MixedObject is that we are
    generally dealing with Python code and not with C code. This will generate
    fewer special cases, because we in Python you don't have the same freedoms
    to modify the runtime.
    """
    def __init__(self, evaluator, parent_context, compiled_object, tree_context):
        self.evaluator = evaluator
        self.parent_context = parent_context
        self.compiled_object = compiled_object
        self._context = tree_context
        self.obj = compiled_object.obj

    # We have to overwrite everything that has to do with trailers, name
    # lookups and filters to make it possible to route name lookups towards
    # compiled objects and the rest towards tree node contexts.
    def eval_trailer(*args, **kwags):
        return Context.eval_trailer(*args, **kwags)

    def py__getattribute__(*args, **kwargs):
        return Context.py__getattribute__(*args, **kwargs)

    def get_filters(self, *args, **kwargs):
        yield MixedObjectFilter(self.evaluator, self)

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, repr(self.obj))

    def __getattr__(self, name):
        return getattr(self._context, name)


class MixedName(compiled.CompiledName):
    """
    The ``CompiledName._compiled_object`` is our MixedObject.
    """
    @property
    def start_pos(self):
        contexts = list(self.infer())
        if not contexts:
            # This means a start_pos that doesn't exist (compiled objects).
            return (0, 0)
        return contexts[0].name.start_pos

    @start_pos.setter
    def start_pos(self, value):
        # Ignore the __init__'s start_pos setter call.
        pass

    @underscore_memoization
    def infer(self):
        obj = self.parent_context.obj
        try:
            obj = getattr(obj, self.string_name)
        except AttributeError:
            # Happens e.g. in properties of
            # PyQt4.QtGui.QStyleOptionComboBox.currentText
            # -> just set it to None
            obj = None
        return [create(self._evaluator, obj, parent_context=self.parent_context)]

    @property
    def api_type(self):
        return next(iter(self.infer())).api_type


class MixedObjectFilter(compiled.CompiledObjectFilter):
    name_class = MixedName

    def __init__(self, evaluator, mixed_object, is_instance=False):
        super(MixedObjectFilter, self).__init__(
            evaluator, mixed_object, is_instance)
        self._mixed_object = mixed_object

    #def _create(self, name):
        #return MixedName(self._evaluator, self._compiled_object, name)


@memoize_default(evaluator_is_first_arg=True)
def _load_module(evaluator, path, python_object):
    module = parse(
        grammar=evaluator.grammar,
        path=path,
        cache=True,
        diff_cache=True
    ).get_root_node()
    python_module = inspect.getmodule(python_object)

    evaluator.modules[python_module.__name__] = module
    return module


def source_findable(python_object):
    """Check if inspect.getfile has a chance to find the source."""
    return (inspect.ismodule(python_object) or
            inspect.isclass(python_object) or
            inspect.ismethod(python_object) or
            inspect.isfunction(python_object) or
            inspect.istraceback(python_object) or
            inspect.isframe(python_object) or
            inspect.iscode(python_object))


def find_syntax_node_name(evaluator, python_object):
    try:
        if not source_findable(python_object):
            raise TypeError  # Prevents computation of `repr` within inspect.
        path = inspect.getsourcefile(python_object)
    except TypeError:
        # The type might not be known (e.g. class_with_dict.__weakref__)
        return None, None
    if path is None or not os.path.exists(path):
        # The path might not exist or be e.g. <stdin>.
        return None, None

    module = _load_module(evaluator, path, python_object)

    if inspect.ismodule(python_object):
        # We don't need to check names for modules, because there's not really
        # a way to write a module in a module in Python (and also __name__ can
        # be something like ``email.utils``).
        return module, path

    try:
        name_str = python_object.__name__
    except AttributeError:
        # Stuff like python_function.__code__.
        return None, None

    if name_str == '<lambda>':
        return None, None  # It's too hard to find lambdas.

    # Doesn't always work (e.g. os.stat_result)
    try:
        names = module.get_used_names()[name_str]
    except KeyError:
        return None, None
    names = [n for n in names if n.is_definition()]

    try:
        code = python_object.__code__
        # By using the line number of a code object we make the lookup in a
        # file pretty easy. There's still a possibility of people defining
        # stuff like ``a = 3; foo(a); a = 4`` on the same line, but if people
        # do so we just don't care.
        line_nr = code.co_firstlineno
    except AttributeError:
        pass
    else:
        line_names = [name for name in names if name.start_pos[0] == line_nr]
        # There's a chance that the object is not available anymore, because
        # the code has changed in the background.
        if line_names:
            return line_names[-1].parent, path

    # It's really hard to actually get the right definition, here as a last
    # resort we just return the last one. This chance might lead to odd
    # completions at some points but will lead to mostly correct type
    # inference, because people tend to define a public name in a module only
    # once.
    return names[-1].parent, path


@compiled.compiled_objects_cache('mixed_cache')
def create(evaluator, obj, parent_context=None, *args):
    tree_node, path = find_syntax_node_name(evaluator, obj)

    compiled_object = compiled.create(
        evaluator, obj, parent_context=parent_context.compiled_object)
    if tree_node is None:
        return compiled_object

    module_node = tree_node.get_root_node()
    if parent_context.tree_node.get_root_node() == module_node:
        module_context = parent_context.get_root_context()
    else:
        from jedi.evaluate.representation import ModuleContext
        module_context = ModuleContext(evaluator, module_node, path=path)
        name = compiled_object.get_root_context().py__name__()
        imports.add_module(evaluator, name, module_context)

    tree_context = module_context.create_context(
        tree_node,
        node_is_context=True,
        node_is_object=True
    )

    return MixedObject(
        evaluator,
        parent_context,
        compiled_object,
        tree_context=tree_context
    )

