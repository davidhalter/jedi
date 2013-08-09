from __future__ import with_statement

import pydoc
import keyword

from jedi._compatibility import is_py3k
from jedi import parsing_representation as pr
from jedi import common
import builtin

try:
    from pydoc_data import topics as pydoc_topics
except ImportError:
    # Python 2.6
    import pydoc_topics

if is_py3k:
    keys = keyword.kwlist
else:
    keys = keyword.kwlist + ['None', 'False', 'True']


def keywords(string='', pos=(0, 0), all=False):
    if all:
        return set([Keyword(k, pos) for k in keys])
    if string in keys:
        return set([Keyword(string, pos)])
    return set()


def keyword_names(*args, **kwargs):
    kwds = []
    for k in keywords(*args, **kwargs):
        start = k.start_pos
        end = start[0], start[1] + len(k.name)
        kwds.append(pr.Name(k.parent, [(k.name, start)], start, end, k))
    return kwds


def get_operator(string, pos):
    return Keyword(string, pos)


class Keyword(object):
    def __init__(self, name, pos):
        self.name = name
        self.start_pos = pos
        self.parent = builtin.Builtin.scope

    def get_parent_until(self):
        return self.parent

    @property
    def names(self):
        """ For a `parsing.Name` like comparision """
        return [self.name]

    @property
    def docstr(self):
        return imitate_pydoc(self.name)

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.name)


def imitate_pydoc(string):
    """
    It's not possible to get the pydoc's without starting the annoying pager
    stuff.
    """
    # str needed because of possible unicode stuff in py2k (pydoc doesn't work
    # with unicode strings)
    string = str(string)
    h = pydoc.help
    with common.ignored(KeyError):
        # try to access symbols
        string = h.symbols[string]
        string, _, related = string.partition(' ')

    get_target = lambda s: h.topics.get(s, h.keywords.get(s))
    while isinstance(string, str):
        string = get_target(string)

    try:
        # is a tuple now
        label, related = string
    except TypeError:
        return ''

    try:
        return pydoc_topics.topics[label] if pydoc_topics else ''
    except KeyError:
        return ''
