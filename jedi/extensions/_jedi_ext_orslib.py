# -*- coding: utf8 -*-
from jedi._compatibility import ImplicitNSInfo
from jedi.evaluate.base_context import ContextSet, NO_CONTEXTS
from jedi.evaluate import imports

# sys_path[0] ist immer das Verzeichnis, aus dem das Import gerufen wird
def jedi_importer_orslib(importer, import_parts, import_path, sys_path):
    module_name = '.'.join(import_parts)
    if module_name == 'ors_lib':
        implicit_ns_info = ImplicitNSInfo('ors_lib', ['e:\\Projekte\\V751\\SCHEDULE_7xx\\Core\\lib'])
        module = imports._load_module(
            importer._evaluator, implicit_ns_info, None, sys_path,
            import_names = import_parts,
            safe_module_name=True,
        )

        if not module is None:
            return ContextSet(module)

    return NO_CONTEXTS

def jedi_importer_orsmodule(importer, import_parts, import_path, sys_path):
    module_name = '.'.join(import_parts)
    if module_name == 'ors_lib':
        implicit_ns_info = ImplicitNSInfo('ors_lib', ['e:\\Projekte\\V751\\SCHEDULE_7xx\\Core\\lib'])
        module = imports._load_module(
            importer._evaluator, implicit_ns_info, None, sys_path,
            import_names = import_parts,
            safe_module_name=True,
        )

        if not module is None:
            return ContextSet(module)

    return NO_CONTEXTS