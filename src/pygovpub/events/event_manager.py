"""
Event management system for PyGovPub.

This module provides an event manager for handling real-time updates
through a publisher-subscriber pattern.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union
from uuid import UUID

from pygovpub.events.event_types import Event, EventCategory, EventType, EventPayload

# Configure logging
logger = logging.getLogger("pygovpub.events")


class EventManager:
    """Manager for event registration, dispatch, and subscription."""
    
    def __init__(self):
        """Initialize event manager."""
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._category_subscribers: Dict[EventCategory, List[Callable]] = {}
        self._global_subscribers: List[Callable] = []
        self._event_history: Dict[UUID, Event] = {}
        self._lock = asyncio.Lock()
        
    async def register_event(self, event: Event) -> UUID:
        """Register a new event in the system.
        
        Args:
            event: Event to register
            
        Returns:
            UUID of registered event
        """
        async with self._lock:
            # Store event in history
            self._event_history[event.id] = event
            logger.debug(f"Registered event {event.id} of type {event.event_type}")
            return event.id
    
    async def emit_event(self, event: Event) -> UUID:
        """Register and dispatch an event.
        
        Args:
            event: Event to emit
            
        Returns:
            UUID of emitted event
        """
        # Register event
        event_id = await self.register_event(event)
        
        # Dispatch event
        await self.dispatch_event(event)
        
        return event_id
    
    async def create_and_emit_event(
        self,
        event_type: EventType,
        payload: EventPayload,
        priority: Optional[str] = None
    ) -> UUID:
        """Create and emit an event.
        
        Args:
            event_type: Type of event
            payload: Event payload
            priority: Optional priority override
            
        Returns:
            UUID of emitted event
        """
        # Determine category from event type
        category = self._get_category_from_type(event_type)
        
        # Create event
        event = Event(
            event_type=event_type,
            category=category,
            payload=payload
        )
        
        if priority:
            event.priority = priority
            
        # Emit event
        return await self.emit_event(event)
    
    def _get_category_from_type(self, event_type: EventType) -> EventCategory:
        """Determine event category from event type.
        
        Args:
            event_type: Event type
            
        Returns:
            Event category
        """
        type_name = event_type.value
        
        if "floor" in type_name:
            return EventCategory.FLOOR_UPDATE
        elif "vote" in type_name:
            return EventCategory.VOTE_UPDATE
        elif "calendar" in type_name:
            return EventCategory.CALENDAR_UPDATE
        elif "hearing" in type_name:
            return EventCategory.HEARING_UPDATE
        elif "bill" in type_name:
            return EventCategory.BILL_UPDATE
        elif "committee" in type_name:
            return EventCategory.COMMITTEE_UPDATE
        elif "member" in type_name:
            return EventCategory.MEMBER_UPDATE
        elif "document" in type_name:
            return EventCategory.DOCUMENT_UPDATE
        else:
            return EventCategory.SYSTEM
    
    async def dispatch_event(self, event: Event) -> None:
        """Dispatch event to all subscribers.
        
        Args:
            event: Event to dispatch
        """
        # Update event metadata
        event.processed_at = datetime.utcnow()
        
        # Get subscribers for this event
        subscribers = self._get_subscribers_for_event(event)
        
        if not subscribers:
            logger.debug(f"No subscribers for event {event.id} of type {event.event_type}")
            return
            
        # Dispatch to all subscribers
        for subscriber in subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(event)
                else:
                    subscriber(event)
            except Exception as e:
                logger.error(f"Error dispatching event {event.id} to subscriber: {e}")
                
        logger.debug(f"Dispatched event {event.id} to {len(subscribers)} subscribers")
    
    def _get_subscribers_for_event(self, event: Event) -> List[Callable]:
        """Get subscribers for a specific event.
        
        Args:
            event: Event to get subscribers for
            
        Returns:
            List of subscriber callables
        """
        subscribers = []
        
        # Add type-specific subscribers
        if event.event_type in self._subscribers:
            subscribers.extend(self._subscribers[event.event_type])
            
        # Add category subscribers
        if event.category in self._category_subscribers:
            subscribers.extend(self._category_subscribers[event.category])
            
        # Add global subscribers
        subscribers.extend(self._global_subscribers)
        
        return subscribers
    
    def subscribe(self, callback: Callable[[Event], Any], 
                  event_type: Optional[EventType] = None,
                  category: Optional[EventCategory] = None) -> None:
        """Subscribe to events.
        
        Args:
            callback: Function to call when event occurs
            event_type: Optional specific event type to subscribe to
            category: Optional event category to subscribe to
        """
        if event_type:
            # Subscribe to specific event type
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            logger.debug(f"Added subscriber to event type {event_type}")
        elif category:
            # Subscribe to event category
            if category not in self._category_subscribers:
                self._category_subscribers[category] = []
            self._category_subscribers[category].append(callback)
            logger.debug(f"Added subscriber to event category {category}")
        else:
            # Subscribe to all events
            self._global_subscribers.append(callback)
            logger.debug("Added global subscriber")
    
    def unsubscribe(self, callback: Callable[[Event], Any],
                    event_type: Optional[EventType] = None,
                    category: Optional[EventCategory] = None) -> bool:
        """Unsubscribe from events.
        
        Args:
            callback: Function to remove from subscribers
            event_type: Optional specific event type to unsubscribe from
            category: Optional event category to unsubscribe from
            
        Returns:
            True if successfully unsubscribed, False otherwise
        """
        if event_type:
            # Unsubscribe from specific event type
            if event_type in self._subscribers and callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Removed subscriber from event type {event_type}")
                return True
        elif category:
            # Unsubscribe from event category
            if category in self._category_subscribers and callback in self._category_subscribers[category]:
                self._category_subscribers[category].remove(callback)
                logger.debug(f"Removed subscriber from event category {category}")
                return True
        else:
            # Unsubscribe from all events
            if callback in self._global_subscribers:
                self._global_subscribers.remove(callback)
                logger.debug("Removed global subscriber")
                return True
                
        return False
    
    def get_event(self, event_id: UUID) -> Optional[Event]:
        """Get event by ID.
        
        Args:
            event_id: UUID of event to retrieve
            
        Returns:
            Event if found, None otherwise
        """
        return self._event_history.get(event_id)
    
    def get_events_by_type(self, event_type: EventType) -> List[Event]:
        """Get events by type.
        
        Args:
            event_type: Event type to filter by
            
        Returns:
            List of matching events
        """
        return [
            event for event in self._event_history.values()
            if event.event_type == event_type
        ]
    
    def get_events_by_category(self, category: EventCategory) -> List[Event]:
        """Get events by category.
        
        Args:
            category: Event category to filter by
            
        Returns:
            List of matching events
        """
        return [
            event for event in self._event_history.values()
            if event.category == category
        ]
    
    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()
        logger.debug("Cleared event history")


# Global event manager instance
_event_manager = None


def get_event_manager() -> EventManager:
    """Get the global event manager instance.
    
    Returns:
        Global event manager instance
    """
    global _event_manager
    if _event_manager is None:
        _event_manager = EventManager()
    return _event_manager