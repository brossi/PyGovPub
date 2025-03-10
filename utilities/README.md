# PyGovPub Utilities

This directory contains utility scripts and tools to support the development and maintenance of the PyGovPub project.

## Core Utilities

### Source Analysis

- **source_analyzer.py**: Analyzes Python source code for quality metrics, complexity, and code smells.
  - Usage: `python -m utilities.source_analyzer --path <path_to_file_or_directory>`
  - Features:
    - Calculates cyclomatic and cognitive complexity
    - Detects code smells and anti-patterns
    - Analyzes dependencies between modules
    - Provides maintainability metrics
    - Identifies refactoring opportunities

### Test and Refactoring

- **test_and_refactor.py**: Runs tests with coverage analysis and performs refactoring analysis.
  - Usage: `./test_refactor.sh --package <package_name> --test-path <test_path> [options]`
  - Options:
    - `--detailed`: Include detailed refactoring recommendations
    - `--skip-tests`: Skip running tests and use existing coverage data
    - `--timeout <seconds>`: Maximum time to wait for command completion
    - `--base-timeout <seconds>`: Base timeout for intelligent calculation

- **refactor_analyzer.py**: Standalone tool for analyzing code and suggesting refactoring opportunities.
  - Usage: `python -m utilities.refactor_analyzer --path <path_to_file_or_directory>`
  - Features:
    - Identifies functions that are too long or complex
    - Suggests extract method opportunities
    - Detects duplicate code
    - Analyzes conditional complexity

### Coverage Analysis

- **projected_coverage.py**: Analyzes test coverage and projects future coverage with test stubs.
  - Usage: `./utilities/projected_coverage.py [options]`
  - Options:
    - `--package <package>`: Analyze specific package
    - `--report`: Show latest coverage report
    - `--history`: Display coverage history
    - `--all-packages`: Analyze all packages
    - `--verbose`: Show detailed output

### Utilities Integration

- **coverage_refactoring_bridge.py**: Integrates coverage data with refactoring analysis.
  - Usage: `python -m utilities.coverage_refactoring_bridge --package <package_name>`
  - Features:
    - Prioritizes refactoring based on coverage data
    - Identifies high-risk, low-coverage code
    - Generates targeted recommendations

### Documentation Utilities

- **update_timestamp.sh**: Updates "Last Updated" field in markdown files.
  - Usage: `utilities/update_timestamp.sh <markdown_file> [section_id]`
  - Note: Process one file at a time

## Documentation

Detailed documentation for each utility is available in the following files:

- [README_TEST_AND_REFACTOR.md](README_TEST_AND_REFACTOR.md): Documentation for test_and_refactor.py
- [README_REFACTOR_ANALYZER.md](README_REFACTOR_ANALYZER.md): Documentation for refactor_analyzer.py
- [README_COVERAGE_REFACTORING_BRIDGE.md](README_COVERAGE_REFACTORING_BRIDGE.md): Documentation for coverage_refactoring_bridge.py

## Usage in Development Workflow

These utilities should be used at various stages of the development process:

1. **Before Implementation**: Use projected_coverage.py to identify areas needing tests
2. **During Development**: Use source_analyzer.py to check code quality
3. **After Implementation**: Use test_and_refactor.py to verify test coverage and identify refactoring opportunities
4. **Before Task Completion**: Run the full test suite with all analysis tools

## Integration with CI/CD

The utilities are designed to be integrated into CI/CD pipelines:

```yaml
# Example CI/CD step
test_and_analyze:
  script:
    - ./test_refactor.sh --package pygovpub --test-path tests/unit/ --detailed
    - ./utilities/projected_coverage.py --all-packages --verbose
```
