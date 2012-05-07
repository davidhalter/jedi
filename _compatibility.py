
# python2.5 compatibility
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
