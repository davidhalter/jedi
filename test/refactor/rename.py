"""
Test coverage for renaming is mostly being done by testing
`Script.get_references`.
"""

# -------------------------------------------------- simple
def test1():
    #? 7 blabla
    test1()
    AssertionError
    return test1, test1.not_existing
# +++++
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,6 +1,6 @@
-def test1():
+def blabla():
     #? 7 blabla
-    test1()
+    blabla()
     AssertionError
-    return test1, test1.not_existing
+    return blabla, blabla.not_existing
# -------------------------------------------------- different-scopes
def x():
    #? 7 v
    some_var = 3
    some_var
def y():
    some_var = 3
    some_var
# ++++++++++++++++++++++++++++++++++++++++++++++++++
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,7 +1,7 @@
 def x():
     #? 7 v
-    some_var = 3
-    some_var
+    v = 3
+    v
 def y():
     some_var = 3
     some_var
# -------------------------------------------------- import
from import_tree.some_mod import foobar
#? 0 renamed
foobar
# ++++++++++++++++++++++++++++++++++++++++++++++++++
--- /home/dave/source/jedi/test/refactor/import_tree/some_mod.py
+++ /home/dave/source/jedi/test/refactor/import_tree/some_mod.py
@@ -1,2 +1,2 @@
-foobar = 3
+renamed = 3
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,4 +1,4 @@
-from import_tree.some_mod import foobar
+from import_tree.some_mod import renamed
 #? 0 renamed
-foobar
+renamed
# -------------------------------------------------- module
from import_tree import some_mod
#? 0 renamedm
some_mod
# ++++++++++++++++++++++++++++++++++++++++++++++++++
rename from /home/dave/source/jedi/test/refactor/import_tree/some_mod.py
rename to /home/dave/source/jedi/test/refactor/import_tree/renamedm.py
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,4 +1,4 @@
-from import_tree import some_mod
+from import_tree import renamedm
 #? 0 renamedm
-some_mod
+renamedm
# -------------------------------------------------- in-package-with-stub
#? 31 renamedm
from import_tree.pkgx import pkgx
# ++++++++++++++++++++++++++++++++++++++++++++++++++
--- /home/dave/source/jedi/test/refactor/import_tree/pkgx/__init__.py
+++ /home/dave/source/jedi/test/refactor/import_tree/pkgx/__init__.py
@@ -1,3 +1,3 @@
-def pkgx():
+def renamedm():
     pass
--- /home/dave/source/jedi/test/refactor/import_tree/pkgx/__init__.pyi
+++ /home/dave/source/jedi/test/refactor/import_tree/pkgx/__init__.pyi
@@ -1,2 +1,2 @@
-def pkgx() -> int: ...
+def renamedm() -> int: ...
--- /home/dave/source/jedi/test/refactor/import_tree/pkgx/mod.pyi
+++ /home/dave/source/jedi/test/refactor/import_tree/pkgx/mod.pyi
@@ -1,2 +1,2 @@
-from . import pkgx
+from . import renamedm
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,3 +1,3 @@
 #? 31 renamedm
-from import_tree.pkgx import pkgx
+from import_tree.pkgx import renamedm
# -------------------------------------------------- package-with-stub
#? 18 renamedp
from import_tree.pkgx
# ++++++++++++++++++++++++++++++++++++++++++++++++++
rename from /home/dave/source/jedi/test/refactor/import_tree/pkgx
rename to /home/dave/source/jedi/test/refactor/import_tree/renamedp
--- /home/dave/source/jedi/test/refactor/import_tree/pkgx/mod2.py
+++ /home/dave/source/jedi/test/refactor/import_tree/renamedp/mod2.py
@@ -1,2 +1,2 @@
-from .. import pkgx
+from .. import renamedp
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,3 +1,3 @@
 #? 18 renamedp
-from import_tree.pkgx
+from import_tree.renamedp
# -------------------------------------------------- weird-package-mix
if random_undefined_variable:
    from import_tree.pkgx import pkgx
else:
    from import_tree import pkgx
#? 4 rename
pkgx
# ++++++++++++++++++++++++++++++++++++++++++++++++++
rename from /home/dave/source/jedi/test/refactor/import_tree/pkgx
rename to /home/dave/source/jedi/test/refactor/import_tree/rename
--- /home/dave/source/jedi/test/refactor/import_tree/pkgx/__init__.py
+++ /home/dave/source/jedi/test/refactor/import_tree/rename/__init__.py
@@ -1,3 +1,3 @@
-def pkgx():
+def rename():
     pass
--- /home/dave/source/jedi/test/refactor/import_tree/pkgx/__init__.pyi
+++ /home/dave/source/jedi/test/refactor/import_tree/rename/__init__.pyi
@@ -1,2 +1,2 @@
-def pkgx() -> int: ...
+def rename() -> int: ...
--- /home/dave/source/jedi/test/refactor/import_tree/pkgx/mod.pyi
+++ /home/dave/source/jedi/test/refactor/import_tree/rename/mod.pyi
@@ -1,2 +1,2 @@
-from . import pkgx
+from . import rename
--- /home/dave/source/jedi/test/refactor/import_tree/pkgx/mod2.py
+++ /home/dave/source/jedi/test/refactor/import_tree/rename/mod2.py
@@ -1,2 +1,2 @@
-from .. import pkgx
+from .. import rename
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,7 +1,7 @@
 if random_undefined_variable:
-    from import_tree.pkgx import pkgx
+    from import_tree.rename import rename
 else:
-    from import_tree import pkgx
+    from import_tree import rename
 #? 4 rename
-pkgx
+rename
