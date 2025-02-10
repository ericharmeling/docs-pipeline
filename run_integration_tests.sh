#!/bin/bash

# Exit on any error
set -e

echo "Building Docker image for integration tests..."
docker build -t doc-builder-tests -f tests/integration/Dockerfile .

echo "Running integration tests..."
docker run --rm doc-builder-tests

# Get the exit code from the test run
TEST_EXIT_CODE=$?

echo "Test run completed with exit code: $TEST_EXIT_CODE"
exit $TEST_EXIT_CODE 