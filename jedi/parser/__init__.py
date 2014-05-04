"""
The ``Parser`` tries to convert the available Python code in an easy to read
format, something like an abstract syntax tree. The classes who represent this
tree, are sitting in the :mod:`jedi.parser.representation` module.

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
import keyword

from jedi._compatibility import next, unicode
from jedi import debug
from jedi import common
from jedi.parser import representation as pr
from jedi.parser import tokenize

OPERATOR_KEYWORDS = 'and', 'for', 'if', 'else', 'in', 'is', 'lambda', 'not', 'or'
# Not used yet. In the future I intend to add something like KeywordStatement
STATEMENT_KEYWORDS = 'assert', 'del', 'global', 'nonlocal', 'raise', \
    'return', 'yield', 'pass', 'continue', 'break'


class Parser(object):
    """
    This class is used to parse a Python file, it then divides them into a
    class structure of different scopes.

    :param source: The codebase for the parser.
    :type source: str
    :param module_path: The path of the module in the file system, may be None.
    :type module_path: str
    :param no_docstr: If True, a string at the beginning is not a docstr.
    :param top_module: Use this module as a parent instead of `self.module`.
    """
    def __init__(self, source, module_path=None, no_docstr=False,
                 tokenizer=None, top_module=None):
        self.no_docstr = no_docstr

        tokenizer = tokenizer or tokenize.source_tokens(source)
        self._gen = PushBackTokenizer(tokenizer)

        # initialize global Scope
        start_pos = next(self._gen).start_pos
        self._gen.push_last_back()
        self.module = pr.SubModule(module_path, start_pos, top_module)
        self._scope = self.module
        self._top_module = top_module or self.module

        try:
            self._parse()
        except (common.MultiLevelStopIteration, StopIteration):
            # StopIteration needs to be added as well, because python 2 has a
            # strange way of handling StopIterations.
            # sometimes StopIteration isn't catched. Just ignore it.

            # on finish, set end_pos correctly
            pass
        s = self._scope
        while s is not None:
            s.end_pos = self._gen.current.end_pos
            s = s.parent

        # clean up unused decorators
        for d in self._decorators:
            # set a parent for unused decorators, avoid NullPointerException
            # because of `self.module.used_names`.
            d.parent = self.module

        self.module.end_pos = self._gen.current.end_pos
        if self._gen.current.type in (tokenize.NEWLINE,):
            # This case is only relevant with the FastTokenizer, because
            # otherwise there's always an EndMarker.
            # we added a newline before, so we need to "remove" it again.
            self.module.end_pos = self._gen.tokenizer_previous.end_pos

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

    def _parse_dot_name(self, pre_used_token=None):
        """
        The dot name parser parses a name, variable or function and returns
        their names.

        :return: tuple of Name, next_token
        """
        def append(el):
            names.append(el)
            self.module.temp_used_names.append(el[0])

        names = []
        tok = next(self._gen) if pre_used_token is None else pre_used_token

        if tok.type != tokenize.NAME and tok.string != '*':
            return None, tok

        first_pos = tok.start_pos
        append((tok.string, first_pos))
        while True:
            end_pos = tok.end_pos
            tok = next(self._gen)
            if tok.string != '.':
                break
            tok = next(self._gen)
            if tok.type != tokenize.NAME:
                break
            append((tok.string, tok.start_pos))

        n = pr.Name(self.module, names, first_pos, end_pos) if names else None
        return n, tok

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
        continue_kw = [",", ";", "\n", '\r\n', ')'] \
            + list(set(keyword.kwlist) - set(['as']))
        while True:
            defunct = False
            tok = next(self._gen)
            if tok.string == '(':  # python allows only one `(` in the statement.
                brackets = True
                tok = next(self._gen)
            if brackets and tok.type == tokenize.NEWLINE:
                tok = next(self._gen)
            i, tok = self._parse_dot_name(tok)
            if not i:
                defunct = True
            name2 = None
            if tok.string == 'as':
                name2, tok = self._parse_dot_name()
            imports.append((i, name2, defunct))
            while tok.string not in continue_kw:
                tok = next(self._gen)
            if not (tok.string == "," or brackets and tok.type == tokenize.NEWLINE):
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
        while tok is None or tok.string not in (')', ':'):
            param, tok = self._parse_statement(added_breaks=breaks,
                                               stmt_class=pr.Param)
            if param and tok.string == ':':
                # parse annotations
                annotation, tok = self._parse_statement(added_breaks=breaks)
                if annotation:
                    param.add_annotation(annotation)

            # params without vars are usually syntax errors.
            if param and (param.get_defined_names()):
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
        first_pos = self._gen.current.start_pos
        tok = next(self._gen)
        if tok.type != tokenize.NAME:
            return None

        fname = pr.Name(self.module, [(tok.string, tok.start_pos)], tok.start_pos,
                        tok.end_pos)

        tok = next(self._gen)
        if tok.string != '(':
            return None
        params = self._parse_parentheses()

        colon = next(self._gen)
        annotation = None
        if colon.string in ('-', '->'):
            # parse annotations
            if colon.string == '-':
                # The Python 2 tokenizer doesn't understand this
                colon = next(self._gen)
                if colon.string != '>':
                    return None
            annotation, colon = self._parse_statement(added_breaks=[':'])

        if colon.string != ':':
            return None

        # because of 2 line func param definitions
        return pr.Function(self.module, fname, params, first_pos, annotation)

    def _parse_class(self):
        """
        The parser for a text class. Process the tokens, which follow a
        class definition.

        :return: Return a Scope representation of the tokens.
        :rtype: Class
        """
        first_pos = self._gen.current.start_pos
        cname = next(self._gen)
        if cname.type != tokenize.NAME:
            debug.warning("class: syntax err, token is not a name@%s (%s: %s)",
                          cname.start_pos[0], tokenize.tok_name[cname.type], cname.string)
            return None

        cname = pr.Name(self.module, [(cname.string, cname.start_pos)],
                        cname.start_pos, cname.end_pos)

        super = []
        _next = next(self._gen)
        if _next.string == '(':
            super = self._parse_parentheses()
            _next = next(self._gen)

        if _next.string != ':':
            debug.warning("class syntax: %s@%s", cname, _next.start_pos[0])
            return None

        return pr.Class(self.module, cname, super, first_pos)

    def _parse_statement(self, pre_used_token=None, added_breaks=None,
                         stmt_class=pr.Statement, names_are_set_vars=False):
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
        level = 0  # The level of parentheses

        if pre_used_token:
            tok = pre_used_token
        else:
            tok = next(self._gen)

        while tok.type == tokenize.COMMENT:
            # remove newline and comment
            next(self._gen)
            tok = next(self._gen)

        first_pos = tok.start_pos
        opening_brackets = ['{', '(', '[']
        closing_brackets = ['}', ')', ']']

        # the difference between "break" and "always break" is that the latter
        # will even break in parentheses. This is true for typical flow
        # commands like def and class and the imports, which will never be used
        # in a statement.
        breaks = set(['\n', '\r\n', ':', ')'])
        always_break = [';', 'import', 'from', 'class', 'def', 'try', 'except',
                        'finally', 'while', 'return', 'yield']
        not_first_break = ['del', 'raise']
        if added_breaks:
            breaks |= set(added_breaks)

        tok_list = []
        as_names = []
        in_lambda_param = False
        while not (tok.string in always_break
                   or tok.string in not_first_break and not tok_list
                   or tok.string in breaks and level <= 0
                   and not (in_lambda_param and tok.string in ',:')):
            try:
                # print 'parse_stmt', tok, tokenize.tok_name[token_type]
                is_kw = tok.string in OPERATOR_KEYWORDS
                if tok.type == tokenize.OP or is_kw:
                    tok_list.append(pr.Operator(tok.string, tok.start_pos))
                else:
                    tok_list.append(tok)

                if tok.string == 'as':
                    tok = next(self._gen)
                    if tok.type == tokenize.NAME:
                        n, tok = self._parse_dot_name(self._gen.current)
                        if n:
                            set_vars.append(n)
                            as_names.append(n)
                        tok_list.append(n)
                    continue
                elif tok.string == 'lambda':
                    breaks.discard(':')
                    in_lambda_param = True
                elif in_lambda_param and tok.string == ':':
                    in_lambda_param = False
                elif tok.type == tokenize.NAME and not is_kw:
                    n, tok = self._parse_dot_name(self._gen.current)
                    # removed last entry, because we add Name
                    tok_list.pop()
                    if n:
                        tok_list.append(n)
                    continue
                elif tok.string in opening_brackets:
                    level += 1
                elif tok.string in closing_brackets:
                    level -= 1

                tok = next(self._gen)
            except (StopIteration, common.MultiLevelStopIteration):
                # comes from tokenizer
                break

        if not tok_list:
            return None, tok

        first_tok = tok_list[0]
        # docstrings
        if len(tok_list) == 1 and isinstance(first_tok, tokenize.Token) \
                and first_tok.type == tokenize.STRING:
            # Normal docstring check
            if self.freshscope and not self.no_docstr:
                self._scope.add_docstr(first_tok)
                return None, tok

            # Attribute docstring (PEP 224) support (sphinx uses it, e.g.)
            # If string literal is being parsed...
            elif first_tok.type == tokenize.STRING:
                with common.ignored(IndexError, AttributeError):
                    # ...then set it as a docstring
                    self._scope.statements[-1].add_docstr(first_tok)
                    return None, tok

        stmt = stmt_class(self.module, tok_list, first_pos, tok.end_pos,
                          as_names=as_names,
                          names_are_set_vars=names_are_set_vars)

        stmt.parent = self._top_module
        self._check_user_stmt(stmt)

        if tok.string in always_break + not_first_break:
            self._gen.push_last_back()
        return stmt, tok

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
        for tok in self._gen:
            token_type = tok.type
            tok_str = tok.string
            first_pos = tok.start_pos
            self.module.temp_used_names = []
            # debug.dbg('main: tok=[%s] type=[%s] indent=[%s]', \
            #           tok, tokenize.tok_name[token_type], start_position[0])

            # check again for unindented stuff. this is true for syntax
            # errors. only check for names, because thats relevant here. If
            # some docstrings are not indented, I don't care.
            while first_pos[1] <= self._scope.start_pos[1] \
                    and (token_type == tokenize.NAME or tok_str in ('(', '['))\
                    and self._scope != self.module:
                self._scope.end_pos = first_pos
                self._scope = self._scope.parent
                if isinstance(self._scope, pr.Module) \
                        and not isinstance(self._scope, pr.SubModule):
                    self._scope = self.module

            if isinstance(self._scope, pr.SubModule):
                use_as_parent_scope = self._top_module
            else:
                use_as_parent_scope = self._scope
            if tok_str == 'def':
                func = self._parse_function()
                if func is None:
                    debug.warning("function: syntax error@%s", first_pos[0])
                    continue
                self.freshscope = True
                self._scope = self._scope.add_scope(func, self._decorators)
                self._decorators = []
            elif tok_str == 'class':
                cls = self._parse_class()
                if cls is None:
                    debug.warning("class: syntax error@%s" % first_pos[0])
                    continue
                self.freshscope = True
                self._scope = self._scope.add_scope(cls, self._decorators)
                self._decorators = []
            # import stuff
            elif tok_str == 'import':
                imports = self._parse_import_list()
                for count, (m, alias, defunct) in enumerate(imports):
                    e = (alias or m or self._gen.previous).end_pos
                    end_pos = self._gen.previous.end_pos if count + 1 == len(imports) else e
                    i = pr.Import(self.module, first_pos, end_pos, m,
                                  alias, defunct=defunct)
                    self._check_user_stmt(i)
                    self._scope.add_import(i)
                if not imports:
                    i = pr.Import(self.module, first_pos, self._gen.current.end_pos,
                                  None, defunct=True)
                    self._check_user_stmt(i)
                self.freshscope = False
            elif tok_str == 'from':
                defunct = False
                # take care for relative imports
                relative_count = 0
                while True:
                    tok = next(self._gen)
                    if tok.string != '.':
                        break
                    relative_count += 1
                # the from import
                mod, tok = self._parse_dot_name(self._gen.current)
                tok_str = tok.string
                if str(mod) == 'import' and relative_count:
                    self._gen.push_last_back()
                    tok_str = 'import'
                    mod = None
                if not mod and not relative_count or tok_str != "import":
                    debug.warning("from: syntax error@%s", tok.start_pos[0])
                    defunct = True
                    if tok_str != 'import':
                        self._gen.push_last_back()
                names = self._parse_import_list()
                for count, (name, alias, defunct2) in enumerate(names):
                    star = name is not None and unicode(name.names[0]) == '*'
                    if star:
                        name = None
                    e = (alias or name or self._gen.previous).end_pos
                    end_pos = self._gen.previous.end_pos if count + 1 == len(names) else e
                    i = pr.Import(self.module, first_pos, end_pos, name,
                                  alias, mod, star, relative_count,
                                  defunct=defunct or defunct2)
                    self._check_user_stmt(i)
                    self._scope.add_import(i)
                self.freshscope = False
            # loops
            elif tok_str == 'for':
                set_stmt, tok = self._parse_statement(added_breaks=['in'],
                                                      names_are_set_vars=True)
                if tok.string != 'in':
                    debug.warning('syntax err, for flow incomplete @%s', tok.start_pos[0])

                try:
                    statement, tok = self._parse_statement()
                except StopIteration:
                    statement, tok = None, None
                s = [] if statement is None else [statement]
                f = pr.ForFlow(self.module, s, first_pos, set_stmt)
                self._scope = self._scope.add_statement(f)
                if tok is None or tok.string != ':':
                    debug.warning('syntax err, for flow started @%s', first_pos[0])
            elif tok_str in ['if', 'while', 'try', 'with'] + extended_flow:
                added_breaks = []
                command = tok_str
                if command in ('except', 'with'):
                    added_breaks.append(',')
                # multiple inputs because of with
                inputs = []
                first = True
                while first or command == 'with' and tok.string not in (':', '\n', '\r\n'):
                    statement, tok = \
                        self._parse_statement(added_breaks=added_breaks)
                    if command == 'except' and tok.string == ',':
                        # the except statement defines a var
                        # this is only true for python 2
                        n, tok = self._parse_dot_name()
                        if n:
                            n.parent = statement
                            statement.as_names.append(n)
                    if statement:
                        inputs.append(statement)
                    first = False

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
                if tok.string != ':':
                    debug.warning('syntax err, flow started @%s', tok.start_pos[0])
            # returns
            elif tok_str in ('return', 'yield'):
                s = tok.start_pos
                self.freshscope = False
                # add returns to the scope
                func = self._scope.get_parent_until(pr.Function)
                if tok_str == 'yield':
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
            elif tok_str == 'assert':
                stmt, tok = self._parse_statement()
                if stmt is not None:
                    stmt.parent = use_as_parent_scope
                    self._scope.asserts.append(stmt)
            elif tok_str in STATEMENT_KEYWORDS:
                stmt, _ = self._parse_statement()
                kw = pr.KeywordStatement(tok_str, tok.start_pos,
                                         use_as_parent_scope, stmt)
                self._scope.add_statement(kw)
                if stmt is not None and tok_str == 'global':
                    for t in stmt._token_list:
                        if isinstance(t, pr.Name):
                            # Add the global to the top module, it counts there.
                            self.module.add_global(t)
            # decorator
            elif tok_str == '@':
                stmt, tok = self._parse_statement()
                if stmt is not None:
                    self._decorators.append(stmt)
            elif tok_str == 'pass':
                continue
            # default
            elif token_type in (tokenize.NAME, tokenize.STRING,
                                tokenize.NUMBER, tokenize.OP) \
                    or tok_str in statement_toks:
                # this is the main part - a name can be a function or a
                # normal var, which can follow anything. but this is done
                # by the statement parser.
                stmt, tok = self._parse_statement(self._gen.current)
                if stmt:
                    self._scope.add_statement(stmt)
                self.freshscope = False
            else:
                if token_type not in (tokenize.COMMENT, tokenize.NEWLINE, tokenize.ENDMARKER):
                    debug.warning('Token not used: %s %s %s', tok_str,
                                  tokenize.tok_name[token_type], first_pos)
                continue
            self.no_docstr = False


class PushBackTokenizer(object):
    def __init__(self, tokenizer):
        self._tokenizer = tokenizer
        self._push_backs = []
        self.current = self.previous = tokenize.Token(None, '', (0, 0))

    def push_last_back(self):
        self._push_backs.append(self.current)

    def next(self):
        """ Python 2 Compatibility """
        return self.__next__()

    def __next__(self):
        if self._push_backs:
            return self._push_backs.pop(0)

        self.previous = self.current
        self.current = next(self._tokenizer)
        return self.current

    def __iter__(self):
        return self

    @property
    def tokenizer_previous(self):
        """
        Temporary hack, basically returns the last previous if the fast parser
        sees an EndMarker. The fast parser positions have to be changed anyway.
        """
        return self._tokenizer.previous
