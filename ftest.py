#!/usr/bin/env python

import functions

functions.debug.debug_function = functions.debug.print_to_stdout
functions.debug.ignored_modules = ['parsing', 'builtin']
#functions.debug.ignored_modules = ['parsing', 'builtin', 'evaluate', 'modules']
functions.modules.builtin.module_find_path.insert(0, '.')

f_name = 'functions.py'
#f_name = 'test/completion/classes.py'
import os
path = os.path.join(os.getcwd(), f_name)

f = open(path)
code = f.read()
for i in range(1):
    completions = functions.complete(code, 163, 200, path)
    #completions = functions.get_definitions(code, 181, 2, path)
    #completions = functions.complete(code, 42, 200, path)

print('\n', ', '.join(sorted(str(c) for c in completions)))
#print [n.name for n in completions]
#print [n.name.get_parent_until() for n in completions]
print('#', len(completions))
