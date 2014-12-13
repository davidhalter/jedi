import copy
from collections import defaultdict
from itertools import chain

from jedi._compatibility import unicode, zip_longest
from jedi import debug
from jedi import common
from jedi.parser import tree as pr
from jedi.evaluate import iterable
from jedi.evaluate import helpers
from jedi.evaluate import analysis
from jedi.evaluate import precedence


class Arguments(pr.Base):
    def __init__(self, evaluator, argument_node, trailer=None):
        """
        The argument_node is either a parser node or a list of evaluated
        objects. Those evaluated objects may be lists of evaluated objects
        themselves (one list for the first argument, one for the second, etc).

        :param argument_node: May be an argument_node or a list of nodes.
        """
        self.argument_node = argument_node
        self._evaluator = evaluator
        self.trailer = trailer  # Can be None, e.g. in a class definition.

    def _split(self):
        if isinstance(self.argument_node, (tuple, list)):
            for el in self.argument_node:
                yield 0, el
        else:
            if not pr.is_node(self.argument_node, 'arglist'):
                yield 0, self.argument_node
                return

            iterator = iter(self.argument_node.children)
            for child in iterator:
                if child == ',':
                    continue
                elif child in ('*', '**'):
                    yield len(child.value), next(iterator)
                else:
                    yield 0, child

    def get_parent_until(self, *args, **kwargs):
        return self.trailer.get_parent_until(*args, **kwargs)

    def as_tuple(self):
        for stars, argument in self._split():
            if pr.is_node(argument, 'argument'):
                argument, default = argument.children[::2]
            else:
                default = None
            yield argument, default, stars

    def unpack(self, func=None):
        named_args = []
        for stars, el in self._split():
            if stars == 1:
                arrays = self._evaluator.eval_element(el)
                iterators = [_iterate_star_args(self._evaluator, a, None, None)
                             for a in arrays]
                iterators = list(iterators)
                for values in list(zip_longest(*iterators)):
                    yield None, [v for v in values if v is not None]
            elif stars == 2:
                arrays = self._evaluator.eval_element(el)
                dicts = [_star_star_dict(self._evaluator, a, func, el)
                         for a in arrays]
                for dct in dicts:
                    for key, values in dct.items():
                        yield key, values
            else:
                if pr.is_node(el, 'argument'):
                    named_args.append((el.children[0].value, (el.children[2],)))
                elif isinstance(el, (list, tuple)):
                    yield None, el
                else:
                    yield None, (el,)

        # Reordering var_args is necessary, because star args sometimes appear
        # after named argument, but in the actual order it's prepended.
        for key_arg in named_args:
            # TODO its always only one value?
            yield key_arg

    def _reorder_var_args(var_args):
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

    def eval_argument_clinic(self, arguments):
        """Uses a list with argument clinic information (see PEP 436)."""
        iterator = self.unpack()
        for i, (name, optional, allow_kwargs) in enumerate(arguments):
            key, va_values = next(iterator, (None, []))
            if key is not None:
                raise NotImplementedError
            if not va_values and not optional:
                debug.warning('TypeError: %s expected at least %s arguments, got %s',
                              name, len(arguments), i)
                raise ValueError
            values = list(chain.from_iterable(self._evaluator.eval_element(el)
                                              for el in va_values))
            if not values and not optional:
                # For the stdlib we always want values. If we don't get them,
                # that's ok, maybe something is too hard to resolve, however,
                # we will not proceed with the evaluation of that function.
                debug.warning('argument_clinic "%s" not resolvable.', name)
                raise ValueError
            yield values

    def scope(self):
        # Returns the scope in which the arguments are used.
        return (self.trailer or self.argument_node).get_parent_until(pr.IsScope)

    def eval_args(self):
        # TODO this method doesn't work with named args and a lot of other
        # things. Use unpack.
        return [self._evaluator.eval_element(el) for stars, el in self._split()]

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.argument_node)

    def get_calling_var_args(self):
        if pr.is_node(self.argument_node, 'arglist', 'argument') \
                or self.argument_node == () and self.trailer is not None:
            return _get_calling_var_args(self._evaluator, self)
        else:
            return None


class ExecutedParam(pr.Param):
    def __init__(self, values):
        """Don't use this method, it's just here to overwrite the old one."""
        self.values = values

    @classmethod
    def from_param(cls, values, param, parent, var_args):
        instance = cls(values)
        before = ()
        for cls in param.__class__.__mro__:
            with common.ignored(AttributeError):
                if before == cls.__slots__:
                    continue
                before = cls.__slots__
                for name in before:
                    setattr(instance, name, getattr(param, name))

        instance.original_param = param
        instance.parent = parent
        instance.var_args = var_args
        return instance

    def eval(self, evaluator):
        types = []
        for v in self.values:
            types += evaluator.eval_element(v)
        return types

    @property
    def position_nr(self):
        return self.original_param.position_nr


def _get_calling_var_args(evaluator, var_args):
    old_var_args = None
    while var_args != old_var_args:
        old_var_args = var_args
        for name, default, stars in reversed(list(var_args.as_tuple())):
            if not stars or not isinstance(name, pr.Name):
                continue

            names = evaluator.goto(name)
            if len(names) != 1:
                break
            param = names[0].get_definition()
            if not isinstance(param, ExecutedParam):
                if isinstance(param, pr.Param):
                    # There is no calling var_args in this case - there's just
                    # a param without any input.
                    return None
                break
            # We never want var_args to be a tuple. This should be enough for
            # now, we can change it later, if we need to.
            if isinstance(param.var_args, Arguments):
                var_args = param.var_args
    return var_args.argument_node or var_args.trailer


def get_params(evaluator, func, var_args):
    result = []
    param_dict = {}
    for param in func.params:
        param_dict[str(param.get_name())] = param
    # There may be calls, which don't fit all the params, this just ignores it.
    #unpacked_va = _unpack_var_args(evaluator, var_args, func)
    unpacked_va = list(var_args.unpack(func))
    from jedi.evaluate.representation import InstanceElement
    if isinstance(func, InstanceElement):
        # Include self at this place.
        unpacked_va.insert(0, (None, [iterable.AlreadyEvaluated([func.instance])]))
    var_arg_iterator = common.PushBackIterator(iter(unpacked_va))

    non_matching_keys = defaultdict(lambda: [])
    keys_used = set()
    keys_only = False
    had_multiple_value_error = False
    for param in func.params:
        # The value and key can both be null. There, the defaults apply.
        # args / kwargs will just be empty arrays / dicts, respectively.
        # Wrong value count is just ignored. If you try to test cases that are
        # not allowed in Python, Jedi will maybe not show any completions.
        default = [] if param.default is None else [param.default]
        key, va_values = next(var_arg_iterator, (None, default))
        while key is not None:
            keys_only = True
            k = unicode(key)
            try:
                key_param = param_dict[unicode(key)]
            except KeyError:
                non_matching_keys[key] += va_values
            else:
                result.append(_gen_param_name_copy(evaluator, func, var_args,
                                                   key_param, values=va_values))

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
            key, va_values = next(var_arg_iterator, (None, ()))

        keys = []
        values = []
        array_type = None
        if param.stars == 1:
            # *args param
            array_type = pr.Array.TUPLE
            lst_values = [iterable.MergedNodes(va_values)] if va_values else []
            for key, va_values in var_arg_iterator:
                # Iterate until a key argument is found.
                if key:
                    var_arg_iterator.push_back((key, va_values))
                    break
                if va_values:
                    lst_values.append(iterable.MergedNodes(va_values))
            seq = iterable.FakeSequence(evaluator, lst_values, pr.Array.TUPLE)
            values = [iterable.AlreadyEvaluated([seq])]
        elif param.stars == 2:
            # **kwargs param
            array_type = pr.Array.DICT
            dct = iterable.FakeDict(evaluator, dict(non_matching_keys))
            values = [iterable.AlreadyEvaluated([dct])]
            non_matching_keys = {}
        else:
            # normal param
            if va_values:
                values = va_values
            else:
                # No value: Return an empty container
                values = []
                if not keys_only:
                    calling_va = var_args.get_calling_var_args()
                    if calling_va is not None:
                        m = _error_argument_count(func, len(unpacked_va))
                        analysis.add(evaluator, 'type-error-too-few-arguments',
                                     calling_va, message=m)

        # Now add to result if it's not one of the previously covered cases.
        if (not keys_only or param.stars == 2):
            keys_used.add(unicode(param.get_name()))
            result.append(_gen_param_name_copy(evaluator, func, var_args, param,
                                               keys=keys, values=values,
                                               array_type=array_type))

    if keys_only:
        # All arguments should be handed over to the next function. It's not
        # about the values inside, it's about the names. Jedi needs to now that
        # there's nothing to find for certain names.
        for k in set(param_dict) - keys_used:
            param = param_dict[k]
            values = [] if param.default is None else [param.default]
            result.append(_gen_param_name_copy(evaluator, func, var_args,
                                               param, [], values))

            if not (non_matching_keys or had_multiple_value_error
                    or param.stars or param.default):
                # add a warning only if there's not another one.
                calling_va = _get_calling_var_args(evaluator, var_args)
                if calling_va is not None:
                    m = _error_argument_count(func, len(unpacked_va))
                    analysis.add(evaluator, 'type-error-too-few-arguments',
                                 calling_va, message=m)

    for key, va_values in non_matching_keys.items():
        m = "TypeError: %s() got an unexpected keyword argument '%s'." \
            % (func.name, key)
        for value in va_values:
            analysis.add(evaluator, 'type-error-keyword-argument', value.parent, message=m)

    remaining_params = list(var_arg_iterator)
    if remaining_params:
        m = _error_argument_count(func, len(unpacked_va))
        # Just report an error for the first param that is not needed (like
        # cPython).
        first_key, first_values = remaining_params[0]
        for v in first_values:
            if first_key is not None:
                # Is a keyword argument, return the whole thing instead of just
                # the value node.
                v = v.parent
            analysis.add(evaluator, 'type-error-too-many-arguments',
                         v, message=m)
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
    for stmt in _reorder_var_args(var_args.iterate()):
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
            iterators = [_iterate_star_args(evaluator, a, func)
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


def _iterate_star_args(evaluator, array, expression_list, func):
    from jedi.evaluate.representation import Instance
    if isinstance(array, iterable.Array):
        for field_stmt in array:  # yield from plz!
            yield field_stmt
    elif isinstance(array, iterable.Generator):
        for field_stmt in array.iter_content():
            yield iterable.AlreadyEvaluated([field_stmt])
    elif isinstance(array, Instance) and array.name.get_code() == 'tuple':
        debug.warning('Ignored a tuple *args input %s' % array)
    else:
        if expression_list:
            m = "TypeError: %s() argument after * must be a sequence, not %s" \
                % (func.name.get_code(), array)
            analysis.add(evaluator, 'type-error-star',
                         expression_list[0], message=m)


def _star_star_dict(evaluator, array, func, input_node):
    dct = defaultdict(lambda: [])
    from jedi.evaluate.representation import Instance
    if isinstance(array, Instance) and array.name.get_code() == 'dict':
        # For now ignore this case. In the future add proper iterators and just
        # make one call without crazy isinstance checks.
        return {}

    if isinstance(array, iterable.FakeDict):
        return array._dct
    elif isinstance(array, iterable.Array) and array.type == pr.Array.DICT:
        # TODO bad call to non-public API
        for key_node, values in array._items():
            for key in evaluator.eval_element(key_node):
                if precedence.is_string(key):
                    dct[key.obj] += values

    else:
        if func is not None:
            m = "TypeError: %s argument after ** must be a mapping, not %s" \
                % (func.name.value, array)
            analysis.add(evaluator, 'type-error-star-star', input_node, message=m)
    return dict(dct)


def _gen_param_name_copy(evaluator, func, var_args, param, keys=(), values=(), array_type=None):
    """
    Create a param with the original scope (of varargs) as parent.
    """
    if isinstance(var_args, pr.Array):
        parent = var_args.parent
        start_pos = var_args.start_pos
    else:
        parent = func
        start_pos = 0, 0

    """
    # create an Array (-> needed for *args/**kwargs tuples/dicts)
    arr = iterable.FakeSequence(evaluator, values, array_type)
    # TODO change?!
    arr = pr.Array(helpers.FakeSubModule, start_pos, array_type, parent)
    key_stmts = []
    for key in keys:
        key_stmts.append(helpers.FakeStatement([key], start_pos))
    arr.keys = key_stmts
    arr.type = array_type
    """

    new_param = ExecutedParam.from_param(values, param, parent, var_args)


    name = copy.copy(param.get_name())
    name.parent = new_param
    return name


def _error_argument_count(func, actual_count):
    default_arguments = sum(1 for p in func.params if p.default or p.stars)

    if default_arguments == 0:
        before = 'exactly '
    else:
        before = 'from %s to ' % (len(func.params) - default_arguments)
    return ('TypeError: %s() takes %s%s arguments (%s given).'
            % (func.name, before, len(func.params), actual_count))
