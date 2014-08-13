"""
Implementations of standard library functions, because it's not possible to
understand them with Jedi.

To add a new implementation, create a function and add it to the
``_implemented`` dict at the bottom of this module.

"""
import collections
from jedi._compatibility import unicode
from jedi.evaluate import compiled
from jedi.evaluate import representation as er
from jedi.evaluate import iterable
from jedi.evaluate.helpers import FakeArray, FakeStatement
from jedi.parser import Parser
from jedi.parser import representation as pr
from jedi import debug


class NotInStdLib(LookupError):
    pass


def execute(evaluator, obj, params):
    try:
        obj_name = str(obj.name)
    except AttributeError:
        pass
    else:
        if obj.parent == compiled.builtin:
            module_name = 'builtins'
        elif isinstance(obj.parent, pr.Module):
            module_name = str(obj.parent.name)
        else:
            module_name = ''

        # for now we just support builtin functions.
        try:
            return _implemented[module_name][obj_name](evaluator, obj, params)
        except KeyError:
            pass
    raise NotInStdLib()


def _follow_param(evaluator, params, index):
    try:
        stmt = params[index]
    except IndexError:
        return []
    else:
        if isinstance(stmt, pr.Statement):
            return evaluator.eval_statement(stmt)
        else:
            return [stmt]  # just some arbitrary object


def builtins_getattr(evaluator, obj, params):
    stmts = []
    # follow the first param
    objects = _follow_param(evaluator, params, 0)
    names = _follow_param(evaluator, params, 1)
    for obj in objects:
        if not isinstance(obj, (er.Instance, er.Class, pr.Module, compiled.CompiledObject)):
            debug.warning('getattr called without instance')
            continue

        for name in names:
            s = unicode, str
            if isinstance(name, compiled.CompiledObject) and isinstance(name.obj, s):
                stmts += evaluator.follow_path(iter([name.obj]), [obj], obj)
            else:
                debug.warning('getattr called without str')
                continue
    return stmts


def builtins_type(evaluator, obj, params):
    if len(params) == 1:
        # otherwise it would be a metaclass... maybe someday...
        objects = _follow_param(evaluator, params, 0)
        return [o.base for o in objects if isinstance(o, er.Instance)]
    return []


class SuperInstance(er.Instance):
    """To be used like the object ``super`` returns."""
    def __init__(self, evaluator, cls):
        su = cls.py_mro()[1]
        super().__init__(evaluator, su and su[0] or self)


def builtins_super(evaluator, obj, params):
    # TODO make this able to detect multiple inheritance super
    accept = (pr.Function, er.FunctionExecution)
    func = params.get_parent_until(accept)
    if func.isinstance(*accept):
        wanted = (pr.Class, er.Instance)
        cls = func.get_parent_until(accept + wanted,
                                    include_current=False)
        if isinstance(cls, wanted):
            if isinstance(cls, pr.Class):
                cls = er.Class(evaluator, cls)
            elif isinstance(cls, er.Instance):
                cls = cls.base
            su = cls.py__bases__(evaluator)
            if su:
                return evaluator.execute(su[0])
    return []


def builtins_reversed(evaluator, obj, params):
    objects = tuple(_follow_param(evaluator, params, 0))
    if objects:
        # unpack the iterator values
        objects = tuple(iterable.get_iterator_types(objects))
        if objects:
            rev = reversed(objects)
            # Repack iterator values and then run it the normal way. This is
            # necessary, because `reversed` is a function and autocompletion
            # would fail in certain cases like `reversed(x).__iter__` if we
            # just returned the result directly.
            stmts = [FakeStatement([r]) for r in rev]
            objects = (iterable.Array(evaluator, FakeArray(stmts, objects[0].parent)),)
    return [er.Instance(evaluator, obj, objects)]


def collections_namedtuple(evaluator, obj, params):
    """
    Implementation of the namedtuple function.

    This has to be done by processing the namedtuple class template and
    evaluating the result.

    .. note:: |jedi| only supports namedtuples on Python >2.6.

    """
    # Namedtuples are not supported on Python 2.6
    if not hasattr(collections, '_class_template'):
        return []

    # Process arguments
    name = _follow_param(evaluator, params, 0)[0].obj
    _fields = _follow_param(evaluator, params, 1)[0]
    if isinstance(_fields, compiled.CompiledObject):
        fields = _fields.obj.replace(',', ' ').split()
    elif isinstance(_fields, iterable.Array):
        try:
            fields = [v.obj for v in _fields.values()]
        except AttributeError:
            return []
    else:
        return []

    # Build source
    source = collections._class_template.format(
        typename=name,
        field_names=fields,
        num_fields=len(fields),
        arg_list=', '.join(fields),
        repr_fmt=', '.join(collections._repr_template.format(name=name) for name in fields),
        field_defs='\n'.join(collections._field_template.format(index=index, name=name)
                             for index, name in enumerate(fields))
    )

    # Parse source
    generated_class = Parser(unicode(source)).module.subscopes[0]
    return [er.Class(evaluator, generated_class)]


def _return_first_param(evaluator, obj, params):
    if len(params) == 1:
        return _follow_param(evaluator, params, 0)
    return []


_implemented = {
    'builtins': {
        'getattr': builtins_getattr,
        'type': builtins_type,
        'super': builtins_super,
        'reversed': builtins_reversed,
    },
    'copy': {
        'copy': _return_first_param,
        'deepcopy': _return_first_param,
    },
    'json': {
        'load': lambda *args: [],
        'loads': lambda *args: [],
    },
    'collections': {
        'namedtuple': collections_namedtuple,
    },
}
