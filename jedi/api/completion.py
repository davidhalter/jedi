from itertools import chain

from jedi.parser import token
from jedi.parser import tree
from jedi import debug
from jedi import settings
from jedi.api import classes
from jedi.api import helpers
from jedi.evaluate import imports
from jedi.api import keywords
from jedi.evaluate import compiled
from jedi.evaluate.helpers import call_of_leaf
from jedi.evaluate.finder import global_names_dict_generator, filter_definition_names


def get_call_signature_param_names(call_signatures):
    # add named params
    for call_sig in call_signatures:
        # Allow protected access, because it's a public API.
        module = call_sig._name.get_parent_until()
        # Compiled modules typically don't allow keyword arguments.
        if not isinstance(module, compiled.CompiledObject):
            for p in call_sig.params:
                # Allow access on _definition here, because it's a
                # public API and we don't want to make the internal
                # Name object public.
                if p._definition.stars == 0:  # no *args/**kwargs
                    yield p._name


def filter_names(evaluator, completion_names, like_name):
    comp_dct = {}
    for name in set(completion_names):
        if settings.case_insensitive_completion \
                and str(name).lower().startswith(like_name.lower()) \
                or str(name).startswith(like_name):

            if isinstance(name.parent, (tree.Function, tree.Class)):
                # TODO I think this is a hack. It should be an
                #   er.Function/er.Class before that.
                name = evaluator.wrap(name.parent).name
            new = classes.Completion(
                evaluator,
                name,
                len(like_name)
            )
            k = (new.name, new.complete)  # key
            if k in comp_dct and settings.no_completion_duplicates:
                comp_dct[k]._same_name_completions.append(new)
            else:
                comp_dct[k] = new
                yield new


class Completion:
    def __init__(self, evaluator, parser, code_lines, position, call_signatures_method):
        self._evaluator = evaluator
        self._parser = parser
        self._module = evaluator.wrap(parser.module())
        self._code_lines = code_lines
        self._pos = position
        self._call_signatures_method = call_signatures_method

    def completions(self, path):
        completion_parts = helpers.get_completion_parts(path)

        completion_names = self._get_context_completions(completion_parts)

        completions = filter_names(self._evaluator, completion_names,
                                   completion_parts.name)

        return sorted(completions, key=lambda x: (x.name.startswith('__'),
                                                  x.name.startswith('_'),
                                                  x.name.lower()))

    def _get_context_completions(self, completion_parts):
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

        # Now we set the position to the place where we try to find out what we
        # have before it.
        pos = self._pos
        if completion_parts.name:
            pos = pos[0], pos[1] - len(completion_parts.name)

        try:
            stack = helpers.get_stack_at_position(grammar, self._code_lines, self._module, pos)
        except helpers.OnErrorLeaf as e:
            if e.error_leaf.value == '.':
                # After ErrorLeaf's that are dots, we will not do any
                # completions since this probably just confuses the user.
                return []
            # If we don't have a context, just use global completion.
            return self._global_completions()

        allowed_keywords, allowed_tokens = \
            helpers.get_possible_completion_types(grammar, stack)

        print(allowed_keywords, [token.tok_name[a] for a in allowed_tokens])
        completion_names = list(self._get_keyword_completion_names(allowed_keywords))

        if token.NAME in allowed_tokens:
            # This means that we actually have to do type inference.

            symbol_names = list(stack.get_node_names(grammar))
            print('symbolnames',symbol_names)

            nodes = list(stack.get_nodes())
            last_symbol = symbol_names[-1]

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
                return []
            elif symbol_names[-1] == 'trailer' and nodes[-1] == '.':
                dot = self._module.get_leaf_for_position(pos)
                atom_expr = call_of_leaf(dot.get_previous_leaf())
                completion_names += self._trailer_completions(atom_expr)
            else:
                completion_names += self._global_completions()

            if 'trailer' in symbol_names:
                call_signatures = self._call_signatures_method()
                completion_names += get_call_signature_param_names(call_signatures)

        return completion_names

    def _get_keyword_completion_names(self, keywords_):
        for k in keywords_:
            yield keywords.keyword(self._evaluator, k).name

    def _global_completions(self):
        scope = self._parser.user_scope()
        if not scope.is_scope():  # Might be a flow (if/while/etc).
            scope = scope.get_parent_scope()
        names_dicts = global_names_dict_generator(
            self._evaluator,
            self._evaluator.wrap(scope),
            self._pos
        )
        completion_names = []
        for names_dict, pos in names_dicts:
            names = list(chain.from_iterable(names_dict.values()))
            if not names:
                continue
            completion_names += filter_definition_names(
                names, self._parser.user_stmt(), pos
            )
        return completion_names

    def _trailer_completions(self, atom_expr):
        scopes = self._evaluator.eval_element(atom_expr)
        completion_names = []
        debug.dbg('possible completion scopes: %s', scopes)
        for s in scopes:
            names = []
            for names_dict in s.names_dicts(search_global=False):
                names += chain.from_iterable(names_dict.values())

            completion_names += filter_definition_names(
                names, self._parser.user_stmt()
            )
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
        names = [str(n) for n in names]
        i = imports.Importer(self._evaluator, names, self._module, level)
        return i.completion_names(self._evaluator, only_modules=only_modules)
