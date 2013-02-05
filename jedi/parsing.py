"""
This module is split in two parts:

- the Python parser itself
- classes for the parser to save the information

The ``Parser`` tries to represent the available Python code in an easy to read
format. The Python module ``tokenize`` is a very important part in the
``Parser``, because it splits the code into different words (tokens).
Sometimes it looks a bit messy. Sorry for that! You might ask now: "Why didn't
you use the ``ast`` module for this? Well, ``ast`` does a very good job
understanding proper Python code, but fails to work as soon as there's a single
line of broken code.

The classes are not very hard to understand. They are being named like you
would call them: ``Import``, ``Class``, etc.

A very central class is ``Scope``. It is not used directly by the parser, but
inherited. It's used by ``Function``, ``Class``, ``Flow``, etc. A ``Scope`` may
have ``subscopes``, ``imports`` and ``statements``. The entire parser is based
on scopes, because they also stand for indentation.

There's one important optimization that needs to be known: Statements are not
being parsed completely. ``Statement`` is just a representation of the tokens
within the statement. This lowers memory usage and cpu time and reduces the
complexity of the ``Parser`` (there's another parser sitting inside
``Statement``, which produces ``Array`` and ``Call``).

Another strange thing about the parser is that ``Array`` is two dimensional.
This has been caused by the fact that each array element can be defined by
operations: ``[1, 2+3]``. So I chose to use a second dimension for ``2+3``. In
the future it might be useful to use Statements there, too. This is also how
``Param`` works. Every single ``Param`` is a ``Statement``.


.. todo:: remove docstr params from Scope.__init__()
"""
from _compatibility import next, StringIO, unicode

import tokenize
import re
import keyword

import debug
import common
import parsing_representation as pr


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
    :param stop_on_scope: Stop if a scope appears -> for fast_parser
    :param top_module: Use this module as a parent instead of `self.module`.
    """
    def __init__(self, source, module_path=None, user_position=None,
                        no_docstr=False, line_offset=0, stop_on_scope=None,
                        top_module=None):
        self.user_position = user_position
        self.user_scope = None
        self.user_stmt = None
        self.no_docstr = no_docstr

        # initialize global Scope
        self.module = pr.SubModule(module_path, (line_offset + 1, 0),
                                                            top_module)
        self.scope = self.module
        self.current = (None, None)
        self.start_pos = 1, 0
        self.end_pos = 1, 0

        # Stuff to fix tokenize errors. The parser is pretty good in tolerating
        # any errors of tokenize and just parse ahead.
        self._line_offset = line_offset

        source = source + '\n'  # end with \n, because the parser needs it
        buf = StringIO(source)
        self._gen = common.NoErrorTokenizer(buf.readline, line_offset,
                                                            stop_on_scope)
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
            token_type, tok = self.next()
            if tok != '.':
                break
            token_type, tok = self.next()
            if token_type != tokenize.NAME:
                break
            append((tok, self.start_pos))

        n = pr.Name(self.module, names, first_pos, self.end_pos) if names \
                                                                else None
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
            if token_type == tokenize.ENDMARKER:
                break
            if brackets and tok == '\n':
                self.next()
            if tok == '(':  # python allows only one `(` in the statement.
                brackets = True
                self.next()
            i, token_type, tok = self._parse_dot_name(self.current)
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
        token_type, next = self.next()
        if next == '(':
            super = self._parse_parentheses()
            token_type, next = self.next()

        if next != ':':
            debug.warning("class syntax: %s@%s" % (cname, self.start_pos[0]))
            return None

        # because of 2 line class initializations
        scope = pr.Class(self.module, cname, super, first_pos)
        if self.user_scope and scope != self.user_scope \
                        and self.user_position > first_pos:
            self.user_scope = scope
        return scope

    def _parse_statement(self, pre_used_token=None, added_breaks=None,
                            stmt_class=pr.Statement, list_comp=False):
        """
        Parses statements like:

        >>> a = test(b)
        >>> a += 3 - 2 or b

        and so on. One line at a time.

        :param pre_used_token: The pre parsed token.
        :type pre_used_token: set
        :return: Statement + last parsed token.
        :rtype: (Statement, str)
        """

        string = unicode('')
        set_vars = []
        used_funcs = []
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
        breaks = ['\n', ':', ')']
        always_break = [';', 'import', 'from', 'class', 'def', 'try', 'except',
                        'finally', 'while', 'return', 'yield']
        not_first_break = ['del', 'raise']
        if added_breaks:
            breaks += added_breaks

        tok_list = []
        while not (tok in always_break
                or tok in not_first_break and not tok_list
                or tok in breaks and level <= 0):
            try:
                set_string = None
                #print 'parse_stmt', tok, tokenize.tok_name[token_type]
                tok_list.append(self.current + (self.start_pos,))
                if tok == 'as':
                    string += " %s " % tok
                    token_type, tok = self.next()
                    if token_type == tokenize.NAME:
                        n, token_type, tok = self._parse_dot_name(self.current)
                        if n:
                            set_vars.append(n)
                        tok_list.append(n)
                        string += ".".join(n.names)
                    continue
                elif tok == 'lambda':
                    params = []
                    start_pos = self.start_pos
                    while tok != ':':
                        param, tok = self._parse_statement(
                                added_breaks=[':', ','], stmt_class=pr.Param)
                        if param is None:
                            break
                        params.append(param)
                    if tok != ':':
                        continue

                    lambd = pr.Lambda(self.module, params, start_pos)
                    ret, tok = self._parse_statement(added_breaks=[','])
                    if ret is not None:
                        ret.parent = lambd
                        lambd.returns.append(ret)
                    lambd.parent = self.scope
                    lambd.end_pos = self.end_pos
                    tok_list[-1] = lambd
                    continue
                elif token_type == tokenize.NAME:
                    if tok == 'for':
                        # list comprehensions!
                        middle, tok = self._parse_statement(
                                                        added_breaks=['in'])
                        if tok != 'in' or middle is None:
                            if middle is None:
                                level -= 1
                            else:
                                middle.parent = self.scope
                            debug.warning('list comprehension formatting @%s' %
                                                            self.start_pos[0])
                            continue

                        b = [')', ']']
                        in_clause, tok = self._parse_statement(added_breaks=b,
                                                                list_comp=True)
                        if tok not in b or in_clause is None:
                            middle.parent = self.scope
                            if in_clause is None:
                                self._gen.push_last_back()
                            else:
                                in_clause.parent = self.scope
                                in_clause.parent = self.scope
                            debug.warning('list comprehension in_clause %s@%s'
                                            % (repr(tok), self.start_pos[0]))
                            continue
                        other_level = 0

                        for i, tok in enumerate(reversed(tok_list)):
                            if not isinstance(tok, (pr.Name,
                                                    pr.ListComprehension)):
                                tok = tok[1]
                            if tok in closing_brackets:
                                other_level -= 1
                            elif tok in opening_brackets:
                                other_level += 1
                            if other_level > 0:
                                break
                        else:
                            # could not detect brackets -> nested list comp
                            i = 0

                        tok_list, toks = tok_list[:-i], tok_list[-i:-1]
                        src = ''
                        for t in toks:
                            src += t[1] if isinstance(t, tuple) \
                                        else t.get_code()
                        st = pr.Statement(self.module, src, [], [], [],
                                        toks, first_pos, self.end_pos)

                        for s in [st, middle, in_clause]:
                            s.parent = self.scope
                        tok = pr.ListComprehension(st, middle, in_clause)
                        tok_list.append(tok)
                        if list_comp:
                            string = ''
                        string += tok.get_code()
                        continue
                    else:
                        n, token_type, tok = self._parse_dot_name(self.current)
                        # removed last entry, because we add Name
                        tok_list.pop()
                        if n:
                            tok_list.append(n)
                            if tok == '(':
                                # it must be a function
                                used_funcs.append(n)
                            else:
                                used_vars.append(n)
                            if string and re.match(r'[\w\d\'"]', string[-1]):
                                string += ' '
                            string += ".".join(n.names)
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

                string = set_string if set_string is not None else string + tok
                token_type, tok = self.next()
            except (StopIteration, common.MultiLevelStopIteration):
                # comes from tokenizer
                break

        if not string:
            return None, tok
        #print 'new_stat', string, set_vars, used_funcs, used_vars
        if self.freshscope and not self.no_docstr and len(tok_list) == 1 \
                    and self.last_token[0] == tokenize.STRING:
            self.scope.add_docstr(self.last_token[1])
            return None, tok
        else:
            stmt = stmt_class(self.module, string, set_vars, used_funcs,
                            used_vars, tok_list, first_pos, self.end_pos)

            self._check_user_stmt(stmt)

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
            typ, tok, self.start_pos, self.end_pos, \
                                self.parserline = next(self._gen)
        except (StopIteration, common.MultiLevelStopIteration):
            # on finish, set end_pos correctly
            s = self.scope
            while s is not None:
                s.end_pos = self.end_pos
                s = s.parent
            raise

        if self.user_position and (self.start_pos[0] == self.user_position[0]
                            or self.user_scope is None
                            and self.start_pos[0] >= self.user_position[0]):
            debug.dbg('user scope found [%s] = %s' % \
                    (self.parserline.replace('\n', ''), repr(self.scope)))
            self.user_scope = self.scope
        self.last_token = self.current
        self.current = (typ, tok)
        return self.current

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
            #debug.dbg('main: tok=[%s] type=[%s] indent=[%s]'\
            #    % (tok, tokenize.tok_name[token_type], start_position[0]))

            while token_type == tokenize.DEDENT and self.scope != self.module:
                token_type, tok = self.next()
                if self.start_pos[1] <= self.scope.start_pos[1]:
                    self.scope.end_pos = self.start_pos
                    self.scope = self.scope.parent
                    if isinstance(self.scope, pr.Module) \
                            and not isinstance(self.scope, pr.SubModule):
                        self.scope = self.module

            # check again for unindented stuff. this is true for syntax
            # errors. only check for names, because thats relevant here. If
            # some docstrings are not indented, I don't care.
            while self.start_pos[1] <= self.scope.start_pos[1] \
                    and (token_type == tokenize.NAME or tok in ['(', '['])\
                    and self.scope != self.module:
                self.scope.end_pos = self.start_pos
                self.scope = self.scope.parent
                if isinstance(self.scope, pr.Module) \
                        and not isinstance(self.scope, pr.SubModule):
                    self.scope = self.module

            use_as_parent_scope = self.top_module if isinstance(self.scope,
                                            pr.SubModule) else self.scope
            first_pos = self.start_pos
            if tok == 'def':
                func = self._parse_function()
                if func is None:
                    debug.warning("function: syntax error@%s" %
                                                        self.start_pos[0])
                    continue
                self.freshscope = True
                self.scope = self.scope.add_scope(func, self._decorators)
                self._decorators = []
            elif tok == 'class':
                cls = self._parse_class()
                if cls is None:
                    debug.warning("class: syntax error@%s" % self.start_pos[0])
                    continue
                self.freshscope = True
                self.scope = self.scope.add_scope(cls, self._decorators)
                self._decorators = []
            # import stuff
            elif tok == 'import':
                imports = self._parse_import_list()
                for m, alias, defunct in imports:
                    i = pr.Import(self.module, first_pos, self.end_pos, m,
                                                alias, defunct=defunct)
                    self._check_user_stmt(i)
                    self.scope.add_import(i)
                if not imports:
                    i = pr.Import(self.module, first_pos, self.end_pos, None,
                                                                defunct=True)
                    self._check_user_stmt(i)
                self.freshscope = False
            elif tok == 'from':
                defunct = False
                # take care for relative imports
                relative_count = 0
                while 1:
                    token_type, tok = self.next()
                    if tok != '.':
                        break
                    relative_count += 1
                # the from import
                mod, token_type, tok = self._parse_dot_name(self.current)
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
                for name, alias, defunct2 in names:
                    star = name is not None and name.names[0] == '*'
                    if star:
                        name = None
                    i = pr.Import(self.module, first_pos, self.end_pos, name,
                                        alias, mod, star, relative_count,
                                        defunct=defunct or defunct2)
                    self._check_user_stmt(i)
                    self.scope.add_import(i)
                self.freshscope = False
            #loops
            elif tok == 'for':
                set_stmt, tok = self._parse_statement(added_breaks=['in'])
                if tok == 'in':
                    statement, tok = self._parse_statement()
                    if tok == ':':
                        s = [] if statement is None else [statement]
                        f = pr.ForFlow(self.module, s, first_pos, set_stmt)
                        self.scope = self.scope.add_statement(f)
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
                # multiple statements because of with
                inits = []
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
                            statement.set_vars.append(n)
                            statement.code += ',' + n.get_code()
                    if statement:
                        inits.append(statement)
                    first = False

                if tok == ':':
                    f = pr.Flow(self.module, command, inits, first_pos)
                    if command in extended_flow:
                        # the last statement has to be another part of
                        # the flow statement, because a dedent releases the
                        # main scope, so just take the last statement.
                        try:
                            s = self.scope.statements[-1].set_next(f)
                        except (AttributeError, IndexError):
                            # If set_next doesn't exist, just add it.
                            s = self.scope.add_statement(f)
                    else:
                        s = self.scope.add_statement(f)
                    self.scope = s
                else:
                    for i in inits:
                        i.parent = use_as_parent_scope
                    debug.warning('syntax err, flow started @%s',
                                                        self.start_pos[0])
            # returns
            elif tok in ['return', 'yield']:
                s = self.start_pos
                self.freshscope = False
                # add returns to the scope
                func = self.scope.get_parent_until(pr.Function)
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
                stmt, tok = self._parse_statement(self.current)
                if stmt:
                    self.scope.add_statement(stmt)
                    for name in stmt.used_vars:
                        # add the global to the top, because there it is
                        # important.
                        self.module.add_global(name)
            # decorator
            elif tok == '@':
                stmt, tok = self._parse_statement()
                self._decorators.append(stmt)
            elif tok == 'pass':
                continue
            elif tok == 'assert':
                stmt, tok = self._parse_statement()
                stmt.parent = use_as_parent_scope
                self.scope.asserts.append(stmt)
            # default
            elif token_type in [tokenize.NAME, tokenize.STRING,
                                tokenize.NUMBER] \
                    or tok in statement_toks:
                # this is the main part - a name can be a function or a
                # normal var, which can follow anything. but this is done
                # by the statement parser.
                stmt, tok = self._parse_statement(self.current)
                if stmt:
                    self.scope.add_statement(stmt)
                self.freshscope = False
            else:
                if token_type not in [tokenize.COMMENT, tokenize.INDENT,
                                      tokenize.NEWLINE, tokenize.NL,
                                      tokenize.ENDMARKER]:
                    debug.warning('token not classified', tok, token_type,
                                                        self.start_pos[0])
