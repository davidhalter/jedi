""""
TODO This is a parser
"""
import sys
import tokenize
import cStringIO
from token import ENDMARKER , NT_OFFSET , NUMBER , STRING , NEWLINE , INDENT , DEDENT , LPAR , RPAR , LSQB , RSQB , COLON , COMMA , SEMI , PLUS , MINUS , STAR , SLASH , VBAR , AMPER , LESS , GREATER , EQUAL , DOT , PERCENT , BACKQUOTE , LBRACE , RBRACE , EQEQUAL , NOTEQUAL , LESSEQUAL , GREATEREQUAL , TILDE , CIRCUMFLEX , LEFTSHIFT , RIGHTSHIFT , DOUBLESTAR , PLUSEQUAL , MINEQUAL , STAREQUAL , SLASHEQUAL , PERCENTEQUAL , AMPEREQUAL , VBAREQUAL , CIRCUMFLEXEQUAL , LEFTSHIFTEQUAL , RIGHTSHIFTEQUAL , DOUBLESTAREQUAL , DOUBLESLASH , DOUBLESLASHEQUAL , AT , NAME , ERRORTOKEN , N_TOKENS , OP

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

    def copy_decl(self,indent=0):
        """ Copy a scope's declaration only, at the specified indent level - not local variables """
        return Scope(self.name,indent,self.docstr)

    def _checkexisting(self,test):
        "Convienance function... keep out duplicates"
        if test.find('=') > -1:
            var = test.split('=')[0].strip()
            for l in self.locals:
                if l.find('=') > -1 and var == l.split('=')[0].strip():
                    self.locals.remove(l)

    def get_code(self):
        str = ""
        #str += 'class _PyCmplNoType:\n    def __getattr__(self,name):\n        return None\n'
        if len(self.docstr) > 0: str += '"""'+self.docstr+'"""\n'
        for i in self.imports:
            str += i.get_code() + '\n'
        #str += 'class _PyCmplNoType:\n    def __getattr__(self,name):\n        return None\n'
        for sub in self.subscopes:
            str += sub.get_code()
        for l in self.locals:
            if not l.startswith('import'): str += l+'\n'

        return str

    def pop(self,indent):
        #print 'pop scope: [%s] to [%s]' % (self.indent,indent)
        outer = self
        while outer.parent != None and outer.indent >= indent:
            outer = outer.parent
        return outer

    def currentindent(self):
        #print 'parse current indent: %s' % self.indent
        return '    '*self.indent

    def childindent(self):
        #print 'parse child indent: [%s]' % (self.indent+1)
        return '    '*(self.indent+1)

class Class(Scope):
    def __init__(self, name, supers, indent, docstr=''):
        Scope.__init__(self,name,indent, docstr)
        self.supers = supers
    def copy_decl(self,indent=0):
        c = Class(self.name,self.supers,indent, self.docstr)
        for s in self.subscopes:
            c.add_scope(s.copy_decl(indent+1))
        return c
    def get_code(self):
        str = '%sclass %s' % (self.currentindent(),self.name)
        if len(self.supers) > 0: str += '(%s)' % ','.join(self.supers)
        str += ':\n'
        if len(self.docstr) > 0: str += self.childindent()+'"""'+self.docstr+'"""\n'
        if len(self.subscopes) > 0:
            for s in self.subscopes: str += s.get_code()
        else:
            str += '%spass\n' % self.childindent()
        return str


class Function(Scope):
    def __init__(self, name, params, indent, docstr=''):
        Scope.__init__(self,name,indent, docstr)
        self.params = params
    def copy_decl(self,indent=0):
        return Function(self.name,self.params,indent, self.docstr)
    def get_code(self):
        str = "%sdef %s(%s):\n" % \
            (self.currentindent(),self.name,','.join(self.params))
        if len(self.docstr) > 0: str += self.childindent()+'"""'+self.docstr+'"""\n'
        str += "%spass\n" % self.childindent()
        print "func_code:", self.locals
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
    This class is used to parse a Python file, it then divides them into
    """
    def __init__(self):
        self.top = Scope('global',0)
        self.scope = self.top

    def _parsedotname(self,pre=None):
        #returns (dottedname, nexttoken)
        name = []
        if pre is None:
            tokentype, token, indent = self.next()
            if tokentype != NAME and token != '*':
                return ('', token)
        else: token = pre
        name.append(token)
        while True:
            tokentype, token, indent = self.next()
            if token != '.': break
            tokentype, token, indent = self.next()
            if tokentype != NAME: break
            name.append(token)
        return (".".join(name), token)

    def _parseimportlist(self):
        imports = []
        while True:
            name, token = self._parsedotname()
            if not name: break
            name2 = ''
            if token == 'as': name2, token = self._parsedotname()
            imports.append((name, name2))
            while token != "," and "\n" not in token:
                tokentype, token, indent = self.next()
            if token != ",": break
        return imports

    def _parseparen(self):
        name = ''
        names = []
        level = 1
        while True:
            tokentype, token, indent = self.next()
            if token in (')', ',') and level == 1:
                if '=' not in name: name = name.replace(' ', '')
                names.append(name.strip())
                name = ''
            if token == '(':
                level += 1
                name += "("
            elif token == ')':
                level -= 1
                if level == 0: break
                else: name += ")"
            elif token == ',' and level == 1:
                pass
            else:
                name += "%s " % str(token)
        return names

    def _parsefunction(self,indent):
        self.scope=self.scope.pop(indent)
        tokentype, fname, ind = self.next()
        if tokentype != NAME: return None

        tokentype, open, ind = self.next()
        if open != '(': return None
        params=self._parseparen()

        tokentype, colon, ind = self.next()
        if colon != ':': return None

        return Function(fname,params,indent)

    def _parseclass(self,indent):
        self.scope=self.scope.pop(indent)
        tokentype, cname, ind = self.next()
        if tokentype != NAME: return None

        super = []
        tokentype, next, ind = self.next()
        if next == '(':
            super=self._parseparen()
        elif next != ':': return None

        return Class(cname,super,indent)

    def _parseassignment(self):
        assign=''
        tokentype, token, indent = self.next()
        if tokentype == tokenize.STRING or token == 'str':
            return '""'
        elif token == '(' or token == 'tuple':
            return '()'
        elif token == '[' or token == 'list':
            return '[]'
        elif token == '{' or token == 'dict':
            return '{}'
        elif tokentype == tokenize.NUMBER:
            return '0'
        elif token == 'open' or token == 'file':
            return 'file'
        elif token == 'None':
            return '_PyCmplNoType()'
        elif token == 'type':
            return 'type(_PyCmplNoType)' #only for method resolution
        else:
            assign += token
            level = 0
            while True:
                tokentype, token, indent = self.next()
                if token in ('(','{','['):
                    level += 1
                elif token in (']','}',')'):
                    level -= 1
                    if level == 0: break
                elif level == 0:
                    if token in (';','\n'): break
                    assign += token
        return "%s" % assign

    def next(self):
        type, token, (lineno, indent), end, self.parserline = self.gen.next()
        if lineno == self.curline:
            #print 'line found [%s] scope=%s' % (line.replace('\n',''),self.scope.name)
            self.currentscope = self.scope
        return (type, token, indent)

    def _adjustvisibility(self):
        newscope = Scope('result',0)
        scp = self.currentscope
        while scp != None:
            if type(scp) == Function:
                slice = 0
                #Handle 'self' params
                if scp.parent != None and type(scp.parent) == Class:
                    slice = 1
                    newscope.add_local('%s = %s' % (scp.params[0],scp.parent.name))
                for p in scp.params[slice:]:
                    i = p.find('=')
                    if len(p) == 0: continue
                    pvar = ''
                    ptype = ''
                    if i == -1:
                        pvar = p
                        ptype = '_PyCmplNoType()'
                    else:
                        pvar = p[:i]
                        ptype = _sanitize(p[i+1:])
                    if pvar.startswith('**'):
                        pvar = pvar[2:]
                        ptype = '{}'
                    elif pvar.startswith('*'):
                        pvar = pvar[1:]
                        ptype = '[]'

                    newscope.add_local('%s = %s' % (pvar,ptype))

            for s in scp.subscopes:
                ns = s.copy_decl(0)
                newscope.add_scope(ns)
            for l in scp.locals: newscope.add_local(l)
            scp = scp.parent

        self.currentscope = newscope
        return self.currentscope

    #p.parse(vim.current.buffer[:],vim.eval("line('.')"))
    def parse(self,text,curline=0):
        self.curline = int(curline)
        buf = cStringIO.StringIO(''.join(text) + '\n')
        self.gen = tokenize.generate_tokens(buf.readline)
        self.currentscope = self.scope

        try:
            freshscope=True
            while True:
                tokentype, token, indent = self.next()
                #dbg( 'main: token=[%s] indent=[%s]' % (token,indent))

                if tokentype == DEDENT or token == "pass":
                    self.scope = self.scope.pop(indent)
                elif token == 'def':
                    func = self._parsefunction(indent)
                    if func is None:
                        print "function: syntax error..."
                        continue
                    dbg("new scope: function")
                    freshscope = True
                    self.scope = self.scope.add_scope(func)
                elif token == 'class':
                    cls = self._parseclass(indent)
                    if cls is None:
                        print "class: syntax error..."
                        continue
                    freshscope = True
                    dbg("new scope: class")
                    self.scope = self.scope.add_scope(cls)

                elif token == 'import':
                    imports = self._parseimportlist()
                    for mod, alias in imports:
                        self.scope.add_import(Import(mod, alias))
                    freshscope = False
                elif token == 'from':
                    mod, token = self._parsedotname()
                    if not mod or token != "import":
                        print "from: syntax error..."
                        continue
                    names = self._parseimportlist()
                    for name, alias in names:
                        self.scope.add_import(Import(name, alias, mod))
                    freshscope = False
                elif tokentype == STRING:
                    if freshscope: self.scope.doc(token)
                elif tokentype == NAME:
                    name,token = self._parsedotname(token)
                    if token == '=':
                        stmt = self._parseassignment()
                        dbg("parseassignment: %s = %s" % (name, stmt))
                        if stmt != None:
                            self.scope.add_local("%s = %s" % (name,stmt))
                    freshscope = False
        except StopIteration: #thrown on EOF
            pass
        except:
            dbg("parse error: %s, %s @ %s" %
                (sys.exc_info()[0], sys.exc_info()[1], self.parserline))
        return self._adjustvisibility()

    def print_parser_code(self):
        """ prints the result of the parser operation """
        print self.scope.get_code()

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
