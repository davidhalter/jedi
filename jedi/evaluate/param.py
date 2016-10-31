from collections import defaultdict
from itertools import chain

from jedi._compatibility import unicode, zip_longest
from jedi import debug
from jedi import common
from jedi.parser import tree
from jedi.evaluate import iterable
from jedi.evaluate import analysis
from jedi.evaluate import precedence
from jedi.evaluate import context


def try_iter_content(types, depth=0):
    """Helper method for static analysis."""
    if depth > 10:
        # It's possible that a loop has references on itself (especially with
        # CompiledObject). Therefore don't loop infinitely.
        return

    for typ in types:
        try:
            f = typ.py__iter__
        except AttributeError:
            pass
        else:
            for iter_types in f():
                try_iter_content(iter_types, depth + 1)


class AbstractArguments(tree.Base):
    def get_parent_until(self, *args, **kwargs):
        raise DeprecationWarning
        if self.trailer is None:
            try:
                element = self.argument_node[0]
                if isinstance(element, iterable.AlreadyEvaluated):
                    element = list(self._evaluator.eval_element(self._context, element))[0]
            except IndexError:
                return None
            else:
                return element.get_parent_until(*args, **kwargs)
        else:
            return self.trailer.get_parent_until(*args, **kwargs)

    def eval_argument_clinic(self, arguments):
        """Uses a list with argument clinic information (see PEP 436)."""
        raise DeprecationWarning('not sure if we really deprecate it')
        iterator = self.unpack()
        for i, (name, optional, allow_kwargs) in enumerate(arguments):
            key, va_values = next(iterator, (None, []))
            if key is not None:
                raise NotImplementedError
            if not va_values and not optional:
                debug.warning('TypeError: %s expected at least %s arguments, got %s',
                              name, len(arguments), i)
                raise ValueError
            values = set(chain.from_iterable(self._evaluator.eval_element(self._context, el)
                                             for el in va_values))
            if not values and not optional:
                # For the stdlib we always want values. If we don't get them,
                # that's ok, maybe something is too hard to resolve, however,
                # we will not proceed with the evaluation of that function.
                debug.warning('argument_clinic "%s" not resolvable.', name)
                raise ValueError
            yield values

    def scope(self):
        raise DeprecationWarning
        # Returns the scope in which the arguments are used.
        return (self.trailer or self.argument_node).get_parent_until(tree.IsScope)

    def eval_args(self):
        # TODO this method doesn't work with named args and a lot of other
        # things. Use unpack.
        raise DeprecationWarning
        return [self._evaluator.eval_element(self._context, el) for stars, el in self._split()]

    def eval_all(self, func=None):
        """
        Evaluates all arguments as a support for static analysis
        (normally Jedi).
        """
        for key, element_values in self.unpack():
            for element in element_values:
                types = self._evaluator.eval_element(self._context, element)
                try_iter_content(types)


class TreeArguments(AbstractArguments):
    def __init__(self, evaluator, context, argument_node, trailer=None):
        """
        The argument_node is either a parser node or a list of evaluated
        objects. Those evaluated objects may be lists of evaluated objects
        themselves (one list for the first argument, one for the second, etc).

        :param argument_node: May be an argument_node or a list of nodes.
        """
        self.argument_node = argument_node
        self._context = context
        self._evaluator = evaluator
        self.trailer = trailer  # Can be None, e.g. in a class definition.

    def _split(self):
        if isinstance(self.argument_node, (tuple, list)):
            for el in self.argument_node:
                yield 0, el
        else:
            if not (tree.is_node(self.argument_node, 'arglist') or (
                    # in python 3.5 **arg is an argument, not arglist
                    (tree.is_node(self.argument_node, 'argument') and
                     self.argument_node.children[0] in ('*', '**')))):
                yield 0, self.argument_node
                return

            iterator = iter(self.argument_node.children)
            for child in iterator:
                if child == ',':
                    continue
                elif child in ('*', '**'):
                    yield len(child.value), next(iterator)
                elif tree.is_node(child, 'argument') and \
                        child.children[0] in ('*', '**'):
                    assert len(child.children) == 2
                    yield len(child.children[0].value), child.children[1]
                else:
                    yield 0, child

    def unpack(self, func=None):
        named_args = []
        for stars, el in self._split():
            if stars == 1:
                arrays = self._context.eval_node(el)
                iterators = [_iterate_star_args(self._evaluator, a, el, func)
                             for a in arrays]
                iterators = list(iterators)
                for values in list(zip_longest(*iterators)):
                    # TODO zip_longest yields None, that means this would raise
                    # an exception?
                    yield None, context.get_merged_lazy_context(values)
            elif stars == 2:
                arrays = self._evaluator.eval_element(self._context, el)
                for dct in arrays:
                    for key, values in _star_star_dict(self._evaluator, dct, el, func):
                        yield key, values
            else:
                if tree.is_node(el, 'argument'):
                    c = el.children
                    if len(c) == 3:  # Keyword argument.
                        named_args.append((c[0].value, context.LazyTreeContext(self._context, c[2]),))
                    else:  # Generator comprehension.
                        # Include the brackets with the parent.
                        comp = iterable.GeneratorComprehension(
                            self._evaluator, self.argument_node.parent)
                        yield None, context.LazyKnownContext(comp)
                else:
                    yield None, context.LazyTreeContext(self._context, el)

        # Reordering var_args is necessary, because star args sometimes appear
        # after named argument, but in the actual order it's prepended.
        for named_arg in named_args:
            yield named_arg

    def as_tuple(self):
        raise DeprecationWarning
        for stars, argument in self._split():
            if tree.is_node(argument, 'argument'):
                argument, default = argument.children[::2]
            else:
                default = None
            yield argument, default, stars

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.argument_node)

    def get_calling_var_args(self):
        return _get_calling_var_args(self._evaluator, self)


class ValuesArguments(AbstractArguments):
    def __init__(self, values_list):
        self._values_list = values_list

    def unpack(self, func=None):
        for values in self._values_list:
            yield None, context.LazyKnownContexts(values)

    def get_calling_var_args(self):
        return None

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self._values_list)


class ExecutedParam(object):
    """Fake a param and give it values."""
    def __init__(self, original_param, var_args, lazy_context):
        assert not isinstance(lazy_context, (tuple, list))
        self._original_param = original_param
        self.var_args = var_args
        self._lazy_context = lazy_context
        self.string_name = self._original_param.name.value

    def infer(self):
        return self._lazy_context.infer()

    @property
    def position_nr(self):
        # Need to use the original logic here, because it uses the parent.
        return self._original_param.position_nr


def _get_calling_var_args(evaluator, var_args):
    old_var_args = None
    while var_args != old_var_args:
        old_var_args = var_args
        continue#TODO REMOVE
        for name, default, stars in reversed(list(var_args.as_tuple())):
            if not stars or not isinstance(name, tree.Name):
                continue

            names = evaluator.goto(name)
            if len(names) != 1:
                break
            param = names[0].get_definition()
            if not isinstance(param, ExecutedParam):
                if isinstance(param, tree.Param):
                    # There is no calling var_args in this case - there's just
                    # a param without any input.
                    return None
                break
            # We never want var_args to be a tuple. This should be enough for
            # now, we can change it later, if we need to.
            if isinstance(param.var_args, Arguments):
                var_args = param.var_args
    return var_args.argument_node or var_args.trailer


def get_params(evaluator, parent_context, func, var_args):
    result_params = []
    param_dict = {}
    for param in func.params:
        param_dict[str(param.name)] = param
    unpacked_va = list(var_args.unpack(func))
    from jedi.evaluate.instance import TreeInstance
    if isinstance(parent_context, TreeInstance):
        # Include the self parameter here.
        unpacked_va.insert(0, (None, context.LazyKnownContext(parent_context)))
    var_arg_iterator = common.PushBackIterator(iter(unpacked_va))

    non_matching_keys = defaultdict(lambda: [])
    keys_used = {}
    keys_only = False
    had_multiple_value_error = False
    for param in func.params:
        # The value and key can both be null. There, the defaults apply.
        # args / kwargs will just be empty arrays / dicts, respectively.
        # Wrong value count is just ignored. If you try to test cases that are
        # not allowed in Python, Jedi will maybe not show any completions.
        default = None
        if param.default is not None:
            default = context.LazyTreeContext(parent_context, param.default)

        key, argument = next(var_arg_iterator, (None, default))
        while key is not None:
            keys_only = True
            k = unicode(key)
            try:
                key_param = param_dict[unicode(key)]
            except KeyError:
                non_matching_keys[key] = argument
            else:
                result_params.append(ExecutedParam(key_param, var_args, argument))

            if k in keys_used:
                had_multiple_value_error = True
                m = ("TypeError: %s() got multiple values for keyword argument '%s'."
                     % (func.name, k))
                calling_va = _get_calling_var_args(evaluator, var_args)
                if calling_va is not None:
                    analysis.add(evaluator, 'type-error-multiple-values',
                                 calling_va, message=m)
            else:
                try:
                    keys_used[k] = result_params[-1]
                except IndexError:
                    # TODO this is wrong stupid and whatever.
                    pass
            key, argument = next(var_arg_iterator, (None, None))

        if param.stars == 1:
            # *args param
            lazy_context_list = []
            if argument is not None:
                lazy_context_list.append(argument)
                for key, argument in var_arg_iterator:
                    # Iterate until a key argument is found.
                    if key:
                        var_arg_iterator.push_back((key, argument))
                        break
                    lazy_context_list.append(argument)
            seq = iterable.FakeSequence(evaluator, 'tuple', lazy_context_list)
            result_arg = context.LazyKnownContext(seq)
        elif param.stars == 2:
            # **kwargs param
            dct = iterable.FakeDict(evaluator, dict(non_matching_keys))
            result_arg = context.LazyKnownContext(dct)
            non_matching_keys = {}
        else:
            # normal param
            if argument is None:
                # No value: Return an empty container
                result_arg = context.LazyUnknownContext()
                if not keys_only:
                    calling_va = var_args.get_calling_var_args()
                    if calling_va is not None:
                        m = _error_argument_count(func, len(unpacked_va))
                        analysis.add(evaluator, 'type-error-too-few-arguments',
                                     calling_va, message=m)
            else:
                result_arg = argument

        # Now add to result if it's not one of the previously covered cases.
        if (not keys_only or param.stars == 2):
            result_params.append(ExecutedParam(param, var_args, result_arg))
            keys_used[unicode(param.name)] = result_params[-1]

    if keys_only:
        # All arguments should be handed over to the next function. It's not
        # about the values inside, it's about the names. Jedi needs to now that
        # there's nothing to find for certain names.
        for k in set(param_dict) - set(keys_used):
            param = param_dict[k]
            result_arg = (context.LazyUnknownContext() if param.default is None else
                          context.LazyTreeContext(parent_context, param.default))
            result_params.append(ExecutedParam(param, var_args, result_arg))

            if not (non_matching_keys or had_multiple_value_error or
                    param.stars or param.default):
                # add a warning only if there's not another one.
                calling_va = _get_calling_var_args(evaluator, var_args)
                if calling_va is not None:
                    m = _error_argument_count(func, len(unpacked_va))
                    analysis.add(evaluator, 'type-error-too-few-arguments',
                                 calling_va, message=m)

    for key, argument in non_matching_keys.items():
        m = "TypeError: %s() got an unexpected keyword argument '%s'." \
            % (func.name, key)
        analysis.add(evaluator, 'type-error-keyword-argument', argument.whatever, message=m)

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
                try:
                    non_kw_param = keys_used[first_key]
                except KeyError:
                    pass
                else:
                    origin_args = non_kw_param.parent.var_args.argument_node
                    # TODO  calculate the var_args tree and check if it's in
                    # the tree (if not continue).
                    # print('\t\tnonkw', non_kw_param.parent.var_args.argument_node, )
                    if origin_args not in [f.parent.parent for f in first_values]:
                        continue
            analysis.add(evaluator, 'type-error-too-many-arguments',
                         v, message=m)
    return result_params


def _iterate_star_args(evaluator, array, input_node, func=None):
    try:
        iter_ = array.py__iter__
    except AttributeError:
        if func is not None:
            # TODO this func should not be needed.
            m = "TypeError: %s() argument after * must be a sequence, not %s" \
                % (func.name.value, array)
            analysis.add(evaluator, 'type-error-star', input_node, message=m)
    else:
        for lazy_context in iter_():
            yield lazy_context


def _star_star_dict(evaluator, array, input_node, func):
    from jedi.evaluate.representation import Instance
    if isinstance(array, Instance) and array.name.get_code() == 'dict':
        # For now ignore this case. In the future add proper iterators and just
        # make one call without crazy isinstance checks.
        return {}
    elif isinstance(array, iterable.AbstractSequence) and array.array_type == 'dict':
        return array.exact_key_items()
    else:
        if func is not None:
            m = "TypeError: %s argument after ** must be a mapping, not %s" \
                % (func.name.value, array)
            analysis.add(evaluator, 'type-error-star-star', input_node, message=m)
        return {}


def _error_argument_count(func, actual_count):
    default_arguments = sum(1 for p in func.params if p.default or p.stars)

    if default_arguments == 0:
        before = 'exactly '
    else:
        before = 'from %s to ' % (len(func.params) - default_arguments)
    return ('TypeError: %s() takes %s%s arguments (%s given).'
            % (func.name, before, len(func.params), actual_count))
