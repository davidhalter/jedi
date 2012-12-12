memoize_caches = []


def clear_caches():
    """ Jedi caches many things, that should be completed after each completion
    finishes.
    """
    global memoize_caches

    # memorize_caches must never be deleted, because the dicts will get lost in
    # the wrappers.
    for m in memoize_caches:
        m.clear()


def memoize_default(default=None):
    """ This is a typical memoization decorator, BUT there is one difference:
    To prevent recursion it sets defaults.

    Preventing recursion is in this case the much bigger use than speed. I
    don't think, that there is a big speed difference, but there are many cases
    where recursion could happen (think about a = b; b = a).
    """
    def func(function):
        memo = {}
        memoize_caches.append(memo)

        def wrapper(*args, **kwargs):
            key = (args, frozenset(kwargs.items()))
            if key in memo:
                return memo[key]
            else:
                memo[key] = default
                rv = function(*args, **kwargs)
                memo[key] = rv
                return rv
        return wrapper
    return func


class CachedMetaClass(type):
    """ This is basically almost the same than the decorator above, it just
    caches class initializations. I haven't found any other way, so I do it
    with meta classes.
    """
    @memoize_default()
    def __call__(self, *args, **kwargs):
        return super(CachedMetaClass, self).__call__(*args, **kwargs)
