""" Processing of docstrings, which means parsing for types. """

import re

import evaluate
import parsing


#@cache.memoize_default()  # TODO add
def follow_param(param):
    func = param.parent_function
    #print func, param, param.parent_function
    param_str = search_param_in_docstr(func.docstr, str(param.get_name()))

    if param_str is not None:
        p = parsing.PyFuzzyParser(param_str, None, (1, 0), no_docstr=True)
        p.user_stmt.parent = func
        return evaluate.follow_statement(p.user_stmt)
    return []


def search_param_in_docstr(docstr, param_str):
    lines = docstr.split('\n')

    # look at #40 to see definitions of those params
    sphinx_comp = ':type %s:' % param_str
    googley_comp = re.compile('\s*%s\s+\(([^()]+)\)' % re.escape(param_str))
    for l in lines:
        if l.startswith(sphinx_comp):
            return l.replace(sphinx_comp, '', 1).strip()

        r = re.match(googley_comp, l)
        if r is not None:
            return r.group(1)
    return None
