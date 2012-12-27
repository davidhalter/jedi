""" Processing of docstrings, which means parsing for types. """

import re

import evaluate
import parsing

DOCSTRING_PARAM_PATTERNS = [
    r'\s*:type\s+%s:\s*([\d\w_]+)', # Sphinx
    r'\s*@type\s+%s:\s*([\d\w_]+)', # Epidoc
    r'\s*%s\s+\(([^()]+)\)'         # googley
]

DOCSTRING_RETURN_PATTERNS = [
        re.compile(r'\s*:rtype:\s*([^\n]+)', re.M), # Sphinx
        re.compile(r'\s*@rtype:\s*([^\n]+)', re.M), # Epidoc

        # Googley is the most undocumented format for
        # return types, so we try to analyze the first
        # line or line after `Returns:` keyword
        re.compile(r'returns\s*:[\s\n]*([^\n]+)', re.M|re.I),
]

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
    patterns = [ re.compile(p % re.escape(param_str)) for p in DOCSTRING_PARAM_PATTERNS ]
    for l in lines:
        for pattern in patterns:
            match = pattern.match(l)
            if match:
                return match.group(1)

    return None


def find_return_types(func):
    if isinstance(func, evaluate.InstanceElement):
        func = func.var

    if isinstance(func, evaluate.Function):
        func = func.base_func

    type_str = search_return_in_docstr(func.docstr)
    if not type_str:
        return []

    p = parsing.PyFuzzyParser(type_str, None, (1, 0), no_docstr=True)
    p.user_stmt.parent = func
    return list(evaluate.follow_statement(p.user_stmt))

def search_return_in_docstr(code):
    for p in DOCSTRING_RETURN_PATTERNS:
        match = p.search(code)
        if match:
            return match.group(1)
