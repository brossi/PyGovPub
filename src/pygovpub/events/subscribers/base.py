"""
Base subscriber for PyGovPub events.

This module provides a base class for event subscribers
that process events and perform actions.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from pygovpub.events.event_types import Event, EventCategory, EventType

# Configure logging
logger = logging.getLogger("pygovpub.events.subscribers")


class EventSubscriberBase(ABC):
    """Base class for event subscribers."""
    
    def __init__(self, name: str):
        """Initialize subscriber.
        
        Args:
            name: Subscriber name
        """
        self.name = name
        self._processed_events: Set[UUID] = set()
        self._processing_history: Dict[str, Dict[str, Any]] = {}
        
    @abstractmethod
    async def process_event(self, event: Event) -> bool:
        """Process an event.
        
        Args:
            event: Event to process
            
        Returns:
            True if processing succeeded, False otherwise
        """
        pass
    
    def record_processing_attempt(self, event: Event, success: bool, error: Optional[str] = None) -> None:
        """Record processing attempt.
        
        Args:
            event: Event that was processed
            success: Whether processing succeeded
            error: Optional error message
        """
        event_id = str(event.id)
        
        if event_id not in self._processing_history:
            self._processing_history[event_id] = {
                "event_type": event.event_type.value,
                "attempts": 0,
                "last_attempt": None,
                "success": False,
                "errors": []
            }
            
        history = self._processing_history[event_id]
        history["attempts"] += 1
        history["last_attempt"] = datetime.utcnow().isoformat()
        history["success"] = success
        
        if error:
            history["errors"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "message": error
            })
            
        if success:
            self._processed_events.add(event.id)
            
        logger.debug(
            f"Processing attempt for event {event_id} by {self.name}: "
            f"{'success' if success else 'failure'}"
        )
    
    def has_processed_event(self, event_id: UUID) -> bool:
        """Check if an event has been processed.
        
        Args:
            event_id: Event ID
            
        Returns:
            True if event has been processed, False otherwise
        """
        return event_id in self._processed_events
    
    def get_processing_history(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get processing history for an event.
        
        Args:
            event_id: Event ID
            
        Returns:
            Processing history if found, None otherwise
        """
        return self._processing_history.get(event_id)