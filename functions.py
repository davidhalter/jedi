import parsing

def complete(source, row, colum, file_callback=None):
    """
    An auto completer for python files.

    :param source: The source code of the current file
    :type source: string
    :param row: The row to complete in.
    :type row: int
    :param col: The column to complete in.
    :type col: int
    :return: list
    :rtype: list
    """
    p = parsing.PyFuzzyParser(source, row)
    return []
