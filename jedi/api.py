__all__ = ['Script', 'NotFoundError', 'set_debug_function']

import re
import weakref

import parsing
import dynamic
import imports
import evaluate
import modules
import debug
import settings
import keywords
import helpers
import builtin

from _compatibility import next


class NotFoundError(Exception):
    """ A custom error to avoid catching the wrong exceptions """
    pass


class Completion(object):
    """ `Completion` objects are returned from `Script.complete`. Providing
    some useful functions for IDE's. """
    def __init__(self, name, needs_dot, like_name_length, base):
        self.name = name
        self.needs_dot = needs_dot
        self.like_name_length = like_name_length
        self._completion_parent = name.parent()  # limit gc
        self.base = base

    @property
    def complete(self):
        """ Delievers the rest of the word, e.g. completing `isinstance`
        >>> isinstan

        would return the string 'ce'. It also adds additional stuff, depending
        on your `settings.py`
        """
        dot = '.' if self.needs_dot else ''
        append = ''
        funcs = (parsing.Function, evaluate.Function)
        if settings.add_bracket_after_function \
                    and self._completion_parent.isinstance(funcs):
            append = '('

        if settings.add_dot_after_module:
            if isinstance(self.base, parsing.Module):
                append += '.'
        if isinstance(self.base, parsing.Param):
            append += '='
        return dot + self.name.names[-1][self.like_name_length:] + append

    @property
    def word(self):
        """ In contrary to `complete` returns the whole word, e.g.
        >>> isinstan

        would return 'isinstance'.
        """
        return str(self.name.names[-1])

    @property
    def description(self):
        """ Provides a description of the completion object
        TODO return value is just __repr__ of some objects, improve! """
        return str(self.name.parent())

    @property
    def doc(self):
        """ Returns the docstring `__doc__` for any object """
        try:
            return str(self.name.parent().docstr)
        except AttributeError:
            return ''

    def get_type(self):
        """ Returns the type of a completion object (e.g. Function/Class
        TODO please don't use yet, behaviour may change in the future. """
        return type(self.name.parent())

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.name)


class Definition(dynamic.BaseOutput):
    """ These are the objects returned by either `Script.goto` or
    `Script.get_definition`. """
    def __init__(self, definition):
        super(Definition, self).__init__(definition.start_pos, definition)
        self._def_parent = definition.parent()  # just here to limit gc

    @property
    def description(self):
        """ A description of the Definition object, which is heavily used in
        testing. e.g. for `isinstance` it returns 'def isinstance' """
        d = self.definition
        if isinstance(d, evaluate.InstanceElement):
            d = d.var
        if isinstance(d, evaluate.parsing.Name):
            d = d.parent()

        if isinstance(d, evaluate.Array):
            d = 'class ' + d.type
        elif isinstance(d, (parsing.Class, evaluate.Class, evaluate.Instance)):
            d = 'class ' + str(d.name)
        elif isinstance(d, (evaluate.Function, evaluate.parsing.Function)):
            d = 'def ' + str(d.name)
        elif isinstance(d, evaluate.parsing.Module):
            # only show module name
            d = 'module %s' % self.module_name
        elif isinstance(d, keywords.Keyword):
            d = 'keyword %s' % d.name
        else:
            d = d.get_code().replace('\n', '')
        return d

    @property
    def doc(self):
        """ Returns the docstr, behaves like `Completion.doc`. """
        try:
            return str(self.definition.docstr)
        except AttributeError:
            return ''

    @property
    def desc_with_module(self):
        """ In addition to the Definition, it also returns the module. Don't
        use it yet, its behaviour may change. If you really need it, talk to me
        TODO add full path. This function is should return a
        module.class.function path. """
        if self.module_path.endswith('.py') \
                    and not isinstance(self.definition, parsing.Module):
            position = '@%s' % (self.line_nr)
        else:
            # is a builtin or module
            position = ''
        return "%s:%s%s" % (self.module_name, self.description, position)


class CallDef(object):
    """ `CallDef` objects is the return value of `Script.get_in_function_call`.
    It knows what functions you are currently in. e.g. `isinstance(` would
    return the `isinstance` function. without `(` it would return nothing."""
    def __init__(self, executable, index, call):
        self.executable = executable
        self.index = index
        self.call = call

    @property
    def params(self):
        if self.executable.isinstance(evaluate.Function):
            if isinstance(self.executable, evaluate.InstanceElement):
                return self.executable.params[1:]
            return self.executable.params
        else:
            try:
                sub = self.executable.get_subscope_by_name('__init__')
                return sub.params[1:]  # ignore self
            except KeyError:
                return []

    @property
    def bracket_start(self):
        """ The indent of the bracket that is responsible for the last function
        call. """
        c = self.call
        while c.next is not None:
            c = c.next
        return c.name.end_pos

    @property
    def call_name(self):
        """ The name (e.g. 'isinstance') as a string. """
        return str(self.executable.name)

    @property
    def module(self):
        return self.executable.get_parent_until()

    def __repr__(self):
        return '<%s: %s index %s>' % (type(self).__name__, self.executable,
                                    self.index)


class Script(object):
    """
    A Script is the base for a completion, goto or whatever call.

    :param source: The source code of the current file
    :type source: string
    :param line: The line to complete in.
    :type line: int
    :param col: The column to complete in.
    :type col: int
    :param source_path: The path in the os, the current module is in.
    :type source_path: string
    """
    def __init__(self, source, line, column, source_path):
        self.pos = line, column
        self.module = modules.ModuleWithCursor(source_path, source=source,
                                                            position=self.pos)
        self.parser = self.module.parser
        self.source_path = source_path

    def complete(self):
        """
        An auto completer for python files.

        :return: list of Completion objects.
        :rtype: list
        """
        path = self.module.get_path_until_cursor()
        path, dot, like = self._get_completion_parts(path)

        try:
            scopes = list(self._prepare_goto(path, True))
        except NotFoundError:
            scopes = []
            scope_generator = evaluate.get_names_for_scope(
                                            self.parser.user_scope, self.pos)
            completions = []
            for scope, name_list in scope_generator:
                for c in name_list:
                    completions.append((c, scope))
        else:
            completions = []
            debug.dbg('possible scopes', scopes)
            for s in scopes:
                # TODO is this really the right way? just ignore the funcs? \
                # do the magic functions first? and then recheck here?
                if not isinstance(s, evaluate.Function):
                    if isinstance(s, imports.ImportPath):
                        if like == 'import':
                            l = self.module.get_line(self.pos[0])[:self.pos[1]]
                            if not l.endswith('import import'):
                                continue
                        names = s.get_defined_names(on_import_stmt=True)
                    else:
                        names = s.get_defined_names()
                    for c in names:
                        completions.append((c, s))

        if not dot:  # named_params have no dots
            call_def = self.get_in_function_call()
            if call_def:
                if not call_def.module.is_builtin():
                    for p in call_def.params:
                        completions.append((p.get_name(), p))

            # Do the completion if there is no path before and no import stmt.
            if (not scopes or not isinstance(scopes[0], imports.ImportPath)) \
                        and not path:
                # add keywords
                bs = builtin.Builtin.scope
                completions += ((k, bs) for k in keywords.get_keywords(
                                                                    all=True))

        completions = [(c, s) for c, s in completions
                        if settings.case_insensitive_completion
                            and c.names[-1].lower().startswith(like.lower())
                            or c.names[-1].startswith(like)]

        needs_dot = not dot and path
        completions = set(completions)

        c = [Completion(c, needs_dot, len(like), s) for c, s in completions]

        return c

    def _prepare_goto(self, goto_path, is_like_search=False):
        """ Base for complete, goto and get_definition. Basically it returns
        the resolved scopes under cursor. """
        debug.dbg('start: %s in %s' % (goto_path, self.parser.scope))

        user_stmt = self.parser.user_stmt
        if not user_stmt and len(goto_path.split('\n')) > 1:
            # If the user_stmt is not defined and the goto_path is multi line,
            # something's strange. Most probably the backwards tokenizer
            # matched to much.
            return []

        if isinstance(user_stmt, parsing.Import):
            scopes = [self._get_on_import_stmt(is_like_search)[0]]
        else:
            # just parse one statement, take it and evaluate it
            stmt = self._get_under_cursor_stmt(goto_path)
            scopes = evaluate.follow_statement(stmt)
        return scopes

    def _get_under_cursor_stmt(self, cursor_txt):
        r = parsing.PyFuzzyParser(cursor_txt, self.source_path, no_docstr=True)
        try:
            stmt = r.module.statements[0]
        except IndexError:
            raise NotFoundError()
        stmt.start_pos = self.pos
        stmt.parent = weakref.ref(self.parser.user_scope)
        return stmt

    def get_definition(self):
        """
        Returns the definitions of a the path under the cursor. This is
        not a goto function! This follows complicated paths and returns the
        end, not the first definition.
        The big difference of goto and get_definition is that goto doesn't
        follow imports and statements.

        :return: list of Definition objects, which are basically scopes.
        :rtype: list
        """
        def resolve_import_paths(scopes):
            for s in scopes.copy():
                if isinstance(s, imports.ImportPath):
                    scopes.remove(s)
                    scopes.update(resolve_import_paths(set(s.follow())))
            return scopes

        goto_path = self.module.get_path_under_cursor()

        context = self.module.get_context()
        if next(context) in ('class', 'def'):
            scopes = set([self.module.parser.user_scope])
        elif not goto_path:
            op = self.module.get_operator_under_cursor()
            scopes = set([keywords.get_operator(op, self.pos)] if op else [])
        else:
            scopes = set(self._prepare_goto(goto_path))

        scopes = resolve_import_paths(scopes)

        # add keywords
        scopes |= keywords.get_keywords(string=goto_path, pos=self.pos)

        d = set([Definition(s) for s in scopes])
        return sorted(d, key=lambda x: (x.module_path, x.start_pos))

    def goto(self):
        """
        Returns the first definition found by goto. This means: It doesn't
        follow imports and statements.

        :return: list of Definition objects, which are basically scopes.
        """
        d = [Definition(d) for d in set(self._goto()[0])]
        return sorted(d, key=lambda x: (x.module_path, x.start_pos))

    def _goto(self, add_import_name=False):
        """
        Used for goto and related_names.
        """
        goto_path = self.module.get_path_under_cursor()
        context = self.module.get_context()
        if next(context) in ('class', 'def'):
            user_scope = self.parser.user_scope
            definitions = set([user_scope.name])
            search_name = str(user_scope.name)
        elif isinstance(self.parser.user_stmt, parsing.Import):
            s, name_part = self._get_on_import_stmt()
            try:
                definitions = [s.follow(is_goto=True)[0]]
            except IndexError:
                definitions = []
            search_name = str(name_part)

            if add_import_name:
                import_name = self.parser.user_stmt.get_defined_names()
                # imports have only one name
                if name_part == import_name[0].names[-1]:
                    definitions.append(import_name[0])
        else:
            stmt = self._get_under_cursor_stmt(goto_path)
            definitions, search_name = evaluate.goto(stmt)
        return definitions, search_name

    def related_names(self, additional_module_paths=[]):
        """
        Returns `dynamic.RelatedName` objects, which contain all names, that
        are defined by the same variable, function, class or import.
        This function can be used either to show all the usages of a variable
        or for renaming purposes.

        TODO implement additional_module_paths
        """
        user_stmt = self.parser.user_stmt
        definitions, search_name = self._goto(add_import_name=True)
        if isinstance(user_stmt, parsing.Statement) \
                    and self.pos < user_stmt.get_assignment_calls().start_pos:
            # the search_name might be before `=`
            definitions = [v for v in user_stmt.set_vars
                                                if str(v) == search_name]
        if not isinstance(user_stmt, parsing.Import):
            # import case is looked at with add_import_name option
            definitions = dynamic.related_name_add_import_modules(definitions,
                                                                search_name)

        module = set([d.get_parent_until() for d in definitions])
        module.add(self.parser.module)
        names = dynamic.related_names(definitions, search_name, module)

        for d in set(definitions):
            if isinstance(d, parsing.Module):
                names.append(dynamic.RelatedName(d, d))
            else:
                names.append(dynamic.RelatedName(d.names[0], d))

        return sorted(set(names), key=lambda x: (x.module_path, x.start_pos),
                                                                reverse=True)

    def get_in_function_call(self):
        """
        Return the function, that the cursor is in, e.g.:
        >>> isinstance(| # | <-- cursor is here

        This would return the `isinstance` function. In contrary:
        >>> isinstance()| # | <-- cursor is here

        This would return `None`.
        """
        def scan_array_for_pos(arr, pos):
            """
            Returns the function Call that match search_name in an Array.
            """
            index = 0
            call = None
            stop = False
            for index, sub in enumerate(arr.values):
                call = None
                for s in sub:
                    if isinstance(s, parsing.Array):
                        new = scan_array_for_pos(s, pos)
                        if new[0] is not None:
                            call, index, stop = new
                            if stop:
                                return call, index, stop
                    elif isinstance(s, parsing.Call):
                        start_s = s
                        while s is not None:
                            if s.start_pos >= pos:
                                return call, index, stop
                            elif s.execution is not None:
                                end = s.execution.end_pos
                                if s.execution.start_pos < pos and \
                                        (end is None or pos < end):
                                    c, index, stop = scan_array_for_pos(
                                                            s.execution, pos)
                                    if stop:
                                        return c, index, stop

                                    # call should return without execution and
                                    # next
                                    reset = c or s
                                    if reset.execution.type not in \
                                                [parsing.Array.TUPLE,
                                                parsing.Array.NOARRAY]:
                                        return start_s, index, False

                                    reset.execution = None
                                    reset.next = None
                                    return c or start_s, index, True
                            s = s.next

            # The third return is just necessary for recursion inside, because
            # it needs to know when to stop iterating.
            return call, index, stop

        user_stmt = self.parser.user_stmt
        if user_stmt is None or not isinstance(user_stmt, parsing.Statement):
            return None
        ass = helpers.fast_parent_copy(user_stmt.get_assignment_calls())

        call, index, stop = scan_array_for_pos(ass, self.pos)
        if call is None:
            return None

        origins = evaluate.follow_call(call)

        if len(origins) == 0:
            return None
        # just take entry zero, because we need just one.
        executable = origins[0]

        after = self.module.get_line(self.pos[0])[self.pos[1]:]
        index -= re.search('^[ ,]*', after).group(0).count(',')
        return CallDef(executable, index, call)

    def _get_on_import_stmt(self, is_like_search=False):
        """ Resolve the user statement, if it is an import. Only resolve the
        parts until the user position. """
        user_stmt = self.parser.user_stmt
        import_names = user_stmt.get_all_import_names()
        kill_count = -1
        cur_name_part = None
        for i in import_names:
            if user_stmt.alias == i:
                continue
            for name_part in i.names:
                if name_part.end_pos >= self.pos:
                    if not cur_name_part:
                        cur_name_part = name_part
                    kill_count += 1

        i = imports.ImportPath(user_stmt, is_like_search,
                                kill_count=kill_count, direct_resolve=True)
        return i, cur_name_part

    def _get_completion_parts(self, path):
        """
        Returns the parts for the completion
        :return: tuple - (path, dot, like)
        """
        match = re.match(r'^(.*?)(\.|)(\w?[\w\d]*)$', path, flags=re.S)
        return match.groups()

    def __del__(self):
        evaluate.clear_caches()


def set_debug_function(func_cb):
    """
    You can define a callback debug function to get all the debug messages.
    :param func_cb: The callback function for debug messages, with n params.
    """
    debug.debug_function = func_cb
