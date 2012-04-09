#!/usr/bin/env python
# python >= 2.4 working with readmodule_ex
import parsing
import functions

functions.debug.debug_function = functions.debug.print_to_stdout

text = open('test.py').read()
p = parsing.PyFuzzyParser(text)


print p.top.get_code()
#print cmpl.parser.top.subscopes[1].subscopes[0].get_code()

def handle_names(names):
    #print names
    for n in names:
        try:
            print n.names
        except AttributeError:
            print 'star!', n.from_ns

"""
print 'global names:'
names = p.top.get_set_vars()
handle_names(names)

print
print 'func names:'
names = p.top.subscopes[7].get_set_vars()
handle_names(names)

print
print 'class names:'
names = p.top.subscopes[2].get_set_vars()
handle_names(names)
for s in p.top.subscopes[2].subscopes:
    print 'method names:'
    names = s.get_set_vars()
    handle_names(names)

print
print 'start/end'
for s in p.top.subscopes:
    print repr(s)
"""

s = p.top
import code
sh = code.InteractiveConsole(locals=locals())
sh.interact("InteractiveConsole")
