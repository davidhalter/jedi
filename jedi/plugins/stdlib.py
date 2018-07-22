from jedi import debug
from jedi.plugins.base import BasePlugin


class StdlibPlugin(BasePlugin):
    def execute(self, callback):
        def wrapper(context, arguments):
            debug.dbg('execute: %s %s', context, arguments)
            from jedi.evaluate import stdlib
            try:
                # Some stdlib functions like super(), namedtuple(), etc. have been
                # hard-coded in Jedi to support them.
                return stdlib.execute(self._evaluator, context, arguments)
            except stdlib.NotInStdLib:
                pass
            return callback(context, arguments)

        return wrapper
