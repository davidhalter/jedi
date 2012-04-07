#!/usr/bin/env python

import functions

functions.debug.debug_function = functions.debug.print_to_stdout
functions.debug.ignored_modules += ['parsing', 'builtin']
functions.modules.module_find_path.insert(0, '.')

with open('test.py') as f:
    code = f.read()
for i in range(1):
    completions = functions.complete(code, 50, 200)

print '\n', ', '.join(str(c) for c in completions)
