from parso.python.tree import Name

from jedi.plugins.base import BasePlugin


class FlaskPlugin(BasePlugin):
    def import_module(self, callback):
        """
        Handle "magic" Flask extension imports:
        ``flask.ext.foo`` is really ``flask_foo`` or ``flaskext.foo``.
        """
        def wrapper(evaluator, import_path, *args, **kwargs):
            import_parts = [
                i.value if isinstance(i, Name) else i
                for i in import_path
            ]

            if len(import_path) > 2 and import_parts[:2] == ['flask', 'ext']:
                # New style.
                ipath = ('flask_' + str(import_parts[2]),) + import_path[3:]
                modules = callback(evaluator, ipath, *args, **kwargs)
                if modules:
                    return modules
                else:
                    # Old style
                    return callback(evaluator, ('flaskext',) + import_path[2:], *args, **kwargs)
            return callback(evaluator, import_path, *args, **kwargs)

        return wrapper
