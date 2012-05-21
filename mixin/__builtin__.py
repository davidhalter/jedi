
def next(iterator, default=None):
    if hasattr("next"):
        return iterator.next()
    else:
        return iterator.__next__()
    return default
