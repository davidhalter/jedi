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
from jedi.evaluate.arguments import ValuesArguments, \
    repack_with_argument_clinic, AbstractArguments
from jedi.evaluate import analysis
from jedi.evaluate import compiled
from jedi.evaluate.context.instance import TreeInstance, \
    AbstractInstanceContext, CompiledInstance, BoundMethod, InstanceArguments
from jedi.evaluate.base_context import ContextualizedNode, \
    NO_CONTEXTS, ContextSet, ContextWrapper
from jedi.evaluate.context import ClassContext, ModuleContext, \
    FunctionExecutionContext
from jedi.plugins import typeshed
from jedi.evaluate.context.klass import py__mro__
from jedi.evaluate.context import iterable
from jedi.evaluate.lazy_context import LazyTreeContext
from jedi.evaluate.syntax_tree import is_string

# Now this is all part of fake tuples in Jedi. However super doesn't work on
# __init__ and __new__ doesn't work at all. So adding this to nametuples is
# just the easiest way.
_NAMEDTUPLE_INIT = """
    def __init__(_cls, {arg_list}):
        'A helper function for namedtuple.'
        self.__iterable = ({arg_list})

    def __iter__(self):
        for i in self.__iterable:
            yield i

    def __getitem__(self, y):
        return self.__iterable[y]

"""


class StdlibPlugin(BasePlugin):
    def execute(self, callback):
        def wrapper(context, arguments):
            debug.dbg('execute: %s %s', context, arguments)
            try:
                obj_name = context.name.string_name
            except AttributeError:
                pass
            else:
                if context.parent_context == self._evaluator.builtins_module:
                    module_name = 'builtins'
                elif isinstance(context.parent_context, ModuleContext):
                    module_name = context.parent_context.name.string_name
                else:
                    module_name = ''

                if isinstance(context, BoundMethod):
                    if module_name == 'builtins' and context.py__name__() == '__get__':
                        if context.class_context.py__name__() == 'property':
                            return builtins_property(
                                context,
                                arguments=arguments
                            )
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
    """
    TODO this function is currently not used. It's a stab at implementing next
    in a different way than fake objects. This would be a bit more flexible.
    """
    if evaluator.environment.version_info.major == 2:
        name = 'next'
    else:
        name = '__next__'

    # TODO theoretically we have to check here if something is an iterator.
    # That is probably done by checking if it's not a class.
    return defaults | iterators.py__getattribute__(name).execute_evaluated()


@argument_clinic('object, name[, default], /')
def builtins_getattr(objects, names, defaults=None):
    # follow the first param
    for obj in objects:
        for name in names:
            if is_string(name):
                return obj.py__getattribute__(force_unicode(name.get_safe_value()))
            else:
                debug.warning('getattr called without str')
                continue
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


from jedi.evaluate.filters import AbstractObjectOverwrite, publish_method
class ReversedObject(AbstractObjectOverwrite, ContextWrapper):
    def __init__(self, reversed_obj, iter_list):
        super(ReversedObject, self).__init__(reversed_obj)
        self._iter_list = iter_list

    def get_object(self):
        return self._wrapped_context

    @publish_method('__iter__')
    def py__iter__(self):
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
        cn = ContextualizedNode(lazy_context._context, lazy_context.data)
    ordered = list(sequences.iterate(cn))

    # Repack iterator values and then run it the normal way. This is
    # necessary, because `reversed` is a function and autocompletion
    # would fail in certain cases like `reversed(x).__iter__` if we
    # just returned the result directly.
    instance = TreeInstance(obj.evaluator, obj.parent_context, obj, ValuesArguments([]))
    return ContextSet(ReversedObject(instance, list(reversed(ordered))))


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

        mro = py__mro__(cls)

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
                    analysis.add(lazy_context._context, 'type-error-isinstance', node, message)

    return ContextSet.from_iterable(
        compiled.builtin_from_name(evaluator, force_unicode(str(b)))
        for b in bool_results
    )


def collections_namedtuple(obj, arguments):
    """
    Implementation of the namedtuple function.

    This has to be done by processing the namedtuple class template and
    evaluating the result.

    """
    evaluator = obj.evaluator
    collections_context = obj.parent_context
    _class_template_set = collections_context.py__getattribute__(u'_class_template')
    if not _class_template_set:
        # Namedtuples are not supported on Python 2.6, early 2.7, because the
        # _class_template variable is not defined, there.
        return NO_CONTEXTS

    # Process arguments
    # TODO here we only use one of the types, we should use all.
    # TODO this is buggy, doesn't need to be a string
    name = list(_follow_param(evaluator, arguments, 0))[0].get_safe_value()
    _fields = list(_follow_param(evaluator, arguments, 1))[0]
    if isinstance(_fields, compiled.CompiledObject):
        fields = _fields.get_safe_value().replace(',', ' ').split()
    elif isinstance(_fields, iterable.Sequence):
        fields = [
            v.get_safe_value()
            for lazy_context in _fields.py__iter__()
            for v in lazy_context.infer() if is_string(v)
        ]
    else:
        return NO_CONTEXTS

    def get_var(name):
        x, = collections_context.py__getattribute__(name)
        return x.get_safe_value()

    base = next(iter(_class_template_set)).get_safe_value()
    base += _NAMEDTUPLE_INIT
    # Build source code
    code = base.format(
        typename=name,
        field_names=tuple(fields),
        num_fields=len(fields),
        arg_list=repr(tuple(fields)).replace("u'", "").replace("'", "")[1:-1],
        repr_fmt=', '.join(get_var(u'_repr_template').format(name=name) for name in fields),
        field_defs='\n'.join(get_var(u'_field_template').format(index=index, name=name)
                             for index, name in enumerate(fields))
    )

    # Parse source code
    module = evaluator.grammar.parse(code)
    generated_class = next(module.iter_classdefs())
    parent_context = ModuleContext(
        evaluator, module,
        path=None,
        string_names=None,
        code_lines=parso.split_lines(code, keepends=True),
    )

    return ContextSet(ClassContext(evaluator, parent_context, generated_class))


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
    return ContextSet.from_iterable(
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


class ItemGetterCallable(object):
    def __init__(self, evaluator, args_context_set):
        # TODO this context is totally incomplete and will raise exceptions.
        self.evaluator = evaluator
        self._args_context_set = args_context_set

    @repack_with_argument_clinic('item, /')
    def py__call__(self, item_context_set):
        context_set = ContextSet()
        for args_context in self._args_context_set:
            lazy_contexts = list(args_context.py__iter__())
            if len(lazy_contexts) == 1:
                # TODO we need to add the contextualized context.
                context_set |= item_context_set.get_item(lazy_contexts[0].infer(), None)
            else:
                return NO_CONTEXTS
                raise NotImplementedError
        return context_set


@argument_clinic('*args, /', want_obj=True, want_arguments=True)
def _operator_itemgetter(args_context_set, obj, arguments):
    # final = obj.py__call__(arguments)
    # TODO use this as a context wrapper
    return ContextSet(ItemGetterCallable(obj.evaluator, args_context_set))


_implemented = {
    'builtins': {
        'getattr': builtins_getattr,
        'type': builtins_type,
        'super': builtins_super,
        'reversed': builtins_reversed,
        'isinstance': builtins_isinstance,
        'next': builtins_next,
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
    }
}
