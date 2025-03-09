# PyGovPub Development Guide

"There is also the other side of the coin minted by Einstein: 'Everything should be as simple as it can be, but not simpler' – a scientist's defense of art and knowledge – of lightness, completeness and accuracy."

1950 June, Poetry, Reviews section, Poetry in a Modern Age by Louis Zukofsky, (Review of the volume "William Carlos Williams" by Vivienne Koch (The Makers of Modern Literature Series)), Page 180, Volume 76, Number 3, Modern Poetry Association. (Google Books snippet view. Verified on paper) [link](http://books.google.com/books?id=GQEKAAAAIAAJ&q=minted#search_anchor)

## Project Overview

PyGovPub is a Python SDK that provides unified access to U.S. Federal Government data through integration with Congress.gov and GovInfo.gov APIs. The SDK aims to simplify access to legislative and regulatory data while ensuring document authenticity and maintaining compliance with API rate limits.

### Core Objectives
- **Intelligent Integration**: Deduplicate overlapping data sources while preserving authoritative origins (e.g., Congress.gov for real-time status, GovInfo.gov for authenticated documents)
- **Data Normalization**: Provide consistent, reliable schemas that normalize disparate data models from multiple government sources
- **Trust Building**: Ensure data authenticity through digital signature verification, authoritative source tracking, and comprehensive audit trails
- **Smart Routing**: Automatically direct requests to optimal data sources based on freshness, authenticity needs, and rate limit availability
- **Unified Access**: Abstract away the complexity of multiple government APIs behind a cohesive, well-documented interface
- **Data Quality**: Implement cross-validation between sources to ensure accuracy and completeness of government data
- **Resilient Updates**: Enable real-time legislative updates with guaranteed delivery and conflict resolution

### Key Use Cases
- **Legislative Tracking**: Monitor bills, amendments, and committee activities
- **Document Retrieval**: Access authenticated government documents with version tracking
- **Member Information**: Access current and historical data about Congressional members, including roles, committee assignments, and legislative activities
- **Regulatory Monitoring**: Track Federal Register publications and CFR updates
- **Real-time Updates**: Receive notifications of legislative and regulatory changes as soon as they are published by official sources
- **Data Integration**: Combine data from multiple government sources with consistent schemas

### Target Users
- Government Affairs Software Developers
- Legislative Tracking Applications
- Regulatory Compliance Systems
- Legal Research Platforms
- Public Policy Research Organizations

## Architecture Overview

### Component Structure
1. **Core SDK Layer**
   - API client management
   - Authentication handling
   - Rate limit monitoring
   - Document verification

2. **Data Integration Layer**
   - Schema normalization
   - Cross-reference resolution
   - Version tracking
   - Change detection

3. **Real-time Updates Layer**
   - Webhook management
   - Event filtering
   - Delivery monitoring
   - Retry handling

### External API Integration

#### Congress.gov API
- **Rate Limit**: 5,000 requests/hour
- **Authentication**: API key in header
- **Primary Uses**:
  - Legislative data
  - Committee information
  - Member activities
  - Real-time updates

#### GovInfo.gov API
- **Rate Limit**: 1,000 requests/hour
- **Authentication**: API key in parameters
- **Primary Uses**:
  - Document retrieval
  - Digital signatures
  - Bulk data access
  - Publication metadata

### Design Decisions & Constraints

1. **Authentication**
   - All requests must be authenticated
   - API keys stored in environment variables
   - Automatic rate limit management

2. **Data Consistency**
   - Congress.gov is primary source for real-time status
   - GovInfo.gov is primary source for documents
   - Conflicts resolved using timestamp-based precedence

3. **Performance**
   - Aggressive caching of document content
   - Lazy loading of related data
   - Background processing for updates
   - Rate limit pooling across requests

4. **Reliability**
   - Automatic retries with exponential backoff
   - Circuit breakers for API failures
   - Persistent queue for webhook delivery
   - Transaction-based data updates

## Commands
- **Environment Setup**:
  - Activate the virtual environment: `source venv/bin/activate`
  - Install in development mode: `pip install -e .`
- **Run Tests**:
  - All tests: `pytest`
  - Specific test: `pytest tests/unit/pygovpub/auth/test_models.py::test_function_name`
  - With coverage: `pytest --cov=pygovpub tests/unit/`
  - Full test suite with detailed output: `./test_refactor.sh --package pygovpub --test-path tests/unit/ --detailed`
- **Linting**: `flake8` or `ruff check .`
- **Type Checking**: `mypy .`
- **Format Code**: `black .`
- **Update Timestamps**: `utilities/update_timestamp.sh <markdown_file>` (updates "Last Updated" field in markdown files to current UTC time)
  - Note: Process one file at a time; for multiple files, run separate commands
  - Optional section ID: `utilities/update_timestamp.sh <markdown_file> <section_id>`
- **Coverage Analysis**:
  - Basic usage: `./utilities/projected_coverage.py` (analyzes all stubs)
  - Analyze specific package: `./utilities/projected_coverage.py --package pygovpub.auth`
  - View latest coverage report: `./utilities/projected_coverage.py --report`
  - Check coverage history: `./utilities/projected_coverage.py --history`
  - Analyze all packages: `./utilities/projected_coverage.py --all-packages`
  - Detailed verbose output: `./utilities/projected_coverage.py --verbose`
- **Source Analysis and Refactoring**:
  - Run source analysis: `python -m utilities.source_analyzer --path <path_to_file_or_directory>`
  - Run refactoring analysis: `./test_refactor.sh --package <package_name> --test-path <test_path>`
  - Run standalone refactoring analysis: `python -m utilities.refactor_analyzer --path <path_to_file_or_directory>`
  - Run with intelligent timeout: `./test_refactor.sh --package <package_name> --timeout 0`

IMPORTANT: Always use the Python 3.13 virtual environment in `venv/` for all development. This ensures consistent dependencies and package versions across all development environments.

## Test Directory Structure

All tests MUST follow these organization rules:

1. **Location**: All tests must reside in the `/tests/` directory at project root
   - Unit tests: `/tests/unit/pygovpub/...`
   - Integration tests: `/tests/integration/...`
   - Do NOT place tests in `/src/tests/` or create nested test directories

2. **Structure**: Tests must mirror the package structure
   - For module `src/pygovpub/auth/models.py`
   - Test at `tests/unit/pygovpub/auth/test_models.py`

3. **Imports**: Use package imports ONLY
   - Correct: `from pygovpub.auth.models import ApiCredential`
   - Incorrect: `import sys; sys.path.insert(0, 'src')`

4. **Configuration**: All path resolution happens through conftest.py
   - Do NOT manually modify sys.path in test files
   - Use pytest fixtures for test dependencies

## Test Stubs and Coverage Projection

The project uses test stubs to plan coverage and document testing requirements before implementation.

### Creating Test Stubs

Test stubs are automatically excluded from test runs using these patterns:

1. **Function name contains "stub"**:
   ```python
   def test_stub_api_validation():
       """This stub tests API validation logic."""
       assert True
   ```

2. **Function contains a STUB comment**:
   ```python
   def test_auth_flow():
       # STUB: This tests lines 45-60 in auth_manager.py
       """Tests authentication flow."""
       assert True
   ```

3. **Function contains a WIP comment**:
   ```python
   def test_complex_scenario():
       # WIP: Will implement when feature is complete
       """Tests a complex scenario."""
       assert False  # Would fail if run, but won't be run
   ```

### Coverage Projection

Use the `projected_coverage.py` tool to predict coverage after stub implementation and track coverage history:

```bash
# Basic usage - analyzes auth package and all stubs
./utilities/projected_coverage.py

# Custom analysis
./utilities/projected_coverage.py --package pygovpub.core --stub-dir tests/unit/core

# View latest coverage report
./utilities/projected_coverage.py --report

# View coverage history
./utilities/projected_coverage.py --history
```

The tool automatically stores coverage results in `.coverage_history.json` for quick reference. This history file maintains records of test coverage over time, including:
- Overall coverage percentage
- Module-specific coverage statistics
- Uncovered line numbers
- Timestamp of each test run

This feature allows for tracking coverage progress without re-running tests, which is especially useful for:
- Checking current test coverage status
- Comparing coverage between different modules
- Identifying persistent uncovered lines
- Documenting coverage improvements over time

### Test Stub Best Practices

1. Document which lines of code the stub will test using `# STUB: This tests lines X-Y`
2. Create stubs alongside implementation to ensure complete coverage
3. Add detailed docstrings explaining what will be tested
4. Keep stubs in sync with code changes
5. See `docs/test_stubs.md` for complete documentation

## Style Guidelines
- **Imports**: Group imports: stdlib, third-party, local. Sort alphabetically within groups.
- **Formatting**: Follow PEP 8 with 88-character line limit (Black default).
- **Type Hints**: Use type annotations for all function parameters and return values.
- **Naming**: Use snake_case for variables/functions, PascalCase for classes, UPPER_CASE for constants.
- **Documentation**: All public APIs must have docstrings following Google style.
- **Error Handling**: Use specific exceptions, prefer context managers, handle API rate limits gracefully.
- **Testing**: Write unit tests for all functions, mock external API calls.

This project follows FastAPI, Pydantic, and SQLModel conventions where applicable.

## Planning Resources

The `planning/` directory contains specification documents that should be consulted during development. These resources define the project requirements, architecture, and implementation guidelines.

### Core Documentation
- `planning/README.md` - Project overview, architecture diagrams, and feature requirements
- `planning/functional-overview.md` - SDK functional requirements and boundaries
- `planning/fastapi-router-structure.md` - API structure specification
- `planning/database-schema.md` - Database schema specification
- `planning/checklist-guide.md` - Development process and quality guidelines
- `planning/bill-version-codes.md` - Comprehensive guide to legislative bill version codes
- `planning/dev-learnings.md` - Documented challenges and solutions from implementation
- `planning/phronesis.md` - Knowledge repository of implementation experience
- `planning/phronesis-llm.md` - LLM-optimized format of development insights

### Implementation Phases
The `planning/actions/` directory contains phase-specific implementation guides:
- `00-phase.md` - Phase sequencing and dependencies
- `01-dx003.md` - Local Development Environment
- `02-auth001.md` - API Authentication Management
- `03-core002.md` - Error Handling
- `04-core001.md` - Unified Data Response Format
- `05-dx004.md` - Development Logging and Debugging
- `06-dx001.md` - SDK Health Check and Validation
- `07-dx002.md` - Command Line Interface
- `08-completion.md` - Public Service Achievement Validation
- `09-cicd.md` - CI/CD Pipeline Implementation

### Standards & Conventions
The `planning/standards/` directory defines project standards:
- `naming-conventions.md` - Naming standards for code and documentation
- `api-documentation.md` - OpenAPI documentation requirements
- `version-compatibility.md` - Version tracking and compatibility standards

### API Specifications
The `planning/endpoints/` directory contains detailed specifications for each API area:
- `authentication/` - Authentication requirements and workflows
- `documents/` - Document handling specifications
- `legislative/` - Legislative data API specifications
- `regulatory/` - Regulatory content API specifications
- `updates/` - Real-time update system specifications

### External API Documentation
The `planning/dev-references/` directory contains essential API documentation:
- `congress_gov-api-documentation.md` - Official Congress.gov API documentation
  - Authentication requirements
  - Endpoint specifications
  - Rate limits and quotas
  - Data models and schemas
  - Real-time update mechanisms

- `govInfo-api-docs-and-samples.txt` - Official GovInfo.gov API documentation
  - Authentication methods
  - Package ID formats
  - Bulk data access
  - Digital signatures
  - Version tracking

- `bill-status-implementation-guide.md` - Bill status tracking implementation
- `library-implementation-guide.md` - SDK implementation patterns
- `uslm-implementation-guide.md` - United States Legislative Markup guide

### Quality Assurance
The `planning/qa/` directory contains:
- `unit-test-manifest.md` - Unit testing requirements and coverage standards
- `integration-test-manifest.md` - Integration testing specifications
- `logging-strategy.md` - Logging standards and implementation
- `openapi_validation.py` - API documentation validation tools

### Development Tools
- `utilities/` - Development and maintenance scripts
  - `update_timestamp.sh` - Updates markdown file timestamps
  - `projected_coverage.py` - Analyzes test coverage, tracks history, and projects future coverage with stubs
  - Additional development utilities

## Development Process

Do not use the phrase: "I found the issue." or variants of the same meaning.

### Phase Sequencing
Development MUST follow the phase sequence defined in `00-phase.md`:
1. Local Development Environment [DX-003] ✅ COMPLETED
2. API Authentication Management [AUTH-001] ✅ COMPLETED
3. Error Handling [CORE-002] ⏩ NEXT
4. Unified Data Response Format [CORE-001]
5. Development Logging and Debugging [DX-004]
6. SDK Health Check and Validation [DX-001]
7. Command Line Interface [DX-002]
8. Public Service Achievement Validation
9. CI/CD Pipeline Implementation

### Checklist Management
IMPORTANT: When implementing a phase, update the checklist in the corresponding action file (e.g., `planning/actions/02-auth001.md` for AUTH-001) AS YOU COMPLETE EACH TASK. Do not wait until the end to mark all items complete at once. So is it generated: [Claude.Anthropic.3.7.Sonnet-20250219-UpdatedInstructions-2025-03-08-04:01-UTC]

#### Task Completion Verification Requirements
CRITICAL FOR ALL AI AGENTS: Before marking ANY task as complete [x] in the phase checklists, you MUST:

1. Run the full test suite: `pytest`
2. Run projected coverage analysis: `./utilities/projected_coverage.py --all-packages --verbose`
3. Run source analysis on the relevant package: `python -m utilities.source_analyzer --path <package_path>`
4. Run refactoring analysis: `./test_refactor.sh --package <package_name> --test-path <test_path>`
5. Verify ALL tests pass without errors or warnings
6. If any tests fail:
   - Fix all errors related to your implementation
   - Document any pre-existing errors that cannot be fixed in the current phase
   - Explain your reasoning for leaving any errors unfixed

DO NOT mark tasks as complete until you have verified through comprehensive testing that your implementation works correctly and integrates properly with the existing codebase. This verification step is non-negotiable and essential for maintaining code quality.

Each completed task should:
1. Be marked with [x] immediately after implementation AND verification
2. Have its corresponding test implemented and passing
3. Include any necessary documentation updates
4. Follow the style guidelines and code quality standards
5. Have passed all required test suites and analysis tools

### Full Test Suite Execution
The full test suite MUST be run before considering any task complete. This includes:

1. **Unit Tests**: Verify individual components work as expected
   ```bash
   pytest tests/unit/
   ```

2. **Integration Tests**: Verify components work together correctly
   ```bash
   pytest tests/integration/
   ```

3. **Coverage Analysis**: Ensure adequate test coverage
   ```bash
   pytest --cov=pygovpub tests/
   ./utilities/projected_coverage.py --all-packages --verbose
   ```

4. **Source Analysis**: Check code quality and complexity
   ```bash
   python -m utilities.source_analyzer --path src/pygovpub/
   ```

5. **Refactoring Analysis**: Identify potential improvements
   ```bash
   ./test_refactor.sh --package pygovpub --test-path tests/unit/ --detailed
   ```

6. **Combined Test and Analysis**: Run all tests and analysis in one command
   ```bash
   ./test_refactor.sh --package pygovpub --test-path tests/unit/ --detailed
   ```

### Session Initialization Requirement
MANDATORY FOR ALL AI AGENTS: At the beginning of EVERY new session, you MUST:

1. Run the full test suite to establish the current state of the codebase:
   ```bash
   ./test_refactor.sh --package pygovpub --test-path tests/unit/ --detailed
   ```

2. Review the test results to understand:
   - Current passing/failing tests
   - Code coverage status
   - Identified code quality issues
   - Refactoring opportunities

3. Summarize the test results for the user, highlighting:
   - Overall test pass/fail status
   - Coverage percentage
   - Critical issues that need attention
   - Stubs that need implementation

This initialization process is required before engaging in any development tasks to ensure you have an accurate understanding of the current codebase state.

### Quality Gates
Each phase must pass the quality gates defined in `08-completion.md`:
1. All tests pass with zero warnings/exceptions
2. 100% code coverage on critical paths
3. All integration tests pass in isolation
4. No deprecation warnings
5. Static type checking passes
6. Documentation complete
7. Commit hash recorded
8. Full test suite execution completed with all analyses

### Test Maintenance Best Practices
When adding new features or command-line options, remember to update all test mocks:

1. **Update all test mocks**: When adding a new parameter to any function or CLI, add it to all mock objects
   - Example: After adding `--all-packages` to a CLI tool, add `all_packages = False` to all mock argument objects
   - This applies even to tests not directly testing the new functionality

2. **Match exact output formats**: When mocking output formats (like reports), include all section markers and formatting
   - Example: Include section markers like `---------- coverage:` and respect exact spacing/indentation
   - Use real command output as reference for creating test mock data

3. **Fix failing tests immediately**: Don't let failing tests linger
   - Postponed fixes can mask real problems
   - Fixed tests increase confidence when making further changes
   - Always run related tests after fixing a specific test

These practices prevent the "broken windows effect" in your test suite - small failures that lead to bigger problems over time [Claude.Anthropic.3.7.Sonnet-20250308-TestMaintenancePractices]

### API Integration Requirements
When working with external APIs:
1. Congress.gov API
   - Rate Limit: 5,000 requests/hour
   - Authentication: API key in header
   - Documentation: `dev-references/congress_gov-api-documentation.md`
   - Version Compatibility: `standards/version-compatibility.md`

2. GovInfo.gov API
   - Rate Limit: 1,000 requests/hour (bulk downloads exempt)
   - Authentication: API key in parameters
   - Documentation: `dev-references/govInfo-api-docs-and-samples.txt`
   - Package IDs: Follow USLM guidelines

## Development Approach

When implementing features, follow this process:

1. **Consult Specifications**: Review relevant documentation in the `planning/` directory
2. **Follow Workflows**: Implement according to the workflow diagrams in `*/workflows.md` files
3. **Adhere to Schema**: Follow database schema in `database-schema.md`
4. **Meet API Requirements**: Implement endpoints as specified in `fastapi-router-structure.md`
5. **Follow Checklist Process**: Use development checklist from `checklist-guide.md`

## Testing Requirements

Implement tests according to the test requirements specified in:
- `planning/qa/` directory
- Test coverage requirements in `planning/README.md`

All code should be developed test-first following the process in `checklist-guide.md`.

For coverage verification:
1. Run `./utilities/projected_coverage.py` after implementing new tests
2. Check the `--report` command to verify current coverage metrics
3. Use the coverage history to track improvements over time
4. Aim for 100% coverage on critical paths as mandated by quality gates
5. Document any intentionally uncovered lines with justification

## Implementation Philosophy

DIRECTIVE[CORE]: When evaluating implementation choices, apply Einstein's razor:
1. MIN_COMPLEXITY = necessary_components + essential_interactions
2. MAX_COMPLEXITY = MIN_COMPLEXITY
3. IF proposed_solution.complexity > MAX_COMPLEXITY:
   - REDUCE until complexity == MIN_COMPLEXITY
   - ELSE IF complexity < MIN_COMPLEXITY:
   - ADD missing_essential_components

VALIDATE[EACH_DECISION]:
- Does this component serve core objectives?
- Can it be simpler without losing function?
- Would simplification break essential guarantees?

PATTERN[IMPLEMENTATION]:
```python
def evaluate_solution(proposed: Solution) -> bool:
    essential_components = get_minimum_required(proposed.objective)
    if len(proposed.components) > len(essential_components):
        return False  # Over-engineered
    if not all(required in proposed.components for required in essential_components):
        return False  # Under-engineered
    return True  # Optimal simplicity
```

This balance between simplicity and completeness must be maintained across all phases. Each implementation decision should be validated against these principles to ensure we build exactly what is needed - no more, no less.

[Claude.Anthropic.3.5.Sonnet-20240308-a966fcba-f74b-452c-a3a6-9dc2d3b75de1__1741398986]
