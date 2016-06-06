from itertools import chain
import re

from jedi.parser import token
from jedi.parser import tree
from jedi import debug
from jedi import settings
from jedi.api import classes
from jedi.api import helpers
from jedi.api import inference
from jedi.evaluate import imports
from jedi.api import keywords
from jedi.evaluate import compiled
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


def filter_names(evaluator, completion_names, needs_dot, like_name):
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
                needs_dot,
                len(like_name)
            )
            k = (new.name, new.complete)  # key
            if k in comp_dct and settings.no_completion_duplicates:
                comp_dct[k]._same_name_completions.append(new)
            else:
                comp_dct[k] = new
                yield new


class Completion:
    def __init__(self, evaluator, parser, user_context, position, call_signatures_method):
        self._evaluator = evaluator
        self._parser = parser
        self._module = evaluator.wrap(parser.module())
        self._user_context = user_context
        self._source = user_context.source
        self._pos = position
        self._call_signatures_method = call_signatures_method

    def completions(self, path):
        # Dots following an int are not the start of a completion but a float
        # literal.
        if re.search(r'^\d\.$', path):
            return []
        completion_parts = helpers.get_completion_parts(path)

        user_stmt = self._parser.user_stmt_with_whitespace()

        completion_names = self._get_context_completions(user_stmt, completion_parts)

        if not completion_parts.has_dot:
            call_signatures = self._call_signatures_method()
            completion_names += get_call_signature_param_names(call_signatures)

        needs_dot = not completion_parts.has_dot and completion_parts.path

        completions = filter_names(self._evaluator, completion_names,
                                   needs_dot, completion_parts.name)

        return sorted(completions, key=lambda x: (x.name.startswith('__'),
                                                  x.name.startswith('_'),
                                                  x.name.lower()))

    def _get_context_completions(self, user_stmt, completion_parts):
        """
        Analyzes the context that a completion is made in and decides what to
        return.

        Could specialized completions for:
        - from/import completions
        - as nothing
        - statements that start always on new line
                       'import', 'class', 'def', 'try', 'except',
                       'finally', 'while', with
        - statements that start always on new line or after ; or after :
                        return raise continue break del pass global nonlocal assert
        - def/class nothing
        - async for/def/with
        - \n@/del/return/raise no keyword (after keyword no keyword)?
        - after keyword
        - continue/break/pass nothing
        - global/nonlocal search global
        - after operator no keyword: return
        - yield like return + after ( and =
        - almost always ok
              'and', 'for', 'if', 'else', 'in', 'is', 'lambda', 'not', 'or'
        - after operations no keyword:
                + = * ** - etc Maybe work with the parser state?

        # hard:
        - await
        - yield from / raise from / from import difference
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
            stack = helpers.get_stack_at_position(grammar, self._source, self._module, pos)
        except helpers.OnErrorLeaf:
            return self._simple_complete(completion_parts)

        allowed_keywords, allowed_tokens = \
            helpers.get_possible_completion_types(grammar, stack)

        print(allowed_keywords, [token.tok_name[a] for a in allowed_tokens])
        completion_names = list(self._get_keyword_completion_names(allowed_keywords))

        if token.NAME in allowed_tokens:
            # This means that we actually have to do type inference.

            symbol_names = list(stack.get_node_names(grammar))
            print(symbol_names)

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
            else:
                completion_names += self._simple_complete(completion_parts)

        return completion_names

    def _get_keyword_completion_names(self, keywords_):
        for k in keywords_:
            yield keywords.keyword(self._evaluator, k).name

    def _simple_complete(self, completion_parts):
        if not completion_parts.path and not completion_parts.has_dot:
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
        elif inference.get_under_cursor_stmt(self._evaluator, self._parser,
                                             completion_parts.path, self._pos) is None:
            return []
        else:
            scopes = list(inference.type_inference(
                self._evaluator, self._parser, self._user_context,
                self._pos, completion_parts.path, is_completion=True
            ))
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
