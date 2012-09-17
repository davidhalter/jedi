if g:jedi#show_function_definition == 1 && has('conceal')
  " conceal is normal for vim >= 7.3

  let e = g:jedi#function_definition_escape
  let l1 = e.'jedi=[^'.e.']*'.e.'[^'.e.']*'.e.'jedi'.e
  let l2 = e.'jedi=\?[^'.e.']*'.e
  exe 'syn match jediIgnore "'.l2.'" contained conceal'
  setlocal conceallevel=2
  syn match jediFatSymbol "*" contained conceal
  syn match jediFat "\*[^*]\+\*" contained contains=jediFatSymbol
  syn match jediSpace "\v[ ]+( )@=" contained
  exe 'syn match jediFunction "'.l1.'" contains=jediIgnore,jediFat,jediSpace'

  hi def link jediIgnore Ignore
  hi def link jediFatSymbol Ignore
  hi def link jediSpace Normal
  hi jediFat term=bold,underline cterm=bold,underline gui=bold,underline ctermbg=0 guibg=Grey
  hi jediFunction term=NONE cterm=NONE ctermfg=6 guifg=Cyan gui=NONE ctermbg=0 guibg=Grey
endif
