from jedi.inference.names import AbstractArbitraryName

_sentinel = object()


class F(AbstractArbitraryName):
    api_type = u'path'
    is_value_name = False


def completions_for_dicts(dicts, literal_string):
    for dct in dicts:
        if dct.array_type == 'dict':
            for key in dct.get_key_values():
                dict_key = key.get_safe_value(default=_sentinel)
                if dict_key is not _sentinel:
                    dict_key_str = str(dict_key)
                    if dict_key_str.startswith(literal_string):
                        yield F(dct.inference_state, dict_key_str[len(literal_string):])
