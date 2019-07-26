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

    @to_list
    def get_param_names(self):
        used_names = set()
        kwarg_params = []
        for param_name in super(TreeSignature, self).get_param_names():
            kind = param_name.get_kind()
            if kind == Parameter.VAR_POSITIONAL:
                for param_names in _iter_nodes_for_param(param_name, star_count=1):
                    for p in param_names:
                        yield p
                    break
                else:
                    yield param_name
            elif kind == Parameter.VAR_KEYWORD:
                kwarg_params.append(param_name)
            else:
                if param_name.maybe_keyword_argument():
                    used_names.add(param_name.string_name)
                yield param_name

        for param_name in kwarg_params:
            for param_names in _iter_nodes_for_param(param_name, star_count=2):
                for p in param_names:
                    if p.string_name not in used_names or p.get_kind() == Parameter.VAR_KEYWORD:
                        used_names.add(p.string_name)
                        yield p


def _iter_nodes_for_param(param_name, star_count):
    from jedi.evaluate.syntax_tree import eval_trailer
    from jedi.evaluate.names import TreeNameDefinition
    from parso.python.tree import search_ancestor
    from jedi.evaluate.arguments import TreeArguments

    execution_context = param_name.parent_context
    function_node = execution_context.tree_node
    module_node = function_node.get_root_node()
    start = function_node.children[-1].start_pos
    end = function_node.children[-1].end_pos
    for name in module_node.get_used_names().get(param_name.string_name):
        if start <= name.start_pos < end:
            # Is used in the function.
            argument = name.parent
            if argument.type == 'argument' and argument.children[0] == '*' * star_count:
                # No support for Python <= 3.4 here, but they are end-of-life
                # anyway.
                trailer = search_ancestor(argument, 'trailer')
                if trailer is not None:
                    atom_expr = trailer.parent
                    context = execution_context.create_context(atom_expr)
                    found = TreeNameDefinition(context, name).goto()
                    if any(param_name.parent_context == p.parent_context
                           and param_name.start_pos == p.start_pos
                           for p in found):
                        index = atom_expr.children[0] == 'await'
                        # Eval atom first
                        contexts = context.eval_node(atom_expr.children[index])
                        for trailer2 in atom_expr.children[index + 1:]:
                            if trailer == trailer2:
                                break
                            contexts = eval_trailer(context, contexts, trailer2)
                        args = TreeArguments(
                            evaluator=execution_context.evaluator,
                            context=context,
                            argument_node=trailer.children[1],
                            trailer=trailer,
                        )
                        for c in contexts:
                            yield list(_process_params(
                                _remove_given_params(args, c.get_param_names()),
                                star_count,
                            ))
                    else:
                        assert False


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
    param_names = list(param_names)
    for p in param_names:
        if star_count == 1 and p.maybe_positional_argument():
            if p.get_kind() == Parameter.VAR_POSITIONAL:
                for param_names in _iter_nodes_for_param(p, star_count=1):
                    for p in param_names:
                        yield p
                    break
                else:
                    yield p
            else:
                yield ParamNameFixedKind(p, Parameter.POSITIONAL_ONLY)
        elif star_count == 2 and p.maybe_keyword_argument():
            if p.get_kind() == Parameter.VAR_KEYWORD:
                itered = list(_iter_nodes_for_param(p, star_count=2))
                if not itered:
                    # We were not able to resolve kwargs.
                    yield p
                for param_names in itered:
                    for p in param_names:
                        if p.string_name not in used_names:
                            used_names.add(p.string_name)
                            yield p
            else:
                yield ParamNameFixedKind(p, Parameter.KEYWORD_ONLY)
        elif star_count == 3:
            yield p


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
