import sys

deferred_modules = {}


class DummyModule(object):

    def __getattr__(self, _):
        raise ValueError(
            "Trying to use deferred imported module before "
            "Jedi is fully imported.")


def deferred_import(current_name, submodule, alias=None):
    module_list = deferred_modules.setdefault(current_name, [])
    module_list.append((submodule, alias or submodule))
    return DummyModule()


def import_all():
    for (current_name, module_list) in deferred_modules.items():
        for (module, alias) in module_list:
            current = sys.modules[current_name]
            module_name = 'jedi.%s' % module
            try:
                deferred = sys.modules[module_name]
            except KeyError:
                jedi = __import__('jedi', fromlist=[module], level=0)
                deferred = getattr(jedi, module)
            setattr(current, alias, deferred)
