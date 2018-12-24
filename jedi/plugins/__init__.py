from jedi.plugins.stdlib import StdlibPlugin
from jedi.plugins.flask import FlaskPlugin


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
        self._plugins = list(plugins)

    def decorate(self, name, callback):
        for plugin in reversed(self._plugins):
            # Need to reverse so the first plugin is run first.
            callback = getattr(plugin, name)(callback)
        return callback


plugin_manager = _PluginManager([
    StdlibPlugin,
    FlaskPlugin,
])
