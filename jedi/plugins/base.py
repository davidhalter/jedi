class BasePlugin(object):
    """
    Plugins are created each time an evaluator is created.
    """
    def __init__(self, evaluator):
        # In __init__ you can do some caching.
        self._evaluator = evaluator

    def execute(self, callback):
        """
        Decorates the execute(context, arguments) function.
        """
        return callback

    def import_module(self, callback):
        """
        Decorates the
        import_module(evaluator, import_path, sys_path, add_error_callback)
        function.
        """
        return callback
