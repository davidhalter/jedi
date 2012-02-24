""""
TODO This is a parser

scope
    imports
    subscopes
    statements

Ignored simple statements:
 - print (no use for it)
 - assert
 - break, continue (because we avoid loops)
 - del (also no used, since this script avoids loops and files)
 - exec (dangerous - not controllable)

global is a special case and will not be used here
"""
import sys
import tokenize
import cStringIO


def indent_block(text, indention="    "):
    """ This function indents a text block with a default of four spaces """
    temp = ''
    while text and text[-1] == '\n':
        temp += text[-1]
        text = text[:-1]
    lines = text.split('\n')
    return '\n'.join(map(lambda s: indention + s, lines)) + temp


class Scope(object):
    def __init__(self, name, indent, line_nr, docstr=''):
        self.subscopes = []
        self.locals = []
        self.imports = []
        self.statements = []
        self.docstr = docstr
        self.parent = None
        self.name = name
        self.indent = indent
        self.line_nr = line_nr

    def add_scope(self, sub):
        if sub == None:
            print 'push scope: [%s@%s]' % (sub.name, sub.indent)
        sub.parent = self
        self.subscopes.append(sub)
        return sub

    def doc(self, str):
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

    def add_local(self, loc):
        self.locals.append(loc)

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
        """ Returns the code of the current scope. """
        string = ""
        if len(self.docstr) > 0:
            string += '"""' + self.docstr + '"""\n'
        for i in self.imports:
            string += i.get_code() + '\n'
        for sub in self.subscopes:
            string += str(sub.line_nr) + sub.get_code(first_indent=True, indention=indention)
        for l in self.locals:
            string += l + '\n'

        if first_indent:
            string = indent_block(string, indention=indention)
        return string

    def is_empty(self):
        """
        this function returns true if there are no subscopes, imports, locals.
        """
        return not (self.locals or self.imports or self.subscopes)


class Class(Scope):
    def __init__(self, name, supers, indent, line_nr, docstr=''):
        super(Class, self).__init__(name, indent, line_nr, docstr)
        self.supers = supers

    def get_code(self, first_indent=False, indention="    "):
        str = 'class %s' % (self.name)
        if len(self.supers) > 0:
            str += '(%s)' % ','.join(self.supers)
        str += ':\n'
        str += super(Class, self).get_code(True, indention)
        print "get_code class %s %i" % (self.name, self.is_empty())
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
    """
    def __init__(self, code, functions, indent, line_nr):
        super(Flow, self).__init__(name, indent, line_nr, None)
        name = code
        self.next = None

    def get_code(self, first_indent=False, indention="    "):
        str = 'class %s' % (self.name)
        str += ':\n'
        str += super(Class, self).get_code(True, indention)
        print "get_code class %s %i" % (self.name, self.is_empty())
        if self.is_empty():
            str += "pass\n"
        return str

class Function(Scope):
    def __init__(self, name, params, indent, line_nr, docstr=''):
        Scope.__init__(self, name, indent, line_nr, docstr)
        self.params = params

    def get_code(self, first_indent=False, indention="    "):
        str = "def %s(%s):\n" % (self.name, ','.join(self.params))
        #if len(self.docstr) > 0:
        #    str += self.childindent()+'"""'+self.docstr+'"""\n'
        str += super(Function, self).get_code(True, indention)
        if self.is_empty():
            str += "pass\n"
        print "func", self.locals
        return str


class Import(object):
    """
    stores the imports of any scopes.

    >>> 1+1
    2

    :param line_nr: Line number.
    :param namespace: the namespace which is imported.
    :param alias: the alias (valid in the current namespace).
    :param from_ns: from declaration in an import.
    :param star: if a star is used -> from time import *.

    :returns: test
    :raises:

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
            ns_str = self.namespace
        if self.from_ns:
            if self.star:
                ns_str = '*'
            return "test from %s import %s" % (self.from_ns, ns_str)
        else:
            return "test import " + ns_str


class Statement(object):
    """ This is the class for Local and Functions """
    def __init__(self, code, locals, functions):
        """
        @param line_nr
        @param stmt the statement string
        """
        self.line_nr = line_nr
        self.stmt = stmt

    def get_code(self):
        raise NotImplementedError()


class Local(object):
    """
    stores locals variables of any scopes
    """
    def __init__(self, line_nr, left, right=None, is_global=False):
        """
        @param line_nr
        @param left: the left part of the local assignment
        @param right: the right part of the assignment, must not be set
                      (in case of global)
        @param is_global: defines a global variable
        """
        self.line_nr = line_nr
        self.left = left
        self.right = right

    def get_code(self):
        if self.alias:
            ns_str = "%s as %s" % (self.namespace, self.alias)
        else:
            ns_str = self.namespace
        if self.from_ns:
            if self.star:
                ns_str = '*'
            return "test from %s import %s" % (self.from_ns, ns_str)
        else:
            return "test import " + ns_str


class Name(object):
    """
    Used to define names in python.
    Which means the whole namespace/class/function stuff.
    So a name like "module.class.function"
    would result in an array of [module, class, function]
    """
    def __init__(self, names):
        super(Name, self).__init__()
        self.names = names

    def get_code(self):
        """ returns the name again in a full string format """
        return ".".join(names)


class PyFuzzyParser(object):
    """
    This class is used to parse a Python file, it then divides them into a
    class structure of differnt scopes.
    """
    def __init__(self):
        self.top = Scope('global', 0, 0)
        self.scope = self.top

    def _parsedotname(self, pre_used_token=None):
        """ @return (dottedname, nexttoken) """
        names = []
        if pre_used_token is None:
            tokentype, tok, indent = self.next()
            if tokentype != tokenize.NAME and tok != '*':
                return ([], tok)
        else:
            tok = pre_used_token
        names.append(tok)
        while True:
            tokentype, tok, indent = self.next()
            if tok != '.':
                break
            tokentype, tok, indent = self.next()
            if tokentype != tokenize.NAME:
                break
            names.append(tok)
        return (names, tok)


    def _parse_value_list(self, pre_used_token=None):
        """
        A value list is a comma separated list. This is used for:
        >>> for a,b,self.c in enumerate(test)
        """
        value_list = []
        if pre_used_token:
            n = self._parsedotname(pre_used_token)
            if n:
                value_list.append(n)

        tokentype, tok, indent = self.next()
        while tok != 'in' or tokentype == tokenize.NEWLINE:
            n = self._parsedotname(tok)
            if n:
                value_list.append(n)

            tokentype, tok, indent = self.next()
        return (value_list, tok)

    def _parseimportlist(self):
        imports = []
        while True:
            name, tok = self._parsedotname()
            if not name:
                break
            name2 = ''
            if tok == 'as':
                name2, tok = self._parsedotname()
            imports.append((name, name2))
            while tok != "," and "\n" not in tok:
                tokentype, tok, indent = self.next()
            if tok != ",":
                break
        return imports

    def _parseparen(self):
        name = ''
        names = []
        level = 1
        while True:
            tokentype, tok, indent = self.next()
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
        tokentype, fname, ind = self.next()
        if tokentype != tokenize.NAME:
            return None

        tokentype, open, ind = self.next()
        if open != '(':
            return None
        params = self._parseparen()

        tokentype, colon, ind = self.next()
        if colon != ':':
            return None

        return Function(fname, params, indent, self.line_nr)


    def _parseclass(self, indent):
        tokentype, cname, ind = self.next()
        if tokentype != tokenize.NAME:
            return None

        super = []
        tokentype, next, ind = self.next()
        if next == '(':
            super = self._parseparen()
        elif next != ':':
            return None

        return Class(cname, super, indent, self.line_nr)


    def _parseassignment(self):
        assign = ''
        tokentype, tok, indent = self.next()
        if tokentype == tokenize.STRING or tok == 'str':
            return '""'
        elif tok == '(' or tok == 'tuple':
            return '()'
        elif tok == '[' or tok == 'list':
            return '[]'
        elif tok == '{' or tok == 'dict':
            return '{}'
        elif tokentype == tokenize.NUMBER:
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
                tokentype, tok, indent = self.next()
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


    def _parse_words(self, word):
        """
        Used to parse a word, if the tokenizer returned a word at the start of
        a new command.
        """
        return 


    def _parse_statement(self, tok = None):
        """
        Parses statements like:
        >>> a = test(b)
        >>> a += 3 - 2 or b
        and so on. One row at a time.
        """
        string = tok 
        tok = True
        while tok:
            tokentype, tok, indent = self.next()
            string += tok
        return string

    def next(self):
        type, tok, position, dummy, self.parserline = self.gen.next()
        (self.line_nr, indent) = position
        return (type, tok, indent)

    def parse(self, text):
        buf = cStringIO.StringIO(''.join(text) + '\n')
        self.gen = tokenize.generate_tokens(buf.readline)
        self.currentscope = self.scope

        try:
            freshscope = True
            while True:
                tokentype, tok, indent = self.next()
                dbg('main: tok=[%s] type=[%s] indent=[%s]'\
                    % (tok, tokentype, indent))

                if tokentype == tokenize.DEDENT:
                    self.scope = self.scope.parent
                elif tok == 'def':
                    func = self._parsefunction(indent)
                    if func is None:
                        print "function: syntax error..."
                        continue
                    dbg("new scope: function %s" % (func.name))
                    freshscope = True
                    self.scope = self.scope.add_scope(func)
                elif tok == 'class':
                    cls = self._parseclass(indent)
                    if cls is None:
                        print "class: syntax error..."
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
                    mod, tok = self._parsedotname()
                    if not mod or tok != "import":
                        print "from: syntax error..."
                        continue
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
                            self.scope.append(statement)

                elif tok == 'while':
                    param_list = self._parse_while_loop()
                elif tokentype == tokenize.STRING:
                    if freshscope:
                        self.scope.doc(tok)
                elif tokentype == tokenize.NAME:
                    name, tok = self._parsedotname(tok)
                    if tok == '=':
                        stmt = self._parseassignment()
                        dbg("parseassignment: %s = %s" % (name, stmt))
                        if stmt != None:
                            self.scope.add_local("%s = %s" % (name, stmt))
                    else:
                        #print "_not_implemented_", tok, self.parserline
                        pass
                    freshscope = False
                #else:
                    #print "_not_implemented_", tok, self.parserline
        except StopIteration:  # thrown on EOF
            pass
        #except:
        #    dbg("parse error: %s, %s @ %s" %
        #        (sys.exc_info()[0], sys.exc_info()[1], self.parserline))
        return self.top


def _sanitize(str):
    val = ''
    level = 0
    for c in str:
        if c in ('(', '{', '['):
            level += 1
        elif c in (']', '}', ')'):
            level -= 1
        elif level == 0:
            val += c
    return val


def dbg(*args):
    print args
