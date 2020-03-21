from collections import namedtuple
from jedi._compatibility import highest_pickle_protocol


def test_highest_pickle_protocol():
    v = namedtuple('version', 'major, minor')
    assert highest_pickle_protocol([v(2, 7), v(2, 7)]) == 2
    assert highest_pickle_protocol([v(2, 7), v(3, 8)]) == 2
    assert highest_pickle_protocol([v(2, 7), v(3, 5)]) == 2
    assert highest_pickle_protocol([v(2, 7), v(3, 6)]) == 2
    assert highest_pickle_protocol([v(3, 8), v(2, 7)]) == 2
    assert highest_pickle_protocol([v(3, 8), v(3, 8)]) == 4
    assert highest_pickle_protocol([v(3, 8), v(3, 5)]) == 4
    assert highest_pickle_protocol([v(3, 8), v(3, 6)]) == 4
    assert highest_pickle_protocol([v(3, 6), v(2, 7)]) == 2
    assert highest_pickle_protocol([v(3, 6), v(3, 8)]) == 4
    assert highest_pickle_protocol([v(3, 6), v(3, 5)]) == 4
    assert highest_pickle_protocol([v(3, 6), v(3, 6)]) == 4
