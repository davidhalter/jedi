# ----------------
# completion output settings
# ----------------

# The completion is by default case insensitive.
case_insensitive_completion = True

# Adds a dot after a module, because a module that is not accessed this way is
# definitely not the normal case. However, in VIM this doesn't work, that's why
# it isn't used at the moment.
add_dot_after_module = False

# Adds an opening bracket after a function, because that's normal behaviour.
# Removed it again, because in VIM that is not very practical.
add_bracket_after_function = False


# ----------------
# dynamic stuff
# ----------------

# check for `append`, etc. on array instances like list()
dynamic_arrays_instances = True
# check for `append`, etc. on arrays: [], {}, ()
dynamic_array_additions = True

# A dynamic param completion, finds the callees of the function, which define
# the params of a function.
dynamic_params = True
# Do the same for other modules.
dynamic_params_for_other_modules = True

# Additional modules in which Jedi checks if statements are to be found. This
# is practical for IDE's, that want to administrate their modules themselves.
additional_dynamic_modules = []

# ----------------
# recursions
# ----------------

# Recursion settings are important if you don't want extremly recursive python
# code to go absolutely crazy. First of there is a global limit
# `max_executions`. This limit is important, to set a maximum amount of time,
# the completion may use.
#
# The `max_until_execution_unique` limit is probably the most important one,
# because if that limit is passed, functions can only be one time executed. So
# new functions will be executed, complex recursions with the same functions
# again and again, are ignored.
#
# `max_function_recursion_level` is more about whether the recursions are
# stopped in deepth or in width. The ratio beetween this and
# `max_until_execution_unique` is important here. It stops a recursion (after
# the number of function calls in the recursion), if it was already used
# earlier.
#
# The values are based on my experimental tries, used on the jedi library. But
# I don't think there's any other Python library, that uses recursion in a
# similar (extreme) way. This makes the completion definitely worse in some
# cases. But a completion should also be fast.

max_function_recursion_level = 5
max_until_execution_unique = 50
max_executions = 1000
