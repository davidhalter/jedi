"""
To understand Python on a deeper level, |jedi| needs to understand some of the
dynamic features of Python, however this probably the most complicated part:

- Array modifications (e.g. ``list.append``)
- Parameter completion in functions
- Flow checks (e.g. ``if isinstance(a, str)`` -> a is a str)

Array modifications
*******************

If the content of an array (``set``/``list``) is wanted somewhere, the current
module will be checked for appearances of ``arr.append``, ``arr.insert``, etc.
If the ``arr`` name points to an actual array, the content will be added

This can be really cpu intensive, as you can imagine. Because |jedi| has to
follow **every** ``append``. However this works pretty good, because in *slow*
cases, the recursion detector and other settings will stop this process.

It is important to note that:

1. Array modfications work only in the current module
2. Only Array additions are being checked, ``list.pop``, etc. is being ignored.

Parameter completion
********************

One of the really important features of |jedi| is to have an option to
understand code like this::

    def foo(bar):
        bar. # completion here
    foo(1)

There's no doubt wheter bar is an ``int`` or not, but if there's also a call
like ``foo('str')``, what would happen? Well, we'll just show both. Because
that's what a human would expect.

It works as follows:

- A param is being encountered
- search for function calls named ``foo``
- execute these calls and check the injected params. This work with a
  ``ParamListener``.

Flow checks
***********

Flow checks are not really mature. There's only a check for ``isinstance``.  It
would check whether a flow has the form of ``if isinstance(a, type_or_tuple)``.
Unfortunately every other thing is being ignored (e.g. a == '' would be easy to
check for -> a is a string). There's big potential in these checks.
"""
from __future__ import with_statement

import os

from jedi import cache
from jedi import parsing_representation as pr
from jedi import modules
from jedi import settings
from jedi import common
from jedi import debug
from jedi import fast_parser
import api_classes
import evaluate
import imports
import evaluate_representation as er

# This is something like the sys.path, but only for searching params. It means
# that this is the order in which Jedi searches params.
search_param_modules = ['.']
search_param_cache = {}


def get_directory_modules_for_name(mods, name):
    """
    Search a name in the directories of modules.
    """
    def check_python_file(path):
        try:
            return cache.parser_cache[path].parser.module
        except KeyError:
            try:
                return check_fs(path)
            except IOError:
                return None

    def check_fs(path):
        with open(path) as f:
            source = modules.source_to_unicode(f.read())
            if name in source:
                return modules.Module(path, source).parser.module

    # skip non python modules
    mods = set(m for m in mods if m.path is None or m.path.endswith('.py'))
    mod_paths = set()
    for m in mods:
        mod_paths.add(m.path)
        yield m

    if settings.dynamic_params_for_other_modules:
        paths = set(settings.additional_dynamic_modules)
        for p in mod_paths:
            if p is not None:
                d = os.path.dirname(p)
                for entry in os.listdir(d):
                    if entry not in mod_paths:
                        if entry.endswith('.py'):
                            paths.add(d + os.path.sep + entry)

        for p in sorted(paths):
            # make testing easier, sort it - same results on every interpreter
            c = check_python_file(p)
            if c is not None and c not in mods:
                yield c


def search_param_memoize(func):
    """
    Is only good for search params memoize, respectively the closure,
    because it just caches the input, not the func, like normal memoize does.
    """
    def wrapper(*args, **kwargs):
        key = (args, frozenset(kwargs.items()))
        if key in search_param_cache:
            return search_param_cache[key]
        else:
            rv = func(*args, **kwargs)
            search_param_cache[key] = rv
            return rv
    return wrapper


class ParamListener(object):
    """
    This listener is used to get the params for a function.
    """
    def __init__(self):
        self.param_possibilities = []

    def execute(self, params):
        self.param_possibilities.append(params)


@cache.memoize_default([])
def search_params(param):
    """
    This is a dynamic search for params. If you try to complete a type:
    >>> def func(foo):
    >>>     # here is the completion
    >>>     foo
    >>> func(1)
    >>> func("")

    It is not known what the type is, because it cannot be guessed with
    recursive madness. Therefore one has to analyse the statements that are
    calling the function, as well as analyzing the incoming params.
    """
    if not settings.dynamic_params:
        return []

    def get_params_for_module(module):
        """
        Returns the values of a param, or an empty array.
        """
        @search_param_memoize
        def get_posibilities(module, func_name):
            try:
                possible_stmts = module.used_names[func_name]
            except KeyError:
                return []

            for stmt in possible_stmts:
                if isinstance(stmt, pr.Import):
                    continue
                calls = _scan_statement(stmt, func_name)
                for c in calls:
                    # no execution means that params cannot be set
                    call_path = list(c.generate_call_path())
                    pos = c.start_pos
                    scope = stmt.parent

                    # this whole stuff is just to not execute certain parts
                    # (speed improvement), basically we could just call
                    # ``follow_call_path`` on the call_path and it would
                    # also work.
                    def listRightIndex(lst, value):
                        return len(lst) - lst[-1::-1].index(value) -1

                    # Need to take right index, because there could be a
                    # func usage before.
                    i = listRightIndex(call_path, func_name)
                    first, last = call_path[:i], call_path[i+1:]
                    if not last and not call_path.index(func_name) != i:
                        continue
                    scopes = [scope]
                    if first:
                        scopes = evaluate.follow_call_path(iter(first), scope, pos)
                        pos = None
                    for scope in scopes:
                        s = evaluate.find_name(scope, func_name, position=pos,
                                               search_global=not first,
                                               resolve_decorator=False)

                        c = [getattr(escope, 'base_func', None) or escope.base
                            for escope in s
                            if escope.isinstance(er.Function, er.Class)
                        ]
                        if compare in c:
                            # only if we have the correct function we execute
                            # it, otherwise just ignore it.
                            evaluate.follow_paths(iter(last), s, scope)

            return listener.param_possibilities

        result = []
        for params in get_posibilities(module, func_name):
            for p in params:
                if str(p) == param_name:
                    result += evaluate.follow_statement(p.parent)
        return result

    func = param.get_parent_until(pr.Function)
    current_module = param.get_parent_until()
    func_name = str(func.name)
    compare = func
    if func_name == '__init__' and isinstance(func.parent, pr.Class):
        func_name = str(func.parent.name)
        compare = func.parent

    # get the param name
    if param.assignment_details:
        # first assignment details, others would be a syntax error
        commands, op = param.assignment_details[0]
    else:
        commands = param.get_commands()
    offset = 1 if commands[0] in ['*', '**'] else 0
    param_name = str(commands[offset].name)

    # add the listener
    listener = ParamListener()
    func.listeners.add(listener)

    result = []
    # This is like backtracking: Get the first possible result.
    for mod in get_directory_modules_for_name([current_module], func_name):
        result = get_params_for_module(mod)
        if result:
            break

    # cleanup: remove the listener; important: should not stick.
    func.listeners.remove(listener)

    return result


def check_array_additions(array):
    """ Just a mapper function for the internal _check_array_additions """
    if not pr.Array.is_type(array._array, pr.Array.LIST, pr.Array.SET):
        # TODO also check for dict updates
        return []

    is_list = array._array.type == 'list'
    current_module = array._array.get_parent_until()
    res = _check_array_additions(array, current_module, is_list)
    return res


def _scan_statement(stmt, search_name, assignment_details=False):
    """ Returns the function Call that match search_name in an Array. """
    def scan_array(arr, search_name):
        result = []
        if arr.type == pr.Array.DICT:
            for key_stmt, value_stmt in arr.items():
                result += _scan_statement(key_stmt, search_name)
                result += _scan_statement(value_stmt, search_name)
        else:
            for stmt in arr:
                result += _scan_statement(stmt, search_name)
        return result

    check = list(stmt.get_commands())
    if assignment_details:
        for commands, op in stmt.assignment_details:
            check += commands

    result = []
    for c in check:
        if isinstance(c, pr.Array):
            result += scan_array(c, search_name)
        elif isinstance(c, pr.Call):
            s_new = c
            while s_new is not None:
                n = s_new.name
                if isinstance(n, pr.Name) and search_name in n.names:
                    result.append(c)

                if s_new.execution is not None:
                    result += scan_array(s_new.execution, search_name)
                s_new = s_new.next

    return result


@cache.memoize_default([])
def _check_array_additions(compare_array, module, is_list):
    """
    Checks if a `pr.Array` has "add" statements:
    >>> a = [""]
    >>> a.append(1)
    """
    if not settings.dynamic_array_additions or module.is_builtin():
        return []

    def check_calls(calls, add_name):
        """
        Calls are processed here. The part before the call is searched and
        compared with the original Array.
        """
        result = []
        for c in calls:
            call_path = list(c.generate_call_path())
            separate_index = call_path.index(add_name)
            if add_name == call_path[-1] or separate_index == 0:
                # this means that there is no execution -> [].append
                # or the keyword is at the start -> append()
                continue
            backtrack_path = iter(call_path[:separate_index])

            position = c.start_pos
            scope = c.get_parent_until(pr.IsScope)

            found = evaluate.follow_call_path(backtrack_path, scope, position)
            if not compare_array in found:
                continue

            params = call_path[separate_index + 1]
            if not params.values:
                continue  # no params: just ignore it
            if add_name in ['append', 'add']:
                for param in params:
                    result += evaluate.follow_statement(param)
            elif add_name in ['insert']:
                try:
                    second_param = params[1]
                except IndexError:
                    continue
                else:
                    result += evaluate.follow_statement(second_param)
            elif add_name in ['extend', 'update']:
                for param in params:
                    iterators = evaluate.follow_statement(param)
                result += evaluate.get_iterator_types(iterators)
        return result

    def get_execution_parent(element, *stop_classes):
        """ Used to get an Instance/Execution parent """
        if isinstance(element, er.Array):
            stmt = element._array.parent
        else:
            # is an Instance with an ArrayInstance inside
            stmt = element.var_args[0].var_args.parent
        if isinstance(stmt, er.InstanceElement):
            stop_classes = list(stop_classes) + [er.Function]
        return stmt.get_parent_until(stop_classes)

    temp_param_add = settings.dynamic_params_for_other_modules
    settings.dynamic_params_for_other_modules = False

    search_names = ['append', 'extend', 'insert'] if is_list else \
        ['add', 'update']
    comp_arr_parent = get_execution_parent(compare_array, er.Execution)

    possible_stmts = []
    res = []
    for n in search_names:
        try:
            possible_stmts += module.used_names[n]
        except KeyError:
            continue
        for stmt in possible_stmts:
            # Check if the original scope is an execution. If it is, one
            # can search for the same statement, that is in the module
            # dict. Executions are somewhat special in jedi, since they
            # literally copy the contents of a function.
            if isinstance(comp_arr_parent, er.Execution):
                stmt = comp_arr_parent. \
                    get_statement_for_position(stmt.start_pos)
                if stmt is None:
                    continue
            # InstanceElements are special, because they don't get copied,
            # but have this wrapper around them.
            if isinstance(comp_arr_parent, er.InstanceElement):
                stmt = er.InstanceElement(comp_arr_parent.instance, stmt)

            if evaluate.follow_statement.push_stmt(stmt):
                # check recursion
                continue
            res += check_calls(_scan_statement(stmt, n), n)
            evaluate.follow_statement.pop_stmt()
    # reset settings
    settings.dynamic_params_for_other_modules = temp_param_add
    return res


def check_array_instances(instance):
    """Used for set() and list() instances."""
    if not settings.dynamic_arrays_instances:
        return instance.var_args
    ai = ArrayInstance(instance)
    return [ai]


class ArrayInstance(pr.Base):
    """
    Used for the usage of set() and list().
    This is definitely a hack, but a good one :-)
    It makes it possible to use set/list conversions.
    """
    def __init__(self, instance):
        self.instance = instance
        self.var_args = instance.var_args

    def iter_content(self):
        """
        The index is here just ignored, because of all the appends, etc.
        lists/sets are too complicated too handle that.
        """
        items = []
        for stmt in self.var_args:
            for typ in evaluate.follow_statement(stmt):
                if isinstance(typ, er.Instance) and len(typ.var_args):
                    array = typ.var_args[0]
                    if isinstance(array, ArrayInstance):
                        # prevent recursions
                        # TODO compare Modules
                        if self.var_args.start_pos != array.var_args.start_pos:
                            items += array.iter_content()
                        else:
                            debug.warning(
                                'ArrayInstance recursion',
                                self.var_args)
                        continue
                items += evaluate.get_iterator_types([typ])

        # TODO check if exclusion of tuple is a problem here.
        if isinstance(self.var_args, tuple) or self.var_args.parent is None:
            return []  # generated var_args should not be checked for arrays

        module = self.var_args.get_parent_until()
        is_list = str(self.instance.name) == 'list'
        items += _check_array_additions(self.instance, module, is_list)
        return items


def usages(definitions, search_name, mods):
    def compare_array(definitions):
        """ `definitions` are being compared by module/start_pos, because
        sometimes the id's of the objects change (e.g. executions).
        """
        result = []
        for d in definitions:
            module = d.get_parent_until()
            result.append((module, d.start_pos))
        return result

    def check_call(call):
        result = []
        follow = []  # There might be multiple search_name's in one call_path
        call_path = list(call.generate_call_path())
        for i, name in enumerate(call_path):
            # name is `pr.NamePart`.
            if name == search_name:
                follow.append(call_path[:i + 1])

        for f in follow:
            follow_res, search = evaluate.goto(call.parent, f)
            follow_res = usages_add_import_modules(follow_res, search)

            compare_follow_res = compare_array(follow_res)
            # compare to see if they match
            if any(r in compare_definitions for r in compare_follow_res):
                scope = call.parent
                result.append(api_classes.Usage(search, scope))

        return result

    if not definitions:
        return set()

    compare_definitions = compare_array(definitions)
    mods |= set([d.get_parent_until() for d in definitions])
    names = []
    for m in get_directory_modules_for_name(mods, search_name):
        try:
            stmts = m.used_names[search_name]
        except KeyError:
            continue
        for stmt in stmts:
            if isinstance(stmt, pr.Import):
                count = 0
                imps = []
                for i in stmt.get_all_import_names():
                    for name_part in i.names:
                        count += 1
                        if name_part == search_name:
                            imps.append((count, name_part))

                for used_count, name_part in imps:
                    i = imports.ImportPath(stmt, kill_count=count - used_count,
                                           direct_resolve=True)
                    f = i.follow(is_goto=True)
                    if set(f) & set(definitions):
                        names.append(api_classes.Usage(name_part, stmt))
            else:
                for call in _scan_statement(stmt, search_name,
                                            assignment_details=True):
                    names += check_call(call)
    return names


def usages_add_import_modules(definitions, search_name):
    """ Adds the modules of the imports """
    new = set()
    for d in definitions:
        if isinstance(d.parent, pr.Import):
            s = imports.ImportPath(d.parent, direct_resolve=True)
            with common.ignored(IndexError):
                new.add(s.follow(is_goto=True)[0])
    return set(definitions) | new


def check_flow_information(flow, search_name, pos):
    """ Try to find out the type of a variable just with the information that
    is given by the flows: e.g. It is also responsible for assert checks.::

        if isinstance(k, str):
            k.  # <- completion here

    ensures that `k` is a string.
    """
    if not settings.dynamic_flow_information:
        return None
    result = []
    if isinstance(flow, (pr.Scope, fast_parser.Module)) and not result:
        for ass in reversed(flow.asserts):
            if pos is None or ass.start_pos > pos:
                continue
            result = _check_isinstance_type(ass, search_name)
            if result:
                break

    if isinstance(flow, pr.Flow) and not result:
        if flow.command in ['if', 'while'] and len(flow.inputs) == 1:
            result = _check_isinstance_type(flow.inputs[0], search_name)
    return result


def _check_isinstance_type(stmt, search_name):
    try:
        commands = stmt.get_commands()
        # this might be removed if we analyze and, etc
        assert len(commands) == 1
        call = commands[0]
        assert type(call) is pr.Call and str(call.name) == 'isinstance'
        assert bool(call.execution)

        # isinstance check
        isinst = call.execution.values
        assert len(isinst) == 2  # has two params
        obj, classes = [statement.get_commands() for statement in isinst]
        assert len(obj) == 1
        assert len(classes) == 1
        assert isinstance(obj[0], pr.Call)
        # names fit?
        assert str(obj[0].name) == search_name
        assert isinstance(classes[0], pr.Call)  # can be type or tuple
    except AssertionError:
        return []

    result = []
    for c in evaluate.follow_call(classes[0]):
        if isinstance(c, er.Array):
            result += c.get_index_types()
        else:
            result.append(c)
    for i, c in enumerate(result):
        result[i] = er.Instance(c)
    return result
