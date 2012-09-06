import keyword

from _compatibility import is_py3k
import builtin

import pydoc
import pydoc_data.topics

if is_py3k():
    keys = keyword.kwlist
else:
    keys = keyword.kwlist + ['None', 'False', 'True']


def get_keywords(string='', all=False):
    if all:
        return set([Keyword(k) for k in keys])
    if string in keys:
        return set([Keyword(string)])
    return set()


def get_operator(string):
    return Keyword(string)


class Keyword(object):
    def __init__(self, name):
        self.name = name
        self.parent = lambda: None

    def get_parent_until(self):
        return builtin.builtin_scope

    @property
    def docstr(self):
        return imitate_pydoc(self.name)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.name)


def imitate_pydoc(string):
    h = pydoc.help
    try:
        # try to access symbols
        string = h.symbols[string]
        string, _, related = string.partition(' ')
    except KeyError:
        pass

    get_target = lambda s: h.topics.get(s, h.keywords.get(s))
    while type(string) == type(''):
        string = get_target(string)

    try:
        # is a tuple now
        label, related = string
    except TypeError:
        return ''

    return pydoc_data.topics.topics[label]
