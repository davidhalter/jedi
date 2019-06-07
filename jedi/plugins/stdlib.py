"""
Implementations of standard library functions, because it's not possible to
understand them with Jedi.

To add a new implementation, create a function and add it to the
``_implemented`` dict at the bottom of this module.

Note that this module exists only to implement very specific functionality in
the standard library. The usual way to understand the standard library is the
compiled module that returns the types for C-builtins.
"""
import parso

from jedi._compatibility import force_unicode
from jedi.plugins.base import BasePlugin
from jedi import debug
from jedi.evaluate.helpers import get_str_or_none
from jedi.evaluate.arguments import ValuesArguments, \
    repack_with_argument_clinic, AbstractArguments, TreeArgumentsWrapper
from jedi.evaluate import analysis
from jedi.evaluate import compiled
from jedi.evaluate.context.instance import \
    AbstractInstanceContext, BoundMethod, InstanceArguments
from jedi.evaluate.base_context import ContextualizedNode, \
    NO_CONTEXTS, ContextSet, ContextWrapper
from jedi.evaluate.context import ClassContext, ModuleContext, \
    FunctionExecutionContext
from jedi.evaluate.context import iterable
from jedi.evaluate.lazy_context import LazyTreeContext, LazyKnownContext, \
    LazyKnownContexts
from jedi.evaluate.syntax_tree import is_string
from jedi.evaluate.filters import AttributeOverwrite, publish_method


# Copied from Python 3.6's stdlib.
_NAMEDTUPLE_CLASS_TEMPLATE = """\
_property = property
_tuple = tuple
from operator import itemgetter as _itemgetter
from collections import OrderedDict

class {typename}(tuple):
    '{typename}({arg_list})'

    __slots__ = ()

    _fields = {field_names!r}

    def __new__(_cls, {arg_list}):
        'Create new instance of {typename}({arg_list})'
        return _tuple.__new__(_cls, ({arg_list}))

    @classmethod
    def _make(cls, iterable, new=tuple.__new__, len=len):
        'Make a new {typename} object from a sequence or iterable'
        result = new(cls, iterable)
        if len(result) != {num_fields:d}:
            raise TypeError('Expected {num_fields:d} arguments, got %d' % len(result))
        return result

    def _replace(_self, **kwds):
        'Return a new {typename} object replacing specified fields with new values'
        result = _self._make(map(kwds.pop, {field_names!r}, _self))
        if kwds:
            raise ValueError('Got unexpected field names: %r' % list(kwds))
        return result

    def __repr__(self):
        'Return a nicely formatted representation string'
        return self.__class__.__name__ + '({repr_fmt})' % self

    def _asdict(self):
        'Return a new OrderedDict which maps field names to their values.'
        return OrderedDict(zip(self._fields, self))

    def __getnewargs__(self):
        'Return self as a plain tuple.  Used by copy and pickle.'
        return tuple(self)

    # These methods were added by Jedi.
    # __new__ doesn't really work with Jedi. So adding this to nametuples seems
    # like the easiest way.
    def __init__(_cls, {arg_list}):
        'A helper function for namedtuple.'
        self.__iterable = ({arg_list})

    def __iter__(self):
        for i in self.__iterable:
            yield i

    def __getitem__(self, y):
        return self.__iterable[y]

{field_defs}
"""

_NAMEDTUPLE_FIELD_TEMPLATE = '''\
    {name} = _property(_itemgetter({index:d}), doc='Alias for field number {index:d}')
'''


class StdlibPlugin(BasePlugin):
    def execute(self, callback):
        def wrapper(context, arguments):
            try:
                obj_name = context.name.string_name
            except AttributeError:
                pass
            else:
                if context.parent_context == self._evaluator.builtins_module:
                    module_name = 'builtins'
                elif context.parent_context is not None and context.parent_context.is_module():
                    module_name = context.parent_context.py__name__()
                else:
                    return callback(context, arguments=arguments)

                if isinstance(context, BoundMethod):
                    if module_name == 'builtins':
                        if context.py__name__() == '__get__':
                            if context.class_context.py__name__() == 'property':
                                return builtins_property(
                                    context,
                                    arguments=arguments
                                )
                        elif context.py__name__() in ('deleter', 'getter', 'setter'):
                            if context.class_context.py__name__() == 'property':
                                return ContextSet([context.instance])

                    return callback(context, arguments=arguments)

                # for now we just support builtin functions.
                try:
                    func = _implemented[module_name][obj_name]
                except KeyError:
                    pass
                else:
                    return func(context, arguments=arguments)
            return callback(context, arguments=arguments)

        return wrapper


def _follow_param(evaluator, arguments, index):
    try:
        key, lazy_context = list(arguments.unpack())[index]
    except IndexError:
        return NO_CONTEXTS
    else:
        return lazy_context.infer()


def argument_clinic(string, want_obj=False, want_context=False,
                    want_arguments=False, want_evaluator=False):
    """
    Works like Argument Clinic (PEP 436), to validate function params.
    """

    def f(func):
        @repack_with_argument_clinic(string, keep_arguments_param=True)
        def wrapper(obj, *args, **kwargs):
            arguments = kwargs.pop('arguments')
            assert not kwargs  # Python 2...
            debug.dbg('builtin start %s' % obj, color='MAGENTA')
            result = NO_CONTEXTS
            if want_context:
                kwargs['context'] = arguments.context
            if want_obj:
                kwargs['obj'] = obj
            if want_evaluator:
                kwargs['evaluator'] = obj.evaluator
            if want_arguments:
                kwargs['arguments'] = arguments
            result = func(*args, **kwargs)
            debug.dbg('builtin end: %s', result, color='MAGENTA')
            return result

        return wrapper
    return f


@argument_clinic('obj, type, /', want_obj=True, want_arguments=True)
def builtins_property(objects, types, obj, arguments):
    property_args = obj.instance.var_args.unpack()
    key, lazy_context = next(property_args, (None, None))
    if key is not None or lazy_context is None:
        debug.warning('property expected a first param, not %s', arguments)
        return NO_CONTEXTS

    return lazy_context.infer().py__call__(arguments=ValuesArguments([objects]))


@argument_clinic('iterator[, default], /', want_evaluator=True)
def builtins_next(iterators, defaults, evaluator):
    if evaluator.environment.version_info.major == 2:
        name = 'next'
    else:
        name = '__next__'

    # TODO theoretically we have to check here if something is an iterator.
    # That is probably done by checking if it's not a class.
    return defaults | iterators.py__getattribute__(name).execute_evaluated()


@argument_clinic('iterator[, default], /')
def builtins_iter(iterators_or_callables, defaults):
    # TODO implement this if it's a callable.
    return iterators_or_callables.py__getattribute__('__iter__').execute_evaluated()


@argument_clinic('object, name[, default], /')
def builtins_getattr(objects, names, defaults=None):
    # follow the first param
    for obj in objects:
        for name in names:
            string = get_str_or_none(name)
            if string is None:
                debug.warning('getattr called without str')
                continue
            else:
                return obj.py__getattribute__(force_unicode(string))
    return NO_CONTEXTS


@argument_clinic('object[, bases, dict], /')
def builtins_type(objects, bases, dicts):
    if bases or dicts:
        # It's a type creation... maybe someday...
        return NO_CONTEXTS
    else:
        return objects.py__class__()


class SuperInstance(AbstractInstanceContext):
    """To be used like the object ``super`` returns."""
    def __init__(self, evaluator, cls):
        su = cls.py_mro()[1]
        super().__init__(evaluator, su and su[0] or self)


@argument_clinic('[type[, obj]], /', want_context=True)
def builtins_super(types, objects, context):
    # TODO make this able to detect multiple inheritance super
    if isinstance(context, FunctionExecutionContext):
        if isinstance(context.var_args, InstanceArguments):
            su = context.var_args.instance.py__class__().py__bases__()
            return su[0].infer().execute_evaluated()

    return NO_CONTEXTS


class ReversedObject(AttributeOverwrite):
    def __init__(self, reversed_obj, iter_list):
        super(ReversedObject, self).__init__(reversed_obj)
        self._iter_list = iter_list

    @publish_method('__iter__')
    def py__iter__(self, contextualized_node=None):
        return self._iter_list

    @publish_method('next', python_version_match=2)
    @publish_method('__next__', python_version_match=3)
    def py__next__(self):
        return ContextSet.from_sets(
            lazy_context.infer() for lazy_context in self._iter_list
        )


@argument_clinic('sequence, /', want_obj=True, want_arguments=True)
def builtins_reversed(sequences, obj, arguments):
    # While we could do without this variable (just by using sequences), we
    # want static analysis to work well. Therefore we need to generated the
    # values again.
    key, lazy_context = next(arguments.unpack())
    cn = None
    if isinstance(lazy_context, LazyTreeContext):
        # TODO access private
        cn = ContextualizedNode(lazy_context.context, lazy_context.data)
    ordered = list(sequences.iterate(cn))

    # Repack iterator values and then run it the normal way. This is
    # necessary, because `reversed` is a function and autocompletion
    # would fail in certain cases like `reversed(x).__iter__` if we
    # just returned the result directly.
    seq, = obj.evaluator.typing_module.py__getattribute__('Iterator').execute_evaluated()
    return ContextSet([ReversedObject(seq, list(reversed(ordered)))])


@argument_clinic('obj, type, /', want_arguments=True, want_evaluator=True)
def builtins_isinstance(objects, types, arguments, evaluator):
    bool_results = set()
    for o in objects:
        cls = o.py__class__()
        try:
            cls.py__bases__
        except AttributeError:
            # This is temporary. Everything should have a class attribute in
            # Python?! Maybe we'll leave it here, because some numpy objects or
            # whatever might not.
            bool_results = set([True, False])
            break

        mro = list(cls.py__mro__())

        for cls_or_tup in types:
            if cls_or_tup.is_class():
                bool_results.add(cls_or_tup in mro)
            elif cls_or_tup.name.string_name == 'tuple' \
                    and cls_or_tup.get_root_context() == evaluator.builtins_module:
                # Check for tuples.
                classes = ContextSet.from_sets(
                    lazy_context.infer()
                    for lazy_context in cls_or_tup.iterate()
                )
                bool_results.add(any(cls in mro for cls in classes))
            else:
                _, lazy_context = list(arguments.unpack())[1]
                if isinstance(lazy_context, LazyTreeContext):
                    node = lazy_context.data
                    message = 'TypeError: isinstance() arg 2 must be a ' \
                              'class, type, or tuple of classes and types, ' \
                              'not %s.' % cls_or_tup
                    analysis.add(lazy_context.context, 'type-error-isinstance', node, message)

    return ContextSet(
        compiled.builtin_from_name(evaluator, force_unicode(str(b)))
        for b in bool_results
    )


class StaticMethodObject(AttributeOverwrite, ContextWrapper):
    def get_object(self):
        return self._wrapped_context

    def py__get__(self, instance, klass):
        return ContextSet([self._wrapped_context])


@argument_clinic('sequence, /')
def builtins_staticmethod(functions):
    return ContextSet(StaticMethodObject(f) for f in functions)


class ClassMethodObject(AttributeOverwrite, ContextWrapper):
    def __init__(self, class_method_obj, function):
        super(ClassMethodObject, self).__init__(class_method_obj)
        self._function = function

    def get_object(self):
        return self._wrapped_context

    def py__get__(self, obj, class_context):
        return ContextSet([
            ClassMethodGet(__get__, class_context, self._function)
            for __get__ in self._wrapped_context.py__getattribute__('__get__')
        ])


class ClassMethodGet(AttributeOverwrite, ContextWrapper):
    def __init__(self, get_method, klass, function):
        super(ClassMethodGet, self).__init__(get_method)
        self._class = klass
        self._function = function

    def get_object(self):
        return self._wrapped_context

    def py__call__(self, arguments):
        return self._function.execute(ClassMethodArguments(self._class, arguments))


class ClassMethodArguments(TreeArgumentsWrapper):
    def __init__(self, klass, arguments):
        super(ClassMethodArguments, self).__init__(arguments)
        self._class = klass

    def unpack(self, func=None):
        yield None, LazyKnownContext(self._class)
        for values in self._wrapped_arguments.unpack(func):
            yield values


@argument_clinic('sequence, /', want_obj=True, want_arguments=True)
def builtins_classmethod(functions, obj, arguments):
    return ContextSet(
        ClassMethodObject(class_method_object, function)
        for class_method_object in obj.py__call__(arguments=arguments)
        for function in functions
    )


def collections_namedtuple(obj, arguments):
    """
    Implementation of the namedtuple function.

    This has to be done by processing the namedtuple class template and
    evaluating the result.

    """
    evaluator = obj.evaluator

    # Process arguments
    name = u'jedi_unknown_namedtuple'
    for c in _follow_param(evaluator, arguments, 0):
        x = get_str_or_none(c)
        if x is not None:
            name = force_unicode(x)
            break

    # TODO here we only use one of the types, we should use all.
    param_contexts = _follow_param(evaluator, arguments, 1)
    if not param_contexts:
        return NO_CONTEXTS
    _fields = list(param_contexts)[0]
    if isinstance(_fields, compiled.CompiledValue):
        fields = force_unicode(_fields.get_safe_value()).replace(',', ' ').split()
    elif isinstance(_fields, iterable.Sequence):
        fields = [
            force_unicode(v.get_safe_value())
            for lazy_context in _fields.py__iter__()
            for v in lazy_context.infer() if is_string(v)
        ]
    else:
        return NO_CONTEXTS

    # Build source code
    code = _NAMEDTUPLE_CLASS_TEMPLATE.format(
        typename=name,
        field_names=tuple(fields),
        num_fields=len(fields),
        arg_list=repr(tuple(fields)).replace("u'", "").replace("'", "")[1:-1],
        repr_fmt='',
        field_defs='\n'.join(_NAMEDTUPLE_FIELD_TEMPLATE.format(index=index, name=name)
                             for index, name in enumerate(fields))
    )

    # Parse source code
    module = evaluator.grammar.parse(code)
    generated_class = next(module.iter_classdefs())
    parent_context = ModuleContext(
        evaluator, module,
        file_io=None,
        string_names=None,
        code_lines=parso.split_lines(code, keepends=True),
    )

    return ContextSet([ClassContext(evaluator, parent_context, generated_class)])


class PartialObject(object):
    def __init__(self, actual_context, arguments):
        self._actual_context = actual_context
        self._arguments = arguments

    def __getattr__(self, name):
        return getattr(self._actual_context, name)

    def py__call__(self, arguments):
        key, lazy_context = next(self._arguments.unpack(), (None, None))
        if key is not None or lazy_context is None:
            debug.warning("Partial should have a proper function %s", self._arguments)
            return NO_CONTEXTS

        return lazy_context.infer().execute(
            MergedPartialArguments(self._arguments, arguments)
        )


class MergedPartialArguments(AbstractArguments):
    def __init__(self, partial_arguments, call_arguments):
        self._partial_arguments = partial_arguments
        self._call_arguments = call_arguments

    def unpack(self, funcdef=None):
        unpacked = self._partial_arguments.unpack(funcdef)
        # Ignore this one, it's the function. It was checked before that it's
        # there.
        next(unpacked)
        for key_lazy_context in unpacked:
            yield key_lazy_context
        for key_lazy_context in self._call_arguments.unpack(funcdef):
            yield key_lazy_context


def functools_partial(obj, arguments):
    return ContextSet(
        PartialObject(instance, arguments)
        for instance in obj.py__call__(arguments)
    )


@argument_clinic('first, /')
def _return_first_param(firsts):
    return firsts


@argument_clinic('seq')
def _random_choice(sequences):
    return ContextSet.from_sets(
        lazy_context.infer()
        for sequence in sequences
        for lazy_context in sequence.py__iter__()
    )


class ItemGetterCallable(ContextWrapper):
    def __init__(self, instance, args_context_set):
        super(ItemGetterCallable, self).__init__(instance)
        self._args_context_set = args_context_set

    @repack_with_argument_clinic('item, /')
    def py__call__(self, item_context_set):
        context_set = NO_CONTEXTS
        for args_context in self._args_context_set:
            lazy_contexts = list(args_context.py__iter__())
            if len(lazy_contexts) == 1:
                # TODO we need to add the contextualized context.
                context_set |= item_context_set.get_item(lazy_contexts[0].infer(), None)
            else:
                context_set |= ContextSet([iterable.FakeSequence(
                    self._wrapped_context.evaluator,
                    'list',
                    [
                        LazyKnownContexts(item_context_set.get_item(lazy_context.infer(), None))
                        for lazy_context in lazy_contexts
                    ],
                )])
        return context_set


@argument_clinic('*args, /', want_obj=True, want_arguments=True)
def _operator_itemgetter(args_context_set, obj, arguments):
    return ContextSet([
        ItemGetterCallable(instance, args_context_set)
        for instance in obj.py__call__(arguments)
    ])


_implemented = {
    'builtins': {
        'getattr': builtins_getattr,
        'type': builtins_type,
        'super': builtins_super,
        'reversed': builtins_reversed,
        'isinstance': builtins_isinstance,
        'next': builtins_next,
        'iter': builtins_iter,
        'staticmethod': builtins_staticmethod,
        'classmethod': builtins_classmethod,
    },
    'copy': {
        'copy': _return_first_param,
        'deepcopy': _return_first_param,
    },
    'json': {
        'load': lambda obj, arguments: NO_CONTEXTS,
        'loads': lambda obj, arguments: NO_CONTEXTS,
    },
    'collections': {
        'namedtuple': collections_namedtuple,
    },
    'functools': {
        'partial': functools_partial,
        'wraps': _return_first_param,
    },
    '_weakref': {
        'proxy': _return_first_param,
    },
    'random': {
        'choice': _random_choice,
    },
    'operator': {
        'itemgetter': _operator_itemgetter,
    },
    'abc': {
        # Not sure if this is necessary, but it's used a lot in typeshed and
        # it's for now easier to just pass the function.
        'abstractmethod': _return_first_param,
    },
    'typing': {
        # The _alias function just leads to some annoying type inference.
        # Therefore, just make it return nothing, which leads to the stubs
        # being used instead. This only matters for 3.7+.
        '_alias': lambda obj, arguments: NO_CONTEXTS,
    },
}
