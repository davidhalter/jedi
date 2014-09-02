import copy
from itertools import chain

from jedi import common
from jedi.parser import representation as pr
from jedi import debug


def deep_ast_copy(obj, new_elements_default=None):
    """
    Much, much faster than copy.deepcopy, but just for Parser elements (Doesn't
    copy parents).
    """
    new_elements = new_elements_default or {}
    accept = (pr.Simple, pr.NamePart, pr.KeywordStatement)

    def recursion(obj):
        if isinstance(obj, pr.Statement):
            # Need to set _set_vars, otherwise the cache is not working
            # correctly, don't know why.
            obj.get_defined_names()

        try:
            return new_elements[obj]
        except KeyError:
            new_obj = copy.copy(obj)
            new_elements[obj] = new_obj

        try:
            items = list(new_obj.__dict__.items())
        except AttributeError:
            # __dict__ not available, because of __slots__
            items = []

        before = ()
        for cls in new_obj.__class__.__mro__:
            with common.ignored(AttributeError):
                if before == cls.__slots__:
                    continue
                before = cls.__slots__
                items += [(n, getattr(new_obj, n)) for n in before]

        for key, value in items:
            # replace parent (first try _parent and then parent)
            if key in ['parent', '_parent'] and value is not None:
                if key == 'parent' and '_parent' in items:
                    # parent can be a property
                    continue
                with common.ignored(KeyError):
                    setattr(new_obj, key, new_elements[value])
            elif key in ['parent_function', 'use_as_parent', '_sub_module']:
                continue
            elif isinstance(value, (list, tuple)):
                setattr(new_obj, key, list_or_tuple_rec(value))
            elif isinstance(value, accept):
                setattr(new_obj, key, recursion(value))
        return new_obj

    def list_or_tuple_rec(array_obj):
        if isinstance(array_obj, tuple):
            copied_array = list(array_obj)
        else:
            copied_array = array_obj[:]   # lists, tuples, strings, unicode
        for i, el in enumerate(copied_array):
            if isinstance(el, accept):
                copied_array[i] = recursion(el)
            elif isinstance(el, (tuple, list)):
                copied_array[i] = list_or_tuple_rec(el)

        if isinstance(array_obj, tuple):
            return tuple(copied_array)
        return copied_array

    return recursion(obj)


def call_signature_array_for_pos(stmt, pos):
    """
    Searches for the array and position of a tuple.
    Returns a tuple of (array, index-in-the-array, call).
    """
    def search_array(arr, pos, origin_call=None):
        accepted_types = pr.Array.TUPLE, pr.Array.NOARRAY
        if arr.type == 'dict':
            for stmt in arr.values + arr.keys:
                tup = call_signature_array_for_pos(stmt, pos)
                if tup[0] is not None:
                    return tup
        else:
            for i, stmt in enumerate(arr):
                tup = call_signature_array_for_pos(stmt, pos)
                if tup[0] is not None:
                    return tup

                # Since we need the index, we duplicate efforts (with empty
                # arrays).
                if arr.start_pos < pos <= stmt.end_pos:
                    if arr.type in accepted_types and origin_call:
                        return arr, i, origin_call

        if len(arr) == 0 and arr.start_pos < pos < arr.end_pos:
            if arr.type in accepted_types and origin_call:
                return arr, 0, origin_call
        return None, 0, None

    def search_call(call, pos, origin_call=None):
        tup = None, 0, None
        while call.next is not None and tup[0] is None:
            method = search_array if isinstance(call.next, pr.Array) else search_call
            # TODO This is wrong, don't call search_call again, because it will
            # automatically be called by call.next.
            tup = method(call.next, pos, origin_call or call)
            call = call.next
        return tup

    if stmt.start_pos >= pos >= stmt.end_pos:
        return None, 0, None

    tup = None, 0, None
    for command in stmt.expression_list():
        if isinstance(command, pr.Array):
            tup = search_array(command, pos)
        elif isinstance(command, pr.StatementElement):
            tup = search_call(command, pos, command)
        if tup[0] is not None:
            break
    return tup


def search_call_signatures(user_stmt, position):
    """
    Returns the function Call that matches the position before.
    """
    debug.speed('func_call start')
    call, arr, index = None, None, 0
    if user_stmt is not None and isinstance(user_stmt, pr.Statement):
        # some parts will of the statement will be removed
        user_stmt = deep_ast_copy(user_stmt)
        arr, index, call = call_signature_array_for_pos(user_stmt, position)

        # Now remove the part after the call. Including the array from the
        # statement.
        stmt_el = call
        while isinstance(stmt_el, pr.StatementElement):
            if stmt_el.next == arr:
                stmt_el.next = None
                break
            stmt_el = stmt_el.next

    debug.speed('func_call parsed')
    return call, arr, index


def scan_statement_for_calls(stmt, search_name, assignment_details=False):
    """ Returns the function Calls that match search_name in an Array. """
    def scan_array(arr, search_name):
        result = []
        if arr.type == pr.Array.DICT:
            for key_stmt, value_stmt in arr.items():
                result += scan_statement_for_calls(key_stmt, search_name)
                result += scan_statement_for_calls(value_stmt, search_name)
        else:
            for stmt in arr:
                result += scan_statement_for_calls(stmt, search_name)
        return result

    check = list(stmt.expression_list())
    if assignment_details:
        for expression_list, op in stmt.assignment_details:
            check += expression_list

    result = []
    for c in check:
        if isinstance(c, pr.Array):
            result += scan_array(c, search_name)
        elif isinstance(c, pr.Call):
            s_new = c
            while s_new is not None:
                if isinstance(s_new, pr.Array):
                    result += scan_array(s_new, search_name)
                else:
                    n = s_new.name
                    if isinstance(n, pr.Name) \
                            and search_name in [str(x) for x in n.names]:
                        result.append(c)

                s_new = s_new.next
        elif isinstance(c, pr.ListComprehension):
            for s in c.stmt, c.middle, c.input:
                result += scan_statement_for_calls(s, search_name)

    return result


def get_module_name_parts(module):
    """
    Returns a dictionary with name parts as keys and their call paths as
    values.
    """
    def scope_name_parts(scope):
        for s in scope.subscopes:
            # Yield the name parts, not names.
            yield s.name.names[0]
            for need_yield_from in scope_name_parts(s):
                yield need_yield_from

    statements_or_imports = set(chain(*module.used_names.values()))
    name_parts = set(scope_name_parts(module))
    for stmt_or_import in statements_or_imports:
        if isinstance(stmt_or_import, pr.Import):
            for name in stmt_or_import.get_all_import_names():
                name_parts.update(name.names)
        else:
            # Running this ensures that all the expression lists are generated
            # and the parents are all set. (Important for Lambdas) Howeer, this
            # is only necessary because of the weird fault-tolerant structure
            # of the parser. I hope to get rid of such behavior in the future.
            stmt_or_import.expression_list()
            # For now this is ok, but this could change if we don't have a
            # token_list anymore, but for now this is the easiest way to get
            # all the name_parts.
            for tok in stmt_or_import._token_list:
                if isinstance(tok, pr.Name):
                    name_parts.update(tok.names)

    return name_parts


def statement_elements_in_statement(stmt):
    """
    Returns a list of statements. Statements can contain statements again in
    Arrays.
    """
    def search_stmt_el(stmt_el, stmt_els):
        stmt_els.append(stmt_el)
        while stmt_el is not None:
            if isinstance(stmt_el, pr.Array):
                for stmt in stmt_el.values + stmt_el.keys:
                    stmt_els.extend(statement_elements_in_statement(stmt))
            stmt_el = stmt_el.next

    stmt_els = []
    for as_name in stmt.as_names:
        # TODO This creates a custom pr.Call, we shouldn't do that.
        stmt_els.append(pr.Call(as_name._sub_module, as_name,
                                as_name.start_pos, as_name.end_pos))

    ass_items = chain.from_iterable(items for items, op in stmt.assignment_details)
    for item in stmt.expression_list() + list(ass_items):
        if isinstance(item, pr.StatementElement):
            search_stmt_el(item, stmt_els)
        elif isinstance(item, pr.ListComprehension):
            for stmt in (item.stmt, item.middle, item.input):
                stmt_els.extend(statement_elements_in_statement(stmt))
        elif isinstance(item, pr.Lambda):
            for stmt in item.params + item.returns:
                stmt_els.extend(statement_elements_in_statement(stmt))

    return stmt_els


class FakeSubModule():
    line_offset = 0


class FakeArray(pr.Array):
    def __init__(self, values, parent=None, arr_type=pr.Array.LIST):
        p = (0, 0)
        super(FakeArray, self).__init__(FakeSubModule, p, arr_type, parent)
        self.values = values


class FakeStatement(pr.Statement):
    def __init__(self, expression_list, start_pos=(0, 0), parent=None):
        p = start_pos
        super(FakeStatement, self).__init__(FakeSubModule, expression_list, p, p)
        self.set_expression_list(expression_list)
        self.parent = parent


class FakeImport(pr.Import):
    def __init__(self, name, parent, level=0):
        p = 0, 0
        super(FakeImport, self).__init__(FakeSubModule, p, p, name,
                                         relative_count=level)
        self.parent = parent


class FakeName(pr.Name):
    def __init__(self, name_or_names, parent=None):
        p = 0, 0
        if isinstance(name_or_names, list):
            names = [(n, p) for n in name_or_names]
        else:
            names = [(name_or_names, p)]
        super(FakeName, self).__init__(FakeSubModule, names, p, p, parent)


class LazyName(FakeName):
    def __init__(self, name, parent_callback):
        super(LazyName, self).__init__(name)
        self._parent_callback = parent_callback

    @property
    def parent(self):
        return self._parent_callback()

    @parent.setter
    def parent(self, value):
        pass  # Do nothing, lower level can try to set the parent.


def stmts_to_stmt(statements):
    """
    Sometimes we want to have something like a result_set and unite some
    statements in one.
    """
    if len(statements) == 1:
        return statements[0]
    array = FakeArray(statements, arr_type=pr.Array.NOARRAY)
    return FakeStatement([array])
