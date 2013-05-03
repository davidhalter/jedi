"""
Evaluation of Python code in |jedi| is based on three assumptions:

* Code is recursive (to weaken this assumption, the :mod:`dynamic` module
  exists).
* No magic is being used:

  - metaclasses
  - ``setattr()`` / ``__import__()``
  - writing to ``globals()``, ``locals()``, ``object.__dict__``
* The programmer is not a total dick, e.g. like `this
  <https://github.com/davidhalter/jedi/issues/24>`_ :-)

That said, there's mainly one entry point in this script: ``follow_statement``.
This is where autocompletion starts. Everything you want to complete is either
a ``Statement`` or some special name like ``class``, which is easy to complete.

Therefore you need to understand what follows after ``follow_statement``. Let's
make an example::

    import datetime
    datetime.date.toda# <-- cursor here

First of all, this module doesn't care about completion. It really just cares
about ``datetime.date``. At the end of the procedure ``follow_statement`` will
return the ``datetime`` class.

To *visualize* this (simplified):

- ``follow_statement`` - ``<Statement: datetime.date>``

    - Unpacking of the statement into ``[[<Call: datetime.date>]]``
- ``follow_call_list``, calls ``follow_call`` with ``<Call: datetime.date>``
- ``follow_call`` - searches the ``datetime`` name within the module.

This is exactly where it starts to get complicated. Now recursions start to
kick in. The statement has not been resolved fully, but now we need to resolve
the datetime import. So it continues

- follow import, which happens in the :mod:`imports` module.
- now the same ``follow_call`` as above calls ``follow_paths`` to follow the
  second part of the statement ``date``.
- After ``follow_paths`` returns with the desired ``datetime.date`` class, the
  result is being returned and the recursion finishes.

Now what would happen if we wanted ``datetime.date.foo.bar``? Just two more
calls to ``follow_paths`` (which calls itself with a recursion). What if the
import would contain another Statement like this::

    from foo import bar
    Date = bar.baz

Well... You get it. Just another ``follow_statement`` recursion. It's really
easy. Just that Python is not that easy sometimes. To understand tuple
assignments and different class scopes, a lot more code had to be written.  Yet
we're still not talking about Descriptors and Nested List Comprehensions, just
the simple stuff.

So if you want to change something, write a test and then just change what you
want. This module has been tested by about 600 tests. Don't be afraid to break
something. The tests are good enough.

I need to mention now that this recursive approach is really good because it
only *evaluates* what needs to be *evaluated*. All the statements and modules
that are not used are just being ignored. It's a little bit similar to the
backtracking algorithm.


.. todo:: nonlocal statement, needed or can be ignored? (py3k)
"""
from __future__ import with_statement

import sys
import itertools

from jedi._compatibility import next, hasattr, is_py3k, unicode, reraise
from jedi import common
from jedi import cache
from jedi import parsing_representation as pr
from jedi import debug
import evaluate_representation as er
import recursion
import docstrings
import builtin
import imports
import dynamic


def get_defined_names_for_position(scope, position=None, start_scope=None):
    """
    Return filtered version of ``scope.get_defined_names()``.

    This function basically does what :meth:`scope.get_defined_names
    <parsing_representation.Scope.get_defined_names>` does.

    - If `position` is given, delete all names defined after `position`.
    - For special objects like instances, `position` is ignored and all
      names are returned.

    :type     scope: :class:`parsing_representation.IsScope`
    :param    scope: Scope in which names are searched.
    :param position: the position as a line/column tuple, default is infinity.
    """
    names = scope.get_defined_names()
    # Instances have special rules, always return all the possible completions,
    # because class variables are always valid and the `self.` variables, too.
    if (not position or isinstance(scope, (er.Array, er.Instance))
                or start_scope != scope
                and isinstance(start_scope, (pr.Function, er.Execution))):
        return names
    names_new = []
    for n in names:
        if n.start_pos[0] is not None and n.start_pos < position:
            names_new.append(n)
    return names_new


def get_names_of_scope(scope, position=None, star_search=True,
                                                        include_builtin=True):
    """
    Get all completions (names) possible for the current scope.
    The star search option is only here to provide an optimization. Otherwise
    the whole thing would probably start a little recursive madness.

    This function is used to include names from outer scopes.  For example,
    when the current scope is function:

    >>> from jedi.parsing import Parser
    >>> parser = Parser('''
    ... x = ['a', 'b', 'c']
    ... def func():
    ...     y = None
    ... ''')
    >>> scope = parser.module.subscopes[0]
    >>> scope
    <Function: func@3-5>

    `get_names_of_scope` is a generator.  First it yields names from
    most inner scope.

    >>> pairs = list(get_names_of_scope(scope))
    >>> pairs[0]
    (<Function: func@3-5>, [<Name: y@4,4>])

    Then it yield the names from one level outer scope.  For this
    example, this is the most outer scope.

    >>> pairs[1]
    (<SubModule: None@1-5>, [<Name: x@2,0>, <Name: func@3,4>])

    Finally, it yields names from builtin, if `include_builtin` is
    true (default).

    >>> pairs[2]                                        #doctest: +ELLIPSIS
    (<Module: ...builtin...>, [<Name: ...>, ...])

    :rtype: [(pr.Scope, [pr.Name])]
    :return: Return an generator that yields a pair of scope and names.
    """
    in_func_scope = scope
    non_flow = scope.get_parent_until(pr.Flow, reverse=True)
    while scope:
        if isinstance(scope, pr.SubModule) and scope.parent:
            # we don't want submodules to report if we have modules.
            scope = scope.parent
            continue
        # `pr.Class` is used, because the parent is never `Class`.
        # Ignore the Flows, because the classes and functions care for that.
        # InstanceElement of Class is ignored, if it is not the start scope.
        if not (scope != non_flow and scope.isinstance(pr.Class)
                    or scope.isinstance(pr.Flow)
                    or scope.isinstance(er.Instance)
                        and non_flow.isinstance(er.Function)
                    ):
            try:
                if isinstance(scope, er.Instance):
                    for g in scope.scope_generator():
                        yield g
                else:
                    yield scope, get_defined_names_for_position(scope,
                                                    position, in_func_scope)
            except StopIteration:
                reraise(common.MultiLevelStopIteration, sys.exc_info()[2])
        if scope.isinstance(pr.ForFlow) and scope.is_list_comp:
            # is a list comprehension
            yield scope, scope.get_set_vars(is_internal_call=True)

        scope = scope.parent
        # This is used, because subscopes (Flow scopes) would distort the
        # results.
        if scope and scope.isinstance(er.Function, pr.Function, er.Execution):
            in_func_scope = scope

    # Add star imports.
    if star_search:
        for s in imports.remove_star_imports(non_flow.get_parent_until()):
            for g in get_names_of_scope(s, star_search=False):
                yield g

        # Add builtins to the global scope.
        if include_builtin:
            builtin_scope = builtin.Builtin.scope
            yield builtin_scope, builtin_scope.get_defined_names()


def find_name(scope, name_str, position=None, search_global=False,
                                                        is_goto=False):
    """
    This is the search function. The most important part to debug.
    `remove_statements` and `filter_statements` really are the core part of
    this completion.

    :param position: Position of the last statement -> tuple of line, column
    :return: List of Names. Their parents are the scopes, they are defined in.
    :rtype: list
    """
    def remove_statements(result):
        """
        This is the part where statements are being stripped.

        Due to lazy evaluation, statements like a = func; b = a; b() have to be
        evaluated.
        """
        res_new = []
        for r in result:
            add = []
            if r.isinstance(pr.Statement):
                check_instance = None
                if isinstance(r, er.InstanceElement) and r.is_class_var:
                    check_instance = r.instance
                    r = r.var

                # Global variables handling.
                if r.is_global():
                    for token_name in r.token_list[1:]:
                        if isinstance(token_name, pr.Name):
                            add = find_name(r.parent, str(token_name))
                else:
                    # generated objects are used within executions, but these
                    # objects are in functions, and we have to dynamically
                    # execute first.
                    if isinstance(r, pr.Param):
                        func = r.parent
                        # Instances are typically faked, if the instance is not
                        # called from outside. Here we check it for __init__
                        # functions and return.
                        if isinstance(func, er.InstanceElement) \
                                and func.instance.is_generated \
                                and hasattr(func, 'name') \
                                and str(func.name) == '__init__' \
                                and r.position_nr > 0:  # 0 would be self
                            r = func.var.params[r.position_nr]

                        # add docstring knowledge
                        doc_params = docstrings.follow_param(r)
                        if doc_params:
                            res_new += doc_params
                            continue

                        if not r.is_generated:
                            res_new += dynamic.search_params(r)
                            if not r.assignment_details:
                                # this means that there are no default params,
                                # so just ignore it.
                                continue

                    if r.docstr:
                        res_new.append(r)

                    scopes = follow_statement(r, seek_name=name_str)
                    add += remove_statements(scopes)

                if check_instance is not None:
                    # class renames
                    add = [er.InstanceElement(check_instance, a, True)
                                if isinstance(a, (er.Function, pr.Function))
                                else a for a in add]
                res_new += add
            else:
                if isinstance(r, pr.Class):
                    r = er.Class(r)
                elif isinstance(r, pr.Function):
                    r = er.Function(r)
                if r.isinstance(er.Function):
                    try:
                        r = r.get_decorated_func()
                    except er.DecoratorNotFound:
                        continue
                res_new.append(r)
        debug.dbg('sfn remove, new: %s, old: %s' % (res_new, result))
        return res_new

    def filter_name(scope_generator):
        """
        Filters all variables of a scope (which are defined in the
        `scope_generator`), until the name fits.
        """
        def handle_for_loops(loop):
            # Take the first statement (for has always only
            # one, remember `in`). And follow it.
            if not loop.inputs:
                return []
            result = get_iterator_types(follow_statement(loop.inputs[0]))
            if len(loop.set_vars) > 1:
                commands = loop.set_stmt.get_commands()
                # loops with loop.set_vars > 0 only have one command
                result = assign_tuples(commands[0], result, name_str)
            return result

        def process(name):
            """
            Returns the parent of a name, which means the element which stands
            behind a name.
            """
            result = []
            no_break_scope = False
            par = name.parent
            exc = pr.Class, pr.Function
            until = lambda: par.parent.parent.get_parent_until(exc)

            if par.isinstance(pr.Flow):
                if par.command == 'for':
                    result += handle_for_loops(par)
                else:
                    debug.warning('Flow: Why are you here? %s' % par.command)
            elif par.isinstance(pr.Param) \
                    and par.parent is not None \
                    and isinstance(until(), pr.Class) \
                    and par.position_nr == 0:
                # This is where self gets added - this happens at another
                # place, if the var_args are clear. But sometimes the class is
                # not known. Therefore add a new instance for self. Otherwise
                # take the existing.
                if isinstance(scope, er.InstanceElement):
                    inst = scope.instance
                else:
                    inst = er.Instance(er.Class(until()))
                    inst.is_generated = True
                result.append(inst)
            elif par.isinstance(pr.Statement):
                def is_execution(calls):
                    for c in calls:
                        if c.isinstance(pr.Array):
                            if is_execution(c):
                                return True
                        elif c.isinstance(pr.Call):
                            # Compare start_pos, because names may be different
                            # because of executions.
                            if c.name.start_pos == name.start_pos \
                                                            and c.execution:
                                return True
                    return False

                is_exe = False
                for assignee, op in par.assignment_details:
                    is_exe |= is_execution(assignee)

                if is_exe:
                    # filter array[3] = ...
                    # TODO check executions for dict contents
                    pass
                else:
                    details = par.assignment_details
                    if details and details[0][1] != '=':
                        no_break_scope = True

                    # TODO this makes self variables non-breakable. wanted?
                    if isinstance(name, er.InstanceElement) \
                                                and not name.is_class_var:
                        no_break_scope = True

                    result.append(par)
            else:
                result.append(par)
            return result, no_break_scope

        flow_scope = scope
        result = []
        # compare func uses the tuple of line/indent = line/column
        comparison_func = lambda name: (name.start_pos)

        for nscope, name_list in scope_generator:
            break_scopes = []
            # here is the position stuff happening (sorting of variables)
            for name in sorted(name_list, key=comparison_func, reverse=True):
                p = name.parent.parent if name.parent else None
                if isinstance(p, er.InstanceElement) \
                            and isinstance(p.var, pr.Class):
                    p = p.var
                if name_str == name.get_code() and p not in break_scopes:
                    r, no_break_scope = process(name)
                    if is_goto:
                        if r:
                            # Directly assign the name, but there has to be a
                            # result.
                            result.append(name)
                    else:
                        result += r
                    # for comparison we need the raw class
                    s = nscope.base if isinstance(nscope, er.Class) else nscope
                    # this means that a definition was found and is not e.g.
                    # in if/else.
                    if result and not no_break_scope:
                        if not name.parent or p == s:
                            break
                        break_scopes.append(p)

            while flow_scope:
                # TODO check if result is in scope -> no evaluation necessary
                n = dynamic.check_flow_information(flow_scope, name_str,
                                                                    position)
                if n:
                    result = n
                    break

                if result:
                    break
                if flow_scope == nscope:
                    break
                flow_scope = flow_scope.parent
            flow_scope = nscope
            if result:
                break

        if not result and isinstance(nscope, er.Instance):
            # __getattr__ / __getattribute__
            result += check_getattr(nscope, name_str)
        debug.dbg('sfn filter "%s" in (%s-%s): %s@%s' % (name_str, scope,
                                                nscope, result, position))
        return result

    def descriptor_check(result):
        """Processes descriptors"""
        res_new = []
        for r in result:
            if isinstance(scope, (er.Instance, er.Class)) \
                                and hasattr(r, 'get_descriptor_return'):
                # handle descriptors
                with common.ignored(KeyError):
                    res_new += r.get_descriptor_return(scope)
                    continue
            res_new.append(r)
        return res_new

    if search_global:
        scope_generator = get_names_of_scope(scope, position=position)
    else:
        if isinstance(scope, er.Instance):
            scope_generator = scope.scope_generator()
        else:
            if isinstance(scope, (er.Class, pr.Module)):
                # classes are only available directly via chaining?
                # strange stuff...
                names = scope.get_defined_names()
            else:
                names = get_defined_names_for_position(scope, position)
            scope_generator = iter([(scope, names)])

    if is_goto:
        return filter_name(scope_generator)
    return descriptor_check(remove_statements(filter_name(scope_generator)))


def check_getattr(inst, name_str):
    """Checks for both __getattr__ and __getattribute__ methods"""
    result = []
    # str is important to lose the NamePart!
    module = builtin.Builtin.scope
    name = pr.Call(module, str(name_str), pr.Call.STRING, (0, 0), inst)
    with common.ignored(KeyError):
        result = inst.execute_subscope_by_name('__getattr__', [name])
    if not result:
        # this is a little bit special. `__getattribute__` is executed
        # before anything else. But: I know no use case, where this
        # could be practical and the jedi would return wrong types. If
        # you ever have something, let me know!
        with common.ignored(KeyError):
            result = inst.execute_subscope_by_name('__getattribute__', [name])
    return result


def get_iterator_types(inputs):
    """Returns the types of any iterator (arrays, yields, __iter__, etc)."""
    iterators = []
    # Take the first statement (for has always only
    # one, remember `in`). And follow it.
    for it in inputs:
        if isinstance(it, (er.Generator, er.Array, dynamic.ArrayInstance)):
            iterators.append(it)
        else:
            if not hasattr(it, 'execute_subscope_by_name'):
                debug.warning('iterator/for loop input wrong', it)
                continue
            try:
                iterators += it.execute_subscope_by_name('__iter__')
            except KeyError:
                debug.warning('iterators: No __iter__ method found.')

    result = []
    for gen in iterators:
        if isinstance(gen, er.Array):
            # Array is a little bit special, since this is an internal
            # array, but there's also the list builtin, which is
            # another thing.
            result += gen.get_index_types()
        elif isinstance(gen, er.Instance):
            # __iter__ returned an instance.
            name = '__next__' if is_py3k else 'next'
            try:
                result += gen.execute_subscope_by_name(name)
            except KeyError:
                debug.warning('Instance has no __next__ function', gen)
        else:
            # is a generator
            result += gen.iter_content()
    return result


def assign_tuples(tup, results, seek_name):
    """
    This is a normal assignment checker. In python functions and other things
    can return tuples:
    >>> a, b = 1, ""
    >>> a, (b, c) = 1, ("", 1.0)

    Here, if `seek_name` is "a", the number type will be returned.
    The first part (before `=`) is the param tuples, the second one result.

    :type tup: pr.Array
    """
    def eval_results(index):
        types = []
        for r in results:
            try:
                func = r.get_exact_index_types
            except AttributeError:
                debug.warning("invalid tuple lookup %s of result %s in %s"
                                    % (tup, results, seek_name))
            else:
                with common.ignored(IndexError):
                    types += func(index)
        return types

    result = []
    for i, stmt in enumerate(tup):
        # Used in assignments. There is just one call and no other things,
        # therefore we can just assume, that the first part is important.
        command = stmt.get_commands()[0]

        if tup.type == pr.Array.NOARRAY:

                # unnessecary braces -> just remove.
            r = results
        else:
            r = eval_results(i)

        # are there still tuples or is it just a Call.
        if isinstance(command, pr.Array):
            # These are "sub"-tuples.
            result += assign_tuples(command, r, seek_name)
        else:
            if command.name.names[-1] == seek_name:
                result += r
    return result


@recursion.RecursionDecorator
@cache.memoize_default(default=())
def follow_statement(stmt, seek_name=None):
    """
    The starting point of the completion. A statement always owns a call list,
    which are the calls, that a statement does.
    In case multiple names are defined in the statement, `seek_name` returns
    the result for this name.

    :param stmt: A `pr.Statement`.
    :param seek_name: A string.
    """
    debug.dbg('follow_stmt %s (%s)' % (stmt, seek_name))
    commands = stmt.get_commands()
    debug.dbg('calls: %s' % commands)

    result = follow_call_list(commands)

    # Assignment checking is only important if the statement defines multiple
    # variables.
    if len(stmt.get_set_vars()) > 1 and seek_name and stmt.assignment_details:
        new_result = []
        for ass_commands, op in stmt.assignment_details:
            new_result += assign_tuples(ass_commands[0], result, seek_name)
        result = new_result
    return set(result)


@common.rethrow_uncaught
def follow_call_list(call_list, follow_array=False):
    """
    `call_list` can be either `pr.Array` or `list of list`.
    It is used to evaluate a two dimensional object, that has calls, arrays and
    operators in it.
    """
    def evaluate_list_comprehension(lc, parent=None):
        input = lc.input
        nested_lc = lc.input.token_list[0]
        if isinstance(nested_lc, pr.ListComprehension):
            # is nested LC
            input = nested_lc.stmt
        module = input.get_parent_until()
        # create a for loop, which does the same as list comprehensions
        loop = pr.ForFlow(module, [input], lc.stmt.start_pos, lc.middle, True)

        loop.parent = parent or lc.get_parent_until(pr.IsScope)

        if isinstance(nested_lc, pr.ListComprehension):
            loop = evaluate_list_comprehension(nested_lc, loop)
        return loop

    result = []
    calls_iterator = iter(call_list)
    for call in calls_iterator:
        if pr.Array.is_type(call, pr.Array.NOARRAY):
            r = list(itertools.chain.from_iterable(follow_statement(s)
                                                   for s in call))
            call_path = call.generate_call_path()
            next(call_path, None)  # the first one has been used already
            result += follow_paths(call_path, r, call.parent,
                                  position=call.start_pos)
        elif isinstance(call, pr.ListComprehension):
            loop = evaluate_list_comprehension(call)
            # Caveat: parents are being changed, but this doesn't matter,
            # because nothing else uses it.
            call.stmt.parent = loop
            result += follow_statement(call.stmt)
        else:
            if isinstance(call, pr.Lambda):
                result.append(er.Function(call))
            # With things like params, these can also be functions...
            elif isinstance(call, (er.Function, er.Class, er.Instance,
                                            dynamic.ArrayInstance)):
                result.append(call)
            # The string tokens are just operations (+, -, etc.)
            elif not isinstance(call, (str, unicode)):
                if str(call.name) == 'if':
                    # Ternary operators.
                    while True:
                        try:
                            call = next(calls_iterator)
                        except StopIteration:
                            break
                        with common.ignored(AttributeError):
                            if str(call.name) == 'else':
                                break
                    continue
                result += follow_call(call)
            elif call == '*':
                if [r for r in result if isinstance(r, er.Array)
                                or isinstance(r, er.Instance)
                                    and str(r.name) == 'str']:
                    # if it is an iterable, ignore * operations
                    next(calls_iterator)
    return set(result)


def follow_call(call):
    """Follow a call is following a function, variable, string, etc."""
    path = call.generate_call_path()

    # find the statement of the Scope
    s = call
    while not s.parent.isinstance(pr.IsScope):
        s = s.parent
    return follow_call_path(path, s.parent, s.start_pos)


def follow_call_path(path, scope, position):
    """Follows a path generated by `pr.Call.generate_call_path()`"""
    current = next(path)

    if isinstance(current, pr.Array):
        result = [er.Array(current)]
    else:
        if isinstance(current, pr.NamePart):
            # This is the first global lookup.
            scopes = find_name(scope, current, position=position,
                                            search_global=True)
        else:
            if current.type in (pr.Call.STRING, pr.Call.NUMBER):
                t = type(current.name).__name__
                scopes = find_name(builtin.Builtin.scope, t)
            else:
                debug.warning('unknown type:', current.type, current)
                scopes = []
            # Make instances of those number/string objects.
            scopes = [er.Instance(s, (current.name,)) for s in scopes]
        result = imports.strip_imports(scopes)

    return follow_paths(path, result, scope, position=position)


def follow_paths(path, results, call_scope, position=None):
    """
    In each result, `path` must be followed. Copies the path iterator.
    """
    results_new = []
    if results:
        if len(results) > 1:
            iter_paths = itertools.tee(path, len(results))
        else:
            iter_paths = [path]

        for i, r in enumerate(results):
            fp = follow_path(iter_paths[i], r, call_scope, position=position)
            if fp is not None:
                results_new += fp
            else:
                # This means stop iteration.
                return results
    return results_new


def follow_path(path, scope, call_scope, position=None):
    """
    Uses a generator and tries to complete the path, e.g.::

        foo.bar.baz

    `follow_path` is only responsible for completing `.bar.baz`, the rest is
    done in the `follow_call` function.
    """
    # current is either an Array or a Scope.
    try:
        current = next(path)
    except StopIteration:
        return None
    debug.dbg('follow %s in scope %s' % (current, scope))

    result = []
    if isinstance(current, pr.Array):
        # This must be an execution, either () or [].
        if current.type == pr.Array.LIST:
            if hasattr(scope, 'get_index_types'):
                result = scope.get_index_types(current)
        elif current.type not in [pr.Array.DICT]:
            # Scope must be a class or func - make an instance or execution.
            debug.dbg('exe', scope)
            result = er.Execution(scope, current).get_return_types()
        else:
            # Curly braces are not allowed, because they make no sense.
            debug.warning('strange function call with {}', current, scope)
    else:
        # The function must not be decorated with something else.
        if scope.isinstance(er.Function):
            scope = scope.get_magic_method_scope()
        else:
            # This is the typical lookup while chaining things.
            if filter_private_variable(scope, call_scope, current):
                return []
        result = imports.strip_imports(find_name(scope, current,
                                                    position=position))
    return follow_paths(path, set(result), call_scope, position=position)


def filter_private_variable(scope, call_scope, var_name):
    """private variables begin with a double underline `__`"""
    if isinstance(var_name, (str, unicode)) \
            and var_name.startswith('__') and isinstance(scope, er.Instance):
        s = call_scope.get_parent_until((pr.Class, er.Instance))
        if s != scope and s != scope.base.base:
            return True
    return False


def goto(stmt, call_path=None):
    if call_path is None:
        commands = stmt.get_commands()
        assert len(commands) == 1
        call = commands[0]
        call_path = list(call.generate_call_path())

    scope = stmt.get_parent_until(pr.IsScope)
    pos = stmt.start_pos
    call_path, search = call_path[:-1], call_path[-1]
    pos = pos[0], pos[1] + 1

    if call_path:
        scopes = follow_call_path(iter(call_path), scope, pos)
        search_global = False
        pos = None
    else:
        scopes = [scope]
        search_global = True
    follow_res = []
    for s in scopes:
        follow_res += find_name(s, search, pos,
                                    search_global=search_global, is_goto=True)
    return follow_res, search
