set -e

python regression.py
python run.py
echo
python refactor.py
echo
nosetests --with-doctest --doctest-tests ../jedi/
