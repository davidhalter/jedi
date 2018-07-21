class BasePlugin(object):
    """
    Plugins are created each time an evaluator is created.
    """
    def __init__(self, evaluator):
        # In __init__ you can do some caching.
        self._evaluator = evaluator

    def execute(self, default_callback, arguments):
        return default_callback(arguments)
