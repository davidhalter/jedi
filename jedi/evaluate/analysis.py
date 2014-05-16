"""
Module for statical analysis.
"""

from jedi import debug
from jedi.parser import representation as pr
from jedi.evaluate.compiled import CompiledObject


CODES = {
    'attribute-error': (1, AttributeError, 'Potential AttributeError.'),
    'name-error': (2, NameError, 'Potential NameError.'),
    'import-error': (3, ImportError, 'Potential ImportError.'),
    'type-error-generator': (4, TypeError, "TypeError: 'generator' object is not subscriptable."),
}


class Error(object):
    def __init__(self, name, module_path, start_pos):
        self.path = module_path
        self._start_pos = start_pos
        self.name = name

    @property
    def line(self):
        return self._start_pos[0]

    @property
    def column(self):
        return self._start_pos[1]

    @property
    def code(self):
        # The class name start
        first = self.__class__.__name__[0]
        return first + str(CODES[self.name][0])

    def description(self):
        return CODES[self.name][2]

    def __unicode__(self):
        return '%s:%s:%s: %s %s' % (self.path, self.line, self.column,
                                    self.code, self.description())

    def __str__(self):
        return self.__unicode__()

    def __eq__(self, other):
        return (self.path == other.path and self.name == other.name
                and self._start_pos == other._start_pos)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.path, self._start_pos, self.name))

    def __repr__(self):
        return '<%s %s: %s@%s,%s' % (self.__class__.__name__,
                                     self.name, self.path,
                                     self._start_pos[0], self._start_pos[1])


class Warning(Error):
    pass


def add(evaluator, name, jedi_obj, typ=Error):
    exception = CODES[name][1]
    if _check_for_exception_catch(evaluator, jedi_obj, exception):
        return

    module_path = jedi_obj.get_parent_until().path
    instance = typ(name, module_path, jedi_obj.start_pos)
    debug.warning(str(instance))
    evaluator.analysis.append(instance)


def _check_for_exception_catch(evaluator, jedi_obj, exception):
    def check_match(cls):
        return isinstance(cls, CompiledObject) and cls.obj == exception

    def check_try_for_except(obj):
        while obj.next is not None:
            obj = obj.next
            for i in obj.inputs:
                except_classes = evaluator.eval_statement(i)
                for cls in except_classes:
                    from jedi.evaluate import iterable
                    if isinstance(cls, iterable.Array) and cls.type == 'tuple':
                        # multiple exceptions
                        for c in cls.values():
                            if check_match(c):
                                return True
                    else:
                        if check_match(cls):
                            return True
        return False

    while jedi_obj is not None and not jedi_obj.isinstance(pr.Function, pr.Class):
        if jedi_obj.isinstance(pr.Flow) and jedi_obj.command == 'try':
            if check_try_for_except(jedi_obj):
                return True
        jedi_obj = jedi_obj.parent
    return False


def get_module_statements(module):
    """
    Returns the statements used in a module. All these statements should be
    evaluated to check for potential exceptions.
    """
    def add_stmts(stmts):
        new = set()
        for stmt in stmts:
            if isinstance(stmt, pr.Scope):
                new |= add_stmts(stmt.inputs)
                continue
            if isinstance(stmt, pr.KeywordStatement):
                stmt = stmt.stmt
                if stmt is None:
                    continue

            for expression in stmt.expression_list():
                if isinstance(expression, pr.Array):
                    new |= add_stmts(expression.values)

                if isinstance(expression, pr.StatementElement):
                    for element in expression.generate_call_path():
                        if isinstance(element, pr.Array):
                            new |= add_stmts(element.values)
            new.add(stmt)
        return new

    stmts = set()
    imports = set()
    for scope in module.walk():
        imports |= set(scope.imports)
        stmts |= add_stmts(scope.statements)
        stmts |= add_stmts(r for r in scope.returns if r is not None)

        try:
            decorators = scope.decorators
        except AttributeError:
            pass
        else:
            stmts |= add_stmts(decorators)
    return stmts, imports
