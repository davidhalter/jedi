
from jedi import functions, evaluate, parsing

el = functions.complete()[0]
#? ['description']
el.description

#? str()
el.description


scopes, path, dot, like = \
    functions.prepare_goto(source, row, column,
                            source_path, True)

# has problems with that (sometimes) very deep nesting.
#? set()
el = scopes

# get_names_for_scope is also recursion stuff
#? tuple()
el = list(evaluate.get_names_for_scope())[0]

#? int() parsing.Module()
el = list(evaluate.get_names_for_scope(1))[0][0]
#? parsing.Module()
el = list(evaluate.get_names_for_scope())[0][0]

#? list()
el = list(evaluate.get_names_for_scope(1))[0][1]
#? list()
el = list(evaluate.get_names_for_scope())[0][1]

# TODO here should stand evaluate.Instance() and so on.
#? 
el = list(evaluate.get_names_for_scope())[0][1][0]
