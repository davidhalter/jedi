"""
This module is here for string completions. This means mostly stuff where
strings are returned, like `foo = dict(bar=3); foo["ba` would complete to
`"bar"]`.

It however does the same for numbers. The difference between string completions
and other completions is mostly that this module doesn't return defined
names in a module, but pretty much an arbitrary string.
"""
import re

from jedi._compatibility import unicode
from jedi.inference.names import AbstractArbitraryName
from jedi.inference.helpers import infer_call_of_leaf
from jedi.api.classes import Completion
from jedi.parser_utils import cut_value_at_position

_sentinel = object()


class StringName(AbstractArbitraryName):
    api_type = u'string'
    is_value_name = False


def complete_dict(module_context, leaf, position, string, fuzzy):
    if string is None:
        string = ''
    bracket_leaf = leaf
    end_quote = ''
    if bracket_leaf.type in ('number', 'error_leaf'):
        string = cut_value_at_position(bracket_leaf, position)
        if bracket_leaf.end_pos > position:
            end_quote = _get_string_quote(string) or ''
            if end_quote:
                ending = cut_value_at_position(
                    bracket_leaf,
                    (position[0], position[1] + len(end_quote))
                )
                if not ending.endswith(end_quote):
                    end_quote = ''

        bracket_leaf = bracket_leaf.get_previous_leaf()

    if bracket_leaf == '[':
        context = module_context.create_context(bracket_leaf)
        before_bracket_leaf = bracket_leaf.get_previous_leaf()
        if before_bracket_leaf.type in ('atom', 'trailer', 'name'):
            values = infer_call_of_leaf(context, before_bracket_leaf)
            return list(_completions_for_dicts(
                module_context.inference_state,
                values,
                '' if string is None else string,
                end_quote,
                fuzzy=fuzzy,
            ))
    return []


def _completions_for_dicts(inference_state, dicts, literal_string, end_quote, fuzzy):
    for dict_key in sorted(_get_python_keys(dicts), key=lambda x: repr(x)):
        dict_key_str = _create_repr_string(literal_string, dict_key)
        if dict_key_str.startswith(literal_string):
            n = dict_key_str[len(literal_string):-len(end_quote) or None]
            name = StringName(inference_state, n)
            yield Completion(
                inference_state,
                name,
                stack=None,
                like_name_length=0,
                is_fuzzy=fuzzy
            )


def _create_repr_string(literal_string, dict_key):
    if not isinstance(dict_key, (unicode, bytes)) or not literal_string:
        return repr(dict_key)

    r = repr(dict_key)
    prefix, quote = _get_string_prefix_and_quote(literal_string)
    if quote == r[0]:
        return prefix + r
    return prefix + quote + r[1:-1] + quote


def _get_python_keys(dicts):
    for dct in dicts:
        if dct.array_type == 'dict':
            for key in dct.get_key_values():
                dict_key = key.get_safe_value(default=_sentinel)
                if dict_key is not _sentinel:
                    yield dict_key


def _get_string_prefix_and_quote(string):
    match = re.match(r'(\w*)("""|\'{3}|"|\')', string)
    if match is None:
        return None, None
    return match.group(1), match.group(2)


def _get_string_quote(string):
    return _get_string_prefix_and_quote(string)[1]


def get_quote_ending(start_leaf, code_lines, position):
    if start_leaf.type == 'string':
        quote = _get_string_quote(start_leaf)
    else:
        assert start_leaf.type == 'error_leaf'
        quote = start_leaf.value
    potential_other_quote = \
        code_lines[position[0] - 1][position[1]:position[1] + len(quote)]
    # Add a quote only if it's not already there.
    if quote == potential_other_quote:
        return ''
    return quote
