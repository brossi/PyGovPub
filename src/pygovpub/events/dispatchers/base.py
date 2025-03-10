"""
Base dispatcher for PyGovPub events.

This module provides a base class for event dispatchers
that can be extended for different delivery mechanisms.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from pygovpub.events.event_types import Event

# Configure logging
logger = logging.getLogger("pygovpub.events.dispatchers")


class EventDispatcherBase(ABC):
    """Base class for event dispatchers."""
    
    def __init__(self, name: str):
        """Initialize dispatcher.
        
        Args:
            name: Dispatcher name
        """
        self.name = name
        self._event_processing_history: Dict[str, Dict[str, Any]] = {}
        
    @abstractmethod
    async def dispatch(self, event: Event) -> bool:
        """Dispatch event to destination.
        
        Args:
            event: Event to dispatch
            
        Returns:
            True if dispatch succeeded, False otherwise
        """
        pass
    
    def record_dispatch_attempt(self, event: Event, success: bool, error: Optional[str] = None) -> None:
        """Record dispatch attempt.
        
        Args:
            event: Event that was dispatched
            success: Whether dispatch succeeded
            error: Optional error message
        """
        event_id = str(event.id)
        
        if event_id not in self._event_processing_history:
            self._event_processing_history[event_id] = {
                "event_type": event.event_type.value,
                "attempts": 0,
                "last_attempt": None,
                "success": False,
                "errors": []
            }
            
        history = self._event_processing_history[event_id]
        history["attempts"] += 1
        history["last_attempt"] = datetime.utcnow().isoformat()
        history["success"] = success
        
        if error:
            history["errors"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "message": error
            })
            
        if success:
            event.delivered_at = datetime.utcnow()
        else:
            event.delivery_attempts += 1
            event.last_delivery_attempt = datetime.utcnow()
            event.error_message = error
            
        logger.debug(
            f"Dispatch attempt for event {event_id} via {self.name}: "
            f"{'success' if success else 'failure'}"
        )
    
    def get_dispatch_history(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get dispatch history for an event.
        
        Args:
            event_id: Event ID
            
        Returns:
            Dispatch history if found, None otherwise
        """
        return self._event_processing_history.get(event_id)