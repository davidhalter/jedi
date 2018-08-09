from parso.python.tree import Name

from jedi.plugins.base import BasePlugin
from jedi.evaluate.imports import JediImportError


class FlaskPlugin(BasePlugin):
    def import_module(self, callback):
        """
        Handle "magic" Flask extension imports:
        ``flask.ext.foo`` is really ``flask_foo`` or ``flaskext.foo``.
        """
        def wrapper(evaluator, import_names, module_context, sys_path):
            if len(import_names) == 3 and import_names[:2] == ('flask', 'ext'):
                # New style.
                ipath = (u'flask_' + import_names[2]),
                try:
                    return callback(evaluator, ipath, None, sys_path)
                except JediImportError:
                    context_set = callback(evaluator, (u'flaskext',), None, sys_path)
                    # If context_set has no content a JediImportError is raised
                    # which should be caught anyway by the caller.
                    return callback(
                        evaluator,
                        (u'flaskext', import_names[2]),
                        next(iter(context_set)),
                        sys_path
                    )
            return callback(evaluator, import_names, module_context, sys_path)
        return wrapper
