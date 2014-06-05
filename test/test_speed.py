"""
Speed tests of Jedi. To prove that certain things don't take longer than they
should.
"""

import time
import functools

from .helpers import TestCase, cwd_at
import jedi

class TestSpeed(TestCase):
    def _check_speed(time_per_run, number=4, run_warm=True):
        """ Speed checks should typically be very tolerant. Some machines are
        faster than others, but the tests should still pass. These tests are
        here to assure that certain effects that kill jedi performance are not
        reintroduced to Jedi."""
        def decorated(func):
            @functools.wraps(func)
            def wrapper(self):
                if run_warm:
                    func(self)
                first = time.time()
                for i in range(number):
                    func(self)
                single_time = (time.time() - first) / number
                print('\nspeed', func, single_time)
                assert single_time < time_per_run
            return wrapper
        return decorated

    @_check_speed(0.2)
    def test_os_path_join(self):
        s = "from posixpath import join; join('', '')."
        assert len(jedi.Script(s).completions()) > 10  # is a str completion

    @_check_speed(0.15)
    def test_scipy_speed(self):
        s = 'import scipy.weave; scipy.weave.inline('
        script = jedi.Script(s, 1, len(s), '')
        script.call_signatures()
        #print(jedi.imports.imports_processed)

    @_check_speed(0.8)
    @cwd_at('test')
    def test_precedence_slowdown(self):
        """
        Precedence calculation can slow down things significantly in edge
        cases. Having strange recursion structures increases the problem.
        """
        with open('speed/precedence.py') as f:
            line = len(f.read().splitlines())
        assert jedi.Script(line=line, path='speed/precedence.py').goto_definitions()
