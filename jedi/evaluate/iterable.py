import itertools

from jedi._compatibility import use_metaclass
from jedi import common
from jedi.parser import representation as pr
from jedi import debug
from jedi.evaluate import builtin
from jedi.evaluate import dynamic
from jedi.evaluate.cache import CachedMetaClass


class Generator(use_metaclass(CachedMetaClass, pr.Base)):
    """ Cares for `yield` statements. """
    def __init__(self, evaluator, func, var_args):
        super(Generator, self).__init__()
        self._evaluator = evaluator
        self.func = func
        self.var_args = var_args

    def get_defined_names(self):
        """
        Returns a list of names that define a generator, which can return the
        content of a generator.
        """
        names = []
        none_pos = (0, 0)
        executes_generator = ('__next__', 'send')
        for n in ('close', 'throw') + executes_generator:
            name = pr.Name(builtin.Builtin.scope, [(n, none_pos)],
                           none_pos, none_pos)
            if n in executes_generator:
                name.parent = self
            else:
                name.parent = builtin.Builtin.scope
            names.append(name)
        debug.dbg('generator names', names)
        return names

    def iter_content(self):
        """ returns the content of __iter__ """
        return self._evaluator.execute(self.func, self.var_args, True)

    def get_index_types(self, index=None):
        debug.warning('Tried to get array access on a generator', self)
        return []

    def __getattr__(self, name):
        if name not in ['start_pos', 'end_pos', 'parent', 'get_imports',
                        'asserts', 'doc', 'docstr', 'get_parent_until',
                        'get_code', 'subscopes']:
            raise AttributeError("Accessing %s of %s is not allowed."
                                 % (self, name))
        return getattr(self.func, name)

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self.func)


class Array(use_metaclass(CachedMetaClass, pr.Base)):
    """
    Used as a mirror to pr.Array, if needed. It defines some getter
    methods which are important in this module.
    """
    def __init__(self, evaluator, array):
        self._evaluator = evaluator
        self._array = array

    def get_index_types(self, index_arr=None):
        """ Get the types of a specific index or all, if not given """
        if index_arr is not None:
            if index_arr and [x for x in index_arr if ':' in x.expression_list()]:
                # array slicing
                return [self]

            index_possibilities = self._follow_values(index_arr)
            if len(index_possibilities) == 1:
                # This is indexing only one element, with a fixed index number,
                # otherwise it just ignores the index (e.g. [1+1]).
                index = index_possibilities[0]

                from jedi.evaluate.representation import Instance
                if isinstance(index, Instance) \
                        and str(index.name) in ['int', 'str'] \
                        and len(index.var_args) == 1:
                    # TODO this is just very hackish and a lot of use cases are
                    # being ignored
                    with common.ignored(KeyError, IndexError,
                                        UnboundLocalError, TypeError):
                        return self.get_exact_index_types(index.var_args[0])

        result = list(self._follow_values(self._array.values))
        result += dynamic.check_array_additions(self._evaluator, self)
        return set(result)

    def get_exact_index_types(self, mixed_index):
        """ Here the index is an int/str. Raises IndexError/KeyError """
        index = mixed_index
        if self.type == pr.Array.DICT:
            index = None
            for i, key_statement in enumerate(self._array.keys):
                # Because we only want the key to be a string.
                key_expression_list = key_statement.expression_list()
                if len(key_expression_list) != 1:  # cannot deal with complex strings
                    continue
                key = key_expression_list[0]
                if isinstance(key, pr.String):
                    str_key = key.value
                elif isinstance(key, pr.Name):
                    str_key = str(key)

                if mixed_index == str_key:
                    index = i
                    break
            if index is None:
                raise KeyError('No key found in dictionary')

        # Can raise an IndexError
        values = [self._array.values[index]]
        return self._follow_values(values)

    def _follow_values(self, values):
        """ helper function for the index getters """
        return list(itertools.chain.from_iterable(self._evaluator.eval_statement(v)
                                                  for v in values))

    def get_defined_names(self):
        """
        This method generates all `ArrayMethod` for one pr.Array.
        It returns e.g. for a list: append, pop, ...
        """
        # `array.type` is a string with the type, e.g. 'list'.
        scope = self._evaluator.find_name(builtin.Builtin.scope, self._array.type)[0]
        scope = self._evaluator.execute(scope)[0]  # builtins only have one class
        names = scope.get_defined_names()
        return [ArrayMethod(n) for n in names]

    @property
    def parent(self):
        return builtin.Builtin.scope

    def get_parent_until(self):
        return builtin.Builtin.scope

    def __getattr__(self, name):
        if name not in ['type', 'start_pos', 'get_only_subelement', 'parent',
                        'get_parent_until', 'items']:
            raise AttributeError('Strange access on %s: %s.' % (self, name))
        return getattr(self._array, name)

    def __getitem__(self):
        return self._array.__getitem__()

    def __iter__(self):
        return self._array.__iter__()

    def __len__(self):
        return self._array.__len__()

    def __repr__(self):
        return "<e%s of %s>" % (type(self).__name__, self._array)


class ArrayMethod(object):
    """
    A name, e.g. `list.append`, it is used to access the original array
    methods.
    """
    def __init__(self, name):
        super(ArrayMethod, self).__init__()
        self.name = name

    def __getattr__(self, name):
        # Set access privileges:
        if name not in ['parent', 'names', 'start_pos', 'end_pos', 'get_code']:
            raise AttributeError('Strange accesson %s: %s.' % (self, name))
        return getattr(self.name, name)

    def get_parent_until(self):
        return builtin.Builtin.scope

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self.name)
