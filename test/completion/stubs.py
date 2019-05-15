from stub_folder import with_stub, stub_only, with_stub_folder, stub_only_folder

# Just files

#? int()
stub_only.in_stub_only
#? str()
with_stub.in_with_stub_both
#?
with_stub.in_with_stub_python
#? float()
with_stub.in_with_stub_stub


# Folders

#? int()
stub_only_folder.in_stub_only_folder
#? str()
with_stub_folder.in_with_stub_both_folder
#?
with_stub_folder.in_with_stub_python_folder
#? float()
with_stub_folder.in_with_stub_stub_folder

# Folders nested

from stub_folder.with_stub_folder import nested_stub_only, nested_with_stub, \
    python_only

#? int()
nested_stub_only.in_stub_only
#? float()
nested_with_stub.in_both
#?
nested_with_stub.in_python
#? int()
nested_with_stub.in_stub
#? str()
python_only.in_python
