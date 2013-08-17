"""
The ``Parser`` tries to convert the available Python code in an easy to read
format, something like an abstract syntax tree. The classes who represent this
tree, are sitting in the :mod:`parsing_representation` module.

The Python module ``tokenize`` is a very important part in the ``Parser``,
because it splits the code into different words (tokens).  Sometimes it looks a
bit messy. Sorry for that! You might ask now: "Why didn't you use the ``ast``
module for this? Well, ``ast`` does a very good job understanding proper Python
code, but fails to work as soon as there's a single line of broken code.

There's one important optimization that needs to be known: Statements are not
being parsed completely. ``Statement`` is just a representation of the tokens
within the statement. This lowers memory usage and cpu time and reduces the
complexity of the ``Parser`` (there's another parser sitting inside
``Statement``, which produces ``Array`` and ``Call``).
"""
from __future__ import with_statement

import tokenizer as tokenize
import keyword

from jedi._compatibility import next, StringIO
from jedi import debug
from jedi import common
from jedi import parsing_representation as pr


class ParserError(Exception):
    pass


class Parser(object):
    """
    This class is used to parse a Python file, it then divides them into a
    class structure of different scopes.

    :param source: The codebase for the parser.
    :type source: str
    :param module_path: The path of the module in the file system, may be None.
    :type module_path: str
    :param user_position: The line/column, the user is currently on.
    :type user_position: tuple(int, int)
    :param no_docstr: If True, a string at the beginning is not a docstr.
    :param is_fast_parser: -> for fast_parser
    :param top_module: Use this module as a parent instead of `self.module`.
    """
    def __init__(self, source, module_path=None, user_position=None,
                 no_docstr=False, offset=(0, 0), is_fast_parser=None,
                 top_module=None):
        self.user_position = user_position
        self.user_scope = None
        self.user_stmt = None
        self.no_docstr = no_docstr

        self.start_pos = self.end_pos = 1 + offset[0], offset[1]
        # initialize global Scope
        self.module = pr.SubModule(module_path, self.start_pos, top_module)
        self._scope = self.module
        self._current = (None, None)

        source = source + '\n'  # end with \n, because the parser needs it
        buf = StringIO(source)
        self._gen = common.NoErrorTokenizer(buf.readline, offset,
                                            is_fast_parser)
        self.top_module = top_module or self.module
        try:
            self._parse()
        except (common.MultiLevelStopIteration, StopIteration):
            # StopIteration needs to be added as well, because python 2 has a
            # strange way of handling StopIterations.
            # sometimes StopIteration isn't catched. Just ignore it.
            pass

        # clean up unused decorators
        for d in self._decorators:
            # set a parent for unused decorators, avoid NullPointerException
            # because of `self.module.used_names`.
            d.parent = self.module

        if self._current[0] in (tokenize.NL, tokenize.NEWLINE):
            # we added a newline before, so we need to "remove" it again.
            self.end_pos = self._gen.previous[2]
        elif self._current[0] == tokenize.INDENT:
            self.end_pos = self._gen.last_previous[2]

        self.start_pos = self.module.start_pos
        self.module.end_pos = self.end_pos
        del self._gen

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, self.module)

    def _check_user_stmt(self, simple):
        # this is not user checking, just update the used_names
        for tok_name in self.module.temp_used_names:
            try:
                self.module.used_names[tok_name].add(simple)
            except KeyError:
                self.module.used_names[tok_name] = set([simple])
        self.module.temp_used_names = []

        if not self.user_position:
            return
        # the position is right
        if simple.start_pos <= self.user_position <= simple.end_pos:
            if self.user_stmt is not None:
                # if there is already a user position (another import, because
                # imports are splitted) the names are checked.
                for n in simple.get_set_vars():
                    if n.start_pos < self.user_position <= n.end_pos:
                        self.user_stmt = simple
            else:
                self.user_stmt = simple

    def _parse_dot_name(self, pre_used_token=None):
        """
        The dot name parser parses a name, variable or function and returns
        their names.

        :return: Tuple of Name, token_type, nexttoken.
        :rtype: tuple(Name, int, str)
        """
        def append(el):
            names.append(el)
            self.module.temp_used_names.append(el[0])

        names = []
        if pre_used_token is None:
            token_type, tok = self.next()
            if token_type != tokenize.NAME and tok != '*':
                return [], token_type, tok
        else:
            token_type, tok = pre_used_token

        if token_type != tokenize.NAME and tok != '*':
            # token maybe a name or star
            return None, token_type, tok

        append((tok, self.start_pos))
        first_pos = self.start_pos
        while True:
            end_pos = self.end_pos
            token_type, tok = self.next()
            if tok != '.':
                break
            token_type, tok = self.next()
            if token_type != tokenize.NAME:
                break
            append((tok, self.start_pos))

        n = pr.Name(self.module, names, first_pos, end_pos) if names else None
        return n, token_type, tok

    def _parse_import_list(self):
        """
        The parser for the imports. Unlike the class and function parse
        function, this returns no Import class, but rather an import list,
        which is then added later on.
        The reason, why this is not done in the same class lies in the nature
        of imports. There are two ways to write them:

        - from ... import ...
        - import ...

        To distinguish, this has to be processed after the parser.

        :return: List of imports.
        :rtype: list
        """
        imports = []
        brackets = False
        continue_kw = [",", ";", "\n", ')'] \
            + list(set(keyword.kwlist) - set(['as']))
        while True:
            defunct = False
            token_type, tok = self.next()
            if tok == '(':  # python allows only one `(` in the statement.
                brackets = True
                token_type, tok = self.next()
            if brackets and tok == '\n':
                self.next()
            i, token_type, tok = self._parse_dot_name(self._current)
            if not i:
                defunct = True
            name2 = None
            if tok == 'as':
                name2, token_type, tok = self._parse_dot_name()
            imports.append((i, name2, defunct))
            while tok not in continue_kw:
                token_type, tok = self.next()
            if not (tok == "," or brackets and tok == '\n'):
                break
        return imports

    def _parse_parentheses(self):
        """
        Functions and Classes have params (which means for classes
        super-classes). They are parsed here and returned as Statements.

        :return: List of Statements
        :rtype: list
        """
        names = []
        tok = None
        pos = 0
        breaks = [',', ':']
        while tok not in [')', ':']:
            param, tok = self._parse_statement(added_breaks=breaks,
                                               stmt_class=pr.Param)
            if param and tok == ':':
                # parse annotations
                annotation, tok = self._parse_statement(added_breaks=breaks)
                if annotation:
                    param.add_annotation(annotation)

            # params without vars are usually syntax errors.
            if param and (param.set_vars or param.used_vars):
                param.position_nr = pos
                names.append(param)
                pos += 1

        return names

    def _parse_function(self):
        """
        The parser for a text functions. Process the tokens, which follow a
        function definition.

        :return: Return a Scope representation of the tokens.
        :rtype: Function
        """
        first_pos = self.start_pos
        token_type, fname = self.next()
        if token_type != tokenize.NAME:
            return None

        fname = pr.Name(self.module, [(fname, self.start_pos)], self.start_pos,
                        self.end_pos)

        token_type, open = self.next()
        if open != '(':
            return None
        params = self._parse_parentheses()

        token_type, colon = self.next()
        annotation = None
        if colon in ['-', '->']:
            # parse annotations
            if colon == '-':
                # The Python 2 tokenizer doesn't understand this
                token_type, colon = self.next()
                if colon != '>':
                    return None
            annotation, colon = self._parse_statement(added_breaks=[':'])

        if colon != ':':
            return None

        # because of 2 line func param definitions
        scope = pr.Function(self.module, fname, params, first_pos, annotation)
        if self.user_scope and scope != self.user_scope \
                and self.user_position > first_pos:
            self.user_scope = scope
        return scope

    def _parse_class(self):
        """
        The parser for a text class. Process the tokens, which follow a
        class definition.

        :return: Return a Scope representation of the tokens.
        :rtype: Class
        """
        first_pos = self.start_pos
        token_type, cname = self.next()
        if token_type != tokenize.NAME:
            debug.warning("class: syntax err, token is not a name@%s (%s: %s)"
                          % (self.start_pos[0], tokenize.tok_name[token_type], cname))
            return None

        cname = pr.Name(self.module, [(cname, self.start_pos)], self.start_pos,
                        self.end_pos)

        super = []
        token_type, _next = self.next()
        if _next == '(':
            super = self._parse_parentheses()
            token_type, _next = self.next()

        if _next != ':':
            debug.warning("class syntax: %s@%s" % (cname, self.start_pos[0]))
            return None

        # because of 2 line class initializations
        scope = pr.Class(self.module, cname, super, first_pos)
        if self.user_scope and scope != self.user_scope \
                and self.user_position > first_pos:
            self.user_scope = scope
        return scope

    def _parse_statement(self, pre_used_token=None, added_breaks=None,
                         stmt_class=pr.Statement):
        """
        Parses statements like::

            a = test(b)
            a += 3 - 2 or b

        and so on. One line at a time.

        :param pre_used_token: The pre parsed token.
        :type pre_used_token: set
        :return: Statement + last parsed token.
        :rtype: (Statement, str)
        """
        set_vars = []
        used_vars = []
        level = 0  # The level of parentheses

        if pre_used_token:
            token_type, tok = pre_used_token
        else:
            token_type, tok = self.next()

        while token_type == tokenize.COMMENT:
            # remove newline and comment
            self.next()
            token_type, tok = self.next()

        first_pos = self.start_pos
        opening_brackets = ['{', '(', '[']
        closing_brackets = ['}', ')', ']']

        # the difference between "break" and "always break" is that the latter
        # will even break in parentheses. This is true for typical flow
        # commands like def and class and the imports, which will never be used
        # in a statement.
        breaks = set(['\n', ':', ')'])
        always_break = [';', 'import', 'from', 'class', 'def', 'try', 'except',
                        'finally', 'while', 'return', 'yield']
        not_first_break = ['del', 'raise']
        if added_breaks:
            breaks |= set(added_breaks)

        tok_list = []
        while not (tok in always_break
                   or tok in not_first_break and not tok_list
                   or tok in breaks and level <= 0):
            try:
                # print 'parse_stmt', tok, tokenize.tok_name[token_type]
                tok_list.append(self._current + (self.start_pos,))
                if tok == 'as':
                    token_type, tok = self.next()
                    if token_type == tokenize.NAME:
                        n, token_type, tok = self._parse_dot_name(self._current)
                        if n:
                            set_vars.append(n)
                        tok_list.append(n)
                    continue
                elif tok in ['lambda', 'for', 'in']:
                    # don't parse these keywords, parse later in stmt.
                    if tok == 'lambda':
                        breaks.discard(':')
                elif token_type == tokenize.NAME:
                    n, token_type, tok = self._parse_dot_name(self._current)
                    # removed last entry, because we add Name
                    tok_list.pop()
                    if n:
                        tok_list.append(n)
                        used_vars.append(n)
                    continue
                elif tok.endswith('=') and tok not in ['>=', '<=', '==', '!=']:
                    # there has been an assignement -> change vars
                    if level == 0:
                        set_vars += used_vars
                        used_vars = []
                elif tok in opening_brackets:
                    level += 1
                elif tok in closing_brackets:
                    level -= 1

                token_type, tok = self.next()
            except (StopIteration, common.MultiLevelStopIteration):
                # comes from tokenizer
                break

        if not tok_list:
            return None, tok
        # print 'new_stat', set_vars, used_vars
        if self.freshscope and not self.no_docstr and len(tok_list) == 1 \
                and self.last_token[0] == tokenize.STRING:
            self._scope.add_docstr(self.last_token[1])
            return None, tok
        else:
            stmt = stmt_class(self.module, set_vars, used_vars, tok_list,
                              first_pos, self.end_pos)

            stmt.parent = self.top_module
            self._check_user_stmt(stmt)

        # Attribute docstring (PEP 224) support (sphinx uses it, e.g.)
        with common.ignored(IndexError, AttributeError):
            # If string literal is being parsed
            first_tok = stmt.token_list[0]
            if (not stmt.set_vars
                    and not stmt.used_vars
                    and len(stmt.token_list) == 1
                    and first_tok[0] == tokenize.STRING):
                # ... then set it as a docstring
                self._scope.statements[-1].add_docstr(first_tok[1])

        if tok in always_break + not_first_break:
            self._gen.push_last_back()
        return stmt, tok

    def next(self):
        return self.__next__()

    def __iter__(self):
        return self

    def __next__(self):
        """ Generate the next tokenize pattern. """
        try:
            typ, tok, start_pos, end_pos, self.parserline = next(self._gen)
            # dedents shouldn't change positions
            if typ != tokenize.DEDENT:
                self.start_pos = start_pos
                if typ not in (tokenize.INDENT, tokenize.NEWLINE, tokenize.NL):
                    self.start_pos, self.end_pos = start_pos, end_pos
        except (StopIteration, common.MultiLevelStopIteration):
            # on finish, set end_pos correctly
            s = self._scope
            while s is not None:
                if isinstance(s, pr.Module) \
                        and not isinstance(s, pr.SubModule):
                    self.module.end_pos = self.end_pos
                    break
                s.end_pos = self.end_pos
                s = s.parent
            raise

        if self.user_position and (self.start_pos[0] == self.user_position[0]
                                   or self.user_scope is None
                                   and self.start_pos[0] >= self.user_position[0]):
            debug.dbg('user scope found [%s] = %s' %
                     (self.parserline.replace('\n', ''), repr(self._scope)))
            self.user_scope = self._scope
        self.last_token = self._current
        self._current = (typ, tok)
        return self._current

    def _parse(self):
        """
        The main part of the program. It analyzes the given code-text and
        returns a tree-like scope. For a more detailed description, see the
        class description.

        :param text: The code which should be parsed.
        :param type: str

        :raises: IndentationError
        """
        extended_flow = ['else', 'elif', 'except', 'finally']
        statement_toks = ['{', '[', '(', '`']

        self._decorators = []
        self.freshscope = True
        self.iterator = iter(self)
        # This iterator stuff is not intentional. It grew historically.
        for token_type, tok in self.iterator:
            self.module.temp_used_names = []
            # debug.dbg('main: tok=[%s] type=[%s] indent=[%s]'\
            #    % (tok, tokenize.tok_name[token_type], start_position[0]))

            while token_type == tokenize.DEDENT and self._scope != self.module:
                token_type, tok = self.next()
                if self.start_pos[1] <= self._scope.start_pos[1]:
                    self._scope.end_pos = self.start_pos
                    self._scope = self._scope.parent
                    if isinstance(self._scope, pr.Module) \
                            and not isinstance(self._scope, pr.SubModule):
                        self._scope = self.module

            # check again for unindented stuff. this is true for syntax
            # errors. only check for names, because thats relevant here. If
            # some docstrings are not indented, I don't care.
            while self.start_pos[1] <= self._scope.start_pos[1] \
                    and (token_type == tokenize.NAME or tok in ['(', '['])\
                    and self._scope != self.module:
                self._scope.end_pos = self.start_pos
                self._scope = self._scope.parent
                if isinstance(self._scope, pr.Module) \
                        and not isinstance(self._scope, pr.SubModule):
                    self._scope = self.module

            use_as_parent_scope = self.top_module if isinstance(self._scope,
                                                                pr.SubModule) else self._scope
            first_pos = self.start_pos
            if tok == 'def':
                func = self._parse_function()
                if func is None:
                    debug.warning("function: syntax error@%s" %
                                  self.start_pos[0])
                    continue
                self.freshscope = True
                self._scope = self._scope.add_scope(func, self._decorators)
                self._decorators = []
            elif tok == 'class':
                cls = self._parse_class()
                if cls is None:
                    debug.warning("class: syntax error@%s" % self.start_pos[0])
                    continue
                self.freshscope = True
                self._scope = self._scope.add_scope(cls, self._decorators)
                self._decorators = []
            # import stuff
            elif tok == 'import':
                imports = self._parse_import_list()
                for count, (m, alias, defunct) in enumerate(imports):
                    e = (alias or m or self).end_pos
                    end_pos = self.end_pos if count + 1 == len(imports) else e
                    i = pr.Import(self.module, first_pos, end_pos, m,
                                  alias, defunct=defunct)
                    self._check_user_stmt(i)
                    self._scope.add_import(i)
                if not imports:
                    i = pr.Import(self.module, first_pos, self.end_pos, None,
                                  defunct=True)
                    self._check_user_stmt(i)
                self.freshscope = False
            elif tok == 'from':
                defunct = False
                # take care for relative imports
                relative_count = 0
                while True:
                    token_type, tok = self.next()
                    if tok != '.':
                        break
                    relative_count += 1
                # the from import
                mod, token_type, tok = self._parse_dot_name(self._current)
                if str(mod) == 'import' and relative_count:
                    self._gen.push_last_back()
                    tok = 'import'
                    mod = None
                if not mod and not relative_count or tok != "import":
                    debug.warning("from: syntax error@%s" % self.start_pos[0])
                    defunct = True
                    if tok != 'import':
                        self._gen.push_last_back()
                names = self._parse_import_list()
                for count, (name, alias, defunct2) in enumerate(names):
                    star = name is not None and name.names[0] == '*'
                    if star:
                        name = None
                    e = (alias or name or self).end_pos
                    end_pos = self.end_pos if count + 1 == len(names) else e
                    i = pr.Import(self.module, first_pos, end_pos, name,
                                  alias, mod, star, relative_count,
                                  defunct=defunct or defunct2)
                    self._check_user_stmt(i)
                    self._scope.add_import(i)
                self.freshscope = False
            # loops
            elif tok == 'for':
                set_stmt, tok = self._parse_statement(added_breaks=['in'])
                if tok == 'in':
                    statement, tok = self._parse_statement()
                    if tok == ':':
                        s = [] if statement is None else [statement]
                        f = pr.ForFlow(self.module, s, first_pos, set_stmt)
                        self._scope = self._scope.add_statement(f)
                    else:
                        debug.warning('syntax err, for flow started @%s',
                                      self.start_pos[0])
                        if statement is not None:
                            statement.parent = use_as_parent_scope
                        if set_stmt is not None:
                            set_stmt.parent = use_as_parent_scope
                else:
                    debug.warning('syntax err, for flow incomplete @%s',
                                  self.start_pos[0])
                    if set_stmt is not None:
                        set_stmt.parent = use_as_parent_scope

            elif tok in ['if', 'while', 'try', 'with'] + extended_flow:
                added_breaks = []
                command = tok
                if command in ['except', 'with']:
                    added_breaks.append(',')
                # multiple inputs because of with
                inputs = []
                first = True
                while first or command == 'with' \
                        and tok not in [':', '\n']:
                    statement, tok = \
                        self._parse_statement(added_breaks=added_breaks)
                    if command == 'except' and tok in added_breaks:
                        # the except statement defines a var
                        # this is only true for python 2
                        n, token_type, tok = self._parse_dot_name()
                        if n:
                            n.parent = statement
                            statement.set_vars.append(n)
                    if statement:
                        inputs.append(statement)
                    first = False

                if tok == ':':
                    f = pr.Flow(self.module, command, inputs, first_pos)
                    if command in extended_flow:
                        # the last statement has to be another part of
                        # the flow statement, because a dedent releases the
                        # main scope, so just take the last statement.
                        try:
                            s = self._scope.statements[-1].set_next(f)
                        except (AttributeError, IndexError):
                            # If set_next doesn't exist, just add it.
                            s = self._scope.add_statement(f)
                    else:
                        s = self._scope.add_statement(f)
                    self._scope = s
                else:
                    for i in inputs:
                        i.parent = use_as_parent_scope
                    debug.warning('syntax err, flow started @%s',
                                  self.start_pos[0])
            # returns
            elif tok in ['return', 'yield']:
                s = self.start_pos
                self.freshscope = False
                # add returns to the scope
                func = self._scope.get_parent_until(pr.Function)
                if tok == 'yield':
                    func.is_generator = True

                stmt, tok = self._parse_statement()
                if stmt is not None:
                    stmt.parent = use_as_parent_scope
                try:
                    func.returns.append(stmt)
                    # start_pos is the one of the return statement
                    stmt.start_pos = s
                except AttributeError:
                    debug.warning('return in non-function')
            # globals
            elif tok == 'global':
                stmt, tok = self._parse_statement(self._current)
                if stmt:
                    self._scope.add_statement(stmt)
                    for name in stmt.used_vars:
                        # add the global to the top, because there it is
                        # important.
                        self.module.add_global(name)
            # decorator
            elif tok == '@':
                stmt, tok = self._parse_statement()
                if stmt is not None:
                    self._decorators.append(stmt)
            elif tok == 'pass':
                continue
            elif tok == 'assert':
                stmt, tok = self._parse_statement()
                if stmt is not None:
                    stmt.parent = use_as_parent_scope
                    self._scope.asserts.append(stmt)
            # default
            elif token_type in [tokenize.NAME, tokenize.STRING,
                                tokenize.NUMBER] \
                    or tok in statement_toks:
                # this is the main part - a name can be a function or a
                # normal var, which can follow anything. but this is done
                # by the statement parser.
                stmt, tok = self._parse_statement(self._current)
                if stmt:
                    self._scope.add_statement(stmt)
                self.freshscope = False
            else:
                if token_type not in [tokenize.COMMENT, tokenize.INDENT,
                                      tokenize.NEWLINE, tokenize.NL]:
                    debug.warning('token not classified', tok, token_type,
                                  self.start_pos[0])
                continue
            self.no_docstr = False
