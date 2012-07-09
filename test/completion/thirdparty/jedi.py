
from jedi import functions, evaluate

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
el = scopes.

#? str() <--- recursion
el = evaluate.get_names_for_scope()[0].
