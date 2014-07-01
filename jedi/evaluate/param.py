import copy

from jedi._compatibility import unicode, zip_longest
from jedi.parser import representation as pr
from jedi.evaluate import iterable
from jedi import common
from jedi.evaluate import helpers
from jedi.evaluate import analysis
from jedi.evaluate.compiled import CompiledObject


class ExecutedParam(pr.Param):
    def __init__(self):
        """Don't use this method, it's just here to overwrite the old one."""
        pass

    @classmethod
    def from_param(cls, param, parent, var_args):
        instance = cls()
        before = ()
        for cls in param.__class__.__mro__:
            with common.ignored(AttributeError):
                if before == cls.__slots__:
                    continue
                before = cls.__slots__
                for name in before:
                    setattr(instance, name, getattr(param, name))

        instance.original_param = param
        instance.is_generated = True
        instance.parent = parent
        instance.var_args = var_args
        return instance


def _get_calling_var_args(evaluator, var_args):
    old_var_args = None
    while var_args != old_var_args:
        old_var_args = var_args
        for argument in reversed(var_args):
            if not isinstance(argument, pr.Statement):
                continue
            exp_list = argument.expression_list()
            if len(exp_list) != 2 or exp_list[0] not in ('*', '**'):
                continue

            names, _ = evaluator.goto(argument, [exp_list[1].get_code()])
            if len(names) != 1:
                break
            param = names[0].parent
            if not isinstance(param, ExecutedParam):
                if isinstance(param, pr.Param):
                    # There is no calling var_args in this case - there's just
                    # a param without any input.
                    return None
                break
            # We never want var_args to be a tuple. This should be enough for
            # now, we can change it later, if we need to.
            if isinstance(param.var_args, pr.Array):
                var_args = param.var_args
    return var_args


def get_params(evaluator, func, var_args):
    result = []
    param_dict = {}
    for param in func.params:
        param_dict[str(param.get_name())] = param
    # There may be calls, which don't fit all the params, this just ignores it.
    unpacked_va = _unpack_var_args(evaluator, var_args, func)
    var_arg_iterator = common.PushBackIterator(iter(unpacked_va))

    non_matching_keys = []
    keys_used = set()
    keys_only = False
    va_values = None
    had_multiple_value_error = False
    for param in func.params:
        # The value and key can both be null. There, the defaults apply.
        # args / kwargs will just be empty arrays / dicts, respectively.
        # Wrong value count is just ignored. If you try to test cases that are
        # not allowed in Python, Jedi will maybe not show any completions.
        key, va_values = next(var_arg_iterator, (None, []))
        while key:
            keys_only = True
            k = unicode(key)
            try:
                key_param = param_dict[unicode(key)]
            except KeyError:
                non_matching_keys.append((key, va_values))
            else:
                result.append(_gen_param_name_copy(func, var_args, key_param,
                                                   values=va_values))

            if k in keys_used:
                had_multiple_value_error = True
                m = ("TypeError: %s() got multiple values for keyword argument '%s'."
                     % (func.name, k))
                calling_va = _get_calling_var_args(evaluator, var_args)
                if calling_va is not None:
                    analysis.add(evaluator, 'type-error-multiple-values',
                                 calling_va, message=m)
            else:
                keys_used.add(k)
            key, va_values = next(var_arg_iterator, (None, []))

        keys = []
        values = []
        array_type = None
        has_default_value = False
        if param.stars == 1:
            # *args param
            array_type = pr.Array.TUPLE
            lst_values = [va_values]
            for key, va_values in var_arg_iterator:
                # Iterate until a key argument is found.
                if key:
                    var_arg_iterator.push_back((key, va_values))
                    break
                lst_values.append(va_values)
            if lst_values[0]:
                values = [helpers.stmts_to_stmt(v) for v in lst_values]
        elif param.stars == 2:
            # **kwargs param
            array_type = pr.Array.DICT
            if non_matching_keys:
                keys, values = zip(*non_matching_keys)
                values = [helpers.stmts_to_stmt(list(v)) for v in values]
            non_matching_keys = []
        else:
            # normal param
            if va_values:
                values = va_values
            else:
                if param.assignment_details:
                    # No value: Return the default values.
                    has_default_value = True
                    result.append(param.get_name())
                    # TODO is this allowed? it changes it long time.
                    param.is_generated = True
                else:
                    # No value: Return an empty container
                    values = []
                    if not keys_only and isinstance(var_args, pr.Array):
                        calling_va = _get_calling_var_args(evaluator, var_args)
                        if calling_va is not None:
                            m = _error_argument_count(func, len(unpacked_va))
                            analysis.add(evaluator, 'type-error-too-few-arguments',
                                         calling_va, message=m)

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
            param = param_dict[k]
            result.append(_gen_param_name_copy(func, var_args, param))

            if not (non_matching_keys or had_multiple_value_error
                    or param.stars or param.assignment_details):
                # add a warning only if there's not another one.
                calling_va = _get_calling_var_args(evaluator, var_args)
                if calling_va is not None:
                    m = _error_argument_count(func, len(unpacked_va))
                    analysis.add(evaluator, 'type-error-too-few-arguments',
                                 calling_va, message=m)

    for key, va_values in non_matching_keys:
        m = "TypeError: %s() got an unexpected keyword argument '%s'." \
            % (func.name, key)
        for value in va_values:
            analysis.add(evaluator, 'type-error-keyword-argument', value, message=m)

    remaining_params = list(var_arg_iterator)
    if remaining_params:
        m = _error_argument_count(func, len(unpacked_va))
        for p in remaining_params[0][1]:
            analysis.add(evaluator, 'type-error-too-many-arguments',
                         p, message=m)
    return result


def _unpack_var_args(evaluator, var_args, func):
    """
    Yields a key/value pair, the key is None, if its not a named arg.
    """
    argument_list = []
    from jedi.evaluate.representation import InstanceElement
    if isinstance(func, InstanceElement):
        # Include self at this place.
        argument_list.append((None, [helpers.FakeStatement([func.instance])]))

    # `var_args` is typically an Array, and not a list.
    for stmt in _reorder_var_args(var_args):
        if not isinstance(stmt, pr.Statement):
            if stmt is None:
                argument_list.append((None, []))
                # TODO generate warning?
                continue
            old = stmt
            # generate a statement if it's not already one.
            stmt = helpers.FakeStatement([old])

        expression_list = stmt.expression_list()
        if not len(expression_list):
            continue
        # *args
        if expression_list[0] == '*':
            arrays = evaluator.eval_expression_list(expression_list[1:])
            iterators = [_iterate_star_args(evaluator, a, expression_list[1:], func)
                         for a in arrays]
            for values in list(zip_longest(*iterators)):
                argument_list.append((None, [v for v in values if v is not None]))
        # **kwargs
        elif expression_list[0] == '**':
            dct = {}
            for array in evaluator.eval_expression_list(expression_list[1:]):
                # Merge multiple kwargs dictionaries, if used with dynamic
                # parameters.
                s = _star_star_dict(evaluator, array, expression_list[1:], func)
                for name, (key, value) in s.items():
                    try:
                        dct[name][1].add(value)
                    except KeyError:
                        dct[name] = key, set([value])

            for key, values in dct.values():
                # merge **kwargs/*args also for dynamic parameters
                for i, p in enumerate(func.params):
                    if str(p.get_name()) == str(key) and not p.stars:
                        try:
                            k, vs = argument_list[i]
                        except IndexError:
                            pass
                        else:
                            if k is None:  # k would imply a named argument
                                # Don't merge if they orginate at the same
                                # place. -> type-error-multiple-values
                                if [v.parent for v in values] != [v.parent for v in vs]:
                                    vs.extend(values)
                                    break
                else:
                    # default is to merge
                    argument_list.append((key, values))
        # Normal arguments (including key arguments).
        else:
            if stmt.assignment_details:
                key_arr, op = stmt.assignment_details[0]
                # Filter error tokens
                key_arr = [x for x in key_arr if isinstance(x, pr.Call)]
                # named parameter
                if key_arr and isinstance(key_arr[0], pr.Call):
                    argument_list.append((key_arr[0].name, [stmt]))
            else:
                argument_list.append((None, [stmt]))
    return argument_list


def _reorder_var_args(var_args):
    """
    Reordering var_args is necessary, because star args sometimes appear after
    named argument, but in the actual order it's prepended.
    """
    named_index = None
    new_args = []
    for i, stmt in enumerate(var_args):
        if isinstance(stmt, pr.Statement):
            if named_index is None and stmt.assignment_details:
                named_index = i

            if named_index is not None:
                expression_list = stmt.expression_list()
                if expression_list and expression_list[0] == '*':
                    new_args.insert(named_index, stmt)
                    named_index += 1
                    continue

        new_args.append(stmt)
    return new_args


def _iterate_star_args(evaluator, array, expression_list, func):
    from jedi.evaluate.representation import Instance
    if isinstance(array, iterable.Array):
        for field_stmt in array:  # yield from plz!
            yield field_stmt
    elif isinstance(array, iterable.Generator):
        for field_stmt in array.iter_content():
            yield helpers.FakeStatement([field_stmt])
    elif isinstance(array, Instance) and array.name == 'tuple':
        pass
    else:
        if expression_list:
            m = "TypeError: %s() argument after * must be a sequence, not %s" \
                % (func.name, array)
            analysis.add(evaluator, 'type-error-star',
                         expression_list[0], message=m)


def _star_star_dict(evaluator, array, expression_list, func):
    dct = {}
    from jedi.evaluate.representation import Instance
    if isinstance(array, Instance) and array.name == 'dict':
        # For now ignore this case. In the future add proper iterators and just
        # make one call without crazy isinstance checks.
        return {}

    if isinstance(array, iterable.Array) and array.type == pr.Array.DICT:
        for key_stmt, value_stmt in array.items():
            # first index, is the key if syntactically correct
            call = key_stmt.expression_list()[0]
            if isinstance(call, pr.Name):
                key = call
            elif isinstance(call, pr.Call):
                key = call.name
            else:
                continue  # We ignore complicated statements here, for now.

            # If the string is a duplicate, we don't care it's illegal Python
            # anyway.
            dct[str(key)] = key, value_stmt
    else:
        if expression_list:
            m = "TypeError: %s argument after ** must be a mapping, not %s" \
                % (func.name, array)
            analysis.add(evaluator, 'type-error-star-star',
                         expression_list[0], message=m)
    return dct


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

    new_param = ExecutedParam.from_param(param, parent, var_args)

    # create an Array (-> needed for *args/**kwargs tuples/dicts)
    arr = pr.Array(helpers.FakeSubModule, start_pos, array_type, parent)
    arr.values = list(values)  # Arrays only work with list.
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
    default_arguments = sum(1 for p in func.params if p.assignment_details or p.stars)

    if default_arguments == 0:
        before = 'exactly '
    else:
        before = 'from %s to ' % (len(func.params) - default_arguments)
    return ('TypeError: %s() takes %s%s arguments (%s given).'
            % (func.name, before, len(func.params), actual_count))
