# PyTest Warning Utils Integration Plan

## Overview
Integrate pytest-warning-utils to improve warning management and provide better visibility into test warnings.

## Implementation Steps

### 1. Package Installation
```bash
pip install pytest-warning-utils
```

Add to development dependencies in pyproject.toml:

```toml
[tool.poetry.dev-dependencies]
pytest-warning-utils = "^0.3.1"
```

### 2. Configuration Setup
Create pytest warning configuration in pyproject.toml:

```toml
[tool.pytest.ini_options]
warning_utils_config = [
    # Convert specific warnings to errors
    "error::DeprecationWarning",
    "error::PendingDeprecationWarning",
    
    # Ignore specific warnings from third-party packages
    "ignore::DeprecationWarning:pkg_resources.*",
    
    # Record all warnings for analysis
    "record::UserWarning",
    "record::RuntimeWarning"
]
```

### 3. Warning Recording Setup
Create warning recording utilities in tests/conftest.py:

```python
import pytest
from pytest_warning_utils import WarningRecorder

@pytest.fixture
def warning_recorder():
    """Fixture to record and analyze warnings during tests."""
    with WarningRecorder() as recorder:
        yield recorder
```

### 4. Test Updates
Add warning verification to critical test files:

```python
def test_example(warning_recorder):
    # Test code here
    warnings = warning_recorder.get_recorded_warnings()
    assert len(warnings) == 0, f"Unexpected warnings: {warnings}"
```

### 5. CI Integration
Update test running commands in CI workflow:

```yaml
- name: Run Tests with Warning Analysis
  run: |
    pytest --warning-utils-record=warning_log.txt
```

### 6. Documentation Updates
Add warning management section to tests/README.md:

- Warning configuration guide
- Common warning patterns
- How to use warning_recorder fixture
- CI integration details

## Success Criteria
- All Pydantic V2 warnings properly managed
- TestCacheStorage warnings addressed
- Warning logs generated and archived
- No unexpected warnings in test suite
- Clear documentation for warning management

## Validation Steps
- Run full test suite with warning recording
- Verify warning logs are generated
- Confirm CI pipeline includes warning analysis
- Check documentation completeness
- Validate warning patterns are properly categorized

## Rollback Plan
- Remove pytest-warning-utils configuration
- Restore original pytest settings
- Remove warning_recorder fixture
- Update CI configuration
