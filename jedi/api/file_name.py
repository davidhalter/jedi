import os

from jedi.evaluate.names import AbstractArbitraryName


def file_name_completions(evaluator, string, like_name):
    base_path = os.path.join(evaluator.project._path, string)
    print(string, base_path)
    for name in os.listdir(base_path):
        if name.startswith(like_name):
            path_for_name = os.path.join(base_path, name)
            if os.path.isdir(path_for_name):
                name += os.path.sep
            yield FileName(evaluator, name)


class FileName(AbstractArbitraryName):
    api_type = u'path'
    is_context_name = False
