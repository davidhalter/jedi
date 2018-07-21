from functools import partial


class _PluginManager(object):
    def __init__(self, registered_plugin_classes=()):
        self._registered_plugin_classes = list(registered_plugin_classes)

    def register(self, plugin_class):
        """
        Makes it possible to register your plugin.
        """
        self._registered_plugins.append(plugin_class)

    def _build_chain(self, evaluator):
        for plugin_class in self._registered_plugin_classes:
            yield plugin_class(evaluator)

    def get_callbacks(self, evaluator):
        return _PluginCallbacks(self._build_chain(evaluator))


class _PluginCallbacks(object):
    def __init__(self, plugins):
        plugins = list(plugins)
        self.execute = self._wrap(plugins, 'execute')

    def _wrap(self, plugins, name):
        if not plugins:
            def default_callback(callback, *args, **kwargs):
                return callback(*args, **kwargs)

            return default_callback

        func = None
        for plugin in plugins:
            if func is None:
                func = getattr(plugin, name)
            else:
                func = partial(getattr(plugin, name), func)
        return func


plugin_manager = _PluginManager()
