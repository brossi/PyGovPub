"""
Unit tests for the synchronization manager.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import UUID, uuid4

from pygovpub.auth.models import ApiSource
from pygovpub.events.event_manager import EventManager
from pygovpub.events.event_types import (
    Event, EventCategory, EventType, EventPayload,
    DocumentPublishedPayload, DocumentUpdatedPayload
)
from pygovpub.sync.manager import SyncManager, SyncStatus
from pygovpub.sync.tracker import EntityTracker


class TestSyncManager:
    """Tests for the SyncManager class."""
    
    @pytest.fixture
    def event_manager(self):
        """Create an event manager."""
        with patch('pygovpub.events.event_manager.get_event_manager') as mock_get:
            manager = EventManager()
            mock_get.return_value = manager
            yield manager
    
    @pytest.fixture
    def entity_tracker(self):
        """Create an entity tracker mock."""
        tracker = AsyncMock(spec=EntityTracker)
        return tracker
    
    @pytest.fixture
    def sync_manager(self, event_manager, entity_tracker):
        """Create a sync manager with mocked dependencies."""
        with patch('pygovpub.sync.manager.EntityTracker', return_value=entity_tracker):
            manager = SyncManager()
            # Manually inject the mocked entity tracker
            manager._entity_tracker = entity_tracker
            return manager
    
    @pytest.fixture
    def bill_data(self):
        """Sample bill data for testing."""
        return {
            "congress": 117,
            "type": "hr",
            "number": 1234,
            "title": "Test Bill",
            "introducedDate": "2023-03-01",
            "sponsors": [
                {
                    "bioguideId": "A000001",
                    "fullName": "Representative Test",
                    "party": "Test Party",
                    "state": "TS"
                }
            ],
            "actions": [
                {
                    "actionDate": "2023-03-01",
                    "text": "Introduced in House",
                    "type": "IntroReferral"
                }
            ]
        }
    
    @pytest.fixture
    def document_data(self):
        """Sample document data for testing."""
        return {
            "packageId": "BILLS-117hr1234ih",
            "packageLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih",
            "title": "Test Bill",
            "congress": "117",
            "dateIssued": "2023-03-01",
            "collectionCode": "BILLS",
            "collectionName": "Bills and Statutes",
            "category": "Bills",
            "docClass": "hr",
            "docNumber": "1234",
            "docVersion": "ih"
        }
    
    async def test_handle_bill_event(self, sync_manager, event_manager, entity_tracker, bill_data):
        """Test handling a bill event."""
        # Create a bill event
        bill_payload = EventPayload(
            event_time=datetime.utcnow(),
            source=ApiSource.CONGRESS,
            source_id=f"bill/117/hr1234",
            source_url="https://api.congress.gov/v3/bill/117/hr/1234",
            resource_type="bill",
            data=bill_data
        )
        
        event = Event(
            event_type=EventType.BILL_INTRODUCED,
            category=EventCategory.BILL_UPDATE,
            payload=bill_payload
        )
        
        # Emit the event
        await event_manager.emit_event(event)
        
        # Verify entity tracker was called
        entity_tracker.track_update.assert_called_once()
        call_args = entity_tracker.track_update.call_args[1]
        assert call_args["entity_type"] == "bill"
        assert call_args["entity_id"] == "117hr1234"
        assert call_args["source"] == ApiSource.CONGRESS
        assert call_args["data"] == bill_data
    
    async def test_handle_document_event(self, sync_manager, event_manager, entity_tracker, document_data):
        """Test handling a document event."""
        # Create a document event
        doc_payload = DocumentPublishedPayload(
            event_time=datetime.utcnow(),
            source=ApiSource.GOVINFO,
            source_id=f"document/{document_data['packageId']}",
            source_url=document_data.get("packageLink", ""),
            resource_type="bill_document",
            document_id=document_data["packageId"],
            document_type="bill",
            title=document_data["title"],
            data=document_data
        )
        
        event = Event(
            event_type=EventType.DOCUMENT_PUBLISHED,
            category=EventCategory.DOCUMENT_UPDATE,
            payload=doc_payload
        )
        
        # Emit the event
        await event_manager.emit_event(event)
        
        # Verify entity tracker was called
        entity_tracker.track_update.assert_called_once()
        call_args = entity_tracker.track_update.call_args[1]
        assert call_args["entity_type"] == "document"
        assert call_args["entity_id"] == document_data["packageId"]
        assert call_args["source"] == ApiSource.GOVINFO
        assert call_args["data"] == document_data
    
    async def test_check_bill_document_consistency(self, sync_manager, event_manager, entity_tracker, bill_data, document_data):
        """Test checking consistency between bill and document data."""
        # Setup mock data in entity tracker
        bill_update = {
            "source": ApiSource.CONGRESS,
            "event_id": uuid4(),
            "timestamp": datetime.utcnow(),
            "data": bill_data
        }
        
        document_update = {
            "source": ApiSource.GOVINFO,
            "event_id": uuid4(),
            "timestamp": datetime.utcnow(),
            "data": document_data
        }
        
        # Configure entity tracker to return our mock data
        entity_tracker.get_updates.side_effect = lambda entity_type, entity_id, source=None: asyncio.Future()
        
        # For bill updates
        bill_future = asyncio.Future()
        bill_future.set_result([bill_update])
        entity_tracker.get_updates.return_value = bill_future
        
        # Create a bill event
        bill_payload = EventPayload(
            event_time=datetime.utcnow(),
            source=ApiSource.CONGRESS,
            source_id=f"bill/117/hr1234",
            source_url="https://api.congress.gov/v3/bill/117/hr/1234",
            resource_type="bill",
            data=bill_data
        )
        
        bill_event = Event(
            event_type=EventType.BILL_INTRODUCED,
            category=EventCategory.BILL_UPDATE,
            payload=bill_payload
        )
        
        # Emit the bill event
        await event_manager.emit_event(bill_event)
        
        # Verify entity tracker was called for bill
        entity_tracker.track_update.assert_called_once()
        
        # Reset mock for document event
        entity_tracker.track_update.reset_mock()
        
        # For document updates
        doc_future = asyncio.Future()
        doc_future.set_result([document_update])
        entity_tracker.get_updates.return_value = doc_future
        
        # Create a document event
        doc_payload = DocumentPublishedPayload(
            event_time=datetime.utcnow(),
            source=ApiSource.GOVINFO,
            source_id=f"document/{document_data['packageId']}",
            source_url=document_data.get("packageLink", ""),
            resource_type="bill_document",
            document_id=document_data["packageId"],
            document_type="bill",
            title=document_data["title"],
            data=document_data
        )
        
        doc_event = Event(
            event_type=EventType.DOCUMENT_PUBLISHED,
            category=EventCategory.DOCUMENT_UPDATE,
            payload=doc_payload
        )
        
        # Emit the document event
        await event_manager.emit_event(doc_event)
        
        # Verify entity tracker was called for document
        entity_tracker.track_update.assert_called_once()
    
    async def test_get_sync_status(self, sync_manager, event_manager, entity_tracker):
        """Test getting synchronization status."""
        # Initialize sync history with a test entry
        entity_type = "bill"
        entity_id = "117hr1234"
        
        sync_id = UUID(int=0)  # Test UUID
        sync_manager._sync_history[sync_id] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "sources": [ApiSource.CONGRESS, ApiSource.GOVINFO],
            "status": SyncStatus.COMPLETED,
            "timestamp": datetime.utcnow(),
            "consistent": True
        }
        
        # Get sync status
        status = await sync_manager.get_sync_status(
            entity_type=entity_type,
            entity_id=entity_id
        )
        
        # Verify status
        assert status is not None
        assert status["entity_type"] == entity_type
        assert status["entity_id"] == entity_id
        assert status["status"] == SyncStatus.COMPLETED
        assert status["consistent"] is True
        assert len(status["sources"]) == 2
        assert ApiSource.CONGRESS in status["sources"]
        assert ApiSource.GOVINFO in status["sources"]