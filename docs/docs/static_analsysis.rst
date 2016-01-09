
This file is the start of the documentation of how static analysis works.

Below is a list of parser names that are used within nodes_to_execute.

------------ cared for:
global_stmt
exec_stmt  # no priority
assert_stmt
if_stmt
while_stmt
for_stmt
try_stmt
(except_clause)
with_stmt
(with_item)
(with_var)
print_stmt
del_stmt
return_stmt
raise_stmt
yield_expr
file_input
funcdef
param
old_lambdef
lambdef
import_name
import_from
(import_as_name)
(dotted_as_name)
(import_as_names)
(dotted_as_names)
(dotted_name)
classdef
comp_for
(comp_if) ?
decorator

----------- add basic
test
or_test
and_test
not_test
expr
xor_expr
and_expr
shift_expr
arith_expr
term
factor
power
atom
comparison
expr_stmt
testlist
testlist1
testlist_safe

----------- special care:
# mostly depends on how we handle the other ones.
testlist_star_expr  # should probably just work with expr_stmt
star_expr
exprlist  # just ignore? then names are just resolved. Strange anyway, bc expr is not really allowed in the list, typically.

----------- ignore:
suite
subscriptlist
subscript
simple_stmt
?? sliceop     # can probably just be added.
testlist_comp  # prob ignore and care about it with atom.
dictorsetmaker
trailer
decorators
decorated
# always execute function arguments? -> no problem with stars.
# Also arglist and argument are different in different grammars.
arglist
argument


----------- remove:
tname      # only exists in current Jedi parser. REMOVE!
tfpdef     # python 2: tuple assignment; python 3: annotation
vfpdef     # reduced in python 3 and therefore not existing.
tfplist    # not in 3
vfplist    # not in 3

--------- not existing with parser reductions.
small_stmt
import_stmt
flow_stmt
compound_stmt
stmt
pass_stmt
break_stmt
continue_stmt
comp_op
augassign
old_test
typedargslist  # afaik becomes [param]
varargslist    # dito
vname
comp_iter
test_nocond
