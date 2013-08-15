import readline

from jedi import utils


class TestSetupReadline():
    namespace = dict()
    utils.setup_readline(namespace)

    def completions(self, text):
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
        assert self.completions('list') == ['list']
        assert self.completions('importerror') == ['ImportError']

    def test_nested(self):
        assert self.completions('list.Insert') == ['list.insert']
        assert self.completions('list().Insert') == ['list().insert']

    def test_magic_methods(self):
        assert self.completions('list.__getitem__') == ['list.__getitem__']
        assert self.completions('list().__getitem__') == ['list().__getitem__']

    def test_modules(self):
        import sys
        import os
        self.namespace['sys'] = sys
        self.namespace['os'] = os

        c = set(['os.' + d for d in dir(os) if d.startswith('ch')])
        assert set(self.completions('os.ch')) == set(c)
        assert self.completions('os.chdir') == ['os.chdir']
        assert self.completions('os.path.join') == ['os.path.join']
        assert self.completions('os.path.join().upper') == ['os.path.join().upper']

        del self.namespace['sys']
        del self.namespace['os']

    def test_import(self):
        s = 'from os.path import a'
        assert set(self.completions(s)) == set([s + 'ltsep', s + 'bspath'])

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
            self.namespace['colorama'] = colorama
            assert self.completions('colorama')
            assert self.completions('colorama.Fore.BLACK') == ['colorama.Fore.BLACK']
            del self.namespace['colorama']
