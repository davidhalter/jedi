
" ------------------------------------------------------------------------
" Initialization of jedi-vim
" ------------------------------------------------------------------------

if g:jedi#auto_initialization
    setlocal omnifunc=jedi#complete
    " map ctrl+space for autocompletion
    inoremap <buffer> <Nul> <C-X><C-O>

    " goto / get_definition / related_names
    execute "noremap <buffer>".g:jedi#goto_command." :call jedi#goto()<CR>"
    execute "noremap <buffer>".g:jedi#get_definition_command." :call jedi#get_definition()<CR>"
    execute "noremap <buffer>".g:jedi#related_names_command." :call jedi#related_names()<CR>"
    " rename
    execute "noremap <buffer>".g:jedi#rename_command." :call jedi#rename()<CR>"
    " pydoc
    execute "nnoremap <silent> <buffer>".g:jedi#pydoc." :call jedi#show_pydoc()<CR>"

    if g:jedi#show_function_definition == 1 && has('conceal')
        call jedi#configure_function_definition()
    endif
end

if g:jedi#popup_on_dot
    inoremap <buffer> . .<C-R>=jedi#do_popup_on_dot() ? "\<lt>C-X>\<lt>C-O>" : ""<CR>
end

if g:jedi#auto_close_doc
    " close preview if its still open after insert
    autocmd InsertLeave <buffer> if pumvisible() == 0|pclose|endif
end
