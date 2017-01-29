from jedi.parser import token
from jedi.parser import tree
from jedi import debug
from jedi import settings
from jedi.api import classes
from jedi.api import helpers
from jedi.evaluate import imports
from jedi.api import keywords
from jedi.evaluate.helpers import evaluate_call_of_leaf
from jedi.evaluate.filters import get_global_filters


def get_call_signature_param_names(call_signatures):
    # add named params
    for call_sig in call_signatures:
        for p in call_sig.params:
            # Allow protected access, because it's a public API.
            tree_name = p._name.tree_name
            # Compiled modules typically don't allow keyword arguments.
            if tree_name is not None:
                # Allow access on _definition here, because it's a
                # public API and we don't want to make the internal
                # Name object public.
                tree_param = tree.search_ancestor(tree_name, 'param')
                if tree_param.stars == 0:  # no *args/**kwargs
                    yield p._name


def filter_names(evaluator, completion_names, stack, like_name):
    comp_dct = {}
    for name in completion_names:
        if settings.case_insensitive_completion \
                and name.string_name.lower().startswith(like_name.lower()) \
                or name.string_name.startswith(like_name):

            new = classes.Completion(
                evaluator,
                name,
                stack,
                len(like_name)
            )
            k = (new.name, new.complete)  # key
            if k in comp_dct and settings.no_completion_duplicates:
                comp_dct[k]._same_name_completions.append(new)
            else:
                comp_dct[k] = new
                yield new


def get_user_scope(module_context, position):
    """
    Returns the scope in which the user resides. This includes flows.
    """
    user_stmt = module_context.tree_node.get_statement_for_position(position)
    if user_stmt is None:
        def scan(scope):
            for s in scope.children:
                if s.start_pos <= position <= s.end_pos:
                    if isinstance(s, (tree.Scope, tree.Flow)):
                        return scan(s) or s
                    elif s.type in ('suite', 'decorated'):
                        return scan(s)
            return None

        scanned_node = scan(module_context.tree_node)
        if scanned_node:
            return module_context.create_context(scanned_node, node_is_context=True)
        return module_context
    else:
        return module_context.create_context(user_stmt)


def get_flow_scope_node(module_node, position):
    node = module_node.get_leaf_for_position(position, include_prefixes=True)
    while not isinstance(node, (tree.Scope, tree.Flow)):
        node = node.parent

    return node


class Completion:
    def __init__(self, evaluator, module, code_lines, position, call_signatures_method):
        self._evaluator = evaluator
        self._module_context = module
        self._module_node = module.tree_node
        self._code_lines = code_lines

        # The first step of completions is to get the name
        self._like_name = helpers.get_on_completion_name(self._module_node, code_lines, position)
        # The actual cursor position is not what we need to calculate
        # everything. We want the start of the name we're on.
        self._position = position[0], position[1] - len(self._like_name)
        self._call_signatures_method = call_signatures_method

    def completions(self):
        completion_names = self._get_context_completions()

        completions = filter_names(self._evaluator, completion_names,
                                   self.stack, self._like_name)

        return sorted(completions, key=lambda x: (x.name.startswith('__'),
                                                  x.name.startswith('_'),
                                                  x.name.lower()))

    def _get_context_completions(self):
        """
        Analyzes the context that a completion is made in and decides what to
        return.

        Technically this works by generating a parser stack and analysing the
        current stack for possible grammar nodes.

        Possible enhancements:
        - global/nonlocal search global
        - yield from / raise from <- could be only exceptions/generators
        - In args: */**: no completion
        - In params (also lambda): no completion before =
        """

        grammar = self._evaluator.grammar

        try:
            self.stack = helpers.get_stack_at_position(
                grammar, self._code_lines, self._module_node, self._position
            )
        except helpers.OnErrorLeaf as e:
            self.stack = None
            if e.error_leaf.value == '.':
                # After ErrorLeaf's that are dots, we will not do any
                # completions since this probably just confuses the user.
                return []
            # If we don't have a context, just use global completion.

            return self._global_completions()

        allowed_keywords, allowed_tokens = \
            helpers.get_possible_completion_types(grammar, self.stack)

        completion_names = list(self._get_keyword_completion_names(allowed_keywords))

        if token.NAME in allowed_tokens or token.INDENT in allowed_tokens:
            # This means that we actually have to do type inference.

            symbol_names = list(self.stack.get_node_names(grammar))

            nodes = list(self.stack.get_nodes())

            if "import_stmt" in symbol_names:
                level = 0
                only_modules = True
                level, names = self._parse_dotted_names(nodes)
                if "import_from" in symbol_names:
                    if 'import' in nodes:
                        only_modules = False
                else:
                    assert "import_name" in symbol_names

                completion_names += self._get_importer_names(
                    names,
                    level,
                    only_modules
                )
            elif nodes and nodes[-1] in ('as', 'def', 'class'):
                # No completions for ``with x as foo`` and ``import x as foo``.
                # Also true for defining names as a class or function.
                return list(self._get_class_context_completions(is_function=True))
            elif symbol_names[-1] == 'trailer' and nodes[-1] == '.':
                dot = self._module_node.get_leaf_for_position(self._position)
                completion_names += self._trailer_completions(dot.get_previous_leaf())
            else:
                completion_names += self._global_completions()
                completion_names += self._get_class_context_completions(is_function=False)

            if 'trailer' in symbol_names:
                call_signatures = self._call_signatures_method()
                completion_names += get_call_signature_param_names(call_signatures)

        return completion_names

    def _get_keyword_completion_names(self, keywords_):
        for k in keywords_:
            yield keywords.keyword(self._evaluator, k).name

    def _global_completions(self):
        context = get_user_scope(self._module_context, self._position)
        debug.dbg('global completion scope: %s', context)
        flow_scope_node = get_flow_scope_node(self._module_node, self._position)
        filters = get_global_filters(
            self._evaluator,
            context,
            self._position,
            origin_scope=flow_scope_node
        )
        completion_names = []
        for filter in filters:
            completion_names += filter.values()
        return completion_names

    def _trailer_completions(self, previous_leaf):
        user_context = get_user_scope(self._module_context, self._position)
        evaluation_context = self._evaluator.create_context(
            self._module_context, previous_leaf
        )
        contexts = evaluate_call_of_leaf(evaluation_context, previous_leaf)
        completion_names = []
        debug.dbg('trailer completion contexts: %s', contexts)
        for context in contexts:
            for filter in context.get_filters(
                    search_global=False, origin_scope=user_context.tree_node):
                completion_names += filter.values()
        return completion_names

    def _parse_dotted_names(self, nodes):
        level = 0
        names = []
        for node in nodes[1:]:
            if node in ('.', '...'):
                if not names:
                    level += len(node.value)
            elif node.type == 'dotted_name':
                names += node.children[::2]
            elif node.type == 'name':
                names.append(node)
            else:
                break
        return level, names

    def _get_importer_names(self, names, level=0, only_modules=True):
        names = [n.value for n in names]
        i = imports.Importer(self._evaluator, names, self._module_context, level)
        return i.completion_names(self._evaluator, only_modules=only_modules)

    def _get_class_context_completions(self, is_function=True):
        """
        Autocomplete inherited methods when overriding in child class.
        """
        leaf = self._module_node.get_leaf_for_position(self._position, include_prefixes=True)
        cls = leaf.get_parent_until(tree.Class)
        if isinstance(cls, (tree.Class, tree.Function)):
            # Complete the methods that are defined in the super classes.
            random_context = self._module_context.create_context(
                cls,
                node_is_context=True
            )
        else:
            return

        if cls.start_pos[1] >= leaf.start_pos[1]:
            return

        filters = random_context.get_filters(search_global=False, is_instance=True)
        # The first dict is the dictionary of class itself.
        next(filters)
        for filter in filters:
            for name in filter.values():
                if (name.api_type == 'function') == is_function:
                    yield name
