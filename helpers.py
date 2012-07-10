import parsing
import debug

class RecursionDecorator(object):
    """ A decorator to detect recursions in statements """
    def __init__(self, func):
        self.func = func
        self.reset()
        self.current = None

    def __call__(self, stmt, *args, **kwargs):
        # don't check param instances, they are not causing recursions
        if isinstance(stmt, parsing.Param):
            return self.func(stmt, *args, **kwargs)

        r = RecursionNode(stmt, self.current)
        if self.check_recursion(r):
            debug.warning('catched recursion', stmt, args, kwargs)
            return []
        parent, self.current = self.current, r
        result = self.func(stmt, *args, **kwargs)
        self.current = parent
        return result

    def check_recursion(self, new):
        test = self.current
        while True:
            if new == test:
                return True
            if not test:
                return False
            test = test.parent

    def reset(self):
        self.top = None
        self.current = None

class RecursionNode(object):
    def __init__(self, stmt, parent):
        self.script = stmt.get_parent_until()
        self.position = (stmt.line_nr, stmt.indent)
        self.parent = parent

    def __eq__(self, other):
        if not other:
            return None
        return self.script == other.script and self.position == other.position
