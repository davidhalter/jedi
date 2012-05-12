
def next(iterator, default=1):
    if hasattr("next"):
        return iterator.next()
    else:
        return iterator.__next__()
    return default
