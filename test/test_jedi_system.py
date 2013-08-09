"""
Test the Jedi "System" which means for example to test if imports are
correctly used.
"""

import os
import inspect

import jedi


def test_settings_module():
    """
    jedi.settings and jedi.cache.settings must be the same module.
    """
    from jedi import cache
    from jedi import settings
    assert cache.settings is settings


def test_no_duplicate_modules():
    """
    Make sure that import hack works as expected.

    Jedi does an import hack (see: jedi/__init__.py) to have submodules
    with circular dependencies.  The modules in this circular dependency
    "loop" must be imported by ``import <module>`` rather than normal
    ``from jedi import <module>`` (or ``from . jedi ...``).  This test
    make sure that this is satisfied.

    See also:

    - `#160 <https://github.com/davidhalter/jedi/issues/160>`_
    - `#161 <https://github.com/davidhalter/jedi/issues/161>`_
    """
    import sys
    jedipath = os.path.dirname(os.path.abspath(jedi.__file__))

    def is_submodule(m):
        try:
            filepath = m.__file__
        except AttributeError:
            return False
        return os.path.abspath(filepath).startswith(jedipath)

    modules = list(filter(is_submodule, sys.modules.values()))
    top_modules = [m for m in modules if not m.__name__.startswith('jedi.')]
    for m in modules:
        if m is jedi:
            # py.test automatically improts `jedi.*` when --doctest-modules
            # is given.  So this test cannot succeeds.
            continue
        for tm in top_modules:
            try:
                imported = getattr(m, tm.__name__)
            except AttributeError:
                continue
            if inspect.ismodule(imported):
                # module could have a function with the same name, e.g.
                # `keywords.keywords`.
                assert imported is tm
