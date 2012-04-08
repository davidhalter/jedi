#!/usr/bin/env python

import functions

#functions.debug.debug_function = functions.debug.print_to_stdout
functions.debug.ignored_modules += ['parsing', 'builtin']
functions.modules.module_find_path.insert(0, '.')

with open('test.py') as f:
    code = f.read()
for i in range(1):
    completions = functions.complete(code, 50, 200)

print '\n', ', '.join(str(c) for c in completions)

out = []
for c in completions:
    d = dict(word=str(c),
             abbr=c.complete,
             menu=c.description,  # the stuff directly behind the completion
             info=c.help,  # docstr and similar stuff
             kind=c.type,  # completion type
             icase=1,  # case insensitive
             dup=1,  # allow duplicates (maybe later remove this)
    )
    out.append(d)

print str(out)
