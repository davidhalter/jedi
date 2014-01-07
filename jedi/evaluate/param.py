import copy

from jedi.parser import representation as pr
from jedi.evaluate import iterable
from jedi.evaluate import builtin
from jedi.evaluate import common


def get_params(evaluator, func, var_args):
    def gen_param_name_copy(param, keys=(), values=(), array_type=None):
        """
        Create a param with the original scope (of varargs) as parent.
        """
        if isinstance(var_args, pr.Array):
            parent = var_args.parent
            start_pos = var_args.start_pos
        else:
            parent = func
            start_pos = 0, 0

        new_param = copy.copy(param)
        new_param.is_generated = True
        if parent is not None:
            new_param.parent = parent

        # create an Array (-> needed for *args/**kwargs tuples/dicts)
        arr = pr.Array(_FakeSubModule, start_pos, array_type, parent)
        arr.values = values
        key_stmts = []
        for key in keys:
            stmt = pr.Statement(_FakeSubModule, [], start_pos, None)
            stmt._expression_list = [key]
            key_stmts.append(stmt)
        arr.keys = key_stmts
        arr.type = array_type

        new_param._expression_list = [arr]

        name = copy.copy(param.get_name())
        name.parent = new_param
        return name

    result = []
    start_offset = 0
    from jedi.evaluate.representation import InstanceElement
    if isinstance(func, InstanceElement):
        # Care for self -> just exclude it and add the instance
        start_offset = 1
        self_name = copy.copy(func.params[0].get_name())
        self_name.parent = func.instance
        result.append(self_name)

    param_dict = {}
    for param in func.params:
        param_dict[str(param.get_name())] = param
    # There may be calls, which don't fit all the params, this just ignores
    # it.
    var_arg_iterator = _get_var_args_iterator(evaluator, var_args)

    non_matching_keys = []
    keys_used = set()
    keys_only = False
    for param in func.params[start_offset:]:
        # The value and key can both be null. There, the defaults apply.
        # args / kwargs will just be empty arrays / dicts, respectively.
        # Wrong value count is just ignored. If you try to test cases that
        # are not allowed in Python, Jedi will maybe not show any
        # completions.
        key, value = next(var_arg_iterator, (None, None))
        while key:
            keys_only = True
            try:
                key_param = param_dict[str(key)]
            except KeyError:
                non_matching_keys.append((key, value))
            else:
                keys_used.add(str(key))
                result.append(gen_param_name_copy(key_param,
                                                  values=[value]))
            key, value = next(var_arg_iterator, (None, None))

        expression_list = param.expression_list()
        keys = []
        values = []
        array_type = None
        ignore_creation = False
        if expression_list[0] == '*':
            # *args param
            array_type = pr.Array.TUPLE
            if value:
                values.append(value)
            for key, value in var_arg_iterator:
                # Iterate until a key argument is found.
                if key:
                    var_arg_iterator.push_back((key, value))
                    break
                values.append(value)
        elif expression_list[0] == '**':
            # **kwargs param
            array_type = pr.Array.DICT
            if non_matching_keys:
                keys, values = zip(*non_matching_keys)
        elif not keys_only:
            # normal param
            if value is not None:
                values = [value]
            else:
                if param.assignment_details:
                    # No value: return the default values.
                    ignore_creation = True
                    result.append(param.get_name())
                    param.is_generated = True
                else:
                    # If there is no assignment detail, that means there is
                    # no assignment, just the result. Therefore nothing has
                    # to be returned.
                    values = []

        # Just ignore all the params that are without a key, after one
        # keyword argument was set.
        if not ignore_creation and (not keys_only or expression_list[0] == '**'):
            keys_used.add(str(key))
            result.append(gen_param_name_copy(param, keys=keys,
                                              values=values, array_type=array_type))

    if keys_only:
        # sometimes param arguments are not completely written (which would
        # create an Exception, but we have to handle that).
        for k in set(param_dict) - keys_used:
            result.append(gen_param_name_copy(param_dict[k]))
    return result


def _get_var_args_iterator(evaluator, var_args):
    """
    Yields a key/value pair, the key is None, if its not a named arg.
    """
    def iterate():
        # `var_args` is typically an Array, and not a list.
        for stmt in var_args:
            if not isinstance(stmt, pr.Statement):
                if stmt is None:
                    yield None, None
                    continue
                old = stmt
                # generate a statement if it's not already one.
                module = builtin.Builtin.scope
                stmt = pr.Statement(module, [], (0, 0), None)
                stmt._expression_list = [old]

            # *args
            expression_list = stmt.expression_list()
            if not len(expression_list):
                continue
            if expression_list[0] == '*':
                arrays = evaluator.eval_expression_list(expression_list[1:])
                # *args must be some sort of an array, otherwise -> ignore

                for array in arrays:
                    if isinstance(array, iterable.Array):
                        for field_stmt in array:  # yield from plz!
                            yield None, field_stmt
                    elif isinstance(array, iterable.Generator):
                        for field_stmt in array.iter_content():
                            yield None, _FakeStatement(field_stmt)
            # **kwargs
            elif expression_list[0] == '**':
                arrays = evaluator.eval_expression_list(expression_list[1:])
                for array in arrays:
                    if isinstance(array, iterable.Array):
                        for key_stmt, value_stmt in array.items():
                            # first index, is the key if syntactically correct
                            call = key_stmt.expression_list()[0]
                            if isinstance(call, pr.Name):
                                yield call, value_stmt
                            elif isinstance(call, pr.Call):
                                yield call.name, value_stmt
            # Normal arguments (including key arguments).
            else:
                if stmt.assignment_details:
                    key_arr, op = stmt.assignment_details[0]
                    # named parameter
                    if key_arr and isinstance(key_arr[0], pr.Call):
                        yield key_arr[0].name, stmt
                else:
                    yield None, stmt

    return iter(common.PushBackIterator(iterate()))


class _FakeSubModule():
    line_offset = 0


class _FakeStatement(pr.Statement):
    def __init__(self, content):
        cls = type(self)
        p = 0, 0
        super(cls, self).__init__(_FakeSubModule, [content], p, p)
