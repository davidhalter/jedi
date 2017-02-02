#!/usr/bin/env bash

python setup.py sdist bdist_wheel
# Maybe do a pip install twine before.
twine upload dist/*
