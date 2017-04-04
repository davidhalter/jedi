"""
Like described in the :mod:`jedi.parser.python.tree` module,
there's a need for an ast like module to represent the states of parsed
modules.

But now there are also structures in Python that need a little bit more than
that. An ``Instance`` for example is only a ``Class`` before it is
instantiated. This class represents these cases.

So, why is there also a ``Class`` class here? Well, there are decorators and
they change classes in Python 3.

Representation modules also define "magic methods". Those methods look like
``py__foo__`` and are typically mappable to the Python equivalents ``__call__``
and others. Here's a list:

====================================== ========================================
**Method**                             **Description**
-------------------------------------- ----------------------------------------
py__call__(params: Array)              On callable objects, returns types.
py__bool__()                           Returns True/False/None; None means that
                                       there's no certainty.
py__bases__()                          Returns a list of base classes.
py__mro__()                            Returns a list of classes (the mro).
py__iter__()                           Returns a generator of a set of types.
py__class__()                          Returns the class of an instance.
py__getitem__(index: int/str)          Returns a a set of types of the index.
                                       Can raise an IndexError/KeyError.
py__file__()                           Only on modules. Returns None if does
                                       not exist.
py__package__()                        Only on modules. For the import system.
py__path__()                           Only on modules. For the import system.
py__get__(call_object)                 Only on instances. Simulates
                                       descriptors.
====================================== ========================================

"""
import os
import pkgutil
import imp
import re
from itertools import chain

from jedi._compatibility import use_metaclass
from jedi.parser.python import tree
from jedi import debug
from jedi import common
from jedi.evaluate.cache import memoize_default, CachedMetaClass, NO_DEFAULT
from jedi.evaluate import compiled
from jedi.evaluate import recursion
from jedi.evaluate import iterable
from jedi.evaluate import docstrings
from jedi.evaluate import pep0484
from jedi.evaluate import param
from jedi.evaluate import flow_analysis
from jedi.evaluate import imports
from jedi.evaluate import helpers
from jedi.evaluate.filters import ParserTreeFilter, FunctionExecutionFilter, \
    GlobalNameFilter, DictFilter, ContextName, AbstractNameDefinition, \
    ParamName, AnonymousInstanceParamName, TreeNameDefinition, \
    ContextNameMixin
from jedi.evaluate.dynamic import search_params
from jedi.evaluate import context
from jedi.evaluate.context import ContextualizedNode


def apply_py__get__(context, base_context):
    try:
        method = context.py__get__
    except AttributeError:
        yield context
    else:
        for descriptor_context in method(base_context):
            yield descriptor_context


class ClassName(TreeNameDefinition):
    def __init__(self, parent_context, tree_name, name_context):
        super(ClassName, self).__init__(parent_context, tree_name)
        self._name_context = name_context

    def infer(self):
        # TODO this _name_to_types might get refactored and be a part of the
        # parent class. Once it is, we can probably just overwrite method to
        # achieve this.
        from jedi.evaluate.finder import _name_to_types
        inferred = _name_to_types(
            self.parent_context.evaluator, self._name_context, self.tree_name)

        for result_context in inferred:
            for c in apply_py__get__(result_context, self.parent_context):
                yield c


class ClassFilter(ParserTreeFilter):
    name_class = ClassName

    def _convert_names(self, names):
        return [self.name_class(self.context, name, self._node_context)
                for name in names]


class ClassContext(use_metaclass(CachedMetaClass, context.TreeContext)):
    """
    This class is not only important to extend `tree.Class`, it is also a
    important for descriptors (if the descriptor methods are evaluated or not).
    """
    api_type = 'class'

    def __init__(self, evaluator, classdef, parent_context):
        super(ClassContext, self).__init__(evaluator, parent_context=parent_context)
        self.tree_node = classdef

    @memoize_default(default=())
    def py__mro__(self):
        def add(cls):
            if cls not in mro:
                mro.append(cls)

        mro = [self]
        # TODO Do a proper mro resolution. Currently we are just listing
        # classes. However, it's a complicated algorithm.
        for lazy_cls in self.py__bases__():
            # TODO there's multiple different mro paths possible if this yields
            # multiple possibilities. Could be changed to be more correct.
            for cls in lazy_cls.infer():
                # TODO detect for TypeError: duplicate base class str,
                # e.g.  `class X(str, str): pass`
                try:
                    mro_method = cls.py__mro__
                except AttributeError:
                    # TODO add a TypeError like:
                    """
                    >>> class Y(lambda: test): pass
                    Traceback (most recent call last):
                      File "<stdin>", line 1, in <module>
                    TypeError: function() argument 1 must be code, not str
                    >>> class Y(1): pass
                    Traceback (most recent call last):
                      File "<stdin>", line 1, in <module>
                    TypeError: int() takes at most 2 arguments (3 given)
                    """
                    pass
                else:
                    add(cls)
                    for cls_new in mro_method():
                        add(cls_new)
        return tuple(mro)

    @memoize_default(default=())
    def py__bases__(self):
        arglist = self.tree_node.get_super_arglist()
        if arglist:
            args = param.TreeArguments(self.evaluator, self, arglist)
            return [value for key, value in args.unpack() if key is None]
        else:
            return [context.LazyKnownContext(compiled.create(self.evaluator, object))]

    def py__call__(self, params):
        from jedi.evaluate.instance import TreeInstance
        return set([TreeInstance(self.evaluator, self.parent_context, self, params)])

    def py__class__(self):
        return compiled.create(self.evaluator, type)

    def get_params(self):
        from jedi.evaluate.instance import AnonymousInstance
        anon = AnonymousInstance(self.evaluator, self.parent_context, self)
        return [AnonymousInstanceParamName(anon, param.name) for param in self.funcdef.params]

    def get_filters(self, search_global, until_position=None, origin_scope=None, is_instance=False):
        if search_global:
            yield ParserTreeFilter(
                self.evaluator,
                context=self,
                until_position=until_position,
                origin_scope=origin_scope
            )
        else:
            for cls in self.py__mro__():
                if isinstance(cls, compiled.CompiledObject):
                    for filter in cls.get_filters(is_instance=is_instance):
                        yield filter
                else:
                    yield ClassFilter(
                        self.evaluator, self, node_context=cls,
                        origin_scope=origin_scope)

    def is_class(self):
        return True

    def get_subscope_by_name(self, name):
        raise DeprecationWarning
        for s in self.py__mro__():
            for sub in reversed(s.subscopes):
                if sub.name.value == name:
                    return sub
        raise KeyError("Couldn't find subscope.")

    def get_function_slot_names(self, name):
        for filter in self.get_filters(search_global=False):
            names = filter.get(name)
            if names:
                return names
        return []

    def get_param_names(self):
        for name in self.get_function_slot_names('__init__'):
            for context_ in name.infer():
                try:
                    method = context_.get_param_names
                except AttributeError:
                    pass
                else:
                    return list(method())[1:]
        return []

    @property
    def name(self):
        return ContextName(self, self.tree_node.name)


class FunctionContext(use_metaclass(CachedMetaClass, context.TreeContext)):
    """
    Needed because of decorators. Decorators are evaluated here.
    """
    api_type = 'function'

    def __init__(self, evaluator, parent_context, funcdef):
        """ This should not be called directly """
        super(FunctionContext, self).__init__(evaluator, parent_context)
        self.tree_node = funcdef

    def get_filters(self, search_global, until_position=None, origin_scope=None):
        if search_global:
            yield ParserTreeFilter(
                self.evaluator,
                context=self,
                until_position=until_position,
                origin_scope=origin_scope
            )
        else:
            scope = self.py__class__()
            for filter in scope.get_filters(search_global=False, origin_scope=origin_scope):
                yield filter

    def infer_function_execution(self, function_execution):
        """
        Created to be used by inheritance.
        """
        if self.tree_node.is_generator():
            return set([iterable.Generator(self.evaluator, function_execution)])
        else:
            return function_execution.get_return_values()

    def get_function_execution(self, arguments=None):
        e = self.evaluator
        if arguments is None:
            return AnonymousFunctionExecution(e, self.parent_context, self)
        else:
            return FunctionExecutionContext(e, self.parent_context, self, arguments)

    def py__call__(self, arguments):
        function_execution = self.get_function_execution(arguments)
        return self.infer_function_execution(function_execution)

    def py__class__(self):
        # This differentiation is only necessary for Python2. Python3 does not
        # use a different method class.
        if isinstance(self.tree_node.get_parent_scope(), tree.Class):
            name = 'METHOD_CLASS'
        else:
            name = 'FUNCTION_CLASS'
        return compiled.get_special_object(self.evaluator, name)

    @property
    def name(self):
        return ContextName(self, self.tree_node.name)

    def get_param_names(self):
        function_execution = self.get_function_execution()
        return [ParamName(function_execution, param.name) for param in self.tree_node.params]


class FunctionExecutionContext(context.TreeContext):
    """
    This class is used to evaluate functions and their returns.

    This is the most complicated class, because it contains the logic to
    transfer parameters. It is even more complicated, because there may be
    multiple calls to functions and recursion has to be avoided. But this is
    responsibility of the decorators.
    """
    function_execution_filter = FunctionExecutionFilter

    def __init__(self, evaluator, parent_context, function_context, var_args):
        super(FunctionExecutionContext, self).__init__(evaluator, parent_context)
        self.function_context = function_context
        self.tree_node = function_context.tree_node
        self.var_args = var_args

    @memoize_default(default=set())
    @recursion.execution_recursion_decorator()
    def get_return_values(self, check_yields=False):
        funcdef = self.tree_node
        if funcdef.type == 'lambda':
            return self.evaluator.eval_element(self, funcdef.children[-1])

        if check_yields:
            types = set()
            returns = funcdef.yields
        else:
            returns = funcdef.returns
            types = set(docstrings.find_return_types(self.get_root_context(), funcdef))
            types |= set(pep0484.find_return_types(self.get_root_context(), funcdef))

        for r in returns:
            check = flow_analysis.reachability_check(self, funcdef, r)
            if check is flow_analysis.UNREACHABLE:
                debug.dbg('Return unreachable: %s', r)
            else:
                if check_yields:
                    types |= set(self._eval_yield(r))
                else:
                    types |= self.eval_node(r.children[1])
            if check is flow_analysis.REACHABLE:
                debug.dbg('Return reachable: %s', r)
                break
        return types

    def _eval_yield(self, yield_expr):
        node = yield_expr.children[1]
        if node.type == 'yield_arg':  # It must be a yield from.
            cn = ContextualizedNode(self, node.children[1])
            for lazy_context in iterable.py__iter__(self.evaluator, cn.infer(), cn):
                yield lazy_context
        else:
            yield context.LazyTreeContext(self, node)

    @recursion.execution_recursion_decorator(default=iter([]))
    def get_yield_values(self):
        for_parents = [(y, tree.search_ancestor(y, ('for_stmt', 'funcdef',
                                                    'while_stmt', 'if_stmt')))
                       for y in self.tree_node.yields]

        # Calculate if the yields are placed within the same for loop.
        yields_order = []
        last_for_stmt = None
        for yield_, for_stmt in for_parents:
            # For really simple for loops we can predict the order. Otherwise
            # we just ignore it.
            parent = for_stmt.parent
            if parent.type == 'suite':
                parent = parent.parent
            if for_stmt.type == 'for_stmt' and parent == self.tree_node \
                    and for_stmt.defines_one_name():  # Simplicity for now.
                if for_stmt == last_for_stmt:
                    yields_order[-1][1].append(yield_)
                else:
                    yields_order.append((for_stmt, [yield_]))
            elif for_stmt == self.tree_node:
                yields_order.append((None, [yield_]))
            else:
                types = self.get_return_values(check_yields=True)
                if types:
                    yield context.get_merged_lazy_context(list(types))
                return
            last_for_stmt = for_stmt

        evaluator = self.evaluator
        for for_stmt, yields in yields_order:
            if for_stmt is None:
                # No for_stmt, just normal yields.
                for yield_ in yields:
                    for result in self._eval_yield(yield_):
                        yield result
            else:
                input_node = for_stmt.get_input_node()
                cn = ContextualizedNode(self, input_node)
                ordered = iterable.py__iter__(evaluator, cn.infer(), cn)
                ordered = list(ordered)
                for lazy_context in ordered:
                    dct = {str(for_stmt.children[1]): lazy_context.infer()}
                    with helpers.predefine_names(self, for_stmt, dct):
                        for yield_in_same_for_stmt in yields:
                            for result in self._eval_yield(yield_in_same_for_stmt):
                                yield result

    def get_filters(self, search_global, until_position=None, origin_scope=None):
        yield self.function_execution_filter(self.evaluator, self,
                                             until_position=until_position,
                                             origin_scope=origin_scope)

    @memoize_default(default=NO_DEFAULT)
    def get_params(self):
        return param.get_params(self.evaluator, self.parent_context, self.tree_node, self.var_args)


class AnonymousFunctionExecution(FunctionExecutionContext):
    def __init__(self, evaluator, parent_context, function_context):
        super(AnonymousFunctionExecution, self).__init__(
            evaluator, parent_context, function_context, var_args=None)

    @memoize_default(default=NO_DEFAULT)
    def get_params(self):
        # We need to do a dynamic search here.
        return search_params(self.evaluator, self.parent_context, self.tree_node)


class ModuleAttributeName(AbstractNameDefinition):
    """
    For module attributes like __file__, __str__ and so on.
    """
    api_type = 'instance'

    def __init__(self, parent_module, string_name):
        self.parent_context = parent_module
        self.string_name = string_name

    def infer(self):
        return compiled.create(self.parent_context.evaluator, str).execute(
            param.ValuesArguments([])
        )


class ModuleName(ContextNameMixin, AbstractNameDefinition):
    start_pos = 1, 0

    def __init__(self, context, name):
        self._context = context
        self._name = name

    @property
    def string_name(self):
        return self._name


class ModuleContext(use_metaclass(CachedMetaClass, context.TreeContext)):
    api_type = 'module'
    parent_context = None

    def __init__(self, evaluator, module_node, path):
        super(ModuleContext, self).__init__(evaluator, parent_context=None)
        self.tree_node = module_node
        self._path = path

    def get_filters(self, search_global, until_position=None, origin_scope=None):
        yield ParserTreeFilter(
            self.evaluator,
            context=self,
            until_position=until_position,
            origin_scope=origin_scope
        )
        yield GlobalNameFilter(self, self.tree_node)
        yield DictFilter(self._sub_modules_dict())
        yield DictFilter(self._module_attributes_dict())
        for star_module in self.star_imports():
            yield next(star_module.get_filters(search_global))

    # I'm not sure if the star import cache is really that effective anymore
    # with all the other really fast import caches. Recheck. Also we would need
    # to push the star imports into Evaluator.modules, if we reenable this.
    @memoize_default([])
    def star_imports(self):
        modules = []
        for i in self.tree_node.imports:
            if i.is_star_import():
                name = i.star_import_name()
                new = imports.infer_import(self, name)
                for module in new:
                    if isinstance(module, ModuleContext):
                        modules += module.star_imports()
                modules += new
        return modules

    @memoize_default()
    def _module_attributes_dict(self):
        names = ['__file__', '__package__', '__doc__', '__name__']
        # All the additional module attributes are strings.
        return dict((n, ModuleAttributeName(self, n)) for n in names)

    @property
    def _string_name(self):
        """ This is used for the goto functions. """
        if self._path is None:
            return ''  # no path -> empty name
        else:
            sep = (re.escape(os.path.sep),) * 2
            r = re.search(r'([^%s]*?)(%s__init__)?(\.py|\.so)?$' % sep, self._path)
            # Remove PEP 3149 names
            return re.sub('\.[a-z]+-\d{2}[mud]{0,3}$', '', r.group(1))

    @property
    @memoize_default()
    def name(self):
        return ModuleName(self, self._string_name)

    def _get_init_directory(self):
        """
        :return: The path to the directory of a package. None in case it's not
                 a package.
        """
        for suffix, _, _ in imp.get_suffixes():
            ending = '__init__' + suffix
            py__file__ = self.py__file__()
            if py__file__ is not None and py__file__.endswith(ending):
                # Remove the ending, including the separator.
                return self.py__file__()[:-len(ending) - 1]
        return None

    def py__name__(self):
        for name, module in self.evaluator.modules.items():
            if module == self and name != '':
                return name

        return '__main__'

    def py__file__(self):
        """
        In contrast to Python's __file__ can be None.
        """
        if self._path is None:
            return None

        return os.path.abspath(self._path)

    def py__package__(self):
        if self._get_init_directory() is None:
            return re.sub(r'\.?[^\.]+$', '', self.py__name__())
        else:
            return self.py__name__()

    def _py__path__(self):
        search_path = self.evaluator.sys_path
        init_path = self.py__file__()
        if os.path.basename(init_path) == '__init__.py':
            with open(init_path, 'rb') as f:
                content = common.source_to_unicode(f.read())
                # these are strings that need to be used for namespace packages,
                # the first one is ``pkgutil``, the second ``pkg_resources``.
                options = ('declare_namespace(__name__)', 'extend_path(__path__')
                if options[0] in content or options[1] in content:
                    # It is a namespace, now try to find the rest of the
                    # modules on sys_path or whatever the search_path is.
                    paths = set()
                    for s in search_path:
                        other = os.path.join(s, self.name.string_name)
                        if os.path.isdir(other):
                            paths.add(other)
                    if paths:
                        return list(paths)
                    # TODO I'm not sure if this is how nested namespace
                    # packages work. The tests are not really good enough to
                    # show that.
        # Default to this.
        return [self._get_init_directory()]

    @property
    def py__path__(self):
        """
        Not seen here, since it's a property. The callback actually uses a
        variable, so use it like::

            foo.py__path__(sys_path)

        In case of a package, this returns Python's __path__ attribute, which
        is a list of paths (strings).
        Raises an AttributeError if the module is not a package.
        """
        path = self._get_init_directory()

        if path is None:
            raise AttributeError('Only packages have __path__ attributes.')
        else:
            return self._py__path__

    @memoize_default()
    def _sub_modules_dict(self):
        """
        Lists modules in the directory of this module (if this module is a
        package).
        """
        path = self._path
        names = {}
        if path is not None and path.endswith(os.path.sep + '__init__.py'):
            mods = pkgutil.iter_modules([os.path.dirname(path)])
            for module_loader, name, is_pkg in mods:
                # It's obviously a relative import to the current module.
                names[name] = imports.SubModuleName(self, name)

        # TODO add something like this in the future, its cleaner than the
        #   import hacks.
        # ``os.path`` is a hardcoded exception, because it's a
        # ``sys.modules`` modification.
        # if str(self.name) == 'os':
        #     names.append(Name('path', parent_context=self))

        return names

    def py__class__(self):
        return compiled.get_special_object(self.evaluator, 'MODULE_CLASS')

    def __repr__(self):
        return "<%s: %s@%s-%s>" % (
            self.__class__.__name__, self._string_name,
            self.tree_node.start_pos[0], self.tree_node.end_pos[0])


class ImplicitNSName(AbstractNameDefinition):
    """
    Accessing names for implicit namespace packages should infer to nothing.
    This object will prevent Jedi from raising exceptions
    """
    def __init__(self, implicit_ns_context, string_name):
        self.implicit_ns_context = implicit_ns_context
        self.string_name = string_name

    def infer(self):
        return []

    def get_root_context(self):
        return self.implicit_ns_context


class ImplicitNamespaceContext(use_metaclass(CachedMetaClass, context.TreeContext)):
    """
    Provides support for implicit namespace packages
    """
    api_type = 'module'
    parent_context = None

    def __init__(self, evaluator, fullname):
        super(ImplicitNamespaceContext, self).__init__(evaluator, parent_context=None)
        self.evaluator = evaluator
        self.fullname = fullname

    def get_filters(self, search_global, until_position=None, origin_scope=None):
        yield DictFilter(self._sub_modules_dict())

    @property
    @memoize_default()
    def name(self):
        string_name = self.py__package__().rpartition('.')[-1]
        return ImplicitNSName(self, string_name)

    def py__file__(self):
        return None

    def py__package__(self):
        """Return the fullname
        """
        return self.fullname

    @property
    def py__path__(self):
        return lambda: [self.paths]

    @memoize_default()
    def _sub_modules_dict(self):
        names = {}

        paths = self.paths
        file_names = chain.from_iterable(os.listdir(path) for path in paths)
        mods = [
            file_name.rpartition('.')[0] if '.' in file_name else file_name
            for file_name in file_names
            if file_name != '__pycache__'
        ]

        for name in mods:
            names[name] = imports.SubModuleName(self, name)
        return names
