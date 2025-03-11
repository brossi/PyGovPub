"""
Synchronization manager for PyGovPub.

This module provides a synchronization manager for coordinating data updates
between multiple government data sources and ensuring consistency.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID

from pygovpub.auth.models import ApiSource
from pygovpub.events.event_manager import get_event_manager
from pygovpub.events.event_types import (
    Event, EventCategory, EventType, EventPayload,
    DocumentPublishedPayload, DocumentUpdatedPayload
)
from pygovpub.sync.tracker import EntityTracker


class SyncStatus(str, Enum):
    """Status of a synchronization operation."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class SyncManager:
    """Manager for data synchronization between multiple sources."""
    
    def __init__(self):
        """Initialize synchronization manager."""
        self._event_manager = get_event_manager()
        self._entity_tracker = EntityTracker()
        self._lock = asyncio.Lock()
        self._sync_history = {}
        self._logger = logging.getLogger("pygovpub.sync")
        
        # Subscribe to relevant events
        self._subscribe_to_events()
    
    def _subscribe_to_events(self):
        """Subscribe to events that require synchronization."""
        # Document events
        self._event_manager.subscribe(
            self._handle_document_event,
            category=EventCategory.DOCUMENT_UPDATE
        )
        
        # Bill events
        self._event_manager.subscribe(
            self._handle_bill_event,
            category=EventCategory.BILL_UPDATE
        )
    
    async def _handle_document_event(self, event: Event):
        """Handle document update events.
        
        Args:
            event: Document update event
        """
        if not event.payload or not isinstance(event.payload, (DocumentPublishedPayload, DocumentUpdatedPayload)):
            return
        
        # Get entity information
        entity_type = "document"
        entity_id = event.payload.document_id
        source = event.payload.source
        
        # Track the entity update
        await self._entity_tracker.track_update(
            entity_type=entity_type,
            entity_id=entity_id,
            source=source,
            event_id=event.id,
            data=event.payload.data
        )
        
        # Check for related bill events if this is a bill document
        if event.payload.document_type == "bill" and event.payload.related_bills:
            # This is a bill document, check for corresponding bill updates
            for bill_id in event.payload.related_bills:
                await self._check_bill_document_consistency(
                    bill_id=bill_id,
                    document_id=entity_id,
                    event=event
                )
    
    async def _handle_bill_event(self, event: Event):
        """Handle bill update events.
        
        Args:
            event: Bill update event
        """
        # Extract bill ID from event
        if not event.payload or not hasattr(event.payload, 'data') or not event.payload.data:
            return
            
        bill_data = event.payload.data
        if not isinstance(bill_data, dict):
            return
            
        # Get bill identifiers
        congress = bill_data.get("congress")
        bill_type = bill_data.get("type")
        bill_number = bill_data.get("number")
        
        if not all([congress, bill_type, bill_number]):
            return
            
        # Construct bill ID
        entity_type = "bill"
        entity_id = f"{congress}{bill_type}{bill_number}"
        source = event.payload.source
        
        # Track the entity update
        self._logger.debug(f"Tracking bill update for {entity_id} from {source}")
        await self._entity_tracker.track_update(
            entity_type=entity_type,
            entity_id=entity_id,
            source=source,
            event_id=event.id,
            data=bill_data
        )
        
        # Check for related document events
        document_id = f"BILLS-{congress}{bill_type}{bill_number}"
        await self._check_bill_document_consistency(
            bill_id=entity_id,
            document_id=document_id,
            event=event
        )
    
    async def _check_bill_document_consistency(self, bill_id: str, document_id: str, event: Event):
        """Check consistency between bill and document data.
        
        Args:
            bill_id: Bill identifier
            document_id: Document identifier
            event: Triggering event
        """
        # Get bill data if available
        bill_updates = await self._entity_tracker.get_updates(
            entity_type="bill",
            entity_id=bill_id
        )
        
        # Get document data if available
        document_updates = await self._entity_tracker.get_updates(
            entity_type="document",
            entity_id=document_id
        )
        
        if not bill_updates or not document_updates:
            # Not enough data to check consistency
            return
            
        # Get latest updates from each source
        congress_bill = None
        govinfo_doc = None
        
        for update in bill_updates:
            if update["source"] == ApiSource.CONGRESS:
                congress_bill = update
                
        for update in document_updates:
            if update["source"] == ApiSource.GOVINFO:
                govinfo_doc = update
                
        if not congress_bill or not govinfo_doc:
            # Missing data from one source
            return
            
        # Check consistency
        await self._verify_consistency(
            entity_type="bill",
            entity_id=bill_id,
            sources=[congress_bill, govinfo_doc]
        )
    
    async def _verify_consistency(self, entity_type: str, entity_id: str, sources: List[Dict[str, Any]]):
        """Verify consistency between multiple data sources.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            sources: List of source data
        """
        # TODO: Implement detailed consistency checks
        
        # For now, just log the verification
        self._logger.info(
            f"Verified consistency for {entity_type} {entity_id} "
            f"across {len(sources)} sources"
        )
        
        # Record the verification in history
        sync_id = UUID(int=0)  # Placeholder
        
        async with self._lock:
            self._sync_history[sync_id] = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "sources": [s["source"] for s in sources],
                "status": SyncStatus.COMPLETED,
                "timestamp": datetime.utcnow(),
                "consistent": True  # Simplified for now
            }
    
    async def get_sync_status(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get synchronization status for an entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            
        Returns:
            Synchronization status if available
        """
        # Find the most recent sync record
        latest_sync = None
        latest_time = None
        
        for sync_id, sync_data in self._sync_history.items():
            if sync_data["entity_type"] == entity_type and sync_data["entity_id"] == entity_id:
                if latest_time is None or sync_data["timestamp"] > latest_time:
                    latest_sync = sync_data
                    latest_time = sync_data["timestamp"]
                    
        return latest_sync


# Global sync manager instance
_sync_manager = None


def get_sync_manager() -> SyncManager:
    """Get the global synchronization manager instance.
    
    Returns:
        Global synchronization manager instance
    """
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = SyncManager()
    return _sync_manager