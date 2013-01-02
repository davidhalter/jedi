"""
This module contains variables with global |jedi| setting. To change the
behavior of |jedi|, change the variables defined in
:mod:`jedi.settings`.

Plugins should expose an interface so that the user can adjust the
configuration.


Example usage::

    from jedi import settings
    settings.case_insensitive_completion = True


Completion output
~~~~~~~~~~~~~~~~~

.. autodata:: case_insensitive_completion
.. autodata:: add_dot_after_module
.. autodata:: add_bracket_after_function
.. autodata:: no_completion_duplicates


Parser
~~~~~~

.. autodata:: fast_parser
.. autodata:: fast_parser_always_reparse
.. autodata:: use_get_in_function_call_cache


Dynamic stuff
~~~~~~~~~~~~~

.. autodata:: dynamic_arrays_instances
.. autodata:: dynamic_array_additions
.. autodata:: dynamic_params
.. autodata:: dynamic_params_for_other_modules
.. autodata:: additional_dynamic_modules


Recursions
~~~~~~~~~~

Recursion settings are important if you don't want extremly
recursive python code to go absolutely crazy. First of there is a
global limit :data:`max_executions`. This limit is important, to set
a maximum amount of time, the completion may use.

The default values are based on experiments while completing the |jedi| library
itself (inception!). But I don't think there's any other Python library that
uses recursion in a similarly extreme way. These settings make the completion
definitely worse in some cases. But a completion should also be fast.

.. autodata:: max_until_execution_unique
.. autodata:: max_function_recursion_level
.. autodata:: max_executions_without_builtins
.. autodata:: max_executions
.. autodata:: scale_get_in_function_call


Caching
~~~~~~~

.. autodata:: star_import_cache_validity
.. autodata:: get_in_function_call_validity


Various
~~~~~~~

.. autodata:: part_line_length


"""

# ----------------
# completion output settings
# ----------------

case_insensitive_completion = True
"""
The completion is by default case insensitive.
"""

add_dot_after_module = False
"""
Adds a dot after a module, because a module that is not accessed this way is
definitely not the normal case. However, in VIM this doesn't work, that's why
it isn't used at the moment.
"""

add_bracket_after_function = False
"""
Adds an opening bracket after a function, because that's normal behaviour.
Removed it again, because in VIM that is not very practical.
"""

no_completion_duplicates = True
"""
If set, completions with the same name don't appear in the output anymore,
but are in the `same_name_completions` attribute.
"""

# ----------------
# parser
# ----------------

fast_parser = True
"""
Use the fast parser. This means that reparsing is only being done if
something has been changed e.g. to a function. If this happens, only the
function is being reparsed.
"""

fast_parser_always_reparse = False
"""
This is just a debugging option. Always reparsing means that the fast parser
is basically useless. So don't use it.
"""

use_get_in_function_call_cache = True
"""
Use the cache (full cache) to generate get_in_function_call's. This may fail
with multiline docstrings (likely) and other complicated changes (unlikely).
The goal is to move away from it by making the rest faster.
"""

# ----------------
# dynamic stuff
# ----------------

dynamic_arrays_instances = True
"""
Check for `append`, etc. on array instances like list()
"""

dynamic_array_additions = True
"""
check for `append`, etc. on arrays: [], {}, ()
"""

dynamic_params = True
"""
A dynamic param completion, finds the callees of the function, which define
the params of a function.
"""

dynamic_params_for_other_modules = True
"""
Do the same for other modules.
"""

additional_dynamic_modules = []
"""
Additional modules in which |jedi| checks if statements are to be found. This
is practical for IDEs, that want to administrate their modules themselves.
"""

# ----------------
# recursions
# ----------------

max_until_execution_unique = 50
"""
This limit is probably the most important one, because if this limit is
exceeded, functions can only be one time executed. So new functions will be
executed, complex recursions with the same functions again and again, are
ignored.
"""

max_function_recursion_level = 5
"""
`max_function_recursion_level` is more about whether the recursions are
stopped in deepth or in width. The ratio beetween this and
`max_until_execution_unique` is important here. It stops a recursion (after
the number of function calls in the recursion), if it was already used
earlier.
"""

max_executions_without_builtins = 200
"""
.. todo:: Document this.
"""

max_executions = 250
"""
A maximum amount of time, the completion may use.
"""

scale_get_in_function_call = 0.1
"""
Because get_in_function_call is normally used on every single key hit, it has
to be faster than a normal completion. This is the factor that is used to
scale `max_executions` and `max_until_execution_unique`:
"""

# ----------------
# various
# ----------------

part_line_length = 20
"""
Size of the current code part, which is used to speed up parsing.
"""

# ----------------
# caching validity (time)
# ----------------


star_import_cache_validity = 60.0
"""
In huge packages like numpy, checking all star imports on every completion
might be slow, therefore we do a star import caching, that lasts a certain
time span (in seconds).
"""

get_in_function_call_validity = 3.0
"""
Finding function calls might be slow (0.1-0.5s). This is not acceptible for
normal writing. Therefore cache it for a short time.
"""
