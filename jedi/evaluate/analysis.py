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
    'type-error-too-many-arguments': (5, TypeError, None),
    'type-error-too-few-arguments': (6, TypeError, None),
    'type-error-keyword-argument': (7, TypeError, None),
    'type-error-multiple-values': (8, TypeError, None),
    'type-error-star-star': (9, TypeError, None),
    'type-error-star': (10, TypeError, None),
    'type-error-operation': (11, TypeError, None),
}


class Error(object):
    def __init__(self, name, module_path, start_pos, message=None):
        self.path = module_path
        self._start_pos = start_pos
        self.name = name
        if message is None:
            message = CODES[self.name][2]
        self.message = message

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

    def __unicode__(self):
        return '%s:%s:%s: %s %s' % (self.path, self.line, self.column,
                                    self.code, self.message)

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


def add(evaluator, name, jedi_obj, message=None, typ=Error, payload=None):
    exception = CODES[name][1]
    if _check_for_exception_catch(evaluator, jedi_obj, exception, payload):
        return

    module_path = jedi_obj.get_parent_until().path
    instance = typ(name, module_path, jedi_obj.start_pos, message)
    debug.warning(str(instance))
    evaluator.analysis.append(instance)


def _check_for_setattr(instance):
    """
    Check if there's any setattr method inside an instance. If so, return True.
    """
    module = instance.get_parent_until()
    try:
        stmts = module.used_names['setattr']
    except KeyError:
        return False

    return any(instance.start_pos < stmt.start_pos < instance.end_pos
               for stmt in stmts)


def add_attribute_error(evaluator, scope, name_part):
    message = ('AttributeError: %s has no attribute %s.' % (scope, name_part))
    from jedi.evaluate.representation import Instance
    # Check for __getattr__/__getattribute__ existance and issue a warning
    # instead of an error, if that happens.
    if isinstance(scope, Instance):
        typ = Warning
        try:
            scope.get_subscope_by_name('__getattr__')
        except KeyError:
            try:
                scope.get_subscope_by_name('__getattribute__')
            except KeyError:
                if not _check_for_setattr(scope):
                    typ = Error
    else:
        typ = Error

    payload = scope, name_part
    add(evaluator, 'attribute-error', name_part, message, typ, payload)


def _check_for_exception_catch(evaluator, jedi_obj, exception, payload=None):
    """
    Checks if a jedi object (e.g. `Statement`) sits inside a try/catch and
    doesn't count as an error (if equal to `exception`).
    Also checks `hasattr` for AttributeErrors and uses the `payload` to compare
    it.
    Returns True if the exception was catched.
    """
    def check_match(cls):
        try:
            return isinstance(cls, CompiledObject) and issubclass(exception, cls.obj)
        except TypeError:
            return False

    def check_try_for_except(obj):
        while obj.next is not None:
            obj = obj.next
            if not obj.inputs:
                # No import implies a `except:` catch, which catches
                # everything.
                return True

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

    def check_hasattr(stmt):
        expression_list = stmt.expression_list()
        try:
            assert len(expression_list) == 1
            call = expression_list[0]
            assert isinstance(call, pr.Call) and str(call.name) == 'hasattr'
            execution = call.execution
            assert execution and len(execution) == 2

            # check if the names match
            names = evaluator.eval_statement(execution[1])
            assert len(names) == 1 and isinstance(names[0], CompiledObject)
            assert names[0].obj == str(payload[1])

            objects = evaluator.eval_statement(execution[0])
            return payload[0] in objects
        except AssertionError:
            pass
        return False

    obj = jedi_obj
    while obj is not None and not obj.isinstance(pr.Function, pr.Class):
        if obj.isinstance(pr.Flow):
            # try/except catch check
            if obj.command == 'try' and check_try_for_except(obj):
                return True
            # hasattr check
            if exception == AttributeError and obj.command in ('if', 'while'):
                if obj.inputs and check_hasattr(obj.inputs[0]):
                    return True
        obj = obj.parent

    return False


def get_module_statements(module):
    """
    Returns the statements used in a module. All these statements should be
    evaluated to check for potential exceptions.
    """
    def add_stmts(stmts):
        new = set()
        for stmt in stmts:
            if isinstance(stmt, pr.Flow):
                while stmt is not None:
                    new |= add_stmts(stmt.inputs)
                    stmt = stmt.next
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
