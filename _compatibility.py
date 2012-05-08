"""
This is a compatibility module, to make it possible to use jedi also with older
python versions.
"""
# next was defined in python 2.6, in python 3 obj.next won't be possible
# anymore
try:
    next = next
except NameError:
    _raiseStopIteration = object()
    def next(iterator, default=_raiseStopIteration):
        if not hasattr(iterator, 'next'):
           raise TypeError("not an iterator")
        try:
           return iterator.next()
        except StopIteration:
            if default is _raiseStopIteration:
                raise
            else:
                return default

# ast module was defined in python 2.6
try:
    from ast import literal_eval
except ImportError:
    literal_eval = eval
