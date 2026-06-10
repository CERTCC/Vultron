#!/bin/bash
# Test that docker-compose configuration is valid and PROJECT_NAME is set

cd "$(dirname "$0")/../../docker" || exit 1

# Test 1: Check that .env file exists
if [ ! -f .env ]; then
    echo "FAIL: .env file not found"
    exit 1
fi

# Test 2: Check that PROJECT_NAME is set in .env
if ! grep -q "PROJECT_NAME=" .env; then
    echo "FAIL: PROJECT_NAME not found in .env"
    exit 1
fi

# Test 3: Check that docker-compose config doesn't produce warnings about missing PROJECT_NAME
# Capture both stdout and stderr
output=$(docker-compose config 2>&1)
if echo "$output" | grep -q "PROJECT_NAME.*is not set"; then
    echo "FAIL: docker-compose config produces warnings about missing PROJECT_NAME"
    echo "$output" | grep "PROJECT_NAME" | head -3
    exit 1
fi

# Test 4: Check that image names are properly formed (should start with 'vultron-')
if ! echo "$output" | grep -q "image: vultron-"; then
    echo "FAIL: Image names are not properly formed (expected format: vultron-*:latest)"
    echo "$output" | grep 'image:' | head -5
    exit 1
fi

echo "PASS: Docker Compose configuration is valid"
exit 0
