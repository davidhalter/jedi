import sys

# python imports are hell sometimes. Especially the combination of relative
# imports and circular imports... Just avoid it:
sys.path.insert(0, __path__[0])

from .api import Script, NotFoundError, set_debug_function
from . import settings

from . import api

__doc__ = api.__doc__

del api

sys.path.pop(0)
