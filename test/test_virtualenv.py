#!/usr/bin/env python

import jedi.modules

import os.path

def test_pth():
    paths = tuple(jedi.modules.gather_site_dir_paths('./site-packages'))

    assert len(paths) == 3, "Should only gather three paths. Got {0}".format(' '.join(paths))

    path_names = tuple(os.path.split(path)[1] for path in paths)
    for expected in ["foo_module-0.0.1-pyX.X.egg", "bar_module-0.0.2-pyX.X.egg", "baz_module-0.0.3-pyX.X.egg"]:
        assert expected in path_names, "Expected path \"{0}\" not found in paths {1}".format(expected, ' '.join(paths))

    for path in paths:
        os.path.exists(path)

    assert "#ignore" not in paths, "Lines beginning with # should be skipped."
    assert "import foo" not in paths, "Lines beginning with 'import' should be skipped."
