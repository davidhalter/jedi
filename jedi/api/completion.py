from itertools import chain
import re

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


class Completion:
    def __init__(self, evaluator, parser, user_context, position, call_signatures_method):
        self._evaluator = evaluator
        self._parser = parser
        self._user_context = user_context
        self._pos = position
        self._call_signatures_method = call_signatures_method

    def get_completions(self, user_stmt, completion_parts):
        # TODO this closure is ugly. it also doesn't work with
        # simple_complete (used for Interpreter), somehow redo.
        module = self._evaluator.wrap(self._parser.module())
        names, level, only_modules, unfinished_dotted = \
            helpers.check_error_statements(module, self._pos)
        completion_names = []
        if names is not None:
            imp_names = tuple(str(n) for n in names if n.end_pos < self._pos)
            i = imports.Importer(self._evaluator, imp_names, module, level)
            completion_names = i.completion_names(self._evaluator, only_modules)

        # TODO this paragraph is necessary, but not sure it works.
        context = self._user_context.get_context()
        if not next(context).startswith('.'):  # skip the path
            if next(context) == 'from':
                # completion is just "import" if before stands from ..
                if unfinished_dotted:
                    return completion_names
                else:
                    return set([keywords.keyword(self._evaluator, 'import').name])

        if isinstance(user_stmt, tree.Import):
            module = self._parser.module()
            completion_names += imports.completion_names(self._evaluator,
                                                         user_stmt, self._pos)
            return completion_names

        if names is None and not isinstance(user_stmt, tree.Import):
            if not completion_parts.path and not completion_parts.has_dot:
                # add keywords
                completion_names += keywords.completion_names(
                    self._evaluator,
                    user_stmt,
                    self._pos,
                    module)
                # TODO delete? We should search for valid parser
                # transformations.
            completion_names += self._simple_complete(completion_parts)
        return completion_names

    def completions(self, path):
        # Dots following an int are not the start of a completion but a float
        # literal.
        if re.search(r'^\d\.$', path):
            return []
        completion_parts = helpers.get_completion_parts(path)

        user_stmt = self._parser.user_stmt_with_whitespace()

        completion_names = self.get_completions(user_stmt, completion_parts)

        if not completion_parts.has_dot:
            # add named params
            for call_sig in self._call_signatures_method():
                # Allow protected access, because it's a public API.
                module = call_sig._name.get_parent_until()
                # Compiled modules typically don't allow keyword arguments.
                if not isinstance(module, compiled.CompiledObject):
                    for p in call_sig.params:
                        # Allow access on _definition here, because it's a
                        # public API and we don't want to make the internal
                        # Name object public.
                        if p._definition.stars == 0:  # no *args/**kwargs
                            completion_names.append(p._name)

        needs_dot = not completion_parts.has_dot and path

        comps = []
        comp_dct = {}
        for c in set(completion_names):
            n = str(c)
            if settings.case_insensitive_completion \
                    and n.lower().startswith(completion_parts.name.lower()) \
                    or n.startswith(completion_parts.name):
                if isinstance(c.parent, (tree.Function, tree.Class)):
                    # TODO I think this is a hack. It should be an
                    #   er.Function/er.Class before that.
                    c = self._evaluator.wrap(c.parent).name
                new = classes.Completion(self._evaluator, c, needs_dot, len(completion_parts.name))
                k = (new.name, new.complete)  # key
                if k in comp_dct and settings.no_completion_duplicates:
                    comp_dct[k]._same_name_completions.append(new)
                else:
                    comp_dct[k] = new
                    comps.append(new)

        debug.speed('completions end')

        return sorted(comps, key=lambda x: (x.name.startswith('__'),
                                            x.name.startswith('_'),
                                            x.name.lower()))

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
