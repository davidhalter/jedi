" ------------------------------------------------------------------------
" completion
" ------------------------------------------------------------------------
function! jedi#complete(findstart, base)
python << PYTHONEOF
if 1:
    vim.eval('jedi#clear_func_def()')
    row, column = vim.current.window.cursor
    if vim.eval('a:findstart') == '1':
        count = 0
        for char in reversed(vim.current.line[:column]):
            if not re.match('[\w\d]', char):
                break
            count += 1
        vim.command('return %i' % (column - count))
    else:
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
            script = get_script(source=source, column=column)
            completions = script.complete()
            call_def = script.get_in_function_call()

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
            completions = []
            call_def = None

        #print 'end', strout
        show_func_def(call_def, len(completions))
        vim.command('return ' + strout)
PYTHONEOF
endfunction


" ------------------------------------------------------------------------
" func_def
" ------------------------------------------------------------------------
function jedi#show_func_def()
    python show_func_def(get_script().get_in_function_call())
    return ''
endfunction


function jedi#clear_func_def()
python << PYTHONEOF
if 1:
    cursor = vim.current.window.cursor
    e = vim.eval('g:jedi#function_definition_escape')
    regex = r'%sjedi=\([^%s]*\)%s.*%sjedi%s'.replace('%s', e)
    vim.command(r'try | %%s/%s/\1/g | catch | endtry' % regex)
    vim.current.window.cursor = cursor
PYTHONEOF
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
function! jedi#rename(...)
python << PYTHONEOF
if 1:
    if not int(vim.eval('a:0')):
        temp_rename = _goto(is_related_name=True, no_output=True)
        _rename_cursor = vim.current.window.cursor

        vim.command('normal A ')  # otherwise startinsert doesn't work well
        vim.current.window.cursor = _rename_cursor

        vim.command('augroup jedi_rename')
        vim.command('autocmd InsertLeave <buffer> call jedi#rename(1)')
        vim.command('augroup END')

        vim.command('normal! diw')
        vim.command(':startinsert')
    else:
        # reset autocommand
        vim.command('autocmd! jedi_rename InsertLeave')

        replace = vim.eval("expand('<cword>')")
        vim.command('normal! u')  # undo new word
        vim.command('normal! u')  # 2u didn't work...

        if replace is None:
            echo_highlight('No rename possible, if no name is given.')
        else:
            for r in temp_rename:
                if r.in_builtin_module():
                    continue
                start_pos = r.start_pos + (0, 1)  # vim cursor starts with 1 indent
                if vim.current.buffer.name != r.module_path:
                    vim.eval("jedi#new_buffer('%s')" % r.module_path)

                vim.current.window.cursor = r.start_pos
                vim.command('normal! cw%s' % replace)

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
        definitions = api.get_definition(source, row, column, buf_path)
    except api.NotFoundError:
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
function! jedi#new_buffer(path)
    if g:jedi#use_tabs_not_buffers
        return jedi#tabnew(a:path)
    else
        if !&hidden && &modified
            w
        endif
        execute 'edit '.a:path
    endif
endfunction


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

function! jedi#configure_function_definition()
    autocmd InsertLeave <buffer> call jedi#clear_func_def()

    " , and () mappings
    inoremap <buffer> ( (<C-R>=jedi#show_func_def()<CR>
    inoremap <buffer> ) )<C-R>=jedi#show_func_def()<CR>
    inoremap <buffer> , ,<C-R>=jedi#show_func_def()<CR>
    inoremap <buffer> <BS> <BS><C-R>=jedi#show_func_def()<CR>
endfunction
