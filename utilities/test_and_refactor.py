#!/usr/bin/env python3
"""
Test and Refactor Integration Script

This script runs pytest with coverage and then performs refactoring analysis
on the results, providing an integrated view of test coverage and code quality.

Usage:
    python -m utilities.test_and_refactor [--package PACKAGE] [--test-path TEST_PATH] [--stub-dir STUB_DIR] [--format {text,json}] [--output OUTPUT] [--detailed]

Example:
    python -m utilities.test_and_refactor --package utilities --test-path tests/unit/utilities
"""

import argparse
import subprocess
import sys
import os
import signal
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import datetime
import time
import math
import statistics
from functools import lru_cache

try:
    # When run as a module
    from utilities.uncover_ignore import get_ignore_patterns
except ImportError:
    # When run directly
    from uncover_ignore import get_ignore_patterns


# Global flag to track if we're in the process of terminating
terminating = False


@lru_cache(maxsize=10)
def calculate_intelligent_timeout(path: str, base_timeout: int = 60) -> int:
    """Calculate an intelligent timeout based on codebase size and complexity.

    Args:
        path: Path to the codebase or module
        base_timeout: Base timeout in seconds for a small codebase

    Returns:
        Estimated timeout in seconds
    """
    try:
        # Import here to avoid circular imports
        from utilities.source_analyzer import SourceAnalyzer, SourceFile, AnalysisError

        # Handle module paths that might refer to files
        if '.' in path and not os.path.exists(path):
            # First, check if it's a direct file reference
            module_parts = path.split('.')
            potential_file_path = os.path.join(*module_parts) + '.py'

            if os.path.exists(potential_file_path):
                # It's a file, use the file itself for analysis
                path = potential_file_path
            else:
                # Try as a directory path
                directory_path = path.replace('.', '/')
                if os.path.exists(directory_path):
                    path = directory_path
                else:
                    # Try to find the module in the current directory structure
                    for root, dirs, files in os.walk('.'):
                        module_file = module_parts[-1] + '.py'
                        if module_file in files and all(part in root.split(os.sep) for part in module_parts[:-1]):
                            path = os.path.join(root, module_file)
                            break
                    else:
                        # If we still can't find it, try just the last part of the path
                        last_part = module_parts[-1]
                        if os.path.exists(last_part + '.py'):
                            path = last_part + '.py'
                        elif os.path.exists(last_part):
                            path = last_part

        # If path doesn't exist, use a minimal timeout
        if not os.path.exists(path):
            print(f"Path not found: {path}, using minimal timeout of 10 seconds")
            return 10  # Minimal timeout for non-existent paths

        # For a single file, use SourceAnalyzer to get complexity metrics
        if os.path.isfile(path):
            try:
                analyzer = SourceAnalyzer()
                source_file = analyzer.identify_source_file(Path(path))
                metrics = analyzer.calculate_quality_metrics(source_file)

                # Use actual complexity metrics to determine timeout
                cyclomatic_complexity = metrics.cyclomatic_complexity
                cognitive_complexity = metrics.cognitive_complexity
                loc = metrics.loc

                # Base timeout on complexity metrics
                # Start with a reasonable minimum
                timeout = 15

                # Add time based on code size
                timeout += loc // 50  # 1 second per 50 lines

                # Add time based on complexity
                timeout += cyclomatic_complexity * 2  # 2 seconds per complexity point
                timeout += cognitive_complexity  # 1 second per cognitive complexity point

                print(f"File analysis for {path}:")
                print(f"  - Lines of code: {loc}")
                print(f"  - Cyclomatic complexity: {cyclomatic_complexity}")
                print(f"  - Cognitive complexity: {cognitive_complexity}")
                print(f"  - Calculated timeout: {timeout} seconds")

                return timeout
            except AnalysisError as e:
                # If analysis fails, fall back to a simple calculation
                print(f"Analysis error for {path}: {str(e)}")
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        line_count = len(lines)
                    timeout = 10 + (line_count // 100)
                    print(f"Fallback analysis for {path}:")
                    print(f"  - Lines of code: {line_count}")
                    print(f"  - Calculated timeout: {timeout} seconds")
                    return timeout
                except Exception:
                    return 15  # Minimal timeout for error cases
            except Exception as e:
                print(f"Error analyzing {path}: {str(e)}")
                return 15  # Minimal timeout for error cases

        # For directories, analyze a sample of files to estimate complexity
        analyzer = SourceAnalyzer()
        total_files = 0
        total_loc = 0
        total_complexity = 0
        total_cognitive = 0

        # Limit the number of files to analyze to avoid excessive startup time
        max_files_to_analyze = 10
        files_analyzed = 0

        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        source_file = analyzer.identify_source_file(Path(file_path))
                        metrics = analyzer.calculate_quality_metrics(source_file)

                        total_loc += metrics.loc
                        total_complexity += metrics.cyclomatic_complexity
                        total_cognitive += metrics.cognitive_complexity
                        files_analyzed += 1

                        if files_analyzed >= max_files_to_analyze:
                            break
                    except Exception:
                        # Skip files that can't be analyzed
                        pass

                    total_files += 1

            if files_analyzed >= max_files_to_analyze:
                break

        # Count total Python files without analyzing them all
        if files_analyzed < total_files:
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith('.py'):
                        total_files += 1

        # If no Python files found, use minimal timeout
        if total_files == 0:
            print(f"No Python files found in {path}, using minimal timeout of 10 seconds")
            return 10

        # Calculate average metrics
        avg_loc = total_loc / files_analyzed if files_analyzed > 0 else 0
        avg_complexity = total_complexity / files_analyzed if files_analyzed > 0 else 0
        avg_cognitive = total_cognitive / files_analyzed if files_analyzed > 0 else 0

        # Estimate total LOC based on average
        estimated_total_loc = avg_loc * total_files

        # Base timeout calculation on estimated metrics
        timeout = 30  # Base timeout

        # Add time based on estimated code size
        timeout += estimated_total_loc // 200  # 1 second per 200 lines

        # Add time based on complexity
        timeout += avg_complexity * total_files // 5  # Complexity factor
        timeout += avg_cognitive * total_files // 10  # Cognitive complexity factor

        # Add a factor for number of files (more files = more overhead)
        timeout += total_files // 2

        # Cap the timeout at a reasonable maximum (10 minutes)
        max_timeout = 10 * 60
        timeout = min(int(timeout), max_timeout)

        print(f"Directory analysis for {path}:")
        print(f"  - Python files: {total_files}")
        print(f"  - Files analyzed: {files_analyzed}")
        print(f"  - Average lines of code: {avg_loc:.1f}")
        print(f"  - Average cyclomatic complexity: {avg_complexity:.1f}")
        print(f"  - Average cognitive complexity: {avg_cognitive:.1f}")
        print(f"  - Estimated total LOC: {estimated_total_loc:.0f}")
        print(f"  - Calculated timeout: {timeout} seconds ({timeout/60:.1f} minutes)")

        return timeout
    except ImportError:
        # If SourceAnalyzer is not available, fall back to a simple calculation
        print(f"Warning: SourceAnalyzer not available, using simple timeout calculation")

        # Simple fallback calculation
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    line_count = len(lines)
                timeout = 10 + (line_count // 100)
                return timeout
            except Exception:
                return 15

        # For directories, count files and estimate
        total_files = 0
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith('.py'):
                    total_files += 1

        return 30 + (total_files * 5)  # 5 seconds per file


def signal_handler(sig, frame):
    """Handle termination signals gracefully."""
    global terminating
    if terminating:
        # If we're already terminating, exit immediately
        print("\nForced exit.")
        sys.exit(130)

    terminating = True
    print("\nReceived termination signal. Cleaning up...")
    # Let the normal flow handle the termination
    # This will allow any running processes to be terminated gracefully


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run tests with coverage and perform refactoring analysis"
    )

    parser.add_argument(
        "--package",
        type=str,
        default="utilities",
        help="Package to analyze (default: utilities)"
    )

    parser.add_argument(
        "--test-path",
        type=str,
        default="tests/unit",
        help="Path to the tests to run (default: tests/unit)"
    )

    parser.add_argument(
        "--stub-dir",
        type=str,
        action="append",
        help="Directory containing test stubs (can be specified multiple times)"
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (text or json)"
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Output file (default: stdout)"
    )

    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include detailed refactoring recommendations"
    )

    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running tests and use existing coverage data"
    )

    parser.add_argument(
        "--ignore-file",
        type=str,
        default=".uncoverignore",
        help="Path to the ignore file (default: .uncoverignore)"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=0,  # 0 means use intelligent timeout
        help="Maximum time in seconds to wait for each command to complete (0 = auto-calculate based on codebase size)"
    )

    parser.add_argument(
        "--base-timeout",
        type=int,
        default=60,
        help="Base timeout for intelligent timeout calculation (default: 60 seconds)"
    )

    return parser.parse_args()


def run_command_with_error_handling(cmd: List[str], description: str, timeout: int = 300) -> int:
    """Run a command with error handling.

    Args:
        cmd: The command to run
        description: A description of the command
        timeout: Maximum time to wait for the command to complete (in seconds)

    Returns:
        The exit code from the command
    """
    try:
        print(f"Running command: {' '.join(cmd)}")
        print(f"(Press Ctrl+C to terminate early)")

        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # Stream output in real-time with timeout handling
        start_time = datetime.datetime.now()
        output_lines = []

        try:
            # Read output line by line with timeout checks
            while process.poll() is None:
                # Check if we've exceeded the timeout
                if (datetime.datetime.now() - start_time).total_seconds() > timeout:
                    print(f"\nTimeout exceeded ({timeout} seconds). Terminating process...")
                    process.terminate()
                    try:
                        process.wait(timeout=5)  # Give it 5 seconds to terminate gracefully
                    except subprocess.TimeoutExpired:
                        process.kill()  # Force kill if it doesn't terminate
                    return 1

                # Read a line of output if available
                if process.stdout:
                    line = process.stdout.readline()
                    if line:
                        print(line, end='')
                        output_lines.append(line)
                    else:
                        # No output available, sleep briefly to avoid CPU spinning
                        time.sleep(0.1)

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            print("\nProcess interrupted by user. Terminating gracefully...")
            process.terminate()
            try:
                process.wait(timeout=5)  # Give it 5 seconds to terminate gracefully
            except subprocess.TimeoutExpired:
                process.kill()  # Force kill if it doesn't terminate
            return 130  # Standard exit code for SIGINT

        # Get any remaining output
        remaining_output, _ = process.communicate()
        if remaining_output:
            print(remaining_output, end='')
            output_lines.append(remaining_output)

        return process.returncode

    except Exception as e:
        print(f"\nError running {description}: {str(e)}")
        return 1


def run_tests(package: str, test_path: str, timeout: int = 300) -> int:
    """Run tests with coverage.

    Args:
        package: The package to measure coverage for
        test_path: The path to the tests to run
        timeout: Maximum time to wait for the command to complete (in seconds)

    Returns:
        The exit code from pytest
    """
    print(f"\n{'='*20} RUNNING TESTS {'='*20}")
    cmd = [
        "python", "-m", "pytest",
        test_path,
        f"--cov={package}",
        "--cov-report=term",
        "-v"
    ]

    return run_command_with_error_handling(cmd, "tests", timeout)


def run_refactoring_analysis(
    package: str,
    stub_dirs: Optional[List[str]] = None,
    output_format: str = "text",
    output_file: Optional[str] = None,
    detailed: bool = False,
    ignore_file: str = ".uncoverignore",
    timeout: int = 300
) -> int:
    """Run refactoring analysis with coverage integration.

    Args:
        package: The package to analyze
        stub_dirs: Directories containing test stubs
        output_format: Output format (text or json)
        output_file: Output file (default: stdout)
        detailed: Whether to include detailed recommendations
        ignore_file: Path to the ignore file
        timeout: Maximum time to wait for the command to complete (in seconds)

    Returns:
        The exit code from the refactoring analyzer
    """
    print(f"\n{'='*20} RUNNING REFACTORING ANALYSIS {'='*20}")

    # Read ignore patterns
    exclude_patterns = get_ignore_patterns(ignore_file)

    cmd = [
        "python", "-m", "utilities.coverage_refactoring_bridge",
        "--package", package,
        "--path", ".",
        "--format", output_format
    ]

    if stub_dirs:
        for stub_dir in stub_dirs:
            cmd.extend(["--stub-dir", stub_dir])

    if detailed:
        cmd.append("--detailed")

    if output_file:
        cmd.extend(["--output", output_file])

    return run_command_with_error_handling(cmd, "refactoring analysis", timeout)


def run_standalone_refactor_analysis(package_path: str, ignore_file: str = ".uncoverignore", timeout: int = 300) -> int:
    """Run standalone refactoring analysis without coverage integration.

    Args:
        package_path: Path to the package to analyze
        ignore_file: Path to the ignore file
        timeout: Maximum time to wait for the command to complete (in seconds)

    Returns:
        The exit code from the refactoring analyzer
    """
    print(f"\n{'='*20} RUNNING STANDALONE REFACTORING ANALYSIS {'='*20}")

    # Read ignore patterns
    exclude_patterns = get_ignore_patterns(ignore_file)

    # Handle module paths that might refer to files
    if '.' in package_path:
        # First, check if it's a direct file reference
        module_parts = package_path.split('.')
        potential_file_path = os.path.join(*module_parts) + '.py'

        if os.path.exists(potential_file_path):
            # It's a file, use its directory
            package_path = os.path.dirname(potential_file_path) or '.'
            print(f"Analyzing directory '{package_path}' containing the module file")
        else:
            # Try as a directory path
            directory_path = package_path.replace('.', '/')
            if os.path.exists(directory_path):
                package_path = directory_path
                print(f"Analyzing directory '{package_path}'")
            else:
                # Try to find the module in the current directory structure
                for root, dirs, files in os.walk('.'):
                    module_file = module_parts[-1] + '.py'
                    if module_file in files and all(part in root.split(os.sep) for part in module_parts[:-1]):
                        package_path = root
                        print(f"Found module in directory '{package_path}'")
                        break
                else:
                    # If we still can't find it, try just the last part of the path
                    last_part = module_parts[-1]
                    if os.path.exists(last_part + '.py'):
                        package_path = '.'
                        print(f"Analyzing current directory containing '{last_part}.py'")
                    elif os.path.exists(last_part):
                        package_path = last_part
                        print(f"Analyzing directory '{package_path}'")

    # Ensure the path exists
    if not os.path.exists(package_path):
        print(f"Error: Path not found: {package_path}")
        return 1

    cmd = [
        "python", "-m", "utilities.refactor_analyzer",
        "--path", package_path
    ]

    # Add exclude patterns
    for pattern in exclude_patterns:
        cmd.extend(["--exclude", pattern])

    return run_command_with_error_handling(cmd, "standalone refactoring analysis", timeout)


def check_coverage_data_exists() -> bool:
    """Check if coverage data exists.

    Returns:
        True if coverage data exists, False otherwise
    """
    coverage_file = Path(".coverage")
    return coverage_file.exists()


def main() -> int:
    """Main entry point."""
    # Set up signal handlers for graceful termination
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    args = parse_args()

    # Set up paths
    package = args.package
    test_path = args.test_path
    stub_dirs = args.stub_dir or []

    # Calculate intelligent timeout if not specified
    timeout = args.timeout
    if timeout <= 0:
        timeout = calculate_intelligent_timeout(package, args.base_timeout)

    print("\nNote: If you see errors about empty files in venv/site-packages, these can be safely ignored.")
    print("These are expected and won't affect the analysis of your project code.")
    print("You can press Ctrl+C at any time to terminate the process gracefully.\n")

    # Run tests with coverage unless skipped
    test_result = 0
    if not args.skip_tests:
        test_result = run_tests(package, test_path, timeout)
        if test_result != 0:
            print("\nWarning: Tests failed, but continuing with refactoring analysis")
    elif not check_coverage_data_exists():
        print("\nWarning: No coverage data found. Running tests is recommended.")
        print("You can run tests with: pytest --cov={} {}".format(package, test_path))

    # Check if we're terminating
    global terminating
    if terminating:
        return 130

    # Run refactoring analysis with coverage integration
    refactor_result = run_refactoring_analysis(
        package=package,
        stub_dirs=stub_dirs,
        output_format=args.format,
        output_file=args.output,
        detailed=args.detailed,
        ignore_file=args.ignore_file,
        timeout=timeout
    )

    # Check if we're terminating
    if terminating:
        return 130

    # Also run standalone refactoring analysis for more detailed code quality insights
    standalone_result = run_standalone_refactor_analysis(f"{package}", args.ignore_file, timeout)

    # Return non-zero if any step failed
    if test_result != 0 or refactor_result != 0 or standalone_result != 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
