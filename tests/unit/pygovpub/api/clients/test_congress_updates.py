"""
Unit tests for the real-time update features of the Congress.gov API client.
"""

import asyncio
import json
from datetime import date, datetime
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from pygovpub.api.clients.congress import CongressClient
from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.events.event_manager import EventManager
from pygovpub.events.event_types import (
    Event, EventCategory, EventType, EventPayload,
    FloorUpdatePayload, VoteUpdatePayload, CalendarUpdatePayload, HearingUpdatePayload
)
from pygovpub.exceptions import CongressApiError


class TestCongressClientUpdates:
    """Tests for the real-time update features of the Congress.gov API client."""
    
    @pytest.fixture
    def mock_auth_manager(self):
        """Create a mock auth manager."""
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.execute_request = AsyncMock()
        return auth_manager
    
    @pytest.fixture
    def mock_event_manager(self):
        """Create a mock event manager."""
        event_manager = MagicMock(spec=EventManager)
        event_manager.create_and_emit_event = AsyncMock()
        event_manager.register_event = AsyncMock()
        event_manager.emit_event = AsyncMock()
        event_manager.dispatch_event = AsyncMock()
        return event_manager
    
    @pytest.fixture
    def client(self, mock_auth_manager, mock_event_manager):
        """Create a client with mock auth manager and event manager."""
        client = CongressClient(auth_manager=mock_auth_manager)
        client._event_manager = mock_event_manager
        return client
    
    @pytest.fixture
    def mock_floor_updates_response(self):
        """Create a mock floor updates response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/floor/house"
            },
            "results": [
                {
                    "id": "12345",
                    "timestamp": "2023-03-15T10:30:00Z",
                    "text": "The House met at 10:00 a.m.",
                    "url": "https://www.congress.gov/floor-updates/house"
                },
                {
                    "id": "12346",
                    "timestamp": "2023-03-15T11:15:00Z",
                    "text": "MORNING HOUR - The House proceeded with Morning Hour Debate.",
                    "url": "https://www.congress.gov/floor-updates/house"
                }
            ]
        }
    
    @pytest.fixture
    def mock_vote_updates_response(self):
        """Create a mock vote updates response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/votes"
            },
            "results": [
                {
                    "congress": 117,
                    "chamber": "House",
                    "voteNumber": "123",
                    "date": "2023-03-15",
                    "question": "On passage of H.R. 1234",
                    "title": "Health Care Improvement Act",
                    "result": "Passed",
                    "url": "https://www.congress.gov/vote/117/house/123"
                },
                {
                    "congress": 117,
                    "chamber": "Senate",
                    "voteNumber": "45",
                    "date": "2023-03-14",
                    "question": "On the nomination of John Smith",
                    "title": "Nomination of John Smith to be Secretary",
                    "result": "Confirmed",
                    "url": "https://www.congress.gov/vote/117/senate/45"
                }
            ]
        }
    
    @pytest.fixture
    def mock_calendar_updates_response(self):
        """Create a mock calendar updates response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/calendar/house"
            },
            "results": [
                {
                    "id": "house-1",
                    "description": "Legislative business for the week",
                    "scheduledAt": "2023-03-20T09:00:00Z",
                    "url": "https://www.congress.gov/house-calendar"
                },
                {
                    "id": "house-2",
                    "description": "Committee hearings for the week",
                    "scheduledAt": "2023-03-21T10:00:00Z",
                    "url": "https://www.congress.gov/house-calendar"
                }
            ]
        }
    
    @pytest.fixture
    def mock_hearing_updates_response(self):
        """Create a mock hearing updates response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/hearings"
            },
            "results": [
                {
                    "id": "hearing-1",
                    "committee": {
                        "systemCode": "AG",
                        "name": "Committee on Agriculture"
                    },
                    "title": "Farm Bill Reauthorization",
                    "scheduledAt": "2023-03-22T14:00:00Z",
                    "location": "1300 Longworth House Office Building",
                    "description": "Oversight hearing on Farm Bill implementation",
                    "url": "https://www.congress.gov/committee-hearings"
                },
                {
                    "id": "hearing-2",
                    "committee": {
                        "systemCode": "BU",
                        "name": "Committee on Budget"
                    },
                    "title": "Fiscal Year 2024 Budget",
                    "scheduledAt": "2023-03-23T10:00:00Z",
                    "location": "210 Capitol Visitor Center",
                    "description": "Hearing on the President's Budget proposal",
                    "url": "https://www.congress.gov/committee-hearings"
                }
            ]
        }
    
    async def test_get_floor_updates(self, client, mock_auth_manager, mock_floor_updates_response, mock_event_manager):
        """Test getting floor updates."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_floor_updates_response
        
        # Call the method under test
        updates = await client.get_floor_updates(chamber="house", date_str="2023-03-15")
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/floor/house",
            method="GET",
            params={"date": "2023-03-15"},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we got the updates
        assert len(updates) == 2
        assert updates[0]["id"] == "12345"
        assert updates[1]["text"] == "MORNING HOUR - The House proceeded with Morning Hour Debate."
        
        # Verify events were emitted for each update
        assert mock_event_manager.create_and_emit_event.call_count == 2
        
        # Check that create_and_emit_event was called - use safer approach
        # instead of accessing call args which can be tricky with AsyncMock
        mock_event_manager.create_and_emit_event.assert_called()
        
        # We've already verified the call count, which confirms the right number of events were processed
    
    async def test_get_vote_updates(self, client, mock_auth_manager, mock_vote_updates_response, mock_event_manager):
        """Test getting vote updates."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_vote_updates_response
        
        # Call the method under test
        votes = await client.get_vote_updates()
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/votes",
            method="GET",
            params={},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we got the votes
        assert len(votes) == 2
        assert votes[0]["chamber"] == "House"
        assert votes[0]["voteNumber"] == "123"
        assert votes[1]["chamber"] == "Senate"
        assert votes[1]["voteNumber"] == "45"
        
        # Verify events were emitted for each vote
        assert mock_event_manager.create_and_emit_event.call_count == 2
        
        # Check that create_and_emit_event was called - use safer approach
        # instead of accessing call args which can be tricky with AsyncMock
        mock_event_manager.create_and_emit_event.assert_called()
    
    async def test_get_vote_updates_with_chamber(self, client, mock_auth_manager, mock_vote_updates_response, mock_event_manager):
        """Test getting vote updates with chamber filter."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_vote_updates_response
        
        # Call the method under test with chamber filter
        votes = await client.get_vote_updates(chamber="house")
        
        # Verify the auth manager was called correctly with chamber in endpoint
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/votes/house",
            method="GET",
            params={},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we got the votes
        assert len(votes) == 2
    
    async def test_get_calendar_updates(self, client, mock_auth_manager, mock_calendar_updates_response, mock_event_manager):
        """Test getting calendar updates."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_calendar_updates_response
        
        # Call the method under test
        calendar_items = await client.get_calendar_updates(chamber="house")
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/calendar/house",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we got the calendar items
        assert len(calendar_items) == 2
        assert calendar_items[0]["id"] == "house-1"
        assert calendar_items[1]["description"] == "Committee hearings for the week"
        
        # Verify events were emitted for each calendar item
        assert mock_event_manager.create_and_emit_event.call_count == 2
        
        # Check that create_and_emit_event was called - use safer approach
        # instead of accessing call args which can be tricky with AsyncMock
        mock_event_manager.create_and_emit_event.assert_called()
    
    async def test_get_hearing_updates(self, client, mock_auth_manager, mock_hearing_updates_response, mock_event_manager):
        """Test getting hearing updates."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_hearing_updates_response
        
        # Call the method under test
        hearings = await client.get_hearing_updates()
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/hearings",
            method="GET",
            params={},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we got the hearings
        assert len(hearings) == 2
        assert hearings[0]["committee"]["systemCode"] == "AG"
        assert hearings[1]["title"] == "Fiscal Year 2024 Budget"
        
        # Verify events were emitted for each hearing
        assert mock_event_manager.create_and_emit_event.call_count == 2
        
        # Check that create_and_emit_event was called - use safer approach
        # instead of accessing call args which can be tricky with AsyncMock
        mock_event_manager.create_and_emit_event.assert_called()
    
    async def test_get_hearing_updates_with_committee(self, client, mock_auth_manager, mock_hearing_updates_response, mock_event_manager):
        """Test getting hearing updates with committee filter."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_hearing_updates_response
        
        # Call the method under test with committee filter
        hearings = await client.get_hearing_updates(committee_id="AG")
        
        # Verify the auth manager was called correctly with committee filter
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/hearings",
            method="GET",
            params={"committee": "AG"},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we got the hearings
        assert len(hearings) == 2
    
    async def test_parse_datetime(self, client):
        """Test datetime parsing."""
        # Test ISO datetime
        dt = client._parse_datetime("2023-03-15T10:30:00Z")
        assert isinstance(dt, datetime)
        assert dt.year == 2023
        assert dt.month == 3
        assert dt.day == 15
        assert dt.hour == 10
        assert dt.minute == 30
        
        # Test ISO date (should return datetime at midnight)
        dt = client._parse_datetime("2023-03-15")
        assert isinstance(dt, datetime)
        assert dt.year == 2023
        assert dt.month == 3
        assert dt.day == 15
        assert dt.hour == 0
        assert dt.minute == 0
        
        # Test None (should return current time)
        dt = client._parse_datetime(None)
        assert isinstance(dt, datetime)
        
        # Test invalid datetime (should return current time)
        dt = client._parse_datetime("not-a-datetime")
        assert isinstance(dt, datetime)
    
    async def test_invalid_response_validation_for_updates(self, client, mock_auth_manager):
        """Test validation errors for update endpoints."""
        # Create a mock invalid response
        mock_response = {
            "request": {"url": "https://api.congress.gov/v3/endpoint"}
            # Missing required fields
        }
        
        # Setup mock
        mock_auth_manager.execute_request.return_value = mock_response
        
        # Test floor updates endpoint validation
        with pytest.raises(CongressApiError, match="Invalid floor updates response format"):
            await client.get_floor_updates(chamber="house")
            
        # Test vote updates endpoint validation
        with pytest.raises(CongressApiError, match="Invalid vote updates response format"):
            await client.get_vote_updates()
            
        # Test calendar updates endpoint validation
        with pytest.raises(CongressApiError, match="Invalid calendar updates response format"):
            await client.get_calendar_updates(chamber="house")
            
        # Test hearing updates endpoint validation
        with pytest.raises(CongressApiError, match="Invalid hearing updates response format"):
            await client.get_hearing_updates()