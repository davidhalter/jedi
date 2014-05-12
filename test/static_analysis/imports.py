
#! import-error
import not_existing

import os

from os.path import abspath
#! import-error
from os.path import not_existing

from datetime import date
date.today

#! attribute-error
date.not_existing_attribute

#! import-error
from datetime.date import today

#! import-error
import datetime.date

import os.path
