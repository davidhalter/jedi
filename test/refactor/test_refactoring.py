import logging
from functools import partial
from itertools import chain

from jedi import Script
from jedi.common import content
from jedi.refactoring import rename, extract, Pos, Content, FileState, Change
from os import walk
from os.path import join, abspath, basename


def test_rename():
    check_refactoring(
            'refactoring_fixtures/rename',
            Pos(6, 9),
            partial(rename, new_name='baz')
    )


def test_extract():
    check_refactoring(
        'refactoring_fixtures/extract',
        Pos(6, 9),
        partial(extract, new_name='f')
    )


def check_refactoring(directory, position, refactoring):
    line = position.line
    column = position.column
    in_files = all_files_below(directory, 'input')

    out_files = all_files_below(directory, 'output')
    in_out_pairs = match_files(in_files, out_files)
    matched, non_matched = split_on(in_out_pairs, lambda t: len(t[1]) >= 1)
    if len(non_matched) != 0:
        logging.warning("{} \n files haven't had a match in output.\
                        Either you have deleted them, or this is a mistake"
                        .format(non_matched))
    changes = [Change(
                old_state=FileState(in_f, Content.from_file(in_f).lines),
                new_state=FileState(change_base_folder(out_fs[0], 'input'), Content.from_file(out_fs[0]).lines)
            )
            for in_f, out_fs in matched]
    initial_file_path = changes[0].old_state.path
    s = Script(
            source=content(initial_file_path),
            column=column,
            line=line,
            path=initial_file_path
    )
    assert changes == refactoring(s)


def change_base_folder(path, folder):
    len = 1
    print(len)
    parts = path.split('/')
    r = list(reversed(parts))
    r[r.index('output')] = folder
    return '/'.join(reversed(r))


def match_files(in_paths, out_paths):
    return ((ip, match_file(ip, out_paths)) for ip in in_paths)


def match_file(in_path, out_paths):
    return filter(lambda fn: basename(fn) == basename(in_path), out_paths)


def split_on(iterable, condition):
    where_true = []
    where_false = []
    for e in iterable:
        if condition(e):
            where_true.append(e)
        else:
            where_false.append(e)
    return where_true, where_false


def all_files_below(directory, path):
    full_path = join(directory, path)
    all_files = chain(*[map(partial(rel_path, dp), filter(is_not_init, files))
                        for dp, _, files in walk(full_path)])
    return map(abspath, list(all_files))


def is_not_init(file):
    return file != '__init__.py'


def rel_path(dir, file):
    return join(dir, file)

