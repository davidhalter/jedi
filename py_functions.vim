"py_fuzzycomplete.vim - Omni Completion for python in vim
" Maintainer: David Halter <davidhalter88@gmail.com>
" Version: 0.1
"
" This part of the software is just the vim interface. The main source code
" lies in the python files around it.

if !has('python')
    echo "Error: Required vim compiled with +python"
    finish
endif

function! pythoncomplete#Complete(findstart, base)
    "findstart = 1 when we need to get the text length
    " TODO check wheter this is really needed
    if a:findstart == 1
        let line = getline('.')
        let idx = col('.')
        while idx > 0
            let idx -= 1
            let c = line[idx]
            if c =~ '\w'
                continue
            elseif ! c =~ '\.'
                let idx = -1
                break
            else
                break
            endif
        endwhile

        return idx
    "findstart = 0 when we need to return the list of completions
    else
        execute "python vimcomplete()"
        return g:pythoncomplete_completions
    endif
endfunction

function! s:DefPython()
python << PYTHONEOF
import functions

def vimcomplete():
    (row, column) = vim.current.window.cursor
    code = '\n'.join(vim.current.buffer)
    all = functions.complete(code, row, column)

    dictstr = '['
    # have to do this for double quoting
    for cmpl in all:
        dictstr += '{'
        for x in cmpl: dictstr += '"%s":"%s",' % (x,cmpl[x])
        dictstr += '"icase":0},'
    if dictstr[-1] == ',': dictstr = dictstr[:-1]
    dictstr += ']'
    vim.command("silent let g:pythoncomplete_completions = %s" % dictstr)

PYTHONEOF
endfunction

call s:DefPython()
" vim: set et ts=4:
