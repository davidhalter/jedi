#!/usr/bin/env python

import functions

functions.debug.debug_function = functions.debug.print_to_stdout
#functions.debug.ignored_modules += ['parsing', 'builtin']
functions.debug.ignored_modules += ['parsing', 'builtin', 'evaluate', 'modules']
functions.modules.module_find_path.insert(0, '.')

f_name = 'test.py'
import os
path = os.getcwd() + '/' + f_name

with open(path) as f:
    code = f.read()
for i in range(1):
    completions = functions.complete(code, 150, 200, path)

print '\n', ', '.join(str(c) for c in completions)
