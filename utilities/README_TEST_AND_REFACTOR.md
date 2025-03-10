# Test and Refactor Integration Tool

This tool integrates test execution with refactoring analysis, providing a comprehensive view of both test coverage and code quality in a single command.

## Features

- Runs tests with coverage measurement
- Performs refactoring analysis based on coverage data
- Provides integrated recommendations for improving both test coverage and code quality
- Supports detailed refactoring recommendations
- Offers both text and JSON output formats
- Can skip test execution and use existing coverage data

## Usage

### Basic Usage

```bash
# Run with default settings (analyzes the utilities package with tests in tests/unit)
./test_refactor.sh

# Analyze a specific package with specific tests
./test_refactor.sh --package mypackage --test-path tests/unit/mypackage
```

### Command-line Options

```
usage: test_and_refactor.py [-h] [--package PACKAGE] [--test-path TEST_PATH]
                           [--stub-dir STUB_DIR] [--format {text,json}]
                           [--output OUTPUT] [--detailed] [--skip-tests]

Run tests with coverage and perform refactoring analysis

options:
  -h, --help            show this help message and exit
  --package PACKAGE     Package to analyze (default: utilities)
  --test-path TEST_PATH
                        Path to the tests to run (default: tests/unit)
  --stub-dir STUB_DIR   Directory containing test stubs (can be specified multiple times)
  --format {text,json}  Output format (text or json)
  --output OUTPUT       Output file (default: stdout)
  --detailed            Include detailed refactoring recommendations
  --skip-tests          Skip running tests and use existing coverage data
```

### Examples

#### Run Tests and Analysis for a Specific Module

```bash
./test_refactor.sh --package utilities.source_analyzer --test-path tests/unit/utilities/test_source_analyzer.py
```

#### Skip Tests and Use Existing Coverage Data

```bash
./test_refactor.sh --skip-tests --detailed
```

#### Generate JSON Output to a File

```bash
./test_refactor.sh --format json --output refactoring_report.json
```

#### Include Test Stubs in Analysis

```bash
./test_refactor.sh --stub-dir tests/unit/utilities --stub-dir tests/integration
```

## How It Works

The tool performs the following steps:

1. **Test Execution**: Runs pytest with coverage measurement for the specified package and tests
2. **Coverage-Aware Refactoring Analysis**: Uses the `coverage_refactoring_bridge` to analyze refactoring opportunities with coverage awareness
3. **Standalone Refactoring Analysis**: Runs the standalone `refactor_analyzer` for more detailed code quality insights

## Integration with CI/CD

You can integrate this tool into your CI/CD pipeline by adding a step that runs:

```bash
./test_refactor.sh --format json --output refactoring_report.json
```

This will generate a JSON report that can be parsed by other tools or displayed in your CI/CD dashboard.

## Extending the Tool

The tool is designed to be extensible. You can modify the `utilities/test_and_refactor.py` script to add more features, such as:

- Generating HTML reports
- Sending notifications when code quality degrades
- Integrating with issue tracking systems
- Adding thresholds for failing the build when code quality is too low
