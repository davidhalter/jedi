"""
This module is here for string completions. This means mostly stuff where
strings are returned, like `foo = dict(bar=3); foo["ba` would complete to
`"bar"]`.

It however does the same for numbers. The difference between string completions
and other completions is mostly that this module doesn't return defined
names in a module, but pretty much an arbitrary string.
"""
from jedi.inference.names import AbstractArbitraryName
from jedi.api.classes import Completion
from jedi.parser_utils import get_string_quote

_sentinel = object()


class StringName(AbstractArbitraryName):
    api_type = u'string'
    is_value_name = False


def completions_for_dicts(inference_state, dicts, literal_string):
    for dict_key in sorted(_get_python_keys(dicts)):
        dict_key_str = repr(dict_key)
        if dict_key_str.startswith(literal_string):
            name = StringName(inference_state, dict_key_str[len(literal_string):])
            yield Completion(inference_state, name, stack=None, like_name_length=0)


def _get_python_keys(dicts):
    for dct in dicts:
        if dct.array_type == 'dict':
            for key in dct.get_key_values():
                dict_key = key.get_safe_value(default=_sentinel)
                if dict_key is not _sentinel:
                    yield dict_key


def get_quote_ending(start_leaf, code_lines, position):
    if start_leaf.type == 'string':
        quote = get_string_quote(start_leaf)
    else:
        assert start_leaf.type == 'error_leaf'
        quote = start_leaf.value
    potential_other_quote = \
        code_lines[position[0] - 1][position[1]:position[1] + len(quote)]
    # Add a quote only if it's not already there.
    if quote == potential_other_quote:
        return ''
    return quote
