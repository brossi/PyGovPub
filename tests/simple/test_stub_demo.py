"""
Example test stubs that demonstrate the stub detection mechanism.
These tests will be automatically excluded from test runs by the
pytest_collection_modifyitems hook in conftest.py.
"""

import pytest


def test_stub_function():
    # STUB: This tests line 42-45 in auth_manager.py
    """This test stub will be excluded based on the function name."""
    assert True


def test_with_stub_comment():
    # STUB: This tests line 53 in models.py
    """This test stub will be excluded based on the comment."""
    assert True


def test_work_in_progress():
    # WIP: Will implement when the new feature is ready
    """This test stub will be excluded based on the WIP comment."""
    assert False  # This would fail if actually run


class TestStubClass:
    def test_method(self):
        # STUB: This tests line 67-72 in rate_limiter.py
        """This test stub will be excluded based on the comment inside a class."""
        assert True


def test_normal_not_excluded():
    """This is a normal test that will NOT be excluded."""
    assert 1 + 1 == 2