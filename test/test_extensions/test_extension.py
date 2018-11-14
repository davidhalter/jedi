# -*- coding: utf8 -*-
import os
from jedi import extensions
from jedi._compatibility import find_module

def test_extension_finder(Script):
    # save globals for restoring them later
    old_ext = extensions._import_extensions

    # set environment to point to the test extension paths
    _d = os.path.dirname
    test_dir = os.path.join(_d(_d(__file__)), 'extensions')
    paths = [
        os.path.join(test_dir, 'extpath1'),
        os.path.join(test_dir, 'extpath2')
    ]
    
    # clear the current extensions
    extensions._import_extensions = []

    # and load the test extensions
    extensions._find_extensions(paths)

    # at least all test extensions have to be found
    assert len(extensions._import_extensions) >= 3

    expected = {'jedi_importer_test1a', 'jedi_importer_test1b', 'jedi_importer_test2a'}
    installed = expected.intersection(fu.__name__ for fu in extensions._import_extensions)
    assert installed == expected, "Not all importers have been installed!"

    completions = Script('from not_there_lib import ').completions()
    assert len(completions) == 0, "This module shouldn't exists (and the importer still have raised an exception)."

    completions = Script('from mylib import ').completions()
    assert set(c.name for c in completions) == {'testmod', 'othermod'}, "Not all modules have been resolved!"

    completions = {c.name for c in Script('from mylib.testmod import ').completions()}
    assert 'MYCONST' in completions

    # reset the globals to their further values
    extensions._import_extensions = old_ext