from jedi._compatibility import Parameter
from jedi.evaluate.utils import to_list
from jedi.evaluate.names import ParamNameWrapper


class _SignatureMixin(object):
    def to_string(self):
        def param_strings():
            is_positional = False
            is_kw_only = False
            for n in self.get_param_names():
                kind = n.get_kind()
                is_positional |= kind == Parameter.POSITIONAL_ONLY
                if is_positional and kind != Parameter.POSITIONAL_ONLY:
                    yield '/'
                    is_positional = False

                if kind == Parameter.VAR_POSITIONAL:
                    is_kw_only = True
                elif kind == Parameter.KEYWORD_ONLY and not is_kw_only:
                    yield '*'
                    is_kw_only = True

                yield n.to_string()

            if is_positional:
                yield '/'

        s = self.name.string_name + '(' + ', '.join(param_strings()) + ')'
        annotation = self.annotation_string
        if annotation:
            s += ' -> ' + annotation
        return s

    def get_param_names(self):
        param_names = self._function_context.get_param_names()
        if self.is_bound:
            return param_names[1:]
        return param_names


class AbstractSignature(_SignatureMixin):
    def __init__(self, context, is_bound=False):
        self.context = context
        self.is_bound = is_bound

    @property
    def name(self):
        return self.context.name

    @property
    def annotation_string(self):
        return ''

    def bind(self, context):
        raise NotImplementedError


class TreeSignature(AbstractSignature):
    def __init__(self, context, function_context=None, is_bound=False):
        super(TreeSignature, self).__init__(context, is_bound)
        self._function_context = function_context or context

    def bind(self, context):
        return TreeSignature(context, self._function_context, is_bound=True)

    @property
    def _annotation(self):
        # Classes don't need annotations, even if __init__ has one. They always
        # return themselves.
        if self.context.is_class():
            return None
        return self._function_context.tree_node.annotation

    @property
    def annotation_string(self):
        a = self._annotation
        if a is None:
            return ''
        return a.get_code(include_prefix=False)

    def get_param_names(self):
        return _process_params(super(TreeSignature, self).get_param_names())


def _iter_nodes_for_param(param_name):
    from parso.python.tree import search_ancestor
    from jedi.evaluate.arguments import TreeArguments

    execution_context = param_name.parent_context
    function_node = execution_context.tree_node
    module_node = function_node.get_root_node()
    start = function_node.children[-1].start_pos
    end = function_node.children[-1].end_pos
    for name in module_node.get_used_names().get(param_name.string_name):
        if start <= name.start_pos < end:
            # Is used in the function
            argument = name.parent
            if argument.type == 'argument' \
                    and argument.children[0] == '*' * param_name.star_count:
                # No support for Python <= 3.4 here, but they are end-of-life
                # anyway
                trailer = search_ancestor(argument, 'trailer')
                if trailer is not None:  # Make sure we're in a function
                    context = execution_context.create_context(trailer)
                    if _goes_to_param_name(param_name, context, name):
                        contexts = _to_callables(context, trailer)

                        args = TreeArguments.create_cached(
                            execution_context.evaluator,
                            context=context,
                            argument_node=trailer.children[1],
                            trailer=trailer,
                        )
                        for c in contexts:
                            yield c, args
                    else:
                        assert False


def _goes_to_param_name(param_name, context, potential_name):
    if potential_name.type != 'name':
        return False
    from jedi.evaluate.names import TreeNameDefinition
    found = TreeNameDefinition(context, potential_name).goto()
    return any(param_name.parent_context == p.parent_context
               and param_name.start_pos == p.start_pos
               for p in found)


def _to_callables(context, trailer):
    from jedi.evaluate.syntax_tree import eval_trailer

    atom_expr = trailer.parent
    index = atom_expr.children[0] == 'await'
    # Eval atom first
    contexts = context.eval_node(atom_expr.children[index])
    for trailer2 in atom_expr.children[index + 1:]:
        if trailer == trailer2:
            break
        contexts = eval_trailer(context, contexts, trailer2)
    return contexts


def _remove_given_params(arguments, param_names):
    count = 0
    used_keys = set()
    for key, _ in arguments.unpack():
        if key is None:
            count += 1
        else:
            used_keys.add(key)

    for p in param_names:
        if count and p.maybe_positional_argument():
            count -= 1
            continue
        if p.string_name in used_keys and p.maybe_keyword_argument():
            continue
        yield p


def _process_params(param_names, star_count=3):  # default means both * and **
    used_names = set()
    kw_only_params = []
    arg_funcs = []
    kwarg_funcs = []
    kwarg_names = []
    longest_param_names = ()
    for p in param_names:
        kind = p.get_kind()
        if kind == Parameter.VAR_POSITIONAL:
            if star_count & 1:
                arg_funcs = list(_iter_nodes_for_param(p))
                if not arg_funcs:
                    yield p
        elif p.get_kind() == Parameter.VAR_KEYWORD:
            if star_count & 2:
                kwarg_funcs = list(_iter_nodes_for_param(p))
                if not kwarg_funcs:
                    kwarg_names.append(p)
        elif kind == Parameter.KEYWORD_ONLY:
            if star_count & 2:
                kw_only_params.append(p)
        elif kind == Parameter.POSITIONAL_ONLY:
            if star_count & 1:
                yield p
        else:
            if star_count == 1:
                yield ParamNameFixedKind(p, Parameter.POSITIONAL_ONLY)
            elif star_count == 2:
                yield ParamNameFixedKind(p, Parameter.KEYWORD_ONLY)
            else:
                yield p

    for func_and_argument in arg_funcs:
        func, arguments = func_and_argument
        new_star_count = star_count
        if func_and_argument in kwarg_funcs:
            kwarg_funcs.remove(func_and_argument)
        else:
            new_star_count = 1

        args_for_this_func = []
        for p in _process_params(
                list(_remove_given_params(
                    arguments,
                    func.get_param_names()
                )), new_star_count):
            if p.get_kind() == Parameter.VAR_KEYWORD:
                kwarg_names.append(p)
            elif p.get_kind() == Parameter.KEYWORD_ONLY:
                kw_only_params.append(p)
            else:
                args_for_this_func.append(p)
        if len(args_for_this_func) > len(longest_param_names):
            longest_param_names = args_for_this_func

    for p in longest_param_names:
        if star_count == 1 and p.get_kind() != Parameter.VAR_POSITIONAL:
            yield ParamNameFixedKind(p, Parameter.POSITIONAL_ONLY)
        else:
            yield p

    for p in kw_only_params:
        yield p

    for func, arguments in kwarg_funcs:
        for p in _process_params(
                list(_remove_given_params(
                    arguments,
                    func.get_param_names()
                )), star_count=2):
            if p.get_kind() != Parameter.KEYWORD_ONLY or not kwarg_names:
                yield p

    if kwarg_names:
        yield kwarg_names[0]
    return


class ParamNameFixedKind(ParamNameWrapper):
    def __init__(self, param_name, new_kind):
        super(ParamNameFixedKind, self).__init__(param_name)
        self._new_kind = new_kind

    def get_kind(self):
        return self._new_kind


class BuiltinSignature(AbstractSignature):
    def __init__(self, context, return_string, is_bound=False):
        super(BuiltinSignature, self).__init__(context, is_bound)
        self._return_string = return_string

    @property
    def annotation_string(self):
        return self._return_string

    @property
    def _function_context(self):
        return self.context

    def bind(self, context):
        assert not self.is_bound
        return BuiltinSignature(context, self._return_string, is_bound=True)


class SignatureWrapper(_SignatureMixin):
    def __init__(self, wrapped_signature):
        self._wrapped_signature = wrapped_signature

    def __getattr__(self, name):
        return getattr(self._wrapped_signature, name)
