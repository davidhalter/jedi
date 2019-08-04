import os

from jedi._compatibility import FileNotFoundError
from jedi.evaluate.names import AbstractArbitraryName
from jedi.api import classes


def file_name_completions(evaluator, string, like_name):
    base_name = os.path.basename(string)
    like_name = base_name + like_name
    string = os.path.dirname(string)

    base_path = os.path.join(evaluator.project._path, string)
    try:
        listed = os.listdir(base_path)
    except FileNotFoundError:
        return
    for name in listed:
        if name.startswith(like_name):
            path_for_name = os.path.join(base_path, name)
            if os.path.isdir(path_for_name):
                name += os.path.sep

            yield classes.Completion(
                evaluator,
                FileName(evaluator, name),
                stack=None,
                like_name_length=len(like_name),
            )


class FileName(AbstractArbitraryName):
    api_type = u'path'
    is_context_name = False
