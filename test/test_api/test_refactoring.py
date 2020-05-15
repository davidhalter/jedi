import os
import sys
from textwrap import dedent

import pytest

import jedi


@pytest.fixture(autouse=True)
def skip_old_python(skip_pre_python36):
    if sys.version_info < (3, 6):
        pytest.skip()


@pytest.fixture()
def dir_with_content(tmpdir):
    with open(os.path.join(tmpdir.strpath, 'modx.py'), 'w', newline='') as f:
        f.write('import modx\nfoo\n')  # self reference
    return tmpdir.strpath


def test_rename_mod(Script, dir_with_content):
    script = Script(
        'import modx; modx\n',
        path=os.path.join(dir_with_content, 'some_script.py'),
        project=jedi.Project(dir_with_content),
    )
    refactoring = script.rename(line=1, new_name='modr')
    refactoring.apply()

    p1 = os.path.join(dir_with_content, 'modx.py')
    p2 = os.path.join(dir_with_content, 'modr.py')
    expected_code = 'import modr\nfoo\n'
    assert not os.path.exists(p1)
    with open(p2, newline='') as f:
        assert f.read() == expected_code

    assert refactoring.get_renames() == [(p1, p2)]

    assert refactoring.get_changed_files()[p1].get_new_code() == expected_code

    assert refactoring.get_diff() == dedent('''\
        rename from modx.py
        rename to modr.py
        --- modx.py
        +++ modr.py
        @@ -1,3 +1,3 @@
        -import modx
        +import modr
         foo
        --- some_script.py
        +++ some_script.py
        @@ -1,2 +1,2 @@
        -import modx; modx
        +import modr; modr
        ''').format(dir=dir_with_content)


def test_rename_none_path(Script):
    refactoring = Script('foo', path=None).rename(new_name='bar')
    with pytest.raises(jedi.RefactoringError, match='on a Script with path=None'):
        refactoring.apply()
    assert refactoring


def test_diff_without_ending_newline(Script):
    refactoring = Script('a = 1\nb\na').rename(1, 0, new_name='c')
    assert refactoring.get_diff() == dedent('''\
        --- 
        +++ 
        @@ -1,3 +1,3 @@
        -a = 1
        +c = 1
         b
        -a
        +c
        ''')
