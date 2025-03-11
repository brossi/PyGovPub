#!/usr/bin/env python3
"""
Performance test runner for PyGovPub.

This script runs all performance tests and generates a performance report.
"""

import os
import sys
import argparse
import subprocess
import glob
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

# Import performance history utilities
try:
    from tests.performance.metrics.performance_history import print_summary_report, generate_trend_charts
    HISTORY_AVAILABLE = True
except ImportError:
    HISTORY_AVAILABLE = False
    print("Performance history module not available. Historical data won't be tracked.")


def find_performance_tests():
    """Find all performance test files."""
    test_files = []
    
    # Search in metrics directory
    metrics_path = os.path.join(project_root, "tests", "performance", "metrics")
    test_files.extend(glob.glob(os.path.join(metrics_path, "test_*.py")))
    
    # Search in performance directory
    perf_tests = glob.glob(os.path.join(project_root, "tests", "performance", "test_*.py"))
    test_files.extend(perf_tests)
    
    return test_files


def run_performance_test(test_file, verbose=False):
    """Run a single performance test file."""
    print(f"Running performance test: {os.path.basename(test_file)}")
    
    # Build command
    cmd = ["python", "-m", "pytest", test_file, "-v"]
    
    # Run the test
    try:
        result = subprocess.run(
            cmd, 
            cwd=project_root,
            capture_output=not verbose,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            print(f"✅ Test passed: {os.path.basename(test_file)}")
            return True
        else:
            print(f"❌ Test failed: {os.path.basename(test_file)}")
            if not verbose:
                print("Errors:")
                print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error running test {os.path.basename(test_file)}: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run performance tests for PyGovPub")
    parser.add_argument("--tests", "-t", nargs="*", help="Specific test files to run")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")
    parser.add_argument("--report-only", "-r", action="store_true", help="Only generate report, don't run tests")
    args = parser.parse_args()
    
    # Print header
    print("\n========== PyGovPub Performance Test Runner ==========\n")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project: {project_root}")
    
    if args.report_only:
        print("\nGenerating performance report only...\n")
    else:
        # Find test files
        if args.tests:
            test_files = []
            for pattern in args.tests:
                # Handle both direct files and patterns
                if os.path.isfile(pattern):
                    test_files.append(pattern)
                else:
                    matching_files = glob.glob(os.path.join(project_root, "**", pattern), recursive=True)
                    test_files.extend(matching_files)
        else:
            test_files = find_performance_tests()
        
        print(f"Found {len(test_files)} performance test files\n")
        
        # Run tests
        results = []
        for test_file in test_files:
            success = run_performance_test(test_file, args.verbose)
            results.append((test_file, success))
            print()  # Add blank line between tests
        
        # Print summary
        print("\n--- Test Run Summary ---")
        success_count = sum(1 for _, success in results if success)
        print(f"Ran {len(results)} tests, {success_count} passed, {len(results) - success_count} failed")
    
    # Generate performance report
    if HISTORY_AVAILABLE:
        print("\n--- Generating Performance Trend Charts ---")
        charts = generate_trend_charts()
        print(f"Generated {len(charts)} performance trend charts")
        
        print("\n--- Performance History Summary ---")
        print_summary_report()
    
    print("\n========== Performance Test Run Complete ==========\n")


if __name__ == "__main__":
    main()