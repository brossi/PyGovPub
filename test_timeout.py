#!/usr/bin/env python3
"""
Test script for intelligent timeout calculation.
"""

import os
import sys
import time
from pathlib import Path

def test_timeout(path):
    """Test the intelligent timeout calculation for a path."""
    print(f"\nTesting timeout for: {path}")

    start = time.time()
    from utilities.test_and_refactor import calculate_intelligent_timeout

    # Clear the LRU cache to get fresh results
    calculate_intelligent_timeout.cache_clear()

    # Calculate the timeout
    timeout = calculate_intelligent_timeout(path)
    elapsed = time.time() - start

    print(f"Calculation took {elapsed:.2f} seconds")
    print(f"Final timeout: {timeout} seconds ({timeout/60:.1f} minutes)")
    print("-" * 80)

    return timeout

def main():
    """Test the intelligent timeout calculation with different paths."""
    # Test with a small file
    test_timeout("utilities/uncover_ignore.py")

    # Test with a medium-sized file
    test_timeout("utilities/source_analyzer.py")

    # Test with a directory
    test_timeout("utilities")

    # Test with a module path
    test_timeout("utilities.source_analyzer")

    # Test with a non-existent path
    test_timeout("nonexistent_path")

    # Test with a test directory
    test_timeout("tests")

    # Test with an empty file
    empty_file = Path("empty_file.py")
    empty_file.write_text("")
    try:
        test_timeout("empty_file.py")
    finally:
        empty_file.unlink(missing_ok=True)

    # Test with a small file
    small_file = Path("small_file.py")
    small_file.write_text("# This is a small file\ndef hello():\n    print('Hello, world!')\n")
    try:
        test_timeout("small_file.py")
    finally:
        small_file.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
