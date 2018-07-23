from parso.python.tree import Name

from jedi.plugins.base import BasePlugin
from jedi.evaluate.imports import JediImportError


class FlaskPlugin(BasePlugin):
    def import_module(self, callback):
        """
        Handle "magic" Flask extension imports:
        ``flask.ext.foo`` is really ``flask_foo`` or ``flaskext.foo``.
        """
        def wrapper(evaluator, import_names, *args, **kwargs):
            if len(import_names) > 2 and import_names[:2] == ('flask', 'ext'):
                # New style.
                ipath = ('flask_' + str(import_names[2]),) + import_names[3:]
                try:
                    return callback(evaluator, ipath, *args, **kwargs)
                except JediImportError:
                    # Old style
                    return callback(
                        evaluator,
                        ('flaskext',) + import_names[2:],
                        *args,
                        **kwargs
                    )
            return callback(evaluator, import_names, *args, **kwargs)

        return wrapper
