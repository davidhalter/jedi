"""
Searcjing for names with given scope and name. This is very central in Jedi and
Python. The name resolution is quite complicated with descripter,
``__getattribute__``, ``__getattr__``, ``global``, etc.

Flow checks
+++++++++++

Flow checks are not really mature. There's only a check for ``isinstance``.  It
would check whether a flow has the form of ``if isinstance(a, type_or_tuple)``.
Unfortunately every other thing is being ignored (e.g. a == '' would be easy to
check for -> a is a string). There's big potential in these checks.
"""
from itertools import chain

from jedi._compatibility import hasattr, unicode, u
from jedi.parser import representation as pr, tokenize
from jedi.parser import fast
from jedi import debug
from jedi import common
from jedi import settings
from jedi.evaluate import representation as er
from jedi.evaluate import dynamic
from jedi.evaluate import compiled
from jedi.evaluate import docstrings
from jedi.evaluate import iterable
from jedi.evaluate import imports
from jedi.evaluate import analysis
from jedi.evaluate import precedence


class NameFinder(object):
    def __init__(self, evaluator, scope, name_str, position=None):
        self._evaluator = evaluator
        self.scope = scope
        self.name_str = name_str
        self.position = position

    @debug.increase_indent
    def find(self, scopes, resolve_decorator=True, search_global=False):
        if unicode(self.name_str) == 'None':
            # Filter None, because it's really just a keyword, nobody wants to
            # access it.
            return []

        names = self.filter_name(scopes)
        types = self._names_to_types(names, resolve_decorator)

        if not names and not types \
                and not (isinstance(self.name_str, pr.NamePart)
                         and isinstance(self.name_str.parent.parent, pr.Param)):
            if not isinstance(self.name_str, (str, unicode)):  # TODO Remove?
                if search_global:
                    message = ("NameError: name '%s' is not defined."
                               % self.name_str)
                    analysis.add(self._evaluator, 'name-error', self.name_str,
                                 message)
                else:
                    analysis.add_attribute_error(self._evaluator,
                                                 self.scope, self.name_str)

        debug.dbg('finder._names_to_types: %s -> %s', names, types)
        return self._resolve_descriptors(types)

    def scopes(self, search_global=False):
        if search_global:
            return get_names_of_scope(self._evaluator, self.scope, self.position)
        else:
            return self.scope.scope_names_generator(self.position)

    def filter_name(self, scope_names_generator):
        """
        Filters all variables of a scope (which are defined in the
        `scope_names_generator`), until the name fits.
        """
        result = []
        for name_list_scope, name_list in scope_names_generator:
            break_scopes = []
            if not isinstance(name_list_scope, compiled.CompiledObject):
                # Here is the position stuff happening (sorting of variables).
                # Compiled objects don't need that, because there's only one
                # reference.
                name_list = sorted(name_list, key=lambda n: n.start_pos, reverse=True)

            for name in name_list:
                if unicode(self.name_str) != name.get_code():
                    continue

                scope = name.parent.parent
                if scope in break_scopes:
                    continue

                # Exclude `arr[1] =` from the result set.
                if not self._name_is_array_assignment(name):
                    result.append(name)

                if result and self._is_name_break_scope(name):
                    if self._does_scope_break_immediately(scope, name_list_scope):
                        break
                    else:
                        break_scopes.append(scope)
            if result:
                break

        scope_txt = (self.scope if self.scope == name_list_scope
                     else '%s-%s' % (self.scope, name_list_scope))
        debug.dbg('finder.filter_name "%s" in (%s): %s@%s', self.name_str,
                  scope_txt, u(result), self.position)
        return result

    def _check_getattr(self, inst):
        """Checks for both __getattr__ and __getattribute__ methods"""
        result = []
        # str is important to lose the NamePart!
        name = compiled.create(self._evaluator, str(self.name_str))
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

    def _is_name_break_scope(self, name):
        """
        Returns True except for nested imports and instance variables.
        """
        par = name.parent
        if par.isinstance(pr.Statement):
            if isinstance(name, er.InstanceElement) and not name.is_class_var:
                return False
        elif isinstance(par, pr.Import) and par.is_nested():
            return False
        return True

    def _does_scope_break_immediately(self, scope, name_list_scope):
        """
        In comparison to everthing else, if/while/etc doesn't break directly,
        because there are multiple different places in which a variable can be
        defined.
        """
        if isinstance(scope, pr.Flow) \
                or isinstance(scope, pr.KeywordStatement) and scope.name == 'global':

            # Check for `if foo is not None`, because Jedi is not interested in
            # None values, so this is the only branch we actually care about.
            # ATM it carries the same issue as the isinstance checks. It
            # doesn't work with instance variables (self.foo).
            if isinstance(scope, pr.Flow) and scope.command in ('if', 'while'):
                try:
                    expression_list = scope.inputs[0].expression_list()
                except IndexError:
                    pass
                else:
                    p = precedence.create_precedence(expression_list)
                    if (isinstance(p, precedence.Precedence)
                            and p.operator.string == 'is not'
                            and p.right.get_code() == 'None'
                            and p.left.get_code() == unicode(self.name_str)):
                        return True

            if isinstance(name_list_scope, er.Class):
                name_list_scope = name_list_scope.base
            return scope == name_list_scope
        else:
            return True

    def _name_is_array_assignment(self, name):
        if name.parent.isinstance(pr.Statement):
            def is_execution(calls):
                for c in calls:
                    if isinstance(c, (unicode, str, tokenize.Token)):
                        continue
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
            for assignee, op in name.parent.assignment_details:
                is_exe |= is_execution(assignee)

            if is_exe:
                # filter array[3] = ...
                # TODO check executions for dict contents
                return True
        return False

    def _names_to_types(self, names, resolve_decorator):
        types = []
        # Add isinstance and other if/assert knowledge.
        flow_scope = self.scope
        evaluator = self._evaluator
        while flow_scope:
            # TODO check if result is in scope -> no evaluation necessary
            n = check_flow_information(evaluator, flow_scope,
                                       self.name_str, self.position)
            if n:
                return n
            flow_scope = flow_scope.parent

        for name in names:
            typ = name.parent
            if typ.isinstance(pr.ForFlow):
                types += self._handle_for_loops(typ)
            elif isinstance(typ, pr.Param):
                types += self._eval_param(typ)
            elif typ.isinstance(pr.Statement):
                if typ.is_global():
                    # global keyword handling.
                    types += evaluator.find_types(typ.parent.parent, str(name))
                else:
                    types += self._remove_statements(typ, name)
            else:
                if isinstance(typ, pr.Class):
                    typ = er.Class(evaluator, typ)
                elif isinstance(typ, pr.Function):
                    typ = er.Function(evaluator, typ)
                elif isinstance(typ, pr.Module):
                    typ = er.ModuleWrapper(evaluator, typ)

                if typ.isinstance(er.Function) and resolve_decorator:
                    typ = typ.get_decorated_func()
                types.append(typ)

        if not names and isinstance(self.scope, er.Instance):
            # handling __getattr__ / __getattribute__
            types = self._check_getattr(self.scope)

        return types

    def _remove_statements(self, stmt, name):
        """
        This is the part where statements are being stripped.

        Due to lazy evaluation, statements like a = func; b = a; b() have to be
        evaluated.
        """
        evaluator = self._evaluator
        types = []
        # Remove the statement docstr stuff for now, that has to be
        # implemented with the evaluator class.
        #if stmt.docstr:
            #res_new.append(stmt)

        check_instance = None
        if isinstance(stmt, er.InstanceElement) and stmt.is_class_var:
            check_instance = stmt.instance
            stmt = stmt.var

        types += evaluator.eval_statement(stmt, seek_name=unicode(self.name_str))

        # check for `except X as y` usages, because y needs to be instantiated.
        p = stmt.parent
        # TODO this looks really hacky, improve parser representation!
        if isinstance(p, pr.Flow) and p.command == 'except' \
                and p.inputs and p.inputs[0].as_names == [name]:
            # TODO check for types that are not classes and add it to the
            # static analysis report.
            types = list(chain.from_iterable(
                         evaluator.execute(t) for t in types))

        if check_instance is not None:
            # class renames
            types = [er.InstanceElement(evaluator, check_instance, a, True)
                     if isinstance(a, (er.Function, pr.Function))
                     else a for a in types]
        return types

    def _eval_param(self, param):
        evaluator = self._evaluator
        res_new = []
        func = param.parent

        cls = func.parent.get_parent_until((pr.Class, pr.Function))

        from jedi.evaluate.param import ExecutedParam
        if isinstance(cls, pr.Class) and param.position_nr == 0 \
                and not isinstance(param, ExecutedParam):
            # This is where we add self - if it has never been
            # instantiated.
            if isinstance(self.scope, er.InstanceElement):
                res_new.append(self.scope.instance)
            else:
                for inst in evaluator.execute(er.Class(evaluator, cls)):
                    inst.is_generated = True
                    res_new.append(inst)
            return res_new

        # Instances are typically faked, if the instance is not called from
        # outside. Here we check it for __init__ functions and return.
        if isinstance(func, er.InstanceElement) \
                and func.instance.is_generated and str(func.name) == '__init__':
            param = func.var.params[param.position_nr]

        # Add docstring knowledge.
        doc_params = docstrings.follow_param(evaluator, param)
        if doc_params:
            return doc_params

        if not param.is_generated:
            # Param owns no information itself.
            res_new += dynamic.search_params(evaluator, param)
            if not res_new:
                if param.stars:
                    t = 'tuple' if param.stars == 1 else 'dict'
                    typ = evaluator.find_types(compiled.builtin, t)[0]
                    res_new = evaluator.execute(typ)
            if not param.assignment_details:
                # this means that there are no default params,
                # so just ignore it.
                return res_new
        return res_new + evaluator.eval_statement(param, seek_name=unicode(self.name_str))

    def _handle_for_loops(self, loop):
        # Take the first statement (for has always only one`in`).
        if not loop.inputs:
            return []
        result = iterable.get_iterator_types(self._evaluator.eval_statement(loop.inputs[0]))
        if len(loop.set_vars) > 1:
            expression_list = loop.set_stmt.expression_list()
            # loops with loop.set_vars > 0 only have one command
            result = _assign_tuples(expression_list[0], result, unicode(self.name_str))
        return result

    def _resolve_descriptors(self, types):
        """Processes descriptors"""
        result = []
        for r in types:
            if isinstance(self.scope, (er.Instance, er.Class)) \
                    and hasattr(r, 'get_descriptor_return'):
                # handle descriptors
                with common.ignored(KeyError):
                    result += r.get_descriptor_return(self.scope)
                    continue
            result.append(r)
        return result


def check_flow_information(evaluator, flow, search_name_part, pos):
    """ Try to find out the type of a variable just with the information that
    is given by the flows: e.g. It is also responsible for assert checks.::

        if isinstance(k, str):
            k.  # <- completion here

    ensures that `k` is a string.
    """
    if not settings.dynamic_flow_information:
        return None

    result = []
    if isinstance(flow, pr.IsScope) and not result:
        for ass in reversed(flow.asserts):
            if pos is None or ass.start_pos > pos:
                continue
            result = _check_isinstance_type(evaluator, ass, search_name_part)
            if result:
                break

    if isinstance(flow, pr.Flow) and not result:
        if flow.command in ['if', 'while'] and len(flow.inputs) == 1:
            result = _check_isinstance_type(evaluator, flow.inputs[0], search_name_part)
    return result


def _check_isinstance_type(evaluator, stmt, search_name_part):
    try:
        expression_list = stmt.expression_list()
        # this might be removed if we analyze and, etc
        assert len(expression_list) == 1
        call = expression_list[0]
        assert isinstance(call, pr.Call) and str(call.name) == 'isinstance'
        assert bool(call.execution)

        # isinstance check
        isinst = call.execution.values
        assert len(isinst) == 2  # has two params
        obj, classes = [statement.expression_list() for statement in isinst]
        assert len(obj) == 1
        assert len(classes) == 1
        assert isinstance(obj[0], pr.Call)

        # names fit?
        assert unicode(obj[0].name) == unicode(search_name_part)
        assert isinstance(classes[0], pr.StatementElement)  # can be type or tuple
    except AssertionError:
        return []

    result = []
    for c in evaluator.eval_call(classes[0]):
        for typ in (c.values() if isinstance(c, iterable.Array) else [c]):
            result += evaluator.execute(typ)
    return result


def get_names_of_scope(evaluator, scope, position=None, star_search=True, include_builtin=True):
    """
    Get all completions (names) possible for the current scope. The star search
    option is only here to provide an optimization. Otherwise the whole thing
    would probably start a little recursive madness.

    This function is used to include names from outer scopes. For example, when
    the current scope is function:

    >>> from jedi._compatibility import u
    >>> from jedi.parser import Parser
    >>> parser = Parser(u('''
    ... x = ['a', 'b', 'c']
    ... def func():
    ...     y = None
    ... '''))
    >>> scope = parser.module.subscopes[0]
    >>> scope
    <Function: func@3-5>

    `get_names_of_scope` is a generator.  First it yields names from most inner
    scope.

    >>> from jedi.evaluate import Evaluator
    >>> pairs = list(get_names_of_scope(Evaluator(), scope))
    >>> pairs[0]
    (<Function: func@3-5>, [<Name: y@4,4>])

    Then it yield the names from one level outer scope. For this example, this
    is the most outer scope.

    >>> pairs[1]
    (<ModuleWrapper: <SubModule: None@1-5>>, [<Name: x@2,0>, <Name: func@3,4>])

    After that we have a few underscore names that have been defined

    >>> pairs[2]
    (<ModuleWrapper: <SubModule: None@1-5>>, [<FakeName: __file__@0,0>, ...])


    Finally, it yields names from builtin, if `include_builtin` is
    true (default).

    >>> pairs[3]                                        #doctest: +ELLIPSIS
    (<Builtin: ...builtin...>, [<CompiledName: ...>, ...])

    :rtype: [(pr.Scope, [pr.Name])]
    :return: Return an generator that yields a pair of scope and names.
    """
    if isinstance(scope, pr.ListComprehension):
        position = scope.parent.start_pos

    in_func_scope = scope
    non_flow = scope.get_parent_until(pr.Flow, reverse=True)
    while scope:
        # We don't want submodules to report if we have modules.
        # As well as some non-scopes, which are parents of list comprehensions.
        if isinstance(scope, pr.SubModule) and scope.parent or not scope.is_scope():
            scope = scope.parent
            continue
        # `pr.Class` is used, because the parent is never `Class`.
        # Ignore the Flows, because the classes and functions care for that.
        # InstanceElement of Class is ignored, if it is not the start scope.
        if not (scope != non_flow and scope.isinstance(pr.Class)
                or scope.isinstance(pr.Flow)
                or scope.isinstance(er.Instance)
                and non_flow.isinstance(er.Function)
                or isinstance(scope, compiled.CompiledObject)
                and scope.type() == 'class' and in_func_scope != scope):

            if isinstance(scope, (pr.SubModule, fast.Module)):
                scope = er.ModuleWrapper(evaluator, scope)

            for g in scope.scope_names_generator(position):
                yield g
        if scope.isinstance(pr.ListComprehension):
            # is a list comprehension
            yield scope, scope.get_defined_names(is_internal_call=True)

        scope = scope.parent
        # This is used, because subscopes (Flow scopes) would distort the
        # results.
        if scope and scope.isinstance(er.Function, pr.Function, er.FunctionExecution):
            in_func_scope = scope
        if in_func_scope != scope \
                and isinstance(in_func_scope, (pr.Function, er.FunctionExecution)):
            position = None

    # Add star imports.
    if star_search:
        for s in imports.remove_star_imports(evaluator, non_flow.get_parent_until()):
            for g in get_names_of_scope(evaluator, s, star_search=False):
                yield g

        # Add builtins to the global scope.
        if include_builtin:
            yield compiled.builtin, compiled.builtin.get_defined_names()


def _assign_tuples(tup, results, seek_name):
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
                debug.warning("invalid tuple lookup %s of result %s in %s",
                              tup, results, seek_name)
            else:
                with common.ignored(IndexError):
                    types += func(index)
        return types

    result = []
    for i, stmt in enumerate(tup):
        # Used in assignments. There is just one call and no other things,
        # therefore we can just assume, that the first part is important.
        command = stmt.expression_list()[0]

        if tup.type == pr.Array.NOARRAY:

                # unnessecary braces -> just remove.
            r = results
        else:
            r = eval_results(i)

        # LHS of tuples can be nested, so resolve it recursively
        result += find_assignments(command, r, seek_name)
    return result


def find_assignments(lhs, results, seek_name):
    """
    Check if `seek_name` is in the left hand side `lhs` of assignment.

    `lhs` can simply be a variable (`pr.Call`) or a tuple/list (`pr.Array`)
    representing the following cases::

        a = 1        # lhs is pr.Call
        (a, b) = 2   # lhs is pr.Array

    :type lhs: pr.Call
    :type results: list
    :type seek_name: str
    """
    if isinstance(lhs, pr.Array):
        return _assign_tuples(lhs, results, seek_name)
    elif unicode(lhs.name.names[-1]) == seek_name:
        return results
    else:
        return []
