# -*- coding: utf8 -*-
"""
Jedi extension module.

Enables Jedi to use module import extension.

What is an extension
--------------------

An extensions is a simple python module prefixed by :data:`_EXT_PREFIX`.

At the moment only importer extensions are used, but more extension points
can follow.

Such an importer extensions is a simple callable prefixed by :data:`_EXT_PREFIX`
which has to accept 4 parameters::
    jedi_ext_myimport(importer, import_parts, import_path, sys_path)

The first one is the :class:`Importer instance<evaluate.imports.Importer>` which
calls the function due to the failed standard import mechanism. For the
rest of the parameters see
:meth:`Importer.do_import<evaluate.imports.Importer.do_import>`.

The callable has to return either a valid
:class:`ContextSet<evaluate.base_context.ContextSet>` for the imported
module or - in case of failure -
:data:`NO_CONTEXTS<evaluate.base_context.NO_CONTEXTS>`.

How to install an extension
---------------------------

For this simply put the extension module (remind the prefix :data:`_EXT_PREFIX`)
directly into the Jedi extension package folder (the folder of this package)
or set an environment variable :data:`_ENV_NAME` containing one or more paths
where Jedi should look for such prefixed extension modules.

Each path in this environment variable has to be separated by ``os.pathsep``.

Import extension example
------------------------

.. code-block:: python

    from jedi._compatibility import ImplicitNSInfo
    from jedi.evaluate.base_context import ContextSet, NO_CONTEXTS
    from jedi.evaluate import imports

    def jedi_importer_myvirtuallib(importer, import_parts, import_path, sys_path):
        '''
        Import extension function for resolving references to a virtual ns
        package ``my_lib`` located in several folders which only I know.
        '''
        module_name = '.'.join(import_parts)

        if module_name == 'my_lib':

            # add a ns package with paths that cannot be found by the standard
            # import mechanism
            implicit_ns_info = ImplicitNSInfo(
                'my_lib', ['/usr/lib/own_stuff', '/usr/lib/other_stuff]
            )

            # now load the module using the standard mechanism
            module = imports._load_module(
                importer._evaluator, implicit_ns_info, None, sys_path,
                import_names = import_parts,
                safe_module_name = True,
            )
            # and return its context in case of success
            if not module is None:
                return ContextSet(module)

        # not our module (or failed to create)
        return NO_CONTEXTS

"""

import os, sys
from jedi import debug
from jedi._compatibility import py_version
from jedi.evaluate.base_context import NO_CONTEXTS

if False:
    _logf = open(r'E:\jedi.log', 'a')
    _logf.write('=' * 80)
    _logf.write('\n\n')
    def _log_to_file(color, str_out):
        _logf.write("%s %s\n" % (color, str_out))

    debug.debug_function = _log_to_file
    debug.enable_warning = True
    debug.enable_notice = True

#: Name of the environment variable containing one or more paths where
#: Jedi extensions may be located.
_ENV_NAME = "JEDI_EXTENSION_PATH"

#: Prefix for Jedi extension modules.
_EXT_PREFIX = 'jedi_ext_'

#: Prefix for importer functions.
_IMPORTER_PREFIX = 'jedi_importer_'

def _load_extension_pre_py34(name, path):
    import imp
    res = imp.find_module(name, [os.path.dirname(path), ])
    return imp.load_module(name, *res)

def _load_extension_py34(name, path):
    from importlib import util
    spec = util.spec_from_file_location(name, path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_load_extension = _load_extension_py34 if py_version >= 34 else _load_extension_pre_py34
_load_extension.__doc__ = """
Tries to load an extension module.

:param str name: Name of the module to load, including the name prefix.

:param str path: Path to the module file.

:returns: The extension module in case of success.
"""

_import_extensions = []

def _install_extension(name, mod):
    """
    Installs the extensions from given module.

    :param str name: Name of the extension module (including the prefix)

    :param module mod: The module instance which contains the extensions to
        install.
    """
    for n, v in mod.__dict__.items():
        if n.startswith(_IMPORTER_PREFIX) and callable(v):
            _import_extensions.append(v)

def _find_in_path(p):
    for item in os.listdir(p):
        if not item.startswith(_EXT_PREFIX):
            continue
        # insert the path as current (first) one for allowing imports of
        # siblings
        sys.path.insert(0, p)
        fname, _ = os.path.splitext(item)
        try:
            mod = _load_extension(fname, os.path.join(p, item))
            _install_extension(fname, mod)
        except Exception as e:
            debug.warning(
                "Failed to install extension module %s from %s: %s",
                fname, p, e, format = True
            )
        else:
            debug.dbg(
                "Installed extension module '%s' from '%s'.",
                fname, p,
                format = True
            )
        # at least remove it
        try:
            del sys.path[ sys.path.index(p) ]
        except IndexError:
            pass

def _find_extensions(paths = None):
    """
    Called to find all available jedi extensions.

    :param paths: Optional sequence of paths to search for extension modules.
        If omitted (or ``None``) this extension package directory and the
        paths from environment (see :data:`_ENV_NAME`) are used.
    """
    if paths is None:
        extension_paths = [os.path.dirname(__file__),]
        # check for environment variable
        p = os.getenv(_ENV_NAME)
        if not p is None:
            extension_paths = p.split(os.pathsep) + extension_paths
    else:
        extension_paths = paths

    debug.dbg("sys.path=%s", sys.path)
    debug.dbg("sys.argv=%s", sys.argv)
    debug.dbg("os.cwd=%s", os.getcwd())
    debug.dbg("Searching for extension modules in %s.", extension_paths, format = True)

    extension_paths = list(filter(os.path.exists, extension_paths))

    # load and install all extensions
    for p in extension_paths:
        _find_in_path(p)

def do_import(importer, import_parts, import_path, sys_path):
    """
    Extension import function.

    Calls each extension function found using :meth:`_find_extensions` and
    returns the result of the first successful call.

    See :meth:`Importer.do_import<evaluate.imports.Importer.do_import>` for
    parameter and result description. 
    """
    result = NO_CONTEXTS
    for impext in _import_extensions:
        try:
            result = impext(importer, import_parts, import_path, sys_path)
        except Exception as e:
            debug.warning(
                "Failed to execute importer %s: %s", impext, e, format = True
            )
        else:
            if result != NO_CONTEXTS:
                break
    return result

# at least find all extensions when this module is loaded.
_find_extensions()