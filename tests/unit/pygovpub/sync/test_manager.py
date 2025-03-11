"""
Unit tests for the synchronization manager.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import UUID, uuid4

from pygovpub.auth.models import ApiSource
from pygovpub.events.event_manager import EventManager
from pygovpub.events.event_types import (
    Event, EventCategory, EventType, EventPayload,
    DocumentPublishedPayload, DocumentUpdatedPayload
)
from pygovpub.sync.manager import (
    SyncManager, SyncStatus, get_sync_manager,
    ConflictResolutionStrategy, ConflictType, FieldConflict
)
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
        # Create a manager with the event manager and entity tracker mocked
        with patch('pygovpub.sync.manager.get_event_manager', return_value=event_manager):
            manager = SyncManager()
            # Replace the entity tracker with our mock
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
    
    async def test_handle_document_event_with_related_bills(self, sync_manager, event_manager, entity_tracker, document_data):
        """Test handling a document event with related bills."""
        # Reset mock
        entity_tracker.reset_mock()
        
        # Setup entity tracker to return bill updates for consistency check
        bill_update = {
            "source": ApiSource.CONGRESS,
            "event_id": uuid4(),
            "timestamp": datetime.utcnow(),
            "data": {"congress": 117, "type": "hr", "number": 1234}
        }
        
        govinfo_update = {
            "source": ApiSource.GOVINFO,
            "event_id": uuid4(),
            "timestamp": datetime.utcnow(),
            "data": document_data
        }
        
        # Create futures for the mock responses
        bill_future = asyncio.Future()
        bill_future.set_result([bill_update])
        
        doc_future = asyncio.Future()
        doc_future.set_result([govinfo_update])
        
        # Configure get_updates to return different results for different calls
        entity_tracker.get_updates.side_effect = lambda entity_type, entity_id, source=None: (
            bill_future if entity_type == "bill" else doc_future
        )
        
        # Create a document event with related bills
        doc_payload = DocumentPublishedPayload(
            event_time=datetime.utcnow(),
            source=ApiSource.GOVINFO,
            source_id=f"document/{document_data['packageId']}",
            source_url=document_data.get("packageLink", ""),
            resource_type="bill_document",
            document_id=document_data["packageId"],
            document_type="bill",
            title=document_data["title"],
            related_bills=["117hr1234"],  # Include related bill
            data=document_data
        )
        
        event = Event(
            event_type=EventType.DOCUMENT_PUBLISHED,
            category=EventCategory.DOCUMENT_UPDATE,
            payload=doc_payload
        )
        
        # Emit the event
        await event_manager.emit_event(event)
        
        # Verify entity tracker was called for the entity update
        assert entity_tracker.track_update.call_count == 1
        
        # Verify get_updates was called for both bill and document
        # (We call it twice for each consistency check)
        assert entity_tracker.get_updates.call_count >= 2
    
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
    
    async def test_get_sync_status_no_records(self, sync_manager):
        """Test getting synchronization status with no records."""
        # Clear sync history
        sync_manager._sync_history = {}
        
        # Get sync status for non-existent entity
        status = await sync_manager.get_sync_status(
            entity_type="bill",
            entity_id="nonexistent"
        )
        
        # Verify status is None
        assert status is None
    
    async def test_get_sync_status_multiple_records(self, sync_manager):
        """Test getting synchronization status with multiple records."""
        # Initialize sync history with two entries for the same entity
        entity_type = "bill"
        entity_id = "117hr1234"
        
        # Create an older entry
        sync_id1 = UUID(int=0)  # Test UUID
        older_time = datetime.utcnow() - timedelta(hours=1)
        sync_manager._sync_history[sync_id1] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "sources": [ApiSource.CONGRESS],
            "status": SyncStatus.COMPLETED,
            "timestamp": older_time,
            "consistent": True
        }
        
        # Create a newer entry
        sync_id2 = UUID(int=1)  # Test UUID
        newer_time = datetime.utcnow()
        sync_manager._sync_history[sync_id2] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "sources": [ApiSource.CONGRESS, ApiSource.GOVINFO],
            "status": SyncStatus.COMPLETED,
            "timestamp": newer_time,
            "consistent": True
        }
        
        # Get sync status
        status = await sync_manager.get_sync_status(
            entity_type=entity_type,
            entity_id=entity_id
        )
        
        # Verify status is the newer entry
        assert status is not None
        assert status["timestamp"] == newer_time
        assert len(status["sources"]) == 2
    
    async def test_subscribe_to_events(self, sync_manager, event_manager):
        """Test subscribing to events."""
        # Verify the sync manager subscribed to relevant events
        subscribers = event_manager._category_subscribers
        
        # Check that we have subscribers for document and bill events
        assert EventCategory.DOCUMENT_UPDATE in subscribers
        assert EventCategory.BILL_UPDATE in subscribers
        
        # There should be at least one subscriber for each category
        assert len(subscribers[EventCategory.DOCUMENT_UPDATE]) > 0
        assert len(subscribers[EventCategory.BILL_UPDATE]) > 0
    
    async def test_handle_invalid_bill_event(self, sync_manager, event_manager, entity_tracker):
        """Test handling a bill event with invalid data."""
        # Create a bill event with empty data dictionary
        bill_payload = EventPayload(
            event_time=datetime.utcnow(),
            source=ApiSource.CONGRESS,
            source_id="bill/117/hr1234",
            source_url="https://api.congress.gov/v3/bill/117/hr/1234",
            resource_type="bill",
            data={}  # Empty data
        )
        
        event = Event(
            event_type=EventType.BILL_INTRODUCED,
            category=EventCategory.BILL_UPDATE,
            payload=bill_payload
        )
        
        # Emit the event
        await event_manager.emit_event(event)
        
        # Verify entity tracker was not called for empty data
        entity_tracker.track_update.assert_not_called()
        
        # Test with missing bill identifiers
        bill_payload.data = {"title": "Missing identifiers"}
        
        # Reset the event
        event = Event(
            event_type=EventType.BILL_INTRODUCED,
            category=EventCategory.BILL_UPDATE,
            payload=bill_payload
        )
        
        await event_manager.emit_event(event)
        entity_tracker.track_update.assert_not_called()
    
    async def test_handle_invalid_document_event(self, sync_manager, event_manager, entity_tracker):
        """Test handling a document event with invalid data."""
        # Create a document event with invalid payload type
        doc_payload = EventPayload(
            event_time=datetime.utcnow(),
            source=ApiSource.GOVINFO,
            source_id="document/BILLS-117hr1234ih",
            source_url="https://api.govinfo.gov/packages/BILLS-117hr1234ih",
            resource_type="document",
            data={"id": "BILLS-117hr1234ih"}
        )
        
        event = Event(
            event_type=EventType.DOCUMENT_PUBLISHED,
            category=EventCategory.DOCUMENT_UPDATE,
            payload=doc_payload
        )
        
        # Emit the event
        await event_manager.emit_event(event)
        
        # Verify entity tracker was not called (payload is not DocumentPublishedPayload)
        entity_tracker.track_update.assert_not_called()
    
    async def test_check_bill_document_consistency_cross_source(self, sync_manager, entity_tracker):
        """Test consistency check with matching entities from both sources."""
        # Reset entity tracker mock
        entity_tracker.reset_mock()
        entity_tracker.get_updates.reset_mock()
        
        # Setup entity tracker to return specific sources for each entity
        bill_update = {
            "source": ApiSource.CONGRESS,
            "event_id": uuid4(),
            "timestamp": datetime.utcnow(),
            "data": {"congress": 117, "type": "hr", "number": 1234}
        }
        
        doc_update = {
            "source": ApiSource.GOVINFO,
            "event_id": uuid4(),
            "timestamp": datetime.utcnow(),
            "data": {"packageId": "BILLS-117hr1234ih"}
        }
        
        # Create result lists with correct source assignments
        bill_updates = [bill_update]  # Bill update from Congress.gov
        doc_updates = [doc_update]  # Document update from GovInfo.gov
        
        # Setup mocks to return the correct results
        bill_future = asyncio.Future()
        bill_future.set_result(bill_updates)
        
        doc_future = asyncio.Future()
        doc_future.set_result(doc_updates)
        
        # Configure entity tracker's side effects
        def mock_get_updates(entity_type, entity_id, source=None):
            if entity_type == "bill":
                return bill_future
            elif entity_type == "document":
                return doc_future
            return asyncio.Future().set_result([])
                
        entity_tracker.get_updates.side_effect = mock_get_updates
        
        # Create test event for the context
        event = MagicMock(spec=Event)
        
        # Now directly call the _verify_consistency method
        await sync_manager._verify_consistency(
            entity_type="bill",
            entity_id="117hr1234",
            sources=[bill_update, doc_update]  # Pass both sources directly
        )
        
        # Verify a sync record was created
        assert len(sync_manager._sync_history) == 1
        
        # Get the record and verify its content
        sync_record = list(sync_manager._sync_history.values())[0]
        assert sync_record["entity_type"] == "bill"
        assert sync_record["entity_id"] == "117hr1234"
        assert len(sync_record["sources"]) == 2
        assert ApiSource.CONGRESS in sync_record["sources"]
        assert ApiSource.GOVINFO in sync_record["sources"]
    
    async def test_check_bill_document_consistency_missing_data(self, sync_manager, entity_tracker):
        """Test consistency check with missing data."""
        # Setup entity tracker to return empty updates
        empty_updates = []
        future = asyncio.Future()
        future.set_result(empty_updates)
        entity_tracker.get_updates.return_value = future
        
        # Create test event for the context
        event = MagicMock(spec=Event)
        
        # Call the consistency check
        await sync_manager._check_bill_document_consistency(
            bill_id="117hr1234",
            document_id="BILLS-117hr1234ih",
            event=event
        )
        
        # Verify get_updates was called but no further processing occurred
        entity_tracker.get_updates.assert_called()
        
        # There should be no sync history since data was missing
        assert len(sync_manager._sync_history) == 0
    
    async def test_check_bill_document_consistency_single_source(self, sync_manager, entity_tracker):
        """Test consistency check with data from only one source."""
        # Setup entity tracker to return updates only from Congress
        bill_update = {
            "source": ApiSource.CONGRESS,
            "event_id": uuid4(),
            "timestamp": datetime.utcnow(),
            "data": {"congress": 117, "type": "hr", "number": 1234}
        }
        bill_updates = [bill_update]
        
        # Create futures for the mock responses
        bill_future = asyncio.Future()
        bill_future.set_result(bill_updates)
        
        empty_future = asyncio.Future()
        empty_future.set_result([])
        
        # Configure get_updates to return different results for different calls
        entity_tracker.get_updates.side_effect = lambda entity_type, entity_id, source=None: (
            bill_future if entity_type == "bill" else empty_future
        )
        
        # Create test event for the context
        event = MagicMock(spec=Event)
        
        # Call the consistency check
        await sync_manager._check_bill_document_consistency(
            bill_id="117hr1234",
            document_id="BILLS-117hr1234ih",
            event=event
        )
        
        # Verify get_updates was called for both entities
        assert entity_tracker.get_updates.call_count == 2
        
        # There should be no sync history since we only had data from one source
        assert len(sync_manager._sync_history) == 0
    
    async def test_verify_consistency(self, sync_manager):
        """Test consistency verification between sources."""
        # Create mock source data
        source1 = {
            "source": ApiSource.CONGRESS,
            "event_id": uuid4(),
            "timestamp": datetime.utcnow(),
            "data": {"congress": 117, "type": "hr", "number": 1234, "title": "Test Bill"}
        }
        
        source2 = {
            "source": ApiSource.GOVINFO,
            "event_id": uuid4(),
            "timestamp": datetime.utcnow(),
            "data": {"packageId": "BILLS-117hr1234ih", "title": "Test Bill"}
        }
        
        # Verify consistency
        await sync_manager._verify_consistency(
            entity_type="bill",
            entity_id="117hr1234",
            sources=[source1, source2]
        )
        
        # Verify a sync record was created
        assert len(sync_manager._sync_history) == 1
        
        # Get the record and verify its content
        sync_record = list(sync_manager._sync_history.values())[0]
        assert sync_record["entity_type"] == "bill"
        assert sync_record["entity_id"] == "117hr1234"
        assert len(sync_record["sources"]) == 2
        assert ApiSource.CONGRESS in sync_record["sources"]
        assert ApiSource.GOVINFO in sync_record["sources"]
        assert sync_record["status"] == SyncStatus.COMPLETED
        assert sync_record["consistent"] is True
    
    async def test_get_sync_manager_singleton(self):
        """Test global sync manager singleton."""
        # Reset the global instance
        import pygovpub.sync.manager
        pygovpub.sync.manager._sync_manager = None
        
        # Get the manager twice
        manager1 = get_sync_manager()
        manager2 = get_sync_manager()
        
        # Verify it's the same instance
        assert manager1 is manager2
        assert isinstance(manager1, SyncManager)
        
    async def test_detect_bill_conflicts(self, sync_manager):
        """Test detection of conflicts in bill data."""
        # Create test bill data with conflicts
        congress_bill_data = {
            "congress": 117,
            "type": "hr",
            "number": 1234,
            "title": "Test Bill from Congress",
            "introducedDate": "2023-03-01",
            "status": "enacted",
            "sponsors": [
                {
                    "bioguideId": "A000001",
                    "fullName": "Representative Test",
                }
            ],
            "actions": [
                {"actionDate": "2023-03-01", "text": "Introduced in House"},
                {"actionDate": "2023-04-01", "text": "Passed House"},
                {"actionDate": "2023-05-01", "text": "Passed Senate"},
                {"actionDate": "2023-06-01", "text": "Signed by President"}
            ]
        }
        
        govinfo_bill_data = {
            "congress": 117,
            "type": "hr",
            "number": 1234,
            "title": "Test Bill from GovInfo",  # Title conflict
            "introducedDate": "2023-03-02",  # Date conflict
            "status": "introduced",  # Status conflict (semantic contradiction)
            "sponsors": [
                {
                    "bioguideId": "B000002",  # Sponsor conflict
                    "fullName": "Different Representative",
                }
            ],
            "actions": [
                {"actionDate": "2023-03-01", "text": "Introduced in House"}
                # Fewer actions (temporal inconsistency)
            ]
        }
        
        # Create source data
        sources = [
            {
                "source": ApiSource.CONGRESS,
                "event_id": uuid4(),
                "timestamp": datetime.utcnow(),
                "data": congress_bill_data
            },
            {
                "source": ApiSource.GOVINFO,
                "event_id": uuid4(),
                "timestamp": datetime.utcnow(),
                "data": govinfo_bill_data
            }
        ]
        
        # Detect conflicts
        conflicts = sync_manager._detect_bill_conflicts("117hr1234", sources)
        
        # Verify conflicts detected
        assert len(conflicts) >= 4  # We expect at least 4 conflicts
        
        # Check for title conflict
        title_conflict = next((c for c in conflicts if c.field_path == "bill.title"), None)
        assert title_conflict is not None
        assert title_conflict.conflict_type == ConflictType.VALUE_MISMATCH
        assert ApiSource.CONGRESS in title_conflict.values
        assert ApiSource.GOVINFO in title_conflict.values
        assert title_conflict.values[ApiSource.CONGRESS] == "Test Bill from Congress"
        assert title_conflict.values[ApiSource.GOVINFO] == "Test Bill from GovInfo"
        
        # Check for date conflict
        date_conflict = next((c for c in conflicts if c.field_path == "bill.introducedDate"), None)
        assert date_conflict is not None
        assert date_conflict.conflict_type == ConflictType.VALUE_MISMATCH
        
        # Check for status conflict (semantic contradiction)
        status_conflict = next((c for c in conflicts if c.field_path == "bill.status"), None)
        assert status_conflict is not None
        assert status_conflict.conflict_type == ConflictType.SEMANTIC_CONTRADICTION
        
        # Check for sponsor conflict
        sponsor_conflict = next((c for c in conflicts if c.field_path == "bill.sponsor"), None)
        assert sponsor_conflict is not None
        assert sponsor_conflict.conflict_type == ConflictType.REFERENCE_INCONSISTENCY
        
        # Check for actions conflict (temporal inconsistency)
        actions_conflict = next((c for c in conflicts if c.field_path == "bill.actions"), None)
        assert actions_conflict is not None
        assert actions_conflict.conflict_type == ConflictType.TEMPORAL_INCONSISTENCY
        
    async def test_detect_document_conflicts(self, sync_manager):
        """Test detection of conflicts in document data."""
        # Create test document data with conflicts
        congress_doc_data = {
            "packageId": "BILLS-117hr1234ih",
            "title": "Document from Congress",
            "dateIssued": "2023-03-01",
            "collectionCode": "BILLS"
        }
        
        govinfo_doc_data = {
            "packageId": "BILLS-117hr1234ih",
            "title": "Document from GovInfo",  # Title conflict
            "dateIssued": "2023-03-02",  # Date conflict
            "collectionCode": "BILLS"
        }
        
        # Create source data
        sources = [
            {
                "source": ApiSource.CONGRESS,
                "event_id": uuid4(),
                "timestamp": datetime.utcnow(),
                "data": congress_doc_data
            },
            {
                "source": ApiSource.GOVINFO,
                "event_id": uuid4(),
                "timestamp": datetime.utcnow(),
                "data": govinfo_doc_data
            }
        ]
        
        # Detect conflicts
        conflicts = sync_manager._detect_document_conflicts("BILLS-117hr1234ih", sources)
        
        # Verify conflicts detected
        assert len(conflicts) >= 2  # We expect at least 2 conflicts
        
        # Check for title conflict
        title_conflict = next((c for c in conflicts if c.field_path == "document.title"), None)
        assert title_conflict is not None
        assert title_conflict.conflict_type == ConflictType.VALUE_MISMATCH
        assert ApiSource.CONGRESS in title_conflict.values
        assert ApiSource.GOVINFO in title_conflict.values
        assert title_conflict.values[ApiSource.CONGRESS] == "Document from Congress"
        assert title_conflict.values[ApiSource.GOVINFO] == "Document from GovInfo"
        
        # Check for date conflict
        date_conflict = next((c for c in conflicts if c.field_path == "document.dateIssued"), None)
        assert date_conflict is not None
        assert date_conflict.conflict_type == ConflictType.VALUE_MISMATCH
        
    async def test_resolve_conflicts(self, sync_manager):
        """Test conflict resolution using different strategies."""
        # Create test conflicts
        title_conflict = FieldConflict(
            field_path="bill.title",
            conflict_type=ConflictType.VALUE_MISMATCH,
            values={
                ApiSource.CONGRESS: "Title from Congress",
                ApiSource.GOVINFO: "Title from GovInfo"
            },
            description="Different bill titles"
        )
        
        date_conflict = FieldConflict(
            field_path="bill.latest_action_date",
            conflict_type=ConflictType.TEMPORAL_INCONSISTENCY,
            values={
                ApiSource.CONGRESS: "2023-06-01",
                ApiSource.GOVINFO: "2023-05-01"
            },
            description="Different latest action dates"
        )
        
        actions_conflict = FieldConflict(
            field_path="bill.actions",
            conflict_type=ConflictType.TEMPORAL_INCONSISTENCY,
            values={
                ApiSource.CONGRESS: [
                    {"actionDate": "2023-03-01", "text": "Introduced"},
                    {"actionDate": "2023-04-01", "text": "Passed House"}
                ],
                ApiSource.GOVINFO: [
                    {"actionDate": "2023-03-01", "text": "Introduced"},
                    {"actionDate": "2023-05-01", "text": "Passed Senate"}
                ]
            },
            description="Different action sets"
        )
        
        conflicts = [title_conflict, date_conflict, actions_conflict]
        
        # Resolve conflicts
        resolution_results = await sync_manager._resolve_conflicts(
            entity_type="bill",
            entity_id="117hr1234",
            conflicts=conflicts
        )
        
        # Verify results
        assert resolution_results["total_count"] == 3
        assert resolution_results["resolved_count"] >= 2  # At least 2 should be resolved
        assert resolution_results["status"] in ["resolved", "partial"]
        
        # Verify individual conflict resolutions
        # Title should be resolved by source precedence
        assert title_conflict.resolution == "resolved"
        assert title_conflict.resolved_value == "Title from Congress"
        assert title_conflict.resolution_strategy == ConflictResolutionStrategy.SOURCE_PRECEDENCE
        
        # Actions should be resolved by field merge
        assert actions_conflict.resolution == "resolved"
        assert len(actions_conflict.resolved_value) == 4  # Combined actions
        
    async def test_verify_consistency_with_conflicts(self, sync_manager, event_manager):
        """Test consistency verification that detects and resolves conflicts."""
        # Create test bill data with conflicts
        congress_bill_data = {
            "congress": 117,
            "type": "hr",
            "number": 1234,
            "title": "Test Bill from Congress",
            "introducedDate": "2023-03-01",
            "status": "enacted"
        }
        
        govinfo_bill_data = {
            "congress": 117,
            "type": "hr",
            "number": 1234,
            "title": "Test Bill from GovInfo",  # Title conflict
            "introducedDate": "2023-03-02",  # Date conflict
            "status": "introduced"  # Status conflict
        }
        
        # Create source data
        sources = [
            {
                "source": ApiSource.CONGRESS,
                "event_id": uuid4(),
                "timestamp": datetime.utcnow(),
                "data": congress_bill_data
            },
            {
                "source": ApiSource.GOVINFO,
                "event_id": uuid4(),
                "timestamp": datetime.utcnow(),
                "data": govinfo_bill_data
            }
        ]
        
        # Verify consistency
        await sync_manager._verify_consistency(
            entity_type="bill",
            entity_id="117hr1234",
            sources=sources
        )
        
        # Check the sync record
        assert len(sync_manager._sync_history) == 1
        sync_record = list(sync_manager._sync_history.values())[0]
        
        # Since we have conflicts, the status should be CONFLICT
        # for any unresolvable conflicts
        assert sync_record["status"] in [SyncStatus.COMPLETED, SyncStatus.CONFLICT]
        
        # Check that conflicts were detected and stored
        assert len(sync_manager._conflict_history) == 1
        conflict_record = list(sync_manager._conflict_history.values())[0]
        assert conflict_record["entity_type"] == "bill"
        assert conflict_record["entity_id"] == "117hr1234"
        assert len(conflict_record["conflicts"]) > 0
        
    async def test_get_conflicts(self, sync_manager):
        """Test retrieving conflicts for an entity."""
        # Setup test data
        entity_type = "bill"
        entity_id = "117hr1234"
        
        # Create a test conflict in history
        conflict_id = uuid4()
        conflict = FieldConflict(
            field_path="bill.title",
            conflict_type=ConflictType.VALUE_MISMATCH,
            values={
                ApiSource.CONGRESS: "Title from Congress",
                ApiSource.GOVINFO: "Title from GovInfo"
            },
            description="Different bill titles"
        )
        
        resolution_results = {
            "status": "partial",
            "total_count": 1,
            "resolved_count": 0,
            "unresolved_count": 1
        }
        
        sync_manager._conflict_history[conflict_id] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "timestamp": datetime.utcnow(),
            "conflicts": [conflict],
            "resolutions": resolution_results
        }
        
        # Get conflicts
        conflicts = await sync_manager.get_conflicts(
            entity_type=entity_type,
            entity_id=entity_id
        )
        
        # Verify results
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_id"] == conflict_id
        assert len(conflicts[0]["conflicts"]) == 1
        assert conflicts[0]["conflicts"][0] is conflict
        
    async def test_resolve_conflict_manually(self, sync_manager):
        """Test manual resolution of a conflict."""
        # Setup test data
        entity_type = "bill"
        entity_id = "117hr1234"
        field_path = "bill.title"
        
        # Create a test conflict in history
        conflict_id = uuid4()
        conflict = FieldConflict(
            field_path=field_path,
            conflict_type=ConflictType.VALUE_MISMATCH,
            values={
                ApiSource.CONGRESS: "Title from Congress",
                ApiSource.GOVINFO: "Title from GovInfo"
            },
            description="Different bill titles"
        )
        conflict.resolution = "unresolved"
        
        resolution_results = {
            "status": "partial",
            "total_count": 1,
            "resolved_count": 0,
            "unresolved_count": 1,
            "resolution_strategies": {}
        }
        
        sync_manager._conflict_history[conflict_id] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "timestamp": datetime.utcnow(),
            "conflicts": [conflict],
            "resolutions": resolution_results
        }
        
        # Resolve the conflict manually
        resolved_value = "Manually Resolved Title"
        success = await sync_manager.resolve_conflict_manually(
            conflict_id=conflict_id,
            field_path=field_path,
            resolved_value=resolved_value
        )
        
        # Verify results
        assert success is True
        assert conflict.resolution == "manual"
        assert conflict.resolved_value == resolved_value
        assert conflict.resolution_strategy == ConflictResolutionStrategy.MANUAL
        
        # Check that resolution statistics were updated
        assert resolution_results["resolved_count"] == 1
        assert resolution_results["unresolved_count"] == 0
        assert resolution_results["status"] == "resolved"