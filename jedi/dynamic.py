"""
For dynamic completion.

Sorry to everyone who is reading this code. Especially the array parts are
really cryptic and not understandable. It's just a hack, that turned out to be
working quite good.
"""
from __future__ import with_statement

import re
import os

import parsing
import modules
import evaluate
import helpers
import settings
import debug
import builtin
import imports

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
            return builtin.CachedModule.cache[path][1].module
        except KeyError:
            return check_fs(path)

    def check_fs(path):
        with open(path) as f:
            source = f.read()
            if name in source:
                return modules.Module(path, source).parser.module

    # skip non python modules
    mods = set(m for m in mods if m.path.endswith('.py'))
    mod_paths = set()
    for m in mods:
        mod_paths.add(m.path)
        yield m

    if settings.dynamic_params_for_other_modules:
        paths = set(settings.additional_dynamic_modules)
        for p in mod_paths:
            d = os.path.dirname(p)
            for entry in os.listdir(d):
                if entry not in mod_paths:
                    if entry.endswith('.py'):
                        paths.add(d + os.path.sep + entry)

        for p in paths:
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


@evaluate.memoize_default([])
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
                if not isinstance(stmt, parsing.Import):
                    calls = _scan_array(stmt.get_assignment_calls(), func_name)
                    for c in calls:
                        # no execution means that params cannot be set
                        call_path = c.generate_call_path()
                        pos = c.start_pos
                        scope = stmt.parent()
                        evaluate.follow_call_path(call_path, scope, pos)
            return listener.param_possibilities

        result = []
        for params in get_posibilities(module, func_name):
            for p in params:
                if str(p) == param_name:
                    result += evaluate.follow_statement(p.parent())
        return result

    func = param.get_parent_until(parsing.Function)
    current_module = param.get_parent_until()
    func_name = str(func.name)
    if func_name == '__init__' and isinstance(func.parent(), parsing.Class):
        func_name = str(func.parent().name)

    # get the param name
    if param.assignment_details:
        arr = param.assignment_details[0][1]
    else:
        arr = param.get_assignment_calls()
    offset = 1 if arr[0][0] in ['*', '**'] else 0
    param_name = str(arr[0][offset].name)

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
    if array._array.type not in ['list', 'set']:
        # TODO also check for dict updates
        return []

    is_list = array._array.type == 'list'
    current_module = array._array.parent_stmt().get_parent_until()
    res = _check_array_additions(array, current_module, is_list)
    return res


def _scan_array(arr, search_name):
    """ Returns the function Call that match search_name in an Array. """
    result = []
    for sub in arr:
        for s in sub:
            if isinstance(s, parsing.Array):
                result += _scan_array(s, search_name)
            elif isinstance(s, parsing.Call):
                s_new = s
                while s_new is not None:
                    n = s_new.name
                    if isinstance(n, parsing.Name) and search_name in n.names:
                        result.append(s)

                    if s_new.execution is not None:
                        result += _scan_array(s_new.execution, search_name)
                    s_new = s_new.next
    return result


counter = 0
def dec(func):
    """ TODO delete this """
    def wrapper(*args, **kwargs):
        global counter
        element = args[0]
        if isinstance(element, evaluate.Array):
            stmt = element._array.parent_stmt()
        else:
            # must be instance
            stmt = element.var_args.parent_stmt()
        print('  ' * counter + 'recursion,', stmt)
        counter += 1
        res = func(*args, **kwargs)
        counter -= 1
        #print '  '*counter + 'end,'
        return res
    return wrapper


#@dec
@evaluate.memoize_default([])
def _check_array_additions(compare_array, module, is_list):
    """
    Checks if a `parsing.Array` has "add" statements:
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
            scope = c.parent_stmt().parent()

            found = evaluate.follow_call_path(backtrack_path, scope, position)
            if not compare_array in found:
                continue

            params = call_path[separate_index + 1]
            if not params.values:
                continue  # no params: just ignore it
            if add_name in ['append', 'add']:
                result += evaluate.follow_call_list(params)
            elif add_name in ['insert']:
                try:
                    second_param = params[1]
                except IndexError:
                    continue
                else:
                    result += evaluate.follow_call_list([second_param])
            elif add_name in ['extend', 'update']:
                iterators = evaluate.follow_call_list(params)
                result += evaluate.get_iterator_types(iterators)
        return result

    def get_execution_parent(element, *stop_classes):
        """ Used to get an Instance/Execution parent """
        if isinstance(element, evaluate.Array):
            stmt = element._array.parent_stmt()
        else:
            # must be instance
            stmt = element.var_args.parent_stmt()
        if isinstance(stmt, evaluate.InstanceElement):
            stop_classes = list(stop_classes) + [evaluate.Function]
        return stmt.get_parent_until(stop_classes)

    temp_param_add = settings.dynamic_params_for_other_modules
    settings.dynamic_params_for_other_modules = False

    search_names = ['append', 'extend', 'insert'] if is_list else \
                                                            ['add', 'update']
    comp_arr_parent = get_execution_parent(compare_array, evaluate.Execution)
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
            if isinstance(comp_arr_parent, evaluate.Execution):
                stmt = comp_arr_parent. \
                                get_statement_for_position(stmt.start_pos)
                if stmt is None:
                    continue
            # InstanceElements are special, because they don't get copied,
            # but have this wrapper around them.
            if isinstance(comp_arr_parent, evaluate.InstanceElement):
                stmt = evaluate.InstanceElement(comp_arr_parent.instance, stmt)

            if evaluate.follow_statement.push_stmt(stmt):
                # check recursion
                continue
            res += check_calls(_scan_array(stmt.get_assignment_calls(), n), n)
            evaluate.follow_statement.pop_stmt()
    # reset settings
    settings.dynamic_params_for_other_modules = temp_param_add
    return res


def check_array_instances(instance):
    """ Used for set() and list() instances. """
    if not settings.dynamic_arrays_instances:
        return instance.var_args
    ai = ArrayInstance(instance)
    return helpers.generate_param_array([ai], instance.var_args.parent_stmt())


class ArrayInstance(parsing.Base):
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
        for array in evaluate.follow_call_list(self.var_args):
            if isinstance(array, evaluate.Instance) and len(array.var_args):
                temp = array.var_args[0][0]
                if isinstance(temp, ArrayInstance):
                    # prevent recursions
                    # TODO compare Modules
                    if self.var_args.start_pos != temp.var_args.start_pos:
                        items += temp.iter_content()
                    else:
                        debug.warning('ArrayInstance recursion', self.var_args)
                    continue
            items += evaluate.get_iterator_types([array])

        if self.var_args.parent_stmt() is None:
            return []  # generated var_args should not be checked for arrays

        module = self.var_args.parent_stmt().get_parent_until()
        is_list = str(self.instance.name) == 'list'
        items += _check_array_additions(self.instance, module, is_list)
        return items


def related_names(definitions, search_name, mods):
    def check_call(call):
        result = []
        follow = []  # There might be multiple search_name's in one call_path
        call_path = list(call.generate_call_path())
        for i, name in enumerate(call_path):
            # name is `parsing.NamePart`.
            if name == search_name:
                follow.append(call_path[:i + 1])

        for f in follow:
            follow_res, search = evaluate.goto(call.parent_stmt(), f)
            follow_res = related_name_add_import_modules(follow_res, search)

            #print follow_res, [d.parent() for d in follow_res]
            # compare to see if they match
            if any(r in definitions for r in follow_res):
                scope = call.parent_stmt()
                result.append(RelatedName(search, scope))

        return result

    if not definitions:
        return set()

    def is_definition(arr):
        try:
            for a in arr:
                assert len(a) == 1
                a = a[0]
                if a.isinstance(parsing.Array):
                    assert is_definition(a)
                elif a.isinstance(parsing.Call):
                    assert a.execution is None
            return True
        except AssertionError:
            return False

    mods |= set([d.get_parent_until() for d in definitions])
    names = []
    for m in get_directory_modules_for_name(mods, search_name):
        try:
            stmts = m.used_names[search_name]
        except KeyError:
            continue
        for stmt in stmts:
            if isinstance(stmt, parsing.Import):
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
                        names.append(RelatedName(name_part, stmt))
            else:
                calls = _scan_array(stmt.get_assignment_calls(), search_name)
                for d in stmt.assignment_details:
                    if not is_definition(d[1]):
                        calls += _scan_array(d[1], search_name)
                for call in calls:
                    names += check_call(call)
    return names


def related_name_add_import_modules(definitions, search_name):
    """ Adds the modules of the imports """
    new = set()
    for d in definitions:
        if isinstance(d.parent(), parsing.Import):
            s = imports.ImportPath(d.parent(), direct_resolve=True)
            try:
                new.add(s.follow(is_goto=True)[0])
            except IndexError:
                pass
    return set(definitions) | new


class BaseOutput(object):
    def __init__(self, start_pos, definition):
        self.module_path = str(definition.get_parent_until().path)
        self.start_pos = start_pos
        self.definition = definition

    @property
    def module_name(self):
        path = self.module_path
        sep = os.path.sep
        p = re.sub(r'^.*?([\w\d]+)(%s__init__)?.py$' % sep, r'\1', path)
        return p

    def in_builtin_module(self):
        return not self.module_path.endswith('.py')

    @property
    def line_nr(self):
        return self.start_pos[0]

    @property
    def column(self):
        return self.start_pos[1]

    @property
    def description(self):
        raise NotImplementedError('Base Class')

    def __repr__(self):
        return "<%s %s>" % (type(self).__name__, self.description)


class RelatedName(BaseOutput):
    def __init__(self, name_part, scope):
        super(RelatedName, self).__init__(name_part.start_pos, scope)
        self.text = str(name_part)
        self.end_pos = name_part.end_pos

    @property
    def description(self):
        return "%s@%s,%s" % (self.text, self.start_pos[0], self.start_pos[1])

    def __eq__(self, other):
        return self.start_pos == other.start_pos \
            and self.module_path == other.module_path

    def __hash__(self):
        return hash((self.start_pos, self.module_path))


def check_flow_information(flow, search_name, pos):
    """ Try to find out the type of a variable just with the information that
    is given by the flows: e.g. It is also responsible for assert checks.
    >>> if isinstance(k, str):
    >>>     k.  # <- completion here

    ensures that `k` is a string.
    """
    result = []
    if isinstance(flow, parsing.Scope) and not result:
        for ass in reversed(flow.asserts):
            if ass.start_pos > pos:
                continue
            result = check_statement_information(ass, search_name)
            if result:
                break

    if isinstance(flow, parsing.Flow) and not result:
        if flow.command in ['if', 'while'] and len(flow.inits) == 1:
            result = check_statement_information(flow.inits[0], search_name)
    return result


def check_statement_information(stmt, search_name):
    try:
        ass = stmt.get_assignment_calls()
        try:
            call = ass.get_only_subelement()
        except AttributeError:
            assert False
        assert type(call) == parsing.Call and str(call.name) == 'isinstance'
        assert bool(call.execution)

        # isinstance check
        isinst = call.execution.values
        assert len(isinst) == 2  # has two params
        assert len(isinst[0]) == 1
        assert len(isinst[1]) == 1
        assert isinstance(isinst[0][0], parsing.Call)
        # names fit?
        assert str(isinst[0][0].name) == search_name
        classes_call = isinst[1][0]  # class_or_type_or_tuple
        assert isinstance(classes_call, parsing.Call)
        result = []
        for c in  evaluate.follow_call(classes_call):
            if isinstance(c, evaluate.Array):
                result += c.get_index_types()
            else:
                result.append(c)
        for i, c in enumerate(result):
            result[i] = evaluate.Instance(c)
        return result
    except AssertionError:
        return []
