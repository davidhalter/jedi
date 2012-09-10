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
                d = dict(word=c.word[:len(base)] + c.complete,
                         abbr=c.word,
                         # stuff directly behind the completion
                         menu=PythonToVimStr(c.description),
                         info=PythonToVimStr(c.doc),  # docstr
                         icase=1,  # case insensitive
                         dup=1  # allow duplicates (maybe later remove this)
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
    python _goto()
endfunction

" ------------------------------------------------------------------------
" get_definition
" ------------------------------------------------------------------------
function! jedi#get_definition()
    python _goto(is_definition=True)
endfunction

" ------------------------------------------------------------------------
" related_names
" ------------------------------------------------------------------------
function! jedi#related_names()
    python _goto(is_related_name=True)
endfunction

" ------------------------------------------------------------------------
" rename
" ------------------------------------------------------------------------
function! jedi#rename()
python << PYTHONEOF
if 1:
    if temp_rename is None:
        temp_rename = _goto(is_related_name=True, no_output=True)
        _rename_cursor = vim.current.window.cursor

        vim.command('normal A ')  # otherwise startinsert doesn't work well
        vim.current.window.cursor = _rename_cursor

        vim.command('augroup jedi_rename')
        vim.command('autocmd InsertLeave * call jedi#rename()')
        vim.command('augroup END')

        vim.command('normal! diw')
        vim.command(':startinsert')
    else:
        current_buf = vim.current.buffer.name
        replace = vim.eval("expand('<cword>')")
        vim.command('normal! u')  # undo new word
        vim.command('normal! u')  # 2u didn't work...

        for r in temp_rename:
            start_pos = r.start_pos + (0, 1)  # vim cursor starts with 1 indent
            # TODO switch modules
            if vim.current.buffer.name == r.module_path:
                vim.current.window.cursor = r.start_pos
                vim.command('normal! cw%s' % replace)

        # reset autocommand
        vim.command('autocmd! jedi_rename InsertLeave')

        echo_highlight('Jedi did %s renames!' % len(temp_rename))
        # reset rename variables
        temp_rename = None
PYTHONEOF
endfunction

" ------------------------------------------------------------------------
" show_pydoc
" ------------------------------------------------------------------------
function! jedi#show_pydoc()
python << PYTHONEOF
if 1:
    row, column = vim.current.window.cursor
    buf_path = vim.current.buffer.name
    source = '\n'.join(vim.current.buffer)
    try:
        definitions = functions.get_definition(source, row, column, buf_path)
    except functions.NotFoundError:
        definitions = []
    except Exception:
        # print to stdout, will be in :messages
        definitions = []
        print("Exception, this shouldn't happen.")
        print(traceback.format_exc())

    if not definitions:
        vim.command('return')
    else:
        docs = ['Docstring for %s\n%s\n%s' % (d.desc_with_module, '='*40, d.doc) if d.doc
                    else '|No Docstring for %s|' % d for d in definitions]
        text = ('\n' + '-' * 79 + '\n').join(docs)
        vim.command('let l:doc = %s' % repr(PythonToVimStr(text)))
        vim.command('let l:doc_lines = %s' % len(text.split('\n')))
PYTHONEOF
    if bufnr("__doc__") > 0
        " If the __doc__ buffer is open in the current window, jump to it
        silent execute "sbuffer ".bufnr("__doc__")
    else
        split '__doc__'
    endif

    setlocal modifiable
    setlocal noswapfile
    setlocal buftype=nofile
    silent normal! ggdG
    silent $put=l:doc
    silent normal! 1Gdd
    setlocal nomodifiable
    setlocal nomodified
    setlocal filetype=rst

    if l:doc_lines > 30  " max lines for plugin
        let l:doc_lines = 30
    endif
    execute "resize ".l:doc_lines

    " quit comands
    nnoremap <buffer> q ZQ
    nnoremap <buffer> K ZQ

    " highlight python code within rst
    unlet! b:current_syntax
    syn include @rstPythonScript syntax/python.vim
    " 4 spaces
    syn region rstPythonRegion start=/^\v {4}/ end=/\v^( {4}|\n)@!/ contains=@rstPythonScript
    " >>> python code -> (doctests)
    syn region rstPythonRegion matchgroup=pythonDoctest start=/^>>>\s*/ end=/\n/ contains=@rstPythonScript
    let b:current_syntax = "rst"
endfunction

" ------------------------------------------------------------------------
" helper functions
" ------------------------------------------------------------------------
function! jedi#tabnew(path)
python << PYTHONEOF
if 1:
    path = os.path.abspath(vim.eval('a:path'))
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
        " close goto_window buffer
        normal ZQ
        call jedi#tabnew(bufname(l:data.bufnr))
        call cursor(l:data.lnum, l:data.col)
    else
        echohl WarningMsg | echo "Builtin module cannot be opened." | echohl None
    endif
endfunction

function! jedi#syn_stack()
    if !exists("*synstack")
        return []
    endif
    return map(synstack(line('.'), col('.') - 1), 'synIDattr(v:val, "name")')
endfunc

function! jedi#do_popup_on_dot()
    let highlight_groups = jedi#syn_stack()
    for a in highlight_groups
        if a == 'pythonDoctest'
            return 1
        endif
    endfor

    for a in highlight_groups
        for b in ['pythonString', 'pythonComment']
            if a == b
                return 0 
            endif
        endfor
    endfor
    return 1
endfunc

" ------------------------------------------------------------------------
" Initialization of jedi-vim
" ------------------------------------------------------------------------

" defaults for jedi-vim
if !exists("g:jedi#use_tabs_not_buffers ")
    let g:jedi#use_tabs_not_buffers = 0
endif
if !exists("g:jedi#auto_initialization")
    let g:jedi#auto_initialization = 1
endif
if !exists("g:jedi#goto_command")
    let g:jedi#goto_command = "<leader>g"
endif
if !exists("g:jedi#get_definition_command")
    let g:jedi#get_definition_command = "<leader>d"
endif
if !exists("g:jedi#related_names_command")
    let g:jedi#related_names_command = "<leader>n"
endif
if !exists("g:jedi#rename_command")
    let g:jedi#rename_command = "<leader>r"
endif
if !exists("g:jedi#popup_on_dot")
    let g:jedi#popup_on_dot = 1
endif
if !exists("g:jedi#pydoc")
    let g:jedi#pydoc = "K"
endif

if g:jedi#auto_initialization
    autocmd FileType python setlocal omnifunc=jedi#complete
    " map ctrl+space for autocompletion
    autocmd FileType python inoremap <buffer> <Nul> <C-X><C-O>

    " goto / get_definition / related_names
    autocmd FileType python execute "noremap <buffer>".g:jedi#goto_command." :call jedi#goto()<CR>"
    autocmd FileType python execute "noremap <buffer>".g:jedi#get_definition_command." :call jedi#get_definition()<CR>"
    autocmd FileType python execute "noremap <buffer>".g:jedi#related_names_command." :call jedi#related_names()<CR>"
    " rename
    autocmd FileType python execute "noremap <buffer>".g:jedi#rename_command." :call jedi#rename()<CR>"
    " pydoc
    autocmd FileType python execute "nnoremap <silent> <buffer>".g:jedi#pydoc." :call jedi#show_pydoc()<CR>"
end

if g:jedi#popup_on_dot
    autocmd FileType python inoremap <buffer> . .<C-R>=jedi#do_popup_on_dot() ? "\<lt>C-X>\<lt>C-O>" : ""<CR>
end

set switchbuf=useopen  " needed for pydoc
let s:current_file=expand("<sfile>")

python << PYTHONEOF
""" here we initialize the jedi stuff """
import vim

# update the system path, to include the python scripts 
import sys
import os
from os.path import dirname
sys.path.insert(0, dirname(dirname(vim.eval('s:current_file'))))

import traceback  # for exception output
import re

# normally you should import jedi. jedi-vim is an exception, because you can
# copy that directly into the .vim directory.
import functions

temp_rename = None  # used for jedi#rename

class PythonToVimStr(str):
    """ Vim has a different string implementation of single quotes """
    __slots__ = []
    def __repr__(self):
        return '"%s"' % self.replace('"', r'\"')

def echo_highlight(msg):
    vim.command('echohl WarningMsg | echo "%s" | echohl None' % msg)

def _goto(is_definition=False, is_related_name=False, no_output=False):
    definitions = []
    row, column = vim.current.window.cursor
    buf_path = vim.current.buffer.name
    source = '\n'.join(vim.current.buffer)
    try:
        if is_related_name:
            definitions = functions.related_names(source, row, column, buf_path)
        elif is_definition:
            definitions = functions.get_definition(source, row, column, buf_path)
        else:
            definitions = functions.goto(source, row, column, buf_path)
    except functions.NotFoundError:
        echo_highlight("Cannot follow nothing. Put your cursor on a valid name.")
    except Exception:
        # print to stdout, will be in :messages
        echo_highlight("Some different eror, this shouldn't happen.")
        print(traceback.format_exc())
    else:
        if no_output:
            return definitions
        if not definitions:
            echo_highlight("Couldn't find any definitions for this.")
        elif len(definitions) == 1 and not is_related_name:
            # just add some mark to add the current position to the jumplist.
            # this is ugly, because it overrides the mark for '`', so if anyone
            # has a better idea, let me know.
            vim.command('normal! m`')

            d = list(definitions)[0]
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
                    lst.append(dict(filename=d.module_path, lnum=d.line_nr, col=d.column+1, text=d.description))
            vim.command('call setqflist(%s)' % str(lst))
            vim.command('call <sid>add_goto_window()')
    return definitions
PYTHONEOF

" vim: set et ts=4:
