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
" defaults for jedi-vim
" ------------------------------------------------------------------------
if !exists("g:jedi#use_tabs_not_buffers ")
    let g:jedi#use_tabs_not_buffers = 1
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
if !exists("g:jedi#show_function_definition")
    let g:jedi#show_function_definition = 1
endif
if !exists("g:jedi#function_definition_escape")
    let g:jedi#function_definition_escape = '≡'
endif
if !exists("g:jedi#auto_close_doc")
    let g:jedi#auto_close_doc = 1
endif

set switchbuf=useopen  " needed for pydoc
let s:current_file=expand("<sfile>")

python << PYTHONEOF
""" here we initialize the jedi stuff """
import vim

# update the system path, to include the python scripts 
import sys
import os
from os.path import dirname, abspath
sys.path.insert(0, dirname(dirname(abspath(vim.eval('s:current_file')))))

import traceback  # for exception output
import re

# normally you should import jedi. jedi-vim is an exception, because you can
# copy that directly into the .vim directory.
import api

temp_rename = None  # used for jedi#rename

class PythonToVimStr(str):
    """ Vim has a different string implementation of single quotes """
    __slots__ = []
    def __repr__(self):
        return '"%s"' % self.replace('"', r'\"')


def echo_highlight(msg):
    vim.command('echohl WarningMsg | echo "%s" | echohl None' % msg)


def get_script(source=None, column=None):
    if source is None:
        source = '\n'.join(vim.current.buffer)
    row = vim.current.window.cursor[0]
    if column is None:
        column = vim.current.window.cursor[1]
    buf_path = vim.current.buffer.name
    return api.Script(source, row, column, buf_path)


def _goto(is_definition=False, is_related_name=False, no_output=False):
    definitions = []
    script = get_script()
    try:
        if is_related_name:
            definitions = script.related_names()
        elif is_definition:
            definitions = script.get_definition()
        else:
            definitions = script.goto()
    except api.NotFoundError:
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
                if isinstance(d.definition, api.keywords.Keyword):
                    echo_highlight("Cannot get the definition of Python keywords.")
                else:
                    echo_highlight("Builtin modules cannot be displayed.")
            else:
                if d.module_path != vim.current.buffer.name:
                    if vim.eval('g:jedi#use_tabs_not_buffers') == '1':
                        vim.command('call jedi#tabnew("%s")' % d.module_path)
                    else:
                        vim.command('edit ' + d.module_path)
                vim.current.window.cursor = d.line_nr, d.column
                vim.command('normal! zt')  # cursor at top of screen
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


def show_func_def(call_def, completion_lines=0):

    if call_def is None:
        return

    vim.eval('jedi#clear_func_def()')
    row, column = call_def.bracket_start
    if column < 2 or row == 0:
        return  # edge cases, just ignore

    row_to_replace = row - 1  # TODO check if completion menu is above or below
    line = vim.eval("getline(%s)" % row_to_replace)

    insert_column = column - 2 # because it has stuff at the beginning

    params = [p.get_code().replace('\n', '') for p in call_def.params]
    try:
        params[call_def.index] = '*%s*' % params[call_def.index]
    except (IndexError, TypeError):
        pass

    text = " (%s) " % ', '.join(params)
    text = ' ' * (insert_column - len(line)) + text
    end_column = insert_column + len(text) - 2  # -2 because of bold symbols
    # replace line before with cursor
    e = vim.eval('g:jedi#function_definition_escape')
    regex = "xjedi=%sx%sxjedix".replace('x', e)
    repl = ("%s" + regex + "%s") % (line[:insert_column],
                    line[insert_column:end_column], text, line[end_column:])
    vim.eval('setline(%s, "%s")' % (row_to_replace, repl))
PYTHONEOF

" vim: set et ts=4:
