import sys
import types
from typing import Any

try:
    import readline
except ImportError:
    readline = False  # type: ignore[assignment]
import unittest
from unittest import mock

from jedi import utils


@unittest.skipIf(not readline, "readline not found")
class TestSetupReadline(unittest.TestCase):
    class NameSpace(object):
        pass

    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)

        self.namespace: Any = self.NameSpace()
        utils.setup_readline(self.namespace)

    def complete(self, text):
        completer = readline.get_completer()
        i = 0
        completions = []
        while True:
            completion = completer(text, i)
            if completion is None:
                break
            completions.append(completion)
            i += 1
        return completions

    def test_simple(self):
        assert self.complete('list') == ['list']
        assert self.complete('importerror') == ['ImportError']
        s = "print(BaseE"
        if sys.version_info >= (3, 11):
            assert self.complete(s) == [s + 'xception', s + 'xceptionGroup']
        else:
            assert self.complete(s) == [s + 'xception']

    def test_nested(self):
        assert self.complete('list.Insert') == ['list.insert']
        assert self.complete('list().Insert') == ['list().insert']

    def test_magic_methods(self):
        assert self.complete('list.__getitem__') == ['list.__getitem__']
        assert self.complete('list().__getitem__') == ['list().__getitem__']

    def test_modules(self):
        import sys
        import os
        self.namespace.sys = sys  # type: ignore[attr-defined]
        self.namespace.os = os  # type: ignore[attr-defined]

        try:
            assert self.complete('os.path.join') == ['os.path.join']
            string = 'os.path.join("a").upper'
            assert self.complete(string) == [string]

            c = {'os.' + d for d in dir(os) if d.startswith('ch')}
            assert set(self.complete('os.ch')) == set(c)
        finally:
            del self.namespace.sys  # type: ignore[attr-defined]
            del self.namespace.os  # type: ignore[attr-defined]

    def test_calls(self):
        s = 'str(bytes'
        assert self.complete(s) == [s, 'str(BytesWarning']

    def test_import(self):
        s = 'from os.path import a'
        assert set(self.complete(s)) == {
            s + 'ltsep',
            s + 'bspath',
            'from os.path import ALLOW_MISSING'
        }
        assert self.complete('import keyword') == ['import keyword']

        import os
        s = 'from os import '
        goal = {s + el for el in dir(os)}

        # There are minor differences, e.g. the dir doesn't include deleted
        # items as well as items that are not only available on linux.
        difference = set(self.complete(s)).symmetric_difference(goal)
        ACCEPTED_DIFFERENCE_PREFIXES = [
            '_', 'O_', 'EX_', 'EFD_', 'MFD_', 'TFD_',
            'SF_', 'ST_', 'CLD_', 'POSIX_SPAWN_', 'P_',
            'RWF_', 'CLONE_', 'SCHED_', 'SPLICE_',
            # Python 3.15+ new constants
            'AT_', 'PIDFD_', 'STATX_', 'GRND_', 'XATTR_',
            'RTLD_', 'PRIO_', 'F_', 'SEEK_', 'NODEV',
        ]
        difference = {
            x for x in difference
            if not any(
                x.startswith('from os import ' + prefix)
                for prefix in ACCEPTED_DIFFERENCE_PREFIXES
            )
        }
        # There are quite a few differences, because both Windows and Linux
        # (posix and nt) libraries are included.
        assert len(difference) < 40

    def test_local_import(self):
        s = 'import test.test_utils'
        assert self.complete(s) == [s]

    def test_preexisting_values(self):
        self.namespace.a = range(10)
        assert set(self.complete('a.')) == {'a.' + n for n in dir(range(1))}
        del self.namespace.a

    def test_colorama(self):
        """
        Only test it if colorama library is available.

        This module is being tested because it uses ``setattr`` at some point,
        which Jedi doesn't understand, but it should still work in the REPL.
        """
        try:
            # if colorama is installed
            import colorama
        except ImportError:
            pass
        else:
            self.namespace.colorama = colorama
            assert self.complete('colorama')
            assert self.complete('colorama.Fore.BLACK') == ['colorama.Fore.BLACK']
            del self.namespace.colorama


def test_version_info():
    assert utils.version_info()[:2] > (0, 7)


def test_setup_readline_pyrepl():
    namespace = types.SimpleNamespace()

    class FakeReadline(types.ModuleType):
        def __init__(self, name):
            super().__init__(name)
            self.completer = None
            self.completer_delims = None
            self.bindings = []
            self._wrapper = types.SimpleNamespace(
                config=types.SimpleNamespace(module_completer='original')
            )
            self._setup_calls = 0

        def parse_and_bind(self, string):
            self.bindings.append(string)

        def set_completer(self, function=None):
            self.completer = function

        def get_completer(self):
            return self.completer

        def set_completer_delims(self, delimiters):
            self.completer_delims = delimiters

        def _setup(self, namespace):
            self._setup_calls += 1
            self._wrapper.config.module_completer = 'pyrepl'

    fake_readline = FakeReadline('readline')
    fake_pyrepl_readline = FakeReadline('_pyrepl.readline')
    fake_pyrepl = types.ModuleType('_pyrepl')
    fake_pyrepl.readline = fake_pyrepl_readline

    with mock.patch.dict(sys.modules, {
        'readline': fake_readline,
        '_pyrepl': fake_pyrepl,
        '_pyrepl.readline': fake_pyrepl_readline,
    }):
        utils.setup_readline(namespace)
        fake_pyrepl_readline._setup({})

    completer = fake_pyrepl_readline.get_completer()
    assert completer is not None
    assert completer('list.Insert', 0) == 'list.insert'
    assert fake_pyrepl_readline.completer_delims == ''
    assert fake_pyrepl_readline._wrapper.config.module_completer.get_completions(
        'from os import a'
    ) is None
