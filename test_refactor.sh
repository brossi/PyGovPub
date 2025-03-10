#!/bin/bash
# Simple wrapper for the test_and_refactor.py script

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to the project root directory
cd "$SCRIPT_DIR"

# Run the Python script with all arguments passed to this script
python -m utilities.test_and_refactor "$@"
