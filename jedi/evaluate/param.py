import copy

from jedi._compatibility import unicode
from jedi.parser import representation as pr
from jedi.evaluate import iterable
from jedi import common
from jedi.evaluate import helpers
from jedi.evaluate import analysis


def get_params(evaluator, func, var_args):
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
    # There may be calls, which don't fit all the params, this just ignores it.
    var_arg_iterator = common.PushBackIterator(_var_args_iterator(evaluator, var_args))

    non_matching_keys = []
    keys_used = set()
    keys_only = False
    value = None
    for param in func.params[start_offset:]:
        # The value and key can both be null. There, the defaults apply.
        # args / kwargs will just be empty arrays / dicts, respectively.
        # Wrong value count is just ignored. If you try to test cases that are
        # not allowed in Python, Jedi will maybe not show any completions.
        key, value = next(var_arg_iterator, (None, None))
        while key:
            keys_only = True
            try:
                key_param = param_dict[unicode(key)]
            except KeyError:
                non_matching_keys.append((key, value))
            else:
                k = unicode(key)
                if k in keys_used:
                    print(keys_used, unicode(key), value)
                    m = ("TypeError: %s() got multiple values for keyword argument '%s'."
                         % (func.name, k))
                    analysis.add(evaluator, 'type-error-multiple-values',
                                 var_args, message=m)
                else:
                    keys_used.add(k)
                    result.append(_gen_param_name_copy(func, var_args, key_param,
                                                       values=[value]))
            key, value = next(var_arg_iterator, (None, None))

        keys = []
        values = []
        array_type = None
        has_default_value = False
        if param.stars == 1:
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
        elif param.stars == 2:
            # **kwargs param
            array_type = pr.Array.DICT
            if non_matching_keys:
                keys, values = zip(*non_matching_keys)
            non_matching_keys = []
        else:
            # normal param
            if value is None:
                if param.assignment_details:
                    # No value: return the default values.
                    has_default_value = True
                    result.append(param.get_name())
                    param.is_generated = True
                else:
                    # If there is no assignment detail, that means there is no
                    # assignment, just the result. Therefore nothing has to be
                    # returned.
                    values = []
                    if not keys_only and isinstance(var_args, pr.Array):
                        #print(var_args, var_args.start_pos, id(var_args))
                        #original_var_ars = var_args
                        #if len(var_args) == 0:
                        #    print(original_var_ars)
                        m = _error_argument_count(func, len(var_args))
                        analysis.add(evaluator, 'type-error-too-few-arguments',
                                     var_args, message=m)
            else:
                values = [value]

        # Now add to result if it's not one of the previously covered cases.
        if not has_default_value and (not keys_only or param.stars == 2):
            keys_used.add(unicode(param.get_name()))
            result.append(_gen_param_name_copy(func, var_args, param,
                                               keys=keys, values=values,
                                               array_type=array_type))

    if keys_only:
        # All arguments should be handed over to the next function. It's not
        # about the values inside, it's about the names. Jedi needs to now that
        # there's nothing to find for certain names.
        for k in set(param_dict) - keys_used:
            result.append(_gen_param_name_copy(func, var_args, param_dict[k]))

    for key, value in non_matching_keys:
        m = "TypeError: %s() got an unexpected keyword argument '%s'." \
            % (func.name, key)
        analysis.add(evaluator, 'type-error-keyword-argument', value, message=m)

    remaining_params = list(var_arg_iterator)
    if remaining_params:
        m = _error_argument_count(func, len(func.params) + len(remaining_params))
        analysis.add(evaluator, 'type-error-too-many-arguments',
                     remaining_params[0][1], message=m)
    return result


def _var_args_iterator(evaluator, var_args):
    """
    Yields a key/value pair, the key is None, if its not a named arg.
    """
    # `var_args` is typically an Array, and not a list.
    for stmt in var_args:
        if not isinstance(stmt, pr.Statement):
            if stmt is None:
                yield None, None
                continue
            old = stmt
            # generate a statement if it's not already one.
            stmt = helpers.FakeStatement([old])

        # *args
        expression_list = stmt.expression_list()
        if not len(expression_list):
            continue
        if expression_list[0] == '*':
            # *args must be some sort of an array, otherwise -> ignore
            for array in evaluator.eval_expression_list(expression_list[1:]):
                if isinstance(array, iterable.Array):
                    #print('star', array, id(array))
                    for field_stmt in array:  # yield from plz!
                        yield None, field_stmt
                elif isinstance(array, iterable.Generator):
                    for field_stmt in array.iter_content():
                        yield None, helpers.FakeStatement([field_stmt])
        # **kwargs
        elif expression_list[0] == '**':
            for array in evaluator.eval_expression_list(expression_list[1:]):
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


def _gen_param_name_copy(func, var_args, param, keys=(), values=(), array_type=None):
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
    arr = pr.Array(helpers.FakeSubModule, start_pos, array_type, parent)
    #print('create', id(arr))
    arr.values = values
    key_stmts = []
    for key in keys:
        key_stmts.append(helpers.FakeStatement([key], start_pos))
    arr.keys = key_stmts
    arr.type = array_type

    new_param.set_expression_list([arr])

    name = copy.copy(param.get_name())
    name.parent = new_param
    return name


def _error_argument_count(func, actual_count):
    return ('TypeError: %s() takes exactly %s arguments (%s given).'
            % (func.name, len(func.params), actual_count))
