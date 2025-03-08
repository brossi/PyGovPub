"""
Tests for the recorder module.
"""

import asyncio
import json
import os
from pathlib import Path
from unittest import mock

import httpx
import pytest
from pytest_mock import mocker

from pygovpub.config import Config
from pygovpub.mock.recorder import Recorder, recording_session


@pytest.fixture
def recorder():
    """Create a recorder instance for testing."""
    # Create temporary fixtures directory
    fixtures_dir = "test_fixtures"
    os.makedirs(os.path.join(fixtures_dir, "recordings"), exist_ok=True)
    
    # Create recorder instance
    recorder = Recorder(fixtures_dir=fixtures_dir)
    
    yield recorder
    
    # Clean up temporary fixtures
    import shutil
    shutil.rmtree(fixtures_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_start_session(recorder):
    """Test starting a recording session."""
    # Mock the config to provide API settings
    with mock.patch("pygovpub.mock.recorder.config") as mock_config:
        mock_config.apis = {
            "congress": mock.MagicMock(
                base_url="https://api.congress.gov/v3",
                api_key="test_key"
            )
        }
        
        session_id = await recorder.start_session("congress")
        
        assert session_id.startswith("congress_")
        assert session_id in recorder.sessions
        assert recorder.active_session == session_id
        
        session = recorder.sessions[session_id]
        assert session.api_name == "congress"
        assert session.base_url == "https://api.congress.gov/v3"
        assert os.path.exists(session.storage_path)


@pytest.mark.asyncio
async def test_start_session_invalid_api(recorder):
    """Test starting a session with an invalid API name."""
    with pytest.raises(ValueError) as exc_info:
        await recorder.start_session("invalid_api")
    
    assert "Invalid API name" in str(exc_info.value)


@pytest.mark.asyncio
async def test_end_session(recorder):
    """Test ending a recording session."""
    # Mock the config to provide API settings
    with mock.patch("pygovpub.mock.recorder.config") as mock_config:
        mock_config.apis = {
            "congress": mock.MagicMock(
                base_url="https://api.congress.gov/v3",
                api_key="test_key"
            )
        }
        
        session_id = await recorder.start_session("congress")
        metadata = await recorder.end_session(session_id)
        
        assert metadata["recording_id"] == session_id
        assert metadata["api_name"] == "congress"
        assert metadata["base_url"] == "https://api.congress.gov/v3"
        assert "start_time" in metadata
        assert "end_time" in metadata
        assert metadata["request_count"] == 0
        
        # Check that the metadata file was created
        metadata_path = os.path.join(
            recorder.fixtures_dir, "recordings", session_id, "metadata.json"
        )
        assert os.path.exists(metadata_path)
        
        # Check that the active session was cleared
        assert recorder.active_session is None


@pytest.mark.asyncio
async def test_record_request(recorder, mocker):
    """Test recording a request."""
    # Mock the httpx.AsyncClient.request method
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"test": "data"}
    mock_response.raise_for_status.return_value = None
    
    mocker.patch("httpx.AsyncClient.request", return_value=mock_response)
    
    # Mock the config to provide API settings
    with mock.patch("pygovpub.mock.recorder.config") as mock_config:
        mock_config.apis = {
            "congress": mock.MagicMock(
                base_url="https://api.congress.gov/v3",
                api_key="test_key"
            )
        }
        
        session_id = await recorder.start_session("congress")
        response_data = await recorder.record_request(
            "bill/117/hr/1234",
            session_id=session_id
        )
        
        assert response_data == {"test": "data"}
        
        # Check that the request was added to the session
        session = recorder.sessions[session_id]
        assert len(session.requests) == 1
        request_data = session.requests[0]
        assert request_data["method"] == "GET"
        assert request_data["endpoint"] == "bill/117/hr/1234"
        
        # Check that the fixture file was created
        fixture_path = os.path.join(
            recorder.fixtures_dir, "recordings", session_id, "bill_117_hr_1234.json"
        )
        assert os.path.exists(fixture_path)
        
        # Check file contents
        with open(fixture_path, "r") as f:
            fixture_data = json.load(f)
        assert fixture_data == {"test": "data"}


@pytest.mark.asyncio
async def test_record_binary_content(recorder, mocker):
    """Test recording binary content (like PDF)."""
    # Mock the httpx.AsyncClient.request method
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.content = b"PDF content"
    mock_response.raise_for_status.return_value = None
    
    mocker.patch("httpx.AsyncClient.request", return_value=mock_response)
    
    # Mock the config to provide API settings
    with mock.patch("pygovpub.mock.recorder.config") as mock_config:
        mock_config.apis = {
            "govinfo": mock.MagicMock(
                base_url="https://api.govinfo.gov",
                api_key="test_key"
            )
        }
        
        session_id = await recorder.start_session("govinfo")
        response_data = await recorder.record_request(
            "packages/BILLS-117hr1enr/content",
            params={"contentType": "pdf"},
            session_id=session_id
        )
        
        assert response_data["content_type"] == "application/pdf"
        assert response_data["size"] == len(b"PDF content")
        
        # Check that the binary file was created
        fixture_path = os.path.join(
            recorder.fixtures_dir, "recordings", session_id, "packages_BILLS-117hr1enr_content.pdf"
        )
        assert os.path.exists(fixture_path)
        
        # Check file contents
        with open(fixture_path, "rb") as f:
            fixture_data = f.read()
        assert fixture_data == b"PDF content"


@pytest.mark.asyncio
async def test_list_sessions(recorder):
    """Test listing recording sessions."""
    # Create some mock session directories and metadata
    recordings_dir = os.path.join(recorder.fixtures_dir, "recordings")
    os.makedirs(os.path.join(recordings_dir, "congress_20220101"), exist_ok=True)
    os.makedirs(os.path.join(recordings_dir, "govinfo_20220102"), exist_ok=True)
    
    metadata1 = {
        "recording_id": "congress_20220101",
        "api_name": "congress",
        "start_time": "2022-01-01T00:00:00Z"
    }
    metadata2 = {
        "recording_id": "govinfo_20220102",
        "api_name": "govinfo",
        "start_time": "2022-01-02T00:00:00Z"
    }
    
    with open(os.path.join(recordings_dir, "congress_20220101", "metadata.json"), "w") as f:
        json.dump(metadata1, f)
    
    with open(os.path.join(recordings_dir, "govinfo_20220102", "metadata.json"), "w") as f:
        json.dump(metadata2, f)
    
    # List sessions
    sessions = recorder.list_sessions()
    
    assert len(sessions) == 2
    assert sessions[0]["recording_id"] == "govinfo_20220102"  # Sorted by start_time, most recent first
    assert sessions[1]["recording_id"] == "congress_20220101"


@pytest.mark.asyncio
async def test_save_fixture(recorder):
    """Test saving a recorded response as a fixture."""
    # Create a mock recording session with a response
    recordings_dir = os.path.join(recorder.fixtures_dir, "recordings")
    session_id = "congress_20220101"
    os.makedirs(os.path.join(recordings_dir, session_id), exist_ok=True)
    
    mock_response = {
        "bill": {
            "congress": 117,
            "type": "hr",
            "number": "1234",
            "title": "Test Bill"
        }
    }
    
    with open(os.path.join(recordings_dir, session_id, "bill_117_hr_1234.json"), "w") as f:
        json.dump(mock_response, f)
    
    # Save as default fixture
    fixture_path = await recorder.save_fixture(
        session_id=session_id,
        endpoint="bill/117/hr/1234",
        fixture_type="default"
    )
    
    assert os.path.exists(fixture_path)
    
    # Check file contents
    with open(fixture_path, "r") as f:
        fixture_data = json.load(f)
    assert fixture_data == mock_response
    
    # Save as specific fixture
    fixture_path = await recorder.save_fixture(
        session_id=session_id,
        endpoint="bill/117/hr/1234",
        fixture_type="specific"
    )
    
    assert os.path.exists(fixture_path)
    
    # Check file contents
    with open(fixture_path, "r") as f:
        fixture_data = json.load(f)
    assert fixture_data == mock_response


@pytest.mark.asyncio
async def test_context_manager():
    """Test the recording_session context manager."""
    # Mock the config to provide API settings
    with mock.patch("pygovpub.mock.recorder.config") as mock_config:
        mock_config.apis = {
            "congress": mock.MagicMock(
                base_url="https://api.congress.gov/v3",
                api_key="test_key"
            )
        }
        
        # Mock the Recorder methods
        with mock.patch("pygovpub.mock.recorder.Recorder") as MockRecorder:
            mock_recorder = MockRecorder.return_value
            mock_recorder.start_session.return_value = "congress_20220101"
            mock_recorder.end_session.return_value = {}
            
            async with recording_session("congress") as recorder:
                assert recorder == mock_recorder
            
            # Check that start_session and end_session were called
            mock_recorder.start_session.assert_called_once_with("congress")
            mock_recorder.end_session.assert_called_once_with("congress_20220101")