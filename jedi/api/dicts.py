from jedi.inference.names import AbstractArbitraryName
from jedi.api.classes import Completion

_sentinel = object()


class F(AbstractArbitraryName):
    api_type = u'path'
    is_value_name = False


def completions_for_dicts(inference_state, dicts, literal_string):
    for dict_key in sorted(_get_python_keys(dicts)):
        dict_key_str = repr(dict_key)
        if dict_key_str.startswith(literal_string):
            name = F(inference_state, dict_key_str[len(literal_string):])
            yield Completion(inference_state, name, stack=None, like_name_length=0)


def _get_python_keys(dicts):
    for dct in dicts:
        if dct.array_type == 'dict':
            for key in dct.get_key_values():
                dict_key = key.get_safe_value(default=_sentinel)
                if dict_key is not _sentinel:
                    yield dict_key
