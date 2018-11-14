# -*- coding: utf8 -*-

import os
import types

from jedi._compatibility import ImplicitNSInfo, cast_path
from jedi.evaluate.base_context import ContextSet, NO_CONTEXTS
from jedi.evaluate import imports

# create the path to the sibling virtual_root path
root = os.path.dirname(os.path.dirname(__file__))
virtual_mod_path = cast_path(os.path.join(root, 'virtual_root'))

def jedi_importer_test1a(importer, import_parts, import_path, sys_path):
    module_name = '.'.join(import_parts)
    if module_name == 'mylib':
        implicit_ns_info = ImplicitNSInfo('mylib', [virtual_mod_path])
        module = imports._load_module(
            importer._evaluator, implicit_ns_info, None, sys_path,
            # module_name = module_name,
            import_names = import_parts,
            safe_module_name = True,
        )

        if not module is None:
            return ContextSet(module)

    return NO_CONTEXTS

def jedi_importer_test1b(*a):
    raise RuntimeError("This should be catched!")