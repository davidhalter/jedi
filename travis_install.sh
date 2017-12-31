set -e
echo "ENV" $JEDI_TEST_ENVIRONMENT
PYTHON=python-3.3

# Check if the desired Python version already exists.
$PYTHON --version && exit 0 || true

# Otherwise download and install.
wget https://s3.amazonaws.com/travis-python-archives/binaries/ubuntu/14.04/x86_64/$PYTHON.tar.bz2
sudo tar xjf $PYTHON.tar.bz2 --directory /
$PYTHON --version
