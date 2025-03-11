# PyGovPub Development Plan - March 11, 2025

## Project State Assessment

**Current Git Commit Hash**: 12d2d44795476d2b11e081aae6dbeff86e62a084

**Branch**: claude-code_01

**Assessed By**: Claude (claude-3-7-sonnet-20250219)

**Session ID**: Requested by Ben on March 11, 2025

## Development Plan Overview

Based on thorough analysis of the codebase and test suite execution, this document outlines a comprehensive plan for addressing issues and improving test coverage.

## 1. Fixing Broken Tests

### 1.1 Missing Committee Router Functions
- ✅ Implement missing `get_committee_membership` and `get_committee_reports` functions in `src/pygovpub/api/routers/committees.py`
- ✅ These functions are referenced in comprehensive router tests but not implemented yet
- ✅ Follow the pattern of existing router functions like `get_committee` and `get_committee_hearings`

### 1.2 TestCacheStorage Warning
- ✅ Fix the `__init__` constructor in `tests/unit/pygovpub/api/cache/test_manager.py` causing the PyTest collection warning
- ✅ Convert to use pytest fixtures instead of creating a test class with an init constructor

## 2. Fixing Warnings

### 2.1 Pydantic V2 Warnings
- ✅ Update the deprecated Pydantic V1 style `@validator` in `src/pygovpub/api/routers/webhooks.py` to the V2 style `@field_validator`
- ✅ Review other files for similar Pydantic v1 to v2 migration needs

### 2.2 Config Schema Extra Warning
- ✅ Replace `schema_extra` with `json_schema_extra` in model Config classes:
  - ✅ In `src/pygovpub/api/routers/committees.py`
  - ✅ In `src/pygovpub/api/routers/webhooks.py`
  - ✅ And other files with similar patterns

## 3. Coverage Improvement Priorities

### 3.1 Auth Package
- The auth package has a few uncovered lines in `auth_manager.py` (lines 67, 71, 105, 387-388, 397)
- Implement the stubs in test files to cover these remaining lines

### 3.2 CLI Package
- The CLI package has zero coverage (especially `mock_server.py`)
- Need to write tests for CLI components as they are completely untested

### 3.3 Mock Package
- The mock package has zero coverage (`recorder.py` and `server.py`)
- Prioritize test implementation for mock components

### 3.4 Exceptions
- Add tests for uncovered lines in `exceptions.py` (lines 31, 100-103)

## 4. Other Issues Found

### 4.1 Comprehensive API Tests
- Multiple new comprehensive API test files have been added but are not ready:
  - ✅ `test_committees_router_comprehensive.py`
  - `test_congress_router_comprehensive.py`
  - `test_documents_router_comprehensive.py`
  - `test_members_router_comprehensive.py`
  - `test_webhooks_router_comprehensive.py`
- ✅ These tests assume functionality that doesn't exist yet or has changed

### 4.2 Current Phase Status
- The codebase is in the development phase for CLI implementation (Command Line Interface [DX-002])
- Need to focus on completing this phase before moving to additional features

## Implementation Priority Order

1. ✅ Fix the immediate test failures (committee router functions)
2. ✅ Update Pydantic validation to V2 style to fix deprecation warnings
3. ✅ Fix TestCacheStorage warning to improve test collection
4. Start implementing coverage for CLI and mock packages
5. Add tests for remaining exception paths
6. Implement stubs for auth_manager to achieve 100% coverage
7. Update and complete the comprehensive API tests as final step

## Coverage Analysis Summary

Current overall coverage: 47.2%
Projected overall coverage after implementing stubs: 48.0%

### Uncovered Critical Paths
- CLI package (0% coverage)
- Mock package (0% coverage)
- Config exceptions (lines 77, 89)
- General exceptions (lines 31, 100-103)

### Next Steps

1. ✅ Address immediate test failures
2. ✅ Fix warnings to ensure clean test execution
3. Implement tests for CLI and mock packages
4. Complete auth package coverage
5. Add remaining exception tests
6. Finalize comprehensive API tests

This plan will ensure progress toward the completion of the Command Line Interface phase while maintaining code quality and test coverage standards.