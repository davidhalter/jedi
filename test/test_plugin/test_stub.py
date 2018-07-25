import os

from jedi.plugins import typeshed
from parso.utils import PythonVersionInfo


def test_get_typeshed_directories():
    def get_dirs(version_info):
        return {
            d.replace(typeshed._TYPESHED_PATH, '').lstrip(os.path.sep)
            for d in typeshed._get_typeshed_directories(version_info)
        }

    dirs = get_dirs(PythonVersionInfo(2, 7))
    assert dirs == {'stdlib/2and3', 'stdlib/2', 'third_party/2and3', 'third_party/2'}

    dirs = get_dirs(PythonVersionInfo(3, 4))
    assert dirs == {'stdlib/2and3', 'stdlib/3', 'third_party/2and3', 'third_party/3'}

    dirs = get_dirs(PythonVersionInfo(3, 5))
    assert dirs == {'stdlib/2and3', 'stdlib/3', 'stdlib/3.5',
                    'third_party/2and3', 'third_party/3', 'third_party/3.5'}

    dirs = get_dirs(PythonVersionInfo(3, 6))
    assert dirs == {'stdlib/2and3', 'stdlib/3', 'stdlib/3.5', 'stdlib/3.6',
                    'third_party/2and3', 'third_party/3', 'third_party/3.5', 'third_party/3.6'}
