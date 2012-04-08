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
" Completion
" ------------------------------------------------------------------------

function! jedi#Complete(findstart, base)
    if a:findstart == 1
        return col('.')
    else
python << PYTHONEOF
if 1:
        # TODO change the finstart column, to switch cases, if they are not right.
        row, column = vim.current.window.cursor
        buf_path = vim.current.buffer.name
        source = '\n'.join(vim.current.buffer)
        try:
            completions = functions.complete(source, row, column, buf_path)
            out = []
            for c in completions:
                d = dict(word=c.complete,
                         abbr=str(c),
                         menu=c.description,  # stuff directly behind the completion
                         info=c.help,  # docstr and similar stuff
                         kind=c.get_vim_type(),  # completion type
                         icase=1,  # case insensitive
                         dup=1,  # allow duplicates (maybe later remove this)
                )
                out.append(d)

            strout = str(out)
        except Exception as e:
            # print to stdout, will be in :messages
            print(traceback.format_exc())
            strout = ''

        #print 'end', strout
        vim.command('return ' + strout)
PYTHONEOF
    endif
endfunction


" ------------------------------------------------------------------------
" Initialization of Jedi
" ------------------------------------------------------------------------

let s:current_file=expand("<sfile>")

python << PYTHONEOF
""" here we initialize the jedi stuff """
import vim

# update the system path, to include the python scripts 
import sys
from os.path import dirname
sys.path.insert(0, dirname(dirname(vim.eval('s:current_file'))))

import traceback  # for exception output

import functions
PYTHONEOF

" vim: set et ts=4:
