"""
Unit tests for the entity tracker component of the synchronization system.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import UUID, uuid4

from pygovpub.auth.models import ApiSource
from pygovpub.sync.tracker import EntityTracker


class TestEntityTracker:
    """Tests for the EntityTracker class."""
    
    @pytest.fixture
    def tracker(self):
        """Create an entity tracker instance."""
        return EntityTracker()
    
    @pytest.fixture
    def sample_data(self):
        """Create sample bill data."""
        return {
            "congress": 117,
            "type": "hr",
            "number": 1234,
            "title": "Test Bill",
            "introducedDate": "2023-03-01"
        }
    
    async def test_track_update(self, tracker, sample_data):
        """Test tracking an entity update."""
        # Track an update
        entity_type = "bill"
        entity_id = "117hr1234"
        source = ApiSource.CONGRESS
        event_id = uuid4()
        
        await tracker.track_update(
            entity_type=entity_type,
            entity_id=entity_id,
            source=source,
            event_id=event_id,
            data=sample_data
        )
        
        # Get updates
        updates = await tracker.get_updates(
            entity_type=entity_type,
            entity_id=entity_id
        )
        
        # Verify update was tracked
        assert len(updates) == 1
        assert updates[0]["source"] == source
        assert updates[0]["event_id"] == event_id
        assert updates[0]["data"] == sample_data
    
    async def test_get_updates_by_source(self, tracker, sample_data):
        """Test getting updates filtered by source."""
        # Track updates from different sources
        entity_type = "bill"
        entity_id = "117hr1234"
        congress_event_id = uuid4()
        govinfo_event_id = uuid4()
        
        # Update from Congress
        await tracker.track_update(
            entity_type=entity_type,
            entity_id=entity_id,
            source=ApiSource.CONGRESS,
            event_id=congress_event_id,
            data=sample_data
        )
        
        # Update from GovInfo
        await tracker.track_update(
            entity_type=entity_type,
            entity_id=entity_id,
            source=ApiSource.GOVINFO,
            event_id=govinfo_event_id,
            data={"packageId": f"BILLS-{entity_id}ih", "title": sample_data["title"]}
        )
        
        # Get updates from Congress
        congress_updates = await tracker.get_updates(
            entity_type=entity_type,
            entity_id=entity_id,
            source=ApiSource.CONGRESS
        )
        
        # Get updates from GovInfo
        govinfo_updates = await tracker.get_updates(
            entity_type=entity_type,
            entity_id=entity_id,
            source=ApiSource.GOVINFO
        )
        
        # Verify filtered updates
        assert len(congress_updates) == 1
        assert congress_updates[0]["source"] == ApiSource.CONGRESS
        assert congress_updates[0]["event_id"] == congress_event_id
        
        assert len(govinfo_updates) == 1
        assert govinfo_updates[0]["source"] == ApiSource.GOVINFO
        assert govinfo_updates[0]["event_id"] == govinfo_event_id
    
    async def test_get_latest_update(self, tracker, sample_data):
        """Test getting the latest update for an entity."""
        # Track multiple updates with different timestamps
        entity_type = "bill"
        entity_id = "117hr1234"
        source = ApiSource.CONGRESS
        
        # First update
        event_id_1 = uuid4()
        await tracker.track_update(
            entity_type=entity_type,
            entity_id=entity_id,
            source=source,
            event_id=event_id_1,
            data=sample_data
        )
        
        # Introduce a delay to ensure different timestamps
        await asyncio.sleep(0.01)
        
        # Second update (should be the latest)
        event_id_2 = uuid4()
        updated_data = sample_data.copy()
        updated_data["title"] = "Updated Test Bill"
        
        await tracker.track_update(
            entity_type=entity_type,
            entity_id=entity_id,
            source=source,
            event_id=event_id_2,
            data=updated_data
        )
        
        # Get the latest update
        latest = await tracker.get_latest_update(
            entity_type=entity_type,
            entity_id=entity_id
        )
        
        # Verify it's the second update
        assert latest is not None
        assert latest["event_id"] == event_id_2
        assert latest["data"]["title"] == "Updated Test Bill"
    
    async def test_get_sources_for_entity(self, tracker, sample_data):
        """Test getting all sources with updates for an entity."""
        # Track updates from different sources
        entity_type = "bill"
        entity_id = "117hr1234"
        
        # No updates yet
        sources = await tracker.get_sources_for_entity(
            entity_type=entity_type,
            entity_id=entity_id
        )
        assert len(sources) == 0
        
        # Add update from Congress
        await tracker.track_update(
            entity_type=entity_type,
            entity_id=entity_id,
            source=ApiSource.CONGRESS,
            event_id=uuid4(),
            data=sample_data
        )
        
        # Check sources again
        sources = await tracker.get_sources_for_entity(
            entity_type=entity_type,
            entity_id=entity_id
        )
        assert len(sources) == 1
        assert ApiSource.CONGRESS in sources
        
        # Add update from GovInfo
        await tracker.track_update(
            entity_type=entity_type,
            entity_id=entity_id,
            source=ApiSource.GOVINFO,
            event_id=uuid4(),
            data={"packageId": f"BILLS-{entity_id}ih"}
        )
        
        # Check sources again
        sources = await tracker.get_sources_for_entity(
            entity_type=entity_type,
            entity_id=entity_id
        )
        assert len(sources) == 2
        assert ApiSource.CONGRESS in sources
        assert ApiSource.GOVINFO in sources
    
    async def test_clear_history(self, tracker, sample_data):
        """Test clearing update history."""
        # Track updates for multiple entities
        await tracker.track_update(
            entity_type="bill",
            entity_id="117hr1234",
            source=ApiSource.CONGRESS,
            event_id=uuid4(),
            data=sample_data
        )
        
        await tracker.track_update(
            entity_type="document",
            entity_id="BILLS-117hr1234ih",
            source=ApiSource.GOVINFO,
            event_id=uuid4(),
            data={"packageId": "BILLS-117hr1234ih"}
        )
        
        # Verify updates exist
        bill_updates = await tracker.get_updates(
            entity_type="bill",
            entity_id="117hr1234"
        )
        assert len(bill_updates) == 1
        
        document_updates = await tracker.get_updates(
            entity_type="document",
            entity_id="BILLS-117hr1234ih"
        )
        assert len(document_updates) == 1
        
        # Clear history for bill
        await tracker.clear_history(
            entity_type="bill",
            entity_id="117hr1234"
        )
        
        # Verify bill updates are cleared
        bill_updates = await tracker.get_updates(
            entity_type="bill",
            entity_id="117hr1234"
        )
        assert len(bill_updates) == 0
        
        # Verify document updates still exist
        document_updates = await tracker.get_updates(
            entity_type="document",
            entity_id="BILLS-117hr1234ih"
        )
        assert len(document_updates) == 1
        
        # Clear all history
        await tracker.clear_history()
        
        # Verify all updates are cleared
        document_updates = await tracker.get_updates(
            entity_type="document",
            entity_id="BILLS-117hr1234ih"
        )
        assert len(document_updates) == 0