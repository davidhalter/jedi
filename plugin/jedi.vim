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

" load plugin only once
if exists("g:loaded_jedi") || &cp
    finish
endif
let g:loaded_jedi = 1

" ------------------------------------------------------------------------
" completion
" ------------------------------------------------------------------------

function! jedi#complete(findstart, base)
python << PYTHONEOF
if 1:
    row, column = vim.current.window.cursor
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
    def echo_highlight(msg):
        vim.command('echohl WarningMsg | echo "%s" | echohl None' % msg)

    row, column = vim.current.window.cursor
    buf_path = vim.current.buffer.name
    source = '\n'.join(vim.current.buffer)
    try:
        definitions = functions.goto(source, row, column, buf_path)
    except functions.NotFoundError:
        echo_highlight("Couldn't find a place to goto.")
    except Exception:
        # print to stdout, will be in :messages
        echo_highlight("Some different eror, this shouldn't happen.")
        print(traceback.format_exc())
    else:
        if not definitions:
            echo_highlight("Couldn't find any definitions for this.")
        elif len(definitions) == 1:
            # just add some mark to add the current position to the jumplist.
            # this is ugly, because it overrides the mark for '`', so if anyone
            # has a better idea, let me know.
            vim.command('normal! m`')

            d = definitions[0]
            if d.in_builtin_module():
                echo_highlight("Builtin modules cannot be displayed.")
            else:
                if d.module_path != vim.current.buffer.name:
                    if vim.eval('g:jedi#use_tabs_not_buffers') == '1':
                        vim.command('call jedi#tabnew("%s")' % d.module_path)
                    else:
                        vim.command('edit ' + d.module_path)
                vim.current.window.cursor = d.line_nr, d.column
        else:
            # multiple solutions
            lst = []
            for d in definitions:
                if d.in_builtin_module():
                    lst.append(dict(text='Builtin ' + d.description))
                else:
                    lst.append(dict(filename=d.module_path, lnum=d.line_nr, col=d.column, text=d.description))
            vim.command('call setqflist(%s)' % str(lst))
            vim.command('call <sid>add_goto_window()')

    #print 'end', strout
PYTHONEOF
endfunction

function! jedi#tabnew(path)
python << PYTHONEOF
if 1:
    path = vim.eval('a:path')
    for tab_nr in range(int(vim.eval("tabpagenr('$')"))):
        for buf_nr in vim.eval("tabpagebuflist(%i + 1)" % tab_nr):
            buf_nr = int(buf_nr) - 1
            try:
                buf_path = vim.buffers[buf_nr].name
            except IndexError:
                # just do good old asking for forgiveness. don't know why this happens :-)
                pass
            else:
                if buf_path == path:
                    # tab exists, just switch to that tab
                    vim.command('tabfirst | tabnext %i' % (tab_nr + 1))
                    break
        else:
            continue
        break
    else:
        # tab doesn't exist, add a new one.
        vim.command('tabnew %s' % path)
PYTHONEOF
endfunction

function! s:add_goto_window()
    set lazyredraw
    cclose
    execute 'belowright copen 3'
    set nolazyredraw
    if g:jedi#use_tabs_not_buffers == 1
        map <buffer> <CR> :call jedi#goto_window_on_enter()<CR>
    endif
    au WinLeave <buffer> q  " automatically leave, if an option is chosen
    redraw!
endfunction

function! jedi#goto_window_on_enter()
    let l:list = getqflist()
    let l:data = l:list[line('.') - 1]
    if l:data.bufnr
        call jedi#tabnew(bufname(l:data.bufnr))
        call cursor(l:data.lnum, l:data.col)
    else
        echohl WarningMsg | echo "Builtin module cannot be opened." | echohl None
    endif
endfunction
" ------------------------------------------------------------------------
" Initialization of jedi-vim
" ------------------------------------------------------------------------

" defaults for jedi-vim
let g:jedi#use_tabs_not_buffers = 0

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
