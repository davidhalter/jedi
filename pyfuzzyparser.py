""""
TODO This is a parser
"""
import sys
import tokenize
import cStringIO

def indent_block(text, indention="    "):
    """ This function indents a text block with a default of four spaces """
    lines = text.split('\n')
    return '\n'.join(map(lambda s: indention+s, lines))

class Scope(object):
    def __init__(self,name,indent,docstr=''):
        self.subscopes = []
        self.locals = []
        self.imports = []
        self.docstr = docstr
        self.parent = None
        self.name = name
        self.indent = indent

    def add_scope(self,sub):
        #print 'push scope: [%s@%s]' % (sub.name,sub.indent)
        sub.parent = self
        self.subscopes.append(sub)
        return sub

    def doc(self,str):
        """ Clean up a docstring """
        d = str.replace('\n',' ')
        d = d.replace('\t',' ')
        while d.find('  ') > -1: d = d.replace('  ',' ')
        while d[0] in '"\'\t ': d = d[1:]
        while d[-1] in '"\'\t ': d = d[:-1]
        dbg("Scope(%s)::docstr = %s" % (self,d))
        self.docstr = d

    def add_local(self,loc):
        self.locals.append(loc)

    def add_import(self, imp):
        self.imports.append(imp)

    def _checkexisting(self,test):
        "Convienance function... keep out duplicates"
        if test.find('=') > -1:
            var = test.split('=')[0].strip()
            for l in self.locals:
                if l.find('=') > -1 and var == l.split('=')[0].strip():
                    self.locals.remove(l)

    def get_code(self, first_indent=False, indention="    "):
        str = ""
        #str += 'class _PyCmplNoType:\n    def __getattr__(self,name):\n        return None\n'
        if len(self.docstr) > 0: str += '"""'+self.docstr+'"""\n'
        for i in self.imports:
            str += i.get_code() + '\n'
        #str += 'class _PyCmplNoType:\n    def __getattr__(self,name):\n        return None\n'
        for sub in self.subscopes:
            str += sub.get_code(first_indent=True, indention=indention)
        for l in self.locals:
            str += l+'\n'

        if first_indent: str = indent_block(str, indention = indention)
        return "_%s_%s" % (self.indent, str)

    def is_empty(self):
        """ 
        this function returns true if there are no subscopes, imports, locals.
        """
        return not (self.locals, self.imports, self.subscopes)

class Class(Scope):
    def __init__(self, name, supers, indent, docstr=''):
        super(Class, self).__init__(name, indent, docstr)
        self.supers = supers

    def get_code(self, first_indent=False, indention="    "):
        str = 'class %s' % (self.name)
        if len(self.supers) > 0: str += '(%s)' % ','.join(self.supers)
        str += ':\n'
        str += super(Class, self).get_code(True, indention)
        if self.is_empty():
            str += indent_block("pass\n", indention=indention)
        return str


class Function(Scope):
    def __init__(self, name, params, indent, docstr=''):
        Scope.__init__(self,name,indent, docstr)
        self.params = params

    def get_code(self, first_indent=False, indention="    "):
        str = "def %s(%s):\n" % (self.name,','.join(self.params))
        #if len(self.docstr) > 0: str += self.childindent()+'"""'+self.docstr+'"""\n'
        str += super(Function, self).get_code(True, indention)
        if self.is_empty():
            str += indent_block("pass\n", indention=indention)
        print "func", self.locals
        return str

class Import(object):
    """
    stores the imports of class files
    """
    def __init__(self, namespace, alias='', from_ns='', star=False):
        """
        @param namespace: the namespace which is imported
        @param alias: the alias (valid in the current namespace)
        @param from_ns: from declaration in an import
        @param star: if a star is used -> from time import *
        """
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

class PyFuzzyParser(object):
    """
    This class is used to parse a Python file, it then divides them into a
    class structure of differnt scopes.
    """
    def __init__(self):
        self.top = Scope('global',0)
        self.scope = self.top

    def _parsedotname(self,pre=None):
        #returns (dottedname, nexttoken)
        name = []
        if pre is None:
            tokentype, tok, indent = self.next()
            if tokentype != tokenize.NAME and tok != '*':
                return ('', tok)
        else: tok = pre
        name.append(tok)
        while True:
            tokentype, tok, indent = self.next()
            if tok != '.': break
            tokentype, tok, indent = self.next()
            if tokentype != tokenize.NAME: break
            name.append(tok)
        return (".".join(name), tok)

    def _parseimportlist(self):
        imports = []
        while True:
            name, tok = self._parsedotname()
            if not name: break
            name2 = ''
            if tok == 'as': name2, tok = self._parsedotname()
            imports.append((name, name2))
            while tok != "," and "\n" not in tok:
                tokentype, tok, indent = self.next()
            if tok != ",": break
        return imports

    def _parseparen(self):
        name = ''
        names = []
        level = 1
        while True:
            tokentype, tok, indent = self.next()
            if tok in (')', ',') and level == 1:
                if '=' not in name: name = name.replace(' ', '')
                names.append(name.strip())
                name = ''
            if tok == '(':
                level += 1
                name += "("
            elif tok == ')':
                level -= 1
                if level == 0: break
                else: name += ")"
            elif tok == ',' and level == 1:
                pass
            else:
                name += "%s " % str(tok)
        return names

    def _parsefunction(self, indent):
        tokentype, fname, ind = self.next()
        if tokentype != tokenize.NAME: return None

        tokentype, open, ind = self.next()
        if open != '(': return None
        params=self._parseparen()

        tokentype, colon, ind = self.next()
        if colon != ':': return None

        return Function(fname, params, indent)

    def _parseclass(self, indent):
        tokentype, cname, ind = self.next()
        if tokentype != tokenize.NAME: return None

        super = []
        tokentype, next, ind = self.next()
        if next == '(':
            super=self._parseparen()
        elif next != ':': return None

        return Class(cname,super,indent)

    def _parseassignment(self):
        assign=''
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
            return 'type(_PyCmplNoType)' #only for method resolution
        else:
            assign += tok
            level = 0
            while True:
                tokentype, tok, indent = self.next()
                if tok in ('(','{','['):
                    level += 1
                elif tok in (']','}',')'):
                    level -= 1
                    if level == 0: break
                elif level == 0:
                    if tok in (';','\n'): break
                    assign += tok
        return "%s" % assign

    def next(self):
        type, tok, (lineno, indent), end, self.parserline = self.gen.next()
        if lineno == self.curline:
            #print 'line found [%s] scope=%s' % (line.replace('\n',''),self.scope.name)
            self.currentscope = self.scope
        return (type, tok, indent)

    #p.parse(vim.current.buffer[:],vim.eval("line('.')"))
    def parse(self,text,curline=0):
        self.curline = int(curline)
        buf = cStringIO.StringIO(''.join(text) + '\n')
        self.gen = tokenize.generate_tokens(buf.readline)
        self.currentscope = self.scope

        try:
            freshscope=True
            while True:
                tokentype, tok, indent = self.next()
                dbg( 'main: tok=[%s] indent=[%s]' % (tok,indent))

                if tokentype == tokenize.DEDENT:
                    self.scope = self.scope.parent
                elif tok == 'def':
                    func = self._parsefunction(indent)
                    if func is None:
                        print "function: syntax error..."
                        continue
                    dbg("new scope: function")
                    freshscope = True
                    self.scope = self.scope.add_scope(func)
                elif tok == 'class':
                    cls = self._parseclass(indent)
                    if cls is None:
                        print "class: syntax error..."
                        continue
                    freshscope = True
                    dbg("new scope: class")
                    self.scope = self.scope.add_scope(cls)
                elif tok == 'import':
                    imports = self._parseimportlist()
                    for mod, alias in imports:
                        self.scope.add_import(Import(mod, alias))
                    freshscope = False
                elif tok == 'from':
                    mod, tok = self._parsedotname()
                    if not mod or tok != "import":
                        print "from: syntax error..."
                        continue
                    names = self._parseimportlist()
                    for name, alias in names:
                        self.scope.add_import(Import(name, alias, mod))
                    freshscope = False
                elif tokentype == tokenize.STRING:
                    if freshscope: self.scope.doc(tok)
                elif tokentype == tokenize.NAME:
                    name,tok = self._parsedotname(tok)
                    if tok == '=':
                        stmt = self._parseassignment()
                        dbg("parseassignment: %s = %s" % (name, stmt))
                        if stmt != None:
                            self.scope.add_local("%s = %s" % (name,stmt))
                    freshscope = False
        except StopIteration: #thrown on EOF
            pass
        #except:
        #    dbg("parse error: %s, %s @ %s" %
        #        (sys.exc_info()[0], sys.exc_info()[1], self.parserline))
        return self.top #self._adjustvisibility()

def _sanitize(str):
    val = ''
    level = 0
    for c in str:
        if c in ('(','{','['):
            level += 1
        elif c in (']','}',')'):
            level -= 1
        elif level == 0:
            val += c
    return val

def dbg(*args):
    print args
