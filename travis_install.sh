#! /usr/bin/env bash
set -e

if [[ $JEDI_TEST_ENVIRONMENT == "33" ]]; then
    VERSION=3.3
    DOWNLOAD=1
fi
if [[ $JEDI_TEST_ENVIRONMENT == "35" ]]; then
    VERSION=3.5
    DOWNLOAD=1
fi

if [[ -z $VERSION ]]; then
    echo "Environments should already be installed"
    exit 0
fi

PYTHON=python-$VERSION

# Check if the desired Python version already exists.
$PYTHON --version && exit 0 || true

if [[ $DOWNLOAD == 1 ]]; then
    # Otherwise download and install.
    DOWNLOAD_NAME=python-$VERSION
    wget https://s3.amazonaws.com/travis-python-archives/binaries/ubuntu/14.04/x86_64/$DOWNLOAD_NAME.tar.bz2
    sudo tar xjf $DOWNLOAD_NAME.tar.bz2 --directory /
fi

echo "Successfully installed environment."
