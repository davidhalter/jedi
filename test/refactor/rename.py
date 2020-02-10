"""
Test coverage for renaming is mostly being done by testing
`Script.get_references`.
"""

# ----- simple
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
