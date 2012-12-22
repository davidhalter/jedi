import time
import settings

# memoize caches will be deleted after every action
memoize_caches = []

time_caches = []


def clear_caches():
    """ Jedi caches many things, that should be completed after each completion
    finishes.
    """
    global memoize_caches

    # memorize_caches must never be deleted, because the dicts will get lost in
    # the wrappers.
    for m in memoize_caches:
        m.clear()

    for tc in time_caches:
        # check time_cache for expired entries
        for key, (t, value) in list(tc.items()):
            if t < time.time():
                # delete expired entries
                del tc[key]


def memoize_default(default=None, cache=memoize_caches):
    """ This is a typical memoization decorator, BUT there is one difference:
    To prevent recursion it sets defaults.

    Preventing recursion is in this case the much bigger use than speed. I
    don't think, that there is a big speed difference, but there are many cases
    where recursion could happen (think about a = b; b = a).
    """
    def func(function):
        memo = {}
        cache.append(memo)

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


def time_cache(time_add_setting):
    """ This decorator works as follows: Call it with a setting and after that
    use the function with a callable that returns the key.
    But: This function is only called if the key is not available. After a
    certain amount of time (`time_add_setting`) the cache is invalid.
    """
    def _temp(key_func):
        dct = {}
        time_caches.append(dct)
        def wrapper(optional_callable, *args, **kwargs):
            key = key_func(*args, **kwargs)
            value = None
            if key in dct:
                expiry, value = dct[key]
                if expiry > time.time():
                    return value
            value = optional_callable()
            time_add = getattr(settings, time_add_setting)
            if key is not None:
                dct[key] = time.time() + time_add, value
            return value
        return wrapper
    return _temp


@time_cache("get_in_function_call_validity")
def cache_get_in_function_call(stmt):
    module_path = stmt.get_parent_until().path
    return None if module_path is None else (module_path, stmt.start_pos)
