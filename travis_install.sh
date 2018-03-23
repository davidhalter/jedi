#! /usr/bin/env bash
set -e

# Check if the desired Python version already exists.
$JEDI_TEST_ENVIRONMENT --version && exit 0 || true

# Otherwise download and install.
VERSION=`expr "$JEDI_TEST_ENVIRONMENT" : '.*\([0-9]\.[0-9]\)'`
DOWNLOAD_NAME=python-$VERSION
wget https://s3.amazonaws.com/travis-python-archives/binaries/ubuntu/14.04/x86_64/$DOWNLOAD_NAME.tar.bz2
sudo tar xjf $DOWNLOAD_NAME.tar.bz2 --directory /

echo "Successfully installed environment."
