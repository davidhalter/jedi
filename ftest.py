#!/usr/bin/env python

import functions

#functions.debug.debug_function
functions.debug.ignored_modules += ['parsing', 'functions']
functions.modules.module_find_path.insert(0, '.')

with open('test.py') as f:
    code = f.read()
completions = functions.complete(code, 50, 20)

print '\n', [c.names for c in completions]
