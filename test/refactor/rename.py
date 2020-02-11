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
from import_tree.mod import foobar
#? 0 renamed
foobar
# ++++++++++++++++++++++++++++++++++++++++++++++++++
--- /home/dave/source/jedi/test/refactor/import_tree/mod.py
+++ /home/dave/source/jedi/test/refactor/import_tree/mod.py
@@ -1,2 +1,2 @@
-foobar = 3
+renamed = 3
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,4 +1,4 @@
-from import_tree.mod import foobar
+from import_tree.mod import renamed
 #? 0 renamed
-foobar
+renamed
# -------------------------------------------------- module
from import_tree import mod
#? 0 renamedm
mod
# ++++++++++++++++++++++++++++++++++++++++++++++++++
rename from /home/dave/source/jedi/test/refactor/import_tree/mod.py
rename to /home/dave/source/jedi/test/refactor/import_tree/renamedm.py
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,4 +1,4 @@
-from import_tree import mod
+from import_tree import renamedm
 #? 0 renamedm
-mod
+renamedm
