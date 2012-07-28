"py_fuzzycomplete.vim - Omni Completion for python in vim
" Maintainer: David Halter <davidhalter88@gmail.com>
" Version: 0.1
"
" This part of the software is just the vim interface. The main source code
" lies in the python files around it.

if !has('python')
    echomsg "Error: Required vim compiled with +python"
    finish
endif

" ------------------------------------------------------------------------
" completion
" ------------------------------------------------------------------------

function! jedi#Complete(findstart, base)
python << PYTHONEOF
if 1:
    row, column = vim.current.window.cursor
    print 
    if vim.eval('a:findstart') == '1':
        count = 0
        for char in reversed(vim.current.line[:column]):
            if not re.match('[\w\d]', char):
                break
            count += 1
        vim.command('return %i' % (column - count))
    else:
        buf_path = vim.current.buffer.name
        base = vim.eval('a:base')
        source = ''
        for i, line in enumerate(vim.current.buffer):
            # enter this path again, otherwise source would be incomplete
            if i == row - 1:
                source += line[:column] + base + line[column:]
            else:
                source += line
            source += '\n'
        # here again, the hacks, because jedi has a different interface than vim
        column += len(base)
        try:
            completions = functions.complete(source, row, column, buf_path)
            out = []
            for c in completions:
                d = dict(word=str(c),
                         abbr=str(c),
                         # stuff directly behind the completion
                         # TODO change it so that ' are allowed (not used now, because of repr)
                         menu=c.description.replace("'", '"'),
                         info=c.help,  # docstr and similar stuff
                         kind=c.get_vim_type(),  # completion type
                         icase=1,  # case insensitive
                         dup=1,  # allow duplicates (maybe later remove this)
                )
                out.append(d)

            strout = str(out)
        except Exception:
            # print to stdout, will be in :messages
            print(traceback.format_exc())
            strout = ''

        #print 'end', strout
        vim.command('return ' + strout)
PYTHONEOF
    endif
endfunction


" ------------------------------------------------------------------------
" goto
" ------------------------------------------------------------------------

function! jedi#goto()
python << PYTHONEOF
if 1:
    row, column = vim.current.window.cursor
    buf_path = vim.current.buffer.name
    source = '\n'.join(vim.current.buffer)
    try:
        definitions = functions.goto(source, row, column, buf_path)
    except functions.NotFoundError:
        msg = 'There is no useful expression under the cursor'
    except Exception:
        # print to stdout, will be in :messages
        print(traceback.format_exc())
        msg = "Some different eror, this shouldn't happen"
    else:
        msg = ', '.join(sorted(str(d) for d in definitions))
        if not msg:
            msg = "No definitions found!"
    vim.command('''echomsg "%s"''' % msg)

    #print 'end', strout
PYTHONEOF
endfunction

" ------------------------------------------------------------------------
" Initialization of Jedi
" ------------------------------------------------------------------------

" defaults for jedi
let g:use_tabs_not_buffers = 0

let s:current_file=expand("<sfile>")

python << PYTHONEOF
""" here we initialize the jedi stuff """
import vim

# update the system path, to include the python scripts 
import sys
from os.path import dirname
sys.path.insert(0, dirname(dirname(vim.eval('s:current_file'))))

import traceback  # for exception output
import re

import functions
PYTHONEOF

" vim: set et ts=4:
