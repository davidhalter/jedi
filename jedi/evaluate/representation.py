"""
Like described in the :mod:`parso.python.tree` module,
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
py__doc__(include_call_signature:      Returns the docstring for a context.
          bool)
====================================== ========================================

"""
import os
from itertools import chain

from parso.python import tree

from jedi._compatibility import use_metaclass
from jedi import debug
from jedi.evaluate.cache import evaluator_method_cache, CachedMetaClass
from jedi.evaluate import compiled
from jedi.evaluate import recursion
from jedi.evaluate import docstrings
from jedi.evaluate import pep0484
from jedi.evaluate import param
from jedi.evaluate import flow_analysis
from jedi.evaluate import imports
from jedi.evaluate import helpers
from jedi.evaluate import iterable
from jedi.evaluate.filters import ParserTreeFilter, FunctionExecutionFilter, \
    DictFilter, ContextName, AbstractNameDefinition, \
    ParamName, AnonymousInstanceParamName, TreeNameDefinition
from jedi.evaluate import context
from jedi.evaluate.context import ContextualizedNode, NO_CONTEXTS, \
    ContextSet, iterator_to_context_set
from jedi import parser_utils
from jedi.evaluate.parser_cache import get_yield_exprs


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

    @iterator_to_context_set
    def infer(self):
        # TODO this _name_to_types might get refactored and be a part of the
        # parent class. Once it is, we can probably just overwrite method to
        # achieve this.
        from jedi.evaluate.syntax_tree import tree_name_to_contexts
        inferred = tree_name_to_contexts(
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

    def __init__(self, evaluator, parent_context, classdef):
        super(ClassContext, self).__init__(evaluator, parent_context=parent_context)
        self.tree_node = classdef

    @evaluator_method_cache(default=())
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

    @evaluator_method_cache(default=())
    def py__bases__(self):
        arglist = self.tree_node.get_super_arglist()
        if arglist:
            args = param.TreeArguments(self.evaluator, self, arglist)
            return [value for key, value in args.unpack() if key is None]
        else:
            return [context.LazyKnownContext(compiled.create(self.evaluator, object))]

    def py__call__(self, params):
        from jedi.evaluate.context.instance import TreeInstance
        return ContextSet(TreeInstance(self.evaluator, self.parent_context, self, params))

    def py__class__(self):
        return compiled.create(self.evaluator, type)

    def get_params(self):
        from jedi.evaluate.context.instance import AnonymousInstance
        anon = AnonymousInstance(self.evaluator, self.parent_context, self)
        return [AnonymousInstanceParamName(anon, param.name) for param in self.funcdef.get_params()]

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


class LambdaName(AbstractNameDefinition):
    string_name = '<lambda>'

    def __init__(self, lambda_context):
        self._lambda_context = lambda_context
        self.parent_context = lambda_context.parent_context

    def start_pos(self):
        return self._lambda_context.tree_node.start_pos

    def infer(self):
        return ContextSet(self._lambda_context)


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
        yield_exprs = get_yield_exprs(self.evaluator, self.tree_node)
        if yield_exprs:
            return ContextSet(iterable.Generator(self.evaluator, function_execution))
        else:
            return function_execution.get_return_values()

    def get_function_execution(self, arguments=None):
        if arguments is None:
            arguments = param.AnonymousArguments()

        return FunctionExecutionContext(self.evaluator, self.parent_context, self, arguments)

    def py__call__(self, arguments):
        function_execution = self.get_function_execution(arguments)
        return self.infer_function_execution(function_execution)

    def py__class__(self):
        # This differentiation is only necessary for Python2. Python3 does not
        # use a different method class.
        if isinstance(parser_utils.get_parent_scope(self.tree_node), tree.Class):
            name = 'METHOD_CLASS'
        else:
            name = 'FUNCTION_CLASS'
        return compiled.get_special_object(self.evaluator, name)

    @property
    def name(self):
        if self.tree_node.type == 'lambdef':
            return LambdaName(self)
        return ContextName(self, self.tree_node.name)

    def get_param_names(self):
        function_execution = self.get_function_execution()
        return [ParamName(function_execution, param.name)
                for param in self.tree_node.get_params()]


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

    @evaluator_method_cache(default=NO_CONTEXTS)
    @recursion.execution_recursion_decorator()
    def get_return_values(self, check_yields=False):
        funcdef = self.tree_node
        if funcdef.type == 'lambdef':
            return self.evaluator.eval_element(self, funcdef.children[-1])

        if check_yields:
            context_set = NO_CONTEXTS
            returns = get_yield_exprs(self.evaluator, funcdef)
        else:
            returns = funcdef.iter_return_stmts()
            context_set = docstrings.infer_return_types(self.function_context)
            context_set |= pep0484.infer_return_types(self.function_context)

        for r in returns:
            check = flow_analysis.reachability_check(self, funcdef, r)
            if check is flow_analysis.UNREACHABLE:
                debug.dbg('Return unreachable: %s', r)
            else:
                if check_yields:
                    context_set |= ContextSet.from_sets(
                        lazy_context.infer()
                        for lazy_context in self._eval_yield(r)
                    )
                else:
                    try:
                        children = r.children
                    except AttributeError:
                        context_set |= ContextSet(compiled.create(self.evaluator, None))
                    else:
                        context_set |= self.eval_node(children[1])
            if check is flow_analysis.REACHABLE:
                debug.dbg('Return reachable: %s', r)
                break
        return context_set

    def _eval_yield(self, yield_expr):
        if yield_expr.type == 'keyword':
            # `yield` just yields None.
            yield context.LazyKnownContext(compiled.create(self.evaluator, None))
            return

        node = yield_expr.children[1]
        if node.type == 'yield_arg':  # It must be a yield from.
            cn = ContextualizedNode(self, node.children[1])
            for lazy_context in cn.infer().iterate(cn):
                yield lazy_context
        else:
            yield context.LazyTreeContext(self, node)

    @recursion.execution_recursion_decorator(default=iter([]))
    def get_yield_values(self):
        for_parents = [(y, tree.search_ancestor(y, 'for_stmt', 'funcdef',
                                                'while_stmt', 'if_stmt'))
                       for y in get_yield_exprs(self.evaluator, self.tree_node)]

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
                    and parser_utils.for_stmt_defines_one_name(for_stmt):  # Simplicity for now.
                if for_stmt == last_for_stmt:
                    yields_order[-1][1].append(yield_)
                else:
                    yields_order.append((for_stmt, [yield_]))
            elif for_stmt == self.tree_node:
                yields_order.append((None, [yield_]))
            else:
                types = self.get_return_values(check_yields=True)
                if types:
                    yield context.LazyKnownContexts(types)
                return
            last_for_stmt = for_stmt

        for for_stmt, yields in yields_order:
            if for_stmt is None:
                # No for_stmt, just normal yields.
                for yield_ in yields:
                    for result in self._eval_yield(yield_):
                        yield result
            else:
                input_node = for_stmt.get_testlist()
                cn = ContextualizedNode(self, input_node)
                ordered = cn.infer().iterate(cn)
                ordered = list(ordered)
                for lazy_context in ordered:
                    dct = {str(for_stmt.children[1].value): lazy_context.infer()}
                    with helpers.predefine_names(self, for_stmt, dct):
                        for yield_in_same_for_stmt in yields:
                            for result in self._eval_yield(yield_in_same_for_stmt):
                                yield result

    def get_filters(self, search_global, until_position=None, origin_scope=None):
        yield self.function_execution_filter(self.evaluator, self,
                                             until_position=until_position,
                                             origin_scope=origin_scope)

    @evaluator_method_cache()
    def get_params(self):
        return self.var_args.get_params(self)


class ImplicitNSName(AbstractNameDefinition):
    """
    Accessing names for implicit namespace packages should infer to nothing.
    This object will prevent Jedi from raising exceptions
    """
    def __init__(self, implicit_ns_context, string_name):
        self.implicit_ns_context = implicit_ns_context
        self.string_name = string_name

    def infer(self):
        return NO_CONTEXTS

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
    @evaluator_method_cache()
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

    @evaluator_method_cache()
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
