"""
Module to handle interpreted Python objects.
"""

import itertools
import tokenize

from jedi.parser import representation as pr
from jedi.parser import token


class ObjectImporter(object):

    """
    Import objects in "raw" namespace such as :func:`locals`.
    """

    def __init__(self, scope):
        self.scope = scope

        count = itertools.count()
        self._genname = lambda: '*jedi-%s*' % next(count)
        """
        Generate unique variable names to avoid name collision.
        To avoid name collision to already defined names, generated
        names are invalid as Python identifier.
        """

    def import_raw_namespace(self, raw_namespace):
        """
        Import interpreted Python objects in a namespace.

        Three kinds of objects are treated here.

        1. Functions and classes.  The objects imported like this::

               from os.path import join

        2. Modules.  The objects imported like this::

               import os

        3. Instances.  The objects created like this::

               from datetime import datetime
               dt = datetime(2013, 1, 1)

        :type raw_namespace: dict
        :arg  raw_namespace: e.g., the dict given by `locals`
        """
        scope = self.scope
        for (variable, obj) in raw_namespace.items():
            objname = getattr(obj, '__name__', None)

            # Import functions and classes
            module = getattr(obj, '__module__', None)
            if module and objname:
                fakeimport = self.make_fakeimport(module, objname, variable)
                scope.add_import(fakeimport)
                continue

            # Import modules
            if getattr(obj, '__file__', None) and objname:
                fakeimport = self.make_fakeimport(objname)
                scope.add_import(fakeimport)
                continue

            # Import instances
            objclass = getattr(obj, '__class__', None)
            module = getattr(objclass, '__module__', None)
            if objclass and module:
                alias = self._genname()
                fakeimport = self.make_fakeimport(module, objclass.__name__,
                                                  alias)
                fakestmt = self.make_fakestatement(variable, alias, call=True)
                scope.add_import(fakeimport)
                scope.add_statement(fakestmt)
                continue

    def make_fakeimport(self, module, variable=None, alias=None):
        """
        Make a fake import object.

        The following statements are created depending on what parameters
        are given:

        - only `module`: ``import <module>``
        - `module` and `variable`: ``from <module> import <variable>``
        - all: ``from <module> import <variable> as <alias>``

        :type   module: str
        :arg    module: ``<module>`` part in ``from <module> import ...``
        :type variable: str
        :arg  variable: ``<variable>`` part in ``from ... import <variable>``
        :type    alias: str
        :arg     alias: ``<alias>`` part in ``... import ... as <alias>``.

        :rtype: :class:`parsing_representation.Import`
        """
        submodule = self.scope._sub_module
        if variable:
            varname = pr.Name(
                module=submodule,
                names=[(variable, (-1, 0))],
                start_pos=(-1, 0),
                end_pos=(None, None))
        else:
            varname = None
        modname = pr.Name(
            module=submodule,
            names=[(module, (-1, 0))],
            start_pos=(-1, 0),
            end_pos=(None, None))
        if alias:
            aliasname = pr.Name(
                module=submodule,
                names=[(alias, (-1, 0))],
                start_pos=(-1, 0),
                end_pos=(None, None))
        else:
            aliasname = None
        if varname:
            fakeimport = pr.Import(
                module=submodule,
                namespace=varname,
                from_ns=modname,
                alias=aliasname,
                start_pos=(-1, 0),
                end_pos=(None, None))
        else:
            fakeimport = pr.Import(
                module=submodule,
                namespace=modname,
                alias=aliasname,
                start_pos=(-1, 0),
                end_pos=(None, None))
        return fakeimport

    def make_fakestatement(self, lhs, rhs, call=False):
        """
        Make a fake statement object that represents ``lhs = rhs``.

        :type call: bool
        :arg  call: When `call` is true, make a fake statement that represents
                   ``lhs = rhs()``.

        :rtype: :class:`parsing_representation.Statement`
        """
        submodule = self.scope._sub_module
        lhsname = pr.Name(
            module=submodule,
            names=[(lhs, (0, 0))],
            start_pos=(0, 0),
            end_pos=(None, None))
        rhsname = pr.Name(
            module=submodule,
            names=[(rhs, (0, 0))],
            start_pos=(0, 0),
            end_pos=(None, None))
        token_list = [lhsname, token.Token.from_tuple(
            (tokenize.OP, '=', (0, 0))
        ), rhsname]
        if call:
            token_list.extend([
                token.Token.from_tuple((tokenize.OP, '(', (0, 0))),
                token.Token.from_tuple((tokenize.OP, ')', (0, 0))),
            ])
        return pr.Statement(
            module=submodule,
            token_list=token_list,
            start_pos=(0, 0),
            end_pos=(None, None))
