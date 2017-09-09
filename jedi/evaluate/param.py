from collections import defaultdict

from jedi._compatibility import zip_longest
from jedi import debug
from jedi import common
from parso.python import tree
from jedi.evaluate import iterable
from jedi.evaluate import analysis
from jedi.evaluate import context
from jedi.evaluate import docstrings
from jedi.evaluate import pep0484
from jedi.evaluate.filters import ParamName


def add_argument_issue(parent_context, error_name, lazy_context, message):
    if isinstance(lazy_context, context.LazyTreeContext):
        node = lazy_context.data
        if node.parent.type == 'argument':
            node = node.parent
        analysis.add(parent_context, error_name, node, message)


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
            for lazy_context in f():
                try_iter_content(lazy_context.infer(), depth + 1)


class AbstractArguments():
    context = None

    def eval_argument_clinic(self, parameters):
        """Uses a list with argument clinic information (see PEP 436)."""
        iterator = self.unpack()
        for i, (name, optional, allow_kwargs) in enumerate(parameters):
            key, argument = next(iterator, (None, None))
            if key is not None:
                raise NotImplementedError
            if argument is None and not optional:
                debug.warning('TypeError: %s expected at least %s arguments, got %s',
                              name, len(parameters), i)
                raise ValueError
            values = set() if argument is None else argument.infer()

            if not values and not optional:
                # For the stdlib we always want values. If we don't get them,
                # that's ok, maybe something is too hard to resolve, however,
                # we will not proceed with the evaluation of that function.
                debug.warning('argument_clinic "%s" not resolvable.', name)
                raise ValueError
            yield values

    def eval_all(self, funcdef=None):
        """
        Evaluates all arguments as a support for static analysis
        (normally Jedi).
        """
        for key, lazy_context in self.unpack():
            types = lazy_context.infer()
            try_iter_content(types)

    def get_calling_nodes(self):
        raise NotImplementedError

    def unpack(self, funcdef=None):
        raise NotImplementedError

    def get_params(self, execution_context):
        return get_params(execution_context, self)


class AnonymousArguments(AbstractArguments):
    def get_params(self, execution_context):
        from jedi.evaluate.dynamic import search_params
        return search_params(
            execution_context.evaluator,
            execution_context,
            execution_context.tree_node
        )


class TreeArguments(AbstractArguments):
    def __init__(self, evaluator, context, argument_node, trailer=None):
        """
        The argument_node is either a parser node or a list of evaluated
        objects. Those evaluated objects may be lists of evaluated objects
        themselves (one list for the first argument, one for the second, etc).

        :param argument_node: May be an argument_node or a list of nodes.
        """
        self.argument_node = argument_node
        self.context = context
        self._evaluator = evaluator
        self.trailer = trailer  # Can be None, e.g. in a class definition.

    def _split(self):
        if isinstance(self.argument_node, (tuple, list)):
            for el in self.argument_node:
                yield 0, el
        else:
            if not (self.argument_node.type == 'arglist' or (
                    # in python 3.5 **arg is an argument, not arglist
                    (self.argument_node.type == 'argument') and
                     self.argument_node.children[0] in ('*', '**'))):
                yield 0, self.argument_node
                return

            iterator = iter(self.argument_node.children)
            for child in iterator:
                if child == ',':
                    continue
                elif child in ('*', '**'):
                    yield len(child.value), next(iterator)
                elif child.type == 'argument' and \
                        child.children[0] in ('*', '**'):
                    assert len(child.children) == 2
                    yield len(child.children[0].value), child.children[1]
                else:
                    yield 0, child

    def unpack(self, funcdef=None):
        named_args = []
        for star_count, el in self._split():
            if star_count == 1:
                arrays = self.context.eval_node(el)
                iterators = [_iterate_star_args(self.context, a, el, funcdef)
                             for a in arrays]
                iterators = list(iterators)
                for values in list(zip_longest(*iterators)):
                    # TODO zip_longest yields None, that means this would raise
                    # an exception?
                    yield None, context.get_merged_lazy_context(
                        [v for v in values if v is not None]
                    )
            elif star_count == 2:
                arrays = self._evaluator.eval_element(self.context, el)
                for dct in arrays:
                    for key, values in _star_star_dict(self.context, dct, el, funcdef):
                        yield key, values
            else:
                if el.type == 'argument':
                    c = el.children
                    if len(c) == 3:  # Keyword argument.
                        named_args.append((c[0].value, context.LazyTreeContext(self.context, c[2]),))
                    else:  # Generator comprehension.
                        # Include the brackets with the parent.
                        comp = iterable.GeneratorComprehension(
                            self._evaluator, self.context, self.argument_node.parent)
                        yield None, context.LazyKnownContext(comp)
                else:
                    yield None, context.LazyTreeContext(self.context, el)

        # Reordering var_args is necessary, because star args sometimes appear
        # after named argument, but in the actual order it's prepended.
        for named_arg in named_args:
            yield named_arg

    def as_tree_tuple_objects(self):
        for star_count, argument in self._split():
            if argument.type == 'argument':
                argument, default = argument.children[::2]
            else:
                default = None
            yield argument, default, star_count

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.argument_node)

    def get_calling_nodes(self):
        from jedi.evaluate.dynamic import MergedExecutedParams
        old_arguments_list = []
        arguments = self

        while arguments not in old_arguments_list:
            if not isinstance(arguments, TreeArguments):
                break

            old_arguments_list.append(arguments)
            for name, default, star_count in reversed(list(arguments.as_tree_tuple_objects())):
                if not star_count or not isinstance(name, tree.Name):
                    continue

                names = self._evaluator.goto(arguments.context, name)
                if len(names) != 1:
                    break
                if not isinstance(names[0], ParamName):
                    break
                param = names[0].get_param()
                if isinstance(param, MergedExecutedParams):
                    # For dynamic searches we don't even want to see errors.
                    return []
                if not isinstance(param, ExecutedParam):
                    break
                if param.var_args is None:
                    break
                arguments = param.var_args
                break

        return [arguments.argument_node or arguments.trailer]


class ValuesArguments(AbstractArguments):
    def __init__(self, values_list):
        self._values_list = values_list

    def unpack(self, funcdef=None):
        for values in self._values_list:
            yield None, context.LazyKnownContexts(values)

    def get_calling_nodes(self):
        return []

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._values_list)


class ExecutedParam(object):
    """Fake a param and give it values."""
    def __init__(self, execution_context, param_node, lazy_context):
        self._execution_context = execution_context
        self._param_node = param_node
        self._lazy_context = lazy_context
        self.string_name = param_node.name.value

    def infer(self):
        pep0484_hints = pep0484.infer_param(self._execution_context, self._param_node)
        doc_params = docstrings.infer_param(self._execution_context, self._param_node)
        if pep0484_hints or doc_params:
            return list(set(pep0484_hints) | set(doc_params))

        return self._lazy_context.infer()

    @property
    def var_args(self):
        return self._execution_context.var_args

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.string_name)


def get_params(execution_context, var_args):
    result_params = []
    param_dict = {}
    funcdef = execution_context.tree_node
    parent_context = execution_context.parent_context

    for param in funcdef.get_params():
        param_dict[param.name.value] = param
    unpacked_va = list(var_args.unpack(funcdef))
    var_arg_iterator = common.PushBackIterator(iter(unpacked_va))

    non_matching_keys = defaultdict(lambda: [])
    keys_used = {}
    keys_only = False
    had_multiple_value_error = False
    for param in funcdef.get_params():
        # The value and key can both be null. There, the defaults apply.
        # args / kwargs will just be empty arrays / dicts, respectively.
        # Wrong value count is just ignored. If you try to test cases that are
        # not allowed in Python, Jedi will maybe not show any completions.
        key, argument = next(var_arg_iterator, (None, None))
        while key is not None:
            keys_only = True
            try:
                key_param = param_dict[key]
            except KeyError:
                non_matching_keys[key] = argument
            else:
                if key in keys_used:
                    had_multiple_value_error = True
                    m = ("TypeError: %s() got multiple values for keyword argument '%s'."
                         % (funcdef.name, key))
                    for node in var_args.get_calling_nodes():
                        analysis.add(parent_context, 'type-error-multiple-values',
                                     node, message=m)
                else:
                    keys_used[key] = ExecutedParam(execution_context, key_param, argument)
            key, argument = next(var_arg_iterator, (None, None))

        try:
            result_params.append(keys_used[param.name.value])
            continue
        except KeyError:
            pass

        if param.star_count == 1:
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
            seq = iterable.FakeSequence(execution_context.evaluator, 'tuple', lazy_context_list)
            result_arg = context.LazyKnownContext(seq)
        elif param.star_count == 2:
            # **kwargs param
            dct = iterable.FakeDict(execution_context.evaluator, dict(non_matching_keys))
            result_arg = context.LazyKnownContext(dct)
            non_matching_keys = {}
        else:
            # normal param
            if argument is None:
                # No value: Return an empty container
                if param.default is None:
                    result_arg = context.LazyUnknownContext()
                    if not keys_only:
                        for node in var_args.get_calling_nodes():
                            m = _error_argument_count(funcdef, len(unpacked_va))
                            analysis.add(parent_context, 'type-error-too-few-arguments',
                                         node, message=m)
                else:
                    result_arg = context.LazyTreeContext(parent_context, param.default)
            else:
                result_arg = argument

        result_params.append(ExecutedParam(execution_context, param, result_arg))
        if not isinstance(result_arg, context.LazyUnknownContext):
            keys_used[param.name.value] = result_params[-1]

    if keys_only:
        # All arguments should be handed over to the next function. It's not
        # about the values inside, it's about the names. Jedi needs to now that
        # there's nothing to find for certain names.
        for k in set(param_dict) - set(keys_used):
            param = param_dict[k]

            if not (non_matching_keys or had_multiple_value_error or
                    param.star_count or param.default):
                # add a warning only if there's not another one.
                for node in var_args.get_calling_nodes():
                    m = _error_argument_count(funcdef, len(unpacked_va))
                    analysis.add(parent_context, 'type-error-too-few-arguments',
                                 node, message=m)

    for key, lazy_context in non_matching_keys.items():
        m = "TypeError: %s() got an unexpected keyword argument '%s'." \
            % (funcdef.name, key)
        add_argument_issue(
            parent_context,
            'type-error-keyword-argument',
            lazy_context,
            message=m
        )

    remaining_arguments = list(var_arg_iterator)
    if remaining_arguments:
        m = _error_argument_count(funcdef, len(unpacked_va))
        # Just report an error for the first param that is not needed (like
        # cPython).
        first_key, lazy_context = remaining_arguments[0]
        if var_args.get_calling_nodes():
            # There might not be a valid calling node so check for that first.
            add_argument_issue(parent_context, 'type-error-too-many-arguments', lazy_context, message=m)
    return result_params


def _iterate_star_args(context, array, input_node, funcdef=None):
    try:
        iter_ = array.py__iter__
    except AttributeError:
        if funcdef is not None:
            # TODO this funcdef should not be needed.
            m = "TypeError: %s() argument after * must be a sequence, not %s" \
                % (funcdef.name.value, array)
            analysis.add(context, 'type-error-star', input_node, message=m)
    else:
        for lazy_context in iter_():
            yield lazy_context


def _star_star_dict(context, array, input_node, funcdef):
    from jedi.evaluate.instance import CompiledInstance
    if isinstance(array, CompiledInstance) and array.name.string_name == 'dict':
        # For now ignore this case. In the future add proper iterators and just
        # make one call without crazy isinstance checks.
        return {}
    elif isinstance(array, iterable.AbstractSequence) and array.array_type == 'dict':
        return array.exact_key_items()
    else:
        if funcdef is not None:
            m = "TypeError: %s argument after ** must be a mapping, not %s" \
                % (funcdef.name.value, array)
            analysis.add(context, 'type-error-star-star', input_node, message=m)
        return {}


def _error_argument_count(funcdef, actual_count):
    params = funcdef.get_params()
    default_arguments = sum(1 for p in params if p.default or p.star_count)

    if default_arguments == 0:
        before = 'exactly '
    else:
        before = 'from %s to ' % (len(params) - default_arguments)
    return ('TypeError: %s() takes %s%s arguments (%s given).'
            % (funcdef.name, before, len(params), actual_count))


def _create_default_param(execution_context, param):
    if param.star_count == 1:
        result_arg = context.LazyKnownContext(
            iterable.FakeSequence(execution_context.evaluator, 'tuple', [])
        )
    elif param.star_count == 2:
        result_arg = context.LazyKnownContext(
            iterable.FakeDict(execution_context.evaluator, {})
        )
    elif param.default is None:
        result_arg = context.LazyUnknownContext()
    else:
        result_arg = context.LazyTreeContext(execution_context.parent_context, param.default)
    return ExecutedParam(execution_context, param, result_arg)


def create_default_params(execution_context, funcdef):
    return [_create_default_param(execution_context, p)
            for p in funcdef.get_params()]

