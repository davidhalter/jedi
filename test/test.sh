set -e

python regression.py
python run.py
echo
python refactor.py
