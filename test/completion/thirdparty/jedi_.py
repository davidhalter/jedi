
from jedi import functions, evaluate, parsing

el = functions.completions()[0]
#? ['description']
el.description

#? str()
el.description


scopes, path, dot, like = \
    api._prepare_goto(source, row, column, path, True)

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

#? list()
parsing.Scope((0,0)).get_set_vars()
#? parsing.Import() parsing.Name()
parsing.Scope((0,0)).get_set_vars()[0]
# TODO access parent is not possible, because that is not set in the class
## parsing.Class()
parsing.Scope((0,0)).get_set_vars()[0].parent

#? parsing.Import() parsing.Name()
el = list(evaluate.get_names_for_scope())[0][1][0]

#? evaluate.Array() evaluate.Class() evaluate.Function() evaluate.Instance()
list(evaluate.follow_call())[0]

# With the right recursion settings, this should be possible (and maybe more):
# Array Class Function Generator Instance Module
# However, this was produced with the recursion settings 10/350/10000, and
# lasted 18.5 seconds. So we just have to be content with the results.
#? evaluate.Class() evaluate.Function()
evaluate.get_scopes_for_name()[0]
