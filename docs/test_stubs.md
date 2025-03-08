# PyGovPub Test Stub Documentation

This document explains how to use test stubs in the PyGovPub project to project coverage and plan future tests.

## What Are Test Stubs?

Test stubs are placeholder tests that:
1. Define what will be tested in the future
2. Document which lines of code they will cover
3. Are automatically excluded from test runs
4. Help project future code coverage

## Creating Test Stubs

To create a test stub that will be automatically excluded from test runs, use one of these methods:

### Method 1: Use "stub" in the Function Name

```python
def test_stub_api_configuration_validation():
    """Test that validates API configuration parameters."""
    # This will be implemented later
    assert True
```

### Method 2: Add a STUB Comment

```python
def test_rate_limit_calculation():
    # STUB: This tests lines 45-60
    """Test that verifies rate limit calculation logic."""
    assert True
```

### Method 3: Add a WIP Comment

```python
def test_complex_auth_flow():
    # WIP: Will complete when the auth flow is finalized
    """Test the complex authentication flow."""
    assert False  # This would fail if run, but it won't be run
```

## How Stubs Are Excluded

Our custom pytest collection hook in `conftest.py` automatically filters out test stubs using these rules:
1. Functions with "stub" in their name
2. Functions containing "# STUB:" anywhere in their source
3. Functions containing "# WIP:" anywhere in their source

## Documenting Coverage in Stubs

To make stubs useful for coverage projection, add comments that specify which lines they will cover:

```python
def test_stub_advanced_api_usage():
    # STUB: This tests lines 72-85
    """Test that validates advanced API usage patterns."""
    assert True
```

## Using the Projected Coverage Tool

The `projected_coverage.py` tool in the `utilities` directory analyzes your test stubs to predict future coverage:

```bash
# Basic usage
./utilities/projected_coverage.py

# Specify package and stub directory
./utilities/projected_coverage.py --package pygovpub.auth --stub-dir tests/unit/auth
```

## Best Practices

1. **Create stubs during development**:
   Write stubs as you write code to document testing needs

2. **Document line coverage**:
   Always specify which lines each stub will cover

3. **Be specific about intent**:
   Document what aspect of functionality the stub will test

4. **Keep stubs in sync**:
   Update stubs when you modify the implementation

5. **Implement stubs**:
   Regularly convert stubs to real tests to increase coverage

## Example Test Stub File

```python
"""
Test stubs for auth_manager.py

These stubs document future tests that will be implemented
to ensure complete coverage of the auth_manager module.
"""

import pytest
from pygovpub.auth.models import ApiConfiguration
from pygovpub.auth.auth_manager import AuthManager

def test_stub_auth_manager_initialization():
    # STUB: This tests lines 15-30
    """Test that AuthManager initializes with correct defaults."""
    pass

def test_stub_credential_validation():
    # STUB: This tests lines 32-45
    """Test that credentials are properly validated."""
    pass
```
