import jedi

def test_path_issues():
    """
    See pull request #684 for details.
    """
    source = '''from datetime import '''
    assert jedi.Script(source).completions()
