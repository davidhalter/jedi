from jedi.plugins import stdlib
from jedi.plugins import flask


class _PluginManager(object):
    def __init__(self, registered_plugin_classes=()):
        self._registered_plugin_classes = list(registered_plugin_classes)

    def register(self, plugin_class):
        """
        Makes it possible to register your plugin.
        """
        self._registered_plugins.append(plugin_class)

    def _build_chain(self):
        for plugin_class in self._registered_plugin_classes:
            yield plugin_class

    def get_callbacks(self):
        return _PluginCallbacks(self._build_chain())


class _PluginCallbacks(object):
    def __init__(self, plugins):
        self._plugins = list(plugins)

    def decorate(self, name, callback):
        for plugin in reversed(self._plugins):
            # Need to reverse so the first plugin is run first.
            try:
                func = getattr(plugin, name)
            except AttributeError:
                pass
            else:
                callback = func(callback)
        return callback


plugin_manager = _PluginManager([stdlib, flask])
