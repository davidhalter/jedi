""""
TODO Description: This is a parser

TODO be tolerant with indents
TODO dictionaries not working with statement parser
TODO except has local vars
TODO take special care for future imports
TODO add global statements

scope
    imports
    subscopes
    statements

Ignored statements:
 - print (no use for it)
 - exec (dangerous - not controllable)

"""
import sys
import tokenize
import cStringIO
import token
import re


def indent_block(text, indention="    "):
    """ This function indents a text block with a default of four spaces """
    temp = ''
    while text and text[-1] == '\n':
        temp += text[-1]
        text = text[:-1]
    lines = text.split('\n')
    return '\n'.join(map(lambda s: indention + s, lines)) + temp


class Scope(object):
    """
    Super class for the parser tree, which represents the state of a python
    text file.
    A Scope manages and owns its subscopes, which are classes and functions, as
    well as variables and imports. It is used to access the structure of python
    files.

    :param name: The name of the current Scope, which could be a class name.
    :type name: string
    :param indent: The indent level of the flow statement.
    :type indent: int
    :param line_nr: Line number of the flow statement.
    :type line_nr: int
    :param docstr: The docstring for the current Scope.
    :type docstr: str
    """
    def __init__(self, name, indent, line_nr, docstr=''):
        self.subscopes = []
        self.imports = []
        self.statements = []
        self.docstr = docstr
        self.parent = None
        self.name = name
        self.indent = indent
        self.line_nr = line_nr

    def add_scope(self, sub):
        # print 'push scope: [%s@%s]' % (sub.name, sub.indent)
        sub.parent = self
        self.subscopes.append(sub)
        return sub

    def add_statement(self, stmt):
        """
        Used to add a Statement or a Scope.
        A statement would be a normal command (Statement) or a Scope (Flow).
        """
        if isinstance(stmt, Scope):
            stmt.parent = self
        self.statements.append(stmt)
        return stmt

    def add_docstr(self, str):
        """ Clean up a docstring """
        d = str.replace('\n', ' ')
        d = d.replace('\t', ' ')
        while d.find('  ') > -1:
            d = d.replace('  ', ' ')
        while d[0] in '"\'\t ':
            d = d[1:]
        while d[-1] in '"\'\t ':
            d = d[:-1]
        dbg("Scope(%s)::docstr = %s" % (self, d))
        self.docstr = d

    def add_import(self, imp):
        self.imports.append(imp)

    def _checkexisting(self, test):
        "Convienance function... keep out duplicates"
        if test.find('=') > -1:
            var = test.split('=')[0].strip()
            for l in self.locals:
                if l.find('=') > -1 and var == l.split('=')[0].strip():
                    self.locals.remove(l)

    def get_code(self, first_indent=False, indention="    "):
        """
        :return: Returns the code of the current scope.
        :rtype: str
        """
        string = ""
        if len(self.docstr) > 0:
            string += '"""' + self.docstr + '"""\n'
        for i in self.imports:
            string += i.get_code()
        for sub in self.subscopes:
            #string += str(sub.line_nr)
            string += sub.get_code(first_indent=True, indention=indention)
        for stmt in self.statements:
            string += stmt.get_code()

        if first_indent:
            string = indent_block(string, indention=indention)
        return string

    def is_empty(self):
        """
        :return: True if there are no subscopes, imports and statements.
        :rtype: bool
        """
        return not (self.imports or self.subscopes or self.statements)


class Class(Scope):
    """
    Used to store the parsed contents of a python class.

    :param name: The Class name.
    :type name: string
    :param name: The super classes of a Class.
    :type name: list
    :param indent: The indent level of the flow statement.
    :type indent: int
    :param line_nr: Line number of the flow statement.
    :type line_nr: int
    :param docstr: The docstring for the current Scope.
    :type docstr: str
    """
    def __init__(self, name, supers, indent, line_nr, docstr=''):
        super(Class, self).__init__(name, indent, line_nr, docstr)
        self.supers = supers

    def get_code(self, first_indent=False, indention="    "):
        str = 'class %s' % (self.name)
        if len(self.supers) > 0:
            str += '(%s)' % ','.join(self.supers)
        str += ':\n'
        str += super(Class, self).get_code(True, indention)
        if self.is_empty():
            str += "pass\n"
        return str


class Flow(Scope):
    """
    Used to describe programming structure - flow statements,
    which indent code, but are not classes or functions:

    - for
    - while
    - if
    - try
    - with

    Therefore statements like else, except and finally are also here,
    they are now saved in the root flow elements, but in the next variable.

    :param command: The flow command, if, while, else, etc.
    :type command: str
    :param statement: The statement after the flow comand -> while 'statement'.
    :type statement: Statement
    :param indent: The indent level of the flow statement.
    :type indent: int
    :param line_nr: Line number of the flow statement.
    :type line_nr: int
    :param set_args: Local variables used in the for loop (only there).
    :type set_args: list
    """
    def __init__(self, command, statement, indent, line_nr, set_args=None):
        name = "%s@%s" % (command, line_nr)
        super(Flow, self).__init__(name, indent, line_nr, '')
        self.command = command
        self.statement = statement
        self.set_args = set_args
        self.next = None

    def get_code(self, first_indent=False, indention="    "):
        if self.set_args:
            args = ",".join(map(lambda x: x.get_code(), self.set_args))
            args += ' in '
        else:
            args = ''

        if self.statement:
            stmt = self.statement.get_code(new_line=False)
        else:
            stmt = ''
        str = "%s %s%s:\n" % (self.command, args, stmt)
        str += super(Flow, self).get_code(True, indention)
        if self.next:
            str += self.next.get_code()
        return str

    def set_next(self, next):
        """ Set the next element in the flow, those are else, except, etc. """
        if self.next:
            return self.next.set_next(next)
        else:
            self.next = next
            next.parent = self.parent
            return next


class Function(Scope):
    """
    Used to store the parsed contents of a python function.

    :param name: The Function name.
    :type name: string
    :param params: The parameters of a Function.
    :type name: list
    :param indent: The indent level of the flow statement.
    :type indent: int
    :param line_nr: Line number of the flow statement.
    :type line_nr: int
    :param docstr: The docstring for the current Scope.
    :type docstr: str
    """
    def __init__(self, name, params, indent, line_nr, docstr=''):
        Scope.__init__(self, name, indent, line_nr, docstr)
        self.params = params

    def get_code(self, first_indent=False, indention="    "):
        str = "def %s(%s):\n" % (self.name, ','.join(self.params))
        str += super(Function, self).get_code(True, indention)
        if self.is_empty():
            str += "pass\n"
        return str


class Import(object):
    """
    Stores the imports of any Scopes.

    >>> 1+1
    2

    :param line_nr: Line number.
    :type line_nr: int
    :param namespace: The import, as an array list of Name,\
    e.g. ['datetime', 'time'].
    :type namespace: list
    :param alias: The alias of a namespace(valid in the current namespace).
    :type alias: str
    :param from_ns: Like the namespace, can be equally used.
    :type from_ns: list
    :param star: If a star is used -> from time import *.
    :type star: bool

    :raises: None

    TODO check star?
    """
    def __init__(self, line_nr, namespace, alias='', from_ns='', star=False):
        self.line_nr = line_nr
        self.namespace = namespace
        self.alias = alias
        self.from_ns = from_ns
        self.star = star

    def get_code(self):
        if self.alias:
            ns_str = "%s as %s" % (self.namespace, self.alias)
        else:
            ns_str = str(self.namespace)
        if self.from_ns:
            if self.star:
                ns_str = '*'
            return "from %s import %s" % (self.from_ns, ns_str) + '\n'
        else:
            return "import " + ns_str + '\n'


class Statement(object):
    """
    This is the class for all the possible statements. Which means, this class
    stores pretty much all the Python code, except functions, classes, imports,
    and flow functions like if, for, etc.

    :param code: The full code of a statement. This is import, if one wants \
    to execute the code at some level.
    :param code: str
    :param set_vars: The variables which are defined by the statement.
    :param set_vars: str
    :param used_funcs: The functions which are used by the statement.
    :param used_funcs: str
    :param used_vars: The variables which are used by the statement.
    :param used_vars: str
    :param indent: The indent level of the flow statement.
    :type indent: int
    :param line_nr: Line number of the flow statement.
    :type line_nr: int
    """
    def __init__(self, code, set_vars, used_funcs, used_vars, indent, line_nr):
        self.code = code
        self.set_vars = set_vars
        self.used_funcs = used_funcs
        self.used_vars = used_vars

        self.indent = indent
        self.line_nr = line_nr

    def get_code(self, new_line=True):
        if new_line:
            return self.code + '\n'
        else:
            return self.code


class Name(object):
    """
    Used to define names in python.
    Which means the whole namespace/class/function stuff.
    So a name like "module.class.function"
    would result in an array of [module, class, function]
    """
    def __init__(self, names, indent, line_nr):
        super(Name, self).__init__()
        self.names = names
        self.indent = indent
        self.line_nr = line_nr

    def get_code(self):
        """ Returns the names in a full string format """
        return ".".join(self.names)

    def __str__(self):
        return self.get_code()


class PyFuzzyParser(object):
    """
    This class is used to parse a Python file, it then divides them into a
    class structure of different scopes.
    """
    def __init__(self):
        self.top = Scope('global', 0, 0)
        self.scope = self.top
        self.current = (None, None, None)

    def _parsedotname(self, pre_used_token=None):
        """
        The dot name parser parses a name, variable or function and returns
        their names.

        :return: list of the names, token_type, nexttoken, start_indent.
        :rtype: (Name, int, str, int)
        """
        names = []
        if pre_used_token is None:
            token_type, tok, indent = self.next()
            if token_type != tokenize.NAME and tok != '*':
                return ([], tok)
        else:
            token_type, tok, indent = pre_used_token
        names.append(tok)
        start_indent = indent
        while True:
            token_type, tok, indent = self.next()
            if tok != '.':
                break
            token_type, tok, indent = self.next()
            if token_type != tokenize.NAME:
                break
            names.append(tok)
        return (names, token_type, tok, start_indent)

    def _parse_value_list(self, pre_used_token=None):
        """
        A value list is a comma separated list. This is used for:
        >>> for a,b,self.c in enumerate(test)
        """
        value_list = []
        if pre_used_token:
            token_type, tok, indent = pre_used_token
            n, token_type, tok, start_indent = self._parsedotname(tok)
            if n:
                value_list.append(Name(n, start_indent, self.line_nr))

        token_type, tok, indent = self.next()
        while tok != 'in' and token_type != tokenize.NEWLINE:
            n, token_type, tok, start_indent = self._parsedotname(self.current)
            if n:
                value_list.append(Name(n, start_indent, self.line_nr))
            if tok == 'in':
                break

            print 'for_tok', tok
            token_type, tok, indent = self.next()
        return (value_list, tok)

    def _parseimportlist(self):
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
        while True:
            name, token_type, tok, start_indent = self._parsedotname()
            if not name:
                break
            name2 = None
            if tok == 'as':
                name2, token_type, tok, start_indent2 = self._parsedotname()
                name2 = Name(name2, start_indent2, self.line_nr)
            imports.append((Name(name, start_indent, self.line_nr), name2))
            while tok != "," and "\n" not in tok:
                token_type, tok, indent = self.next()
            if tok != ",":
                break
        return imports

    def _parseparen(self):
        """
        Functions and Classes have params (which means for classes
        super-classes). They are parsed here and returned as Names.

        TODO change behaviour, at the moment it's acting pretty weird and
        doesn't return list(Name)
        :return: List of Names
        :rtype: list
        """
        name = ''
        names = []
        level = 1
        while True:
            token_type, tok, indent = self.next()
            if tok in (')', ',') and level == 1:
                if '=' not in name:
                    name = name.replace(' ', '')
                names.append(name.strip())
                name = ''
            if tok == '(':
                level += 1
                name += "("
            elif tok == ')':
                level -= 1
                if level == 0:
                    break
                else:
                    name += ")"
            elif tok == ',' and level == 1:
                pass
            else:
                name += "%s " % str(tok)
        return names

    def _parsefunction(self, indent):
        """
        The parser for a text functions. Process the tokens, which follow a
        function definition.

        :return: Return a Scope representation of the tokens.
        :rtype: Function
        """
        token_type, fname, ind = self.next()
        if token_type != tokenize.NAME:
            return None

        token_type, open, ind = self.next()
        if open != '(':
            return None
        params = self._parseparen()

        token_type, colon, ind = self.next()
        if colon != ':':
            return None

        return Function(fname, params, indent, self.line_nr)

    def _parseclass(self, indent):
        """
        The parser for a text class. Process the tokens, which follow a
        class definition.

        :return: Return a Scope representation of the tokens.
        :rtype: Class
        """
        token_type, cname, ind = self.next()
        if token_type != tokenize.NAME:
            print "class: syntax error - token is not a name@%s (%s: %s)" \
                            % (self.line_nr, token.tok_name[token_type], cname)
            return None

        super = []
        token_type, next, ind = self.next()
        if next == '(':
            super = self._parseparen()
        elif next != ':':
            print "class: syntax error - %s@%s" % (cname, self.line_nr)
            return None

        return Class(cname, super, indent, self.line_nr)

    def _parseassignment(self):
        """ TODO remove or replace, at the moment not used """
        assign = ''
        token_type, tok, indent = self.next()
        if token_type == tokenize.STRING or tok == 'str':
            return '""'
        elif tok == '(' or tok == 'tuple':
            return '()'
        elif tok == '[' or tok == 'list':
            return '[]'
        elif tok == '{' or tok == 'dict':
            return '{}'
        elif token_type == tokenize.NUMBER:
            return '0'
        elif tok == 'open' or tok == 'file':
            return 'file'
        elif tok == 'None':
            return '_PyCmplNoType()'
        elif tok == 'type':
            return 'type(_PyCmplNoType)'  # only for method resolution
        else:
            assign += tok
            level = 0
            while True:
                token_type, tok, indent = self.next()
                if tok in ('(', '{', '['):
                    level += 1
                elif tok in (']', '}', ')'):
                    level -= 1
                    if level == 0:
                        break
                elif level == 0:
                    if tok in (';', '\n'):
                        break
                    assign += tok
        return "%s" % assign

    def _parse_statement(self, pre_used_token=None):
        """
        Parses statements like:

        >>> a = test(b)
        >>> a += 3 - 2 or b

        and so on. One row at a time.

        :param pre_used_token: The pre parsed token.
        :type pre_used_token: set
        :return: Statement + last parsed token.
        :rtype: (Statement, str)
        """
        string = ''
        set_vars = []
        used_funcs = []
        used_vars = []

        if pre_used_token:
            token_type, tok, indent = pre_used_token
        else:
            token_type, tok, indent = self.next()

        is_break_token = lambda tok: tok in ['\n', ':', ';']

        while not is_break_token(tok):
            set_string = ''
            #print 'parse_stmt', tok, token.tok_name[token_type]
            if token_type == tokenize.NAME:
                print 'is_name', tok
                if tok == 'pass':
                    set_string = ''
                elif tok in ['return', 'yield', 'del', 'raise', 'assert']:
                    set_string = tok + ' '
                elif tok == 'print':
                    set_string = tok + ' '
                else:
                    path, token_type, tok, start_indent = \
                            self._parsedotname(self.current)
                    print 'path', path
                    n = Name(path, start_indent, self.line_nr)
                    if tok == '(':
                        # it must be a function
                        used_funcs.append(n)
                    else:
                        used_vars.append(n)
                    if string:
                        print 'str', string[-1]
                    if string and re.match(r'[\w\d]', string[-1]):
                        print 'yay'
                        string += ' '
                    #if token_type == tokenize.NAME \
                    #    and self.last_token[0] == tokenize.NAME:
                    #    print 'last_token', self.last_token, token_type
                    #    string += ' ' + tok
                    string += ".".join(path)
                    #print 'parse_stmt', tok, token.tok_name[token_type]
                    continue
            elif ('=' in tok and not tok in ['>=', '<=', '==', '!=']):
                # there has been an assignement -> change vars
                set_vars = used_vars
                used_vars = []

            if set_string:
                string = set_string
            else:
                string += tok
            # caution: don't use indent anywhere,
            # it's not working with the name parsing
            token_type, tok, indent_dummy = self.next()
        if not string:
            return None, tok
        #print 'new_stat', string, set_vars, used_funcs, used_vars
        stmt = Statement(string, set_vars, used_funcs, used_vars,\
                            self.line_nr, indent)
        return stmt, tok

    def next(self):
        """ Generate the next tokenize pattern. """
        type, tok, position, dummy, self.parserline = self.gen.next()
        (self.line_nr, indent) = position
        self.last_token = self.current
        self.current = (type, tok, indent)
        return self.current

    def parse(self, text):
        """
        The main part of the program. It analyzes the given code-text and
        returns a tree-like scope. For a more detailed description, see the
        class description.

        :param text: The code which should be parsed.
        :param type: str
        """
        buf = cStringIO.StringIO(''.join(text) + '\n')
        self.gen = tokenize.generate_tokens(buf.readline)
        self.currentscope = self.scope

        try:
            extended_flow = ['else', 'except', 'finally']
            statement_toks = ['{', '[', '(', '`']

            freshscope = True
            while True:
                token_type, tok, indent = self.next()
                dbg('main: tok=[%s] type=[%s] indent=[%s]'\
                    % (tok, token_type, indent))

                if token_type == tokenize.DEDENT:
                    print 'dedent', self.scope.name
                    self.scope = self.scope.parent
                elif tok == 'def':
                    func = self._parsefunction(indent)
                    if func is None:
                        print "function: syntax error@%s" % self.line_nr
                        continue
                    dbg("new scope: function %s" % (func.name))
                    freshscope = True
                    self.scope = self.scope.add_scope(func)
                elif tok == 'class':
                    cls = self._parseclass(indent)
                    if cls is None:
                        continue
                    freshscope = True
                    dbg("new scope: class %s" % (cls.name))
                    self.scope = self.scope.add_scope(cls)
                # import stuff
                elif tok == 'import':
                    imports = self._parseimportlist()
                    for mod, alias in imports:
                        self.scope.add_import(Import(self.line_nr, mod, alias))
                    freshscope = False
                elif tok == 'from':
                    mod, token_type, tok, start_indent = self._parsedotname()
                    if not mod or tok != "import":
                        print "from: syntax error..."
                        continue
                    mod = Name(mod, start_indent, self.line_nr)
                    names = self._parseimportlist()
                    for name, alias in names:
                        i = Import(self.line_nr, name, alias, mod)
                        self.scope.add_import(i)
                    freshscope = False
                #loops
                elif tok == 'for':
                    value_list, tok = self._parse_value_list()
                    if tok == 'in':
                        statement, tok = self._parse_statement()
                        if tok == ':':
                            f = Flow('for', statement, indent, self.line_nr, \
                                        value_list)
                            dbg("new scope: flow %s" % (f.name))
                            self.scope = self.scope.add_statement(f)

                elif tok in ['if', 'while', 'try', 'with'] + extended_flow:
                    # TODO with statement has local variables
                    command = tok
                    statement, tok = self._parse_statement()
                    if tok == ':':
                        f = Flow(command, statement, indent, self.line_nr)
                        dbg("new scope: flow %s" % (f.name))
                        if command in extended_flow:
                            # the last statement has to be another part of
                            # the flow statement
                            self.scope = self.scope.statements[-1].set_next(f)
                        else:
                            self.scope = self.scope.add_statement(f)

                elif tok == 'global':
                    self._parse_statement(self.current)
                    pass
                    # TODO add suport for global
                elif token_type == tokenize.STRING:
                    if freshscope:
                        self.scope.add_docstr(tok)
                elif token_type == tokenize.NAME or tok in statement_toks:
                    stmt, tok = self._parse_statement(self.current)
                    if stmt:
                        self.scope.add_statement(stmt)
                    freshscope = False
                #else:
                    #print "_not_implemented_", tok, self.parserline
        except StopIteration:  # thrown on EOF
            pass
        #except:
        #    dbg("parse error: %s, %s @ %s" %
        #        (sys.exc_info()[0], sys.exc_info()[1], self.parserline))
        return self.top


def dbg(*args):
    global debug_function
    if debug_function:
        debug_function(*args)


debug_function = None
