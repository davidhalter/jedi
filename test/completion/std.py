"""
std library stuff
"""

# -----------------
# re
# -----------------
import re
c = re.compile(r'a')
#? int()
c.match().start()

#? int()
re.match(r'a', 'a').start()

#? int()
next(re.finditer('a', 'a')).start()

#? str()
re.sub('a', 'a')
