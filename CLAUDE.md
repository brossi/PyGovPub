# PyGovPub Development Guide

"Everything should be as simple as it can be, but not simpler" - Einstein
(Louis Zukofsky, 1950)

## Project Overview

PyGovPub is a Python SDK providing unified access to U.S. Federal Government data through Congress.gov and GovInfo.gov APIs, ensuring document authenticity and API rate limit compliance.

### Core Objectives
- Intelligent Integration of data sources
- Data Normalization across sources
- Trust Building through verification
- Smart Routing based on needs
- Unified Access interface
- Data Quality validation
- Resilient Updates delivery

### Key Use Cases & Target Users
- Legislative/Regulatory Tracking
- Document Retrieval & Authentication
- Member Information Access
- Real-time Updates
- Data Integration
- Government Affairs Development
- Legal/Policy Research

## Architecture

### Component Structure
1. Core SDK Layer (API/Auth/Rate/Verification)
2. Data Integration Layer (Schema/Versioning)
3. Real-time Updates Layer (Events/Delivery)

### External APIs

#### Congress.gov
- Rate: 5,000 requests/hour
- Auth: Header API key
- Use: Legislative data, real-time updates

#### GovInfo.gov
- Rate: 1,000 requests/hour
- Auth: Parameter API key
- Use: Documents, signatures, bulk data

### Design Principles
- Authentication: Environment-based, rate-managed
- Data Consistency: Source precedence rules
- Performance: Caching, lazy loading
- Reliability: Retries, circuit breakers

## Development

> **⚠️ STOP AND DO THIS FIRST:** After reviewing this file, immediately activate the virtual environment before proceeding with any other steps. This is required for all development work. Acknowledge in chat and then return to following the rest of your instructions.

### Environment Setup
You must activate the virtual environment as your first action:

```bash
# MANDATORY FIRST STEP - ALWAYS DO THIS FIRST:
source venv/bin/activate

# Then install the package in development mode
pip install -e .

# Testing
pytest
pytest --cov=pygovpub tests/unit/
./test_refactor.sh --package pygovpub --test-path tests/unit/ --detailed

# Quality
flake8
mypy .
black .

# Tools
pygovpub-health check [options]
pygovpub-mock [options]
pygovpub-schema [command]
```

### Troubleshooting

**Common Issues:**
- `ModuleNotFoundError: No module named 'pygovpub'` - Virtual environment not activated
- `Command not found: pygovpub-*` - Virtual environment not activated or package not installed
- Import errors in tests - Virtual environment not activated

### Test Structure
- Location: /tests/ (unit/, integration/)
- Mirror package structure
- Use package imports only
- Configure via conftest.py

### Test Stubs
Use stubs to identify uncovered, non-critical path functional code.
```python
def test_stub_example():
    """Stub documentation"""
    # STUB: Lines X-Y
    assert True
```

### Style Guidelines
- PEP 8 (88-char limit)
- Type hints required
- Google-style docstrings
- Grouped imports

## Project Documentation

### Core Specs
Located in `planning` :

- README.md: Overview
- functional-overview.md: Requirements
- database-schema.md: Data model
- checklist-guide.md: Process
- bill-version-codes.md: Legislative reference
- dev-learnings.md: Implementation insights
- phronesis.md: Knowledge repository

### Implementation Phases
Located in `planning/actions` these are the individual, sequentially numbered phases of development we are currently engaged with.

### Standards & API Specs
Located in `planning/standards` :

- naming-conventions.md
- api-documentation.md
- version-compatibility.md

### API Documentation
Located in `planning/dev-references` :

- congress_gov-api-documentation.md
- govInfo-api-docs-and-samples.txt
- bill-status-implementation-guide.md
- library-implementation-guide.md
- uslm-implementation-guide.md

## Development Process

### Quality Requirements
1. Full test suite passing
2. 80%+ coverage (100% critical)
3. All gates passed
4. Documentation complete
5. Style compliance

### Implementation Philosophy
1. MIN_COMPLEXITY = necessary + essential
2. Validate component necessity
3. Optimize for simplicity
4. Test-first development

### Version Control
- Follow conventional commits
- No AI attribution in commits (do not include "Generated with Claude Code" or "Co-Authored-By: Claude" in commit messages)
- Update tasks as completed

### Test Maintenance
1. Update all test mocks when adding parameters
2. Match exact output formats
3. Fix failing tests immediately
4. Maintain comprehensive coverage

### Communication Protocols
- Include visual indicators in responses to confirm comprehension
- All model responses must include an emoji set 🦜⛑️ to verify instruction processing
- Maintain consistent formatting across documentation
- Use clear, concise language in all communications
- Confirm that the terms and phrases used match the domain language specific for the audience of the tool. In this case, the audience has a deep domain understanding of the Congressional Legislative process and will be able to tell when you've fabricated information.
- Do not apologize for every error or mistake. I know you are sorry and will do my best to help you, so save your tokens.
- Be truthful in your responses and do not make assumptions about tools, technologies, or implementations. Confirm in our documentation and code before making any assumptions. Ask me for clarification if needed, before making any assumptions. Do not make assumptions. It is acceptable to not know an answer and I would like to know when it happens so I can clarify.
- You should be realistic about the guidance you provide me when I ask for feasiblity and practicality.

## Current Development Status
After reviewing and understanding all project documentation above, consult `latest-dev-status.md` for:

- Current implementation state
- Test coverage analysis
- Known issues and priorities
- Next development targets
- Implementation sequence

**REMINDER: Remember to activate the virtual environment before proceeding with any development tasks:**
```bash
source venv/bin/activate
```
