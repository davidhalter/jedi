def import_module(callback):
    """
    Handle "magic" Flask extension imports:
    ``flask.ext.foo`` is really ``flask_foo`` or ``flaskext.foo``.
    """
    def wrapper(infer_state, import_names, module_value, *args, **kwargs):
        if len(import_names) == 3 and import_names[:2] == ('flask', 'ext'):
            # New style.
            ipath = (u'flask_' + import_names[2]),
            value_set = callback(infer_state, ipath, None, *args, **kwargs)
            if value_set:
                return value_set
            value_set = callback(infer_state, (u'flaskext',), None, *args, **kwargs)
            return callback(
                infer_state,
                (u'flaskext', import_names[2]),
                next(iter(value_set)),
                *args, **kwargs
            )
        return callback(infer_state, import_names, module_value, *args, **kwargs)
    return wrapper
