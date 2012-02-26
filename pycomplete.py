#!/usr/bin/env python
# python >= 2.4 working with readmodule_ex
import pyclbr
import cStringIO
import sys
import types

from pyfuzzyparser import PyFuzzyParser, _sanitize


def complete(file_name, line, colon):
    options = []
    print file_name, line, colon
    module = pyclbr.readmodule_ex('test')
    for name, ty in module.iteritems():
        #print ty.name, ty.module, ty.file, ty.lineno#, dir(ty)

        if isinstance(ty, pyclbr.Class):
            #print 'class: ', ty.methods, ty.super
            #options.append(Class(name))
            pass
        else:
            #options.append(Function(name))
            pass
    return options


print 1
if __name__ == '__main__':
    #print complete('test.py', 50, 3)
    #print complete('test.py', 51, 10)
    pass


class Completer(object):
    def __init__(self):
        self.compldict = {}
        self.parser = PyFuzzyParser()

    def evalsource(self, text, line=0):
        sc = self.parser.parse(text)
        self.sc = sc  # TODO rm
        src = sc.get_code()
        #dbg("source: %s" % src)
        #try: exec(src) in self.compldict
        #except: dbg("parser: %s, %s" % (sys.exc_info()[0], sys.exc_info()[1]))
        #for l in sc.locals:
        #    dbg("local: %s" % l)
        #    try: exec(l) in self.compldict
        #    except: dbg("locals: %s, %s [%s]" % (sys.exc_info()[0], sys.exc_info()[1], l))

    def _cleanstr(self, doc):
        return doc.replace('"', ' ').replace("'", ' ')

    def get_arguments(self, func_obj):
        def _ctor(obj):
            try:
                return class_ob.__init__.im_func
            except AttributeError:
                for base in class_ob.__bases__:
                    rc = _find_constructor(base)
                    if rc is not None:
                        return rc
            return None

        arg_offset = 1
        if type(func_obj) == types.ClassType:
            func_obj = _ctor(func_obj)
        elif type(func_obj) == types.MethodType:
            func_obj = func_obj.im_func
        else:
            arg_offset = 0

        arg_text = ''
        if type(func_obj) in [types.FunctionType, types.LambdaType]:
            try:
                cd = func_obj.func_code
                real_args = cd.co_varnames[arg_offset:cd.co_argcount]
                defaults = func_obj.func_defaults or ''
                defaults = map(lambda name: "=%s" % name, defaults)
                defaults = [""] * (len(real_args) - len(defaults)) + defaults
                items = map(lambda a, d: a + d, real_args, defaults)
                if func_obj.func_code.co_flags & 0x4:
                    items.append("...")
                if func_obj.func_code.co_flags & 0x8:
                    items.append("***")
                arg_text = (','.join(items)) + ')'

            except:
                dbg("arg completion: %s: %s" % (sys.exc_info()[0], sys.exc_info()[1]))
                pass
        if len(arg_text) == 0:
            # The doc string sometimes contains the function signature
            #  this works for alot of C modules that are part of the
            #  standard library
            doc = func_obj.__doc__
            if doc:
                doc = doc.lstrip()
                pos = doc.find('\n')
                if pos > 0:
                    sigline = doc[:pos]
                    lidx = sigline.find('(')
                    ridx = sigline.find(')')
                    if lidx > 0 and ridx > 0:
                        arg_text = sigline[lidx + 1:ridx] + ')'
        if len(arg_text) == 0:
            arg_text = ')'
        return arg_text

    def get_completions(self, context, match):
        dbg("get_completions('%s','%s')" % (context, match))
        stmt = ''
        if context:
            stmt += str(context)
        if match:
            stmt += str(match)
        try:
            result = None
            all = {}
            ridx = stmt.rfind('.')
            if len(stmt) > 0 and stmt[-1] == '(':
                result = eval(_sanitize(stmt[:-1]), self.compldict)
                doc = result.__doc__
                if doc is None:
                    doc = ''
                args = self.get_arguments(result)
                return [{'word': self._cleanstr(args), 'info': self._cleanstr(doc)}]
            elif ridx == -1:
                match = stmt
                all = self.compldict
            else:
                match = stmt[ridx + 1:]
                stmt = _sanitize(stmt[:ridx])
                result = eval(stmt, self.compldict)
                all = dir(result)

            dbg("completing: stmt:%s" % stmt)
            completions = []

            try:
                maindoc = result.__doc__
            except:
                maindoc = ' '
            if maindoc is None:
                maindoc = ' '
            for m in all:
                if m == "_PyCmplNoType":
                    continue  # this is internal
                try:
                    dbg('possible completion: %s' % m)
                    if m.find(match) == 0:
                        if result is None:
                            inst = all[m]
                        else:
                            inst = getattr(result, m)
                        try:
                            doc = inst.__doc__
                        except:
                            doc = maindoc
                        typestr = str(inst)
                        if doc is None or doc == '':
                            doc = maindoc

                        wrd = m[len(match):]
                        c = {'word': wrd, 'abbr': m,  'info': self._cleanstr(doc)}
                        if "function" in typestr:
                            c['word'] += '('
                            c['abbr'] += '(' + self._cleanstr(self.get_arguments(inst))
                        elif "method" in typestr:
                            c['word'] += '('
                            c['abbr'] += '(' + self._cleanstr(self.get_arguments(inst))
                        elif "module" in typestr:
                            c['word'] += '.'
                        elif "class" in typestr:
                            c['word'] += '('
                            c['abbr'] += '('
                        completions.append(c)
                except:
                    i = sys.exc_info()
                    dbg("inner completion: %s, %s [stmt='%s']" % (i[0], i[1], stmt))
            return completions
        except:
            i = sys.exc_info()
            dbg("completion: %s, %s [stmt='%s']" % (i[0], i[1], stmt))
            return []

debugstmts = []
def dbg(s):
    debugstmts.append(s)


def showdbg():
    for d in debugstmts:
        print "DBG: %s " % d


text = cStringIO.StringIO(open('test.py').read())
cmpl = Completer()
cmpl.evalsource(text, 51)
#print cmpl.sc.get_code()
#all = cmpl.get_completions("cdef.", '')

#print "Completions:", len(all)
#for c in all:
#    print c['word'],
#    print ',',
#print ''
showdbg()

print cmpl.parser.top.get_code()
#print cmpl.parser.top.subscopes[1].subscopes[0].get_code()

p = cmpl.parser
s = p.top
import code
sh = code.InteractiveConsole(locals=locals())
#sh.interact("InteractiveConsole")
