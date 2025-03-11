"""
Unit tests for pygovpub.mock package initialization.
"""
import pytest
from unittest.mock import patch, MagicMock

from pygovpub.mock import __all__


def test_all_exports():
    """Test that __all__ exports the correct items."""
    # Check that all expected items are in __all__
    expected_exports = [
        "create_app", 
        "start_mock_server", 
        "stop_mock_server",
        "Recorder",
        "recording_session"
    ]
    
    for item in expected_exports:
        assert item in __all__, f"{item} should be in __all__"
    
    # Check that __all__ doesn't contain unexpected items
    assert len(__all__) == len(expected_exports), f"__all__ contains unexpected items: {set(__all__) - set(expected_exports)}"


def test_import_from_module():
    """Test that we can import all items from the module."""
    # Import all items from the module to check they exist
    from pygovpub.mock import create_app, start_mock_server, stop_mock_server, Recorder, recording_session
    
    # Simply assert that they were imported successfully
    assert create_app is not None
    assert start_mock_server is not None
    assert stop_mock_server is not None
    assert Recorder is not None
    assert recording_session is not None