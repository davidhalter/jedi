#!/usr/bin/env bash

rm -rf dist/
python setup.py sdist bdist_wheel
# Maybe do a pip install twine before.
twine upload dist/*
