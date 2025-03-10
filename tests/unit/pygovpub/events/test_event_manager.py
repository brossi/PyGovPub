"""
Unit tests for the event management system.
"""

import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import uuid

import pytest

from pygovpub.auth.models import ApiSource
from pygovpub.events.event_manager import EventManager, get_event_manager
from pygovpub.events.event_types import (
    Event, EventCategory, EventType, EventPayload,
    FloorUpdatePayload, VoteUpdatePayload, CalendarUpdatePayload, HearingUpdatePayload
)


class TestEventManager:
    """Tests for the event manager."""
    
    @pytest.fixture
    def event_manager(self):
        """Create an event manager for testing."""
        return EventManager()
    
    @pytest.fixture
    def sample_payload(self):
        """Create a sample event payload."""
        return EventPayload(
            source=ApiSource.CONGRESS,
            source_id="123",
            resource_type="test"
        )
    
    @pytest.fixture
    def sample_event(self, sample_payload):
        """Create a sample event."""
        return Event(
            event_type=EventType.FLOOR_PROCEEDINGS_UPDATE,
            category=EventCategory.FLOOR_UPDATE,
            payload=sample_payload
        )
    
    async def test_register_event(self, event_manager, sample_event):
        """Test registering an event."""
        # Register the event
        event_id = await event_manager.register_event(sample_event)
        
        # Verify the event was stored
        assert event_id == sample_event.id
        assert event_manager._event_history[event_id] == sample_event
    
    async def test_emit_event(self, event_manager, sample_event):
        """Test emitting an event."""
        # Mock the dispatch_event method
        event_manager.dispatch_event = AsyncMock()
        
        # Emit the event
        event_id = await event_manager.emit_event(sample_event)
        
        # Verify the event was registered and dispatched
        assert event_id == sample_event.id
        assert event_manager._event_history[event_id] == sample_event
        event_manager.dispatch_event.assert_called_once_with(sample_event)
    
    async def test_create_and_emit_event(self, event_manager, sample_payload):
        """Test creating and emitting an event."""
        # Mock the emit_event method
        event_manager.emit_event = AsyncMock()
        event_manager.emit_event.return_value = uuid.uuid4()
        
        # Create and emit an event
        event_id = await event_manager.create_and_emit_event(
            event_type=EventType.FLOOR_PROCEEDINGS_UPDATE,
            payload=sample_payload,
            priority="high"
        )
        
        # Verify emit_event was called with correct event
        assert event_manager.emit_event.called
        event_arg = event_manager.emit_event.call_args[0][0]
        assert event_arg.event_type == EventType.FLOOR_PROCEEDINGS_UPDATE
        assert event_arg.category == EventCategory.FLOOR_UPDATE
        assert event_arg.payload == sample_payload
        assert event_arg.priority == "high"
    
    def test_get_category_from_type(self, event_manager):
        """Test category determination from event type."""
        # Test floor update event types
        assert event_manager._get_category_from_type(EventType.FLOOR_PROCEEDINGS_UPDATE) == EventCategory.FLOOR_UPDATE
        assert event_manager._get_category_from_type(EventType.FLOOR_ACTION) == EventCategory.FLOOR_UPDATE
        
        # Test vote update event types
        assert event_manager._get_category_from_type(EventType.VOTE_SCHEDULED) == EventCategory.VOTE_UPDATE
        assert event_manager._get_category_from_type(EventType.VOTE_COMPLETED) == EventCategory.VOTE_UPDATE
        
        # Test calendar update event types
        assert event_manager._get_category_from_type(EventType.CALENDAR_ITEM_ADDED) == EventCategory.CALENDAR_UPDATE
        
        # Test hearing update event types
        assert event_manager._get_category_from_type(EventType.HEARING_SCHEDULED) == EventCategory.HEARING_UPDATE
        
        # Test bill update event types
        assert event_manager._get_category_from_type(EventType.BILL_INTRODUCED) == EventCategory.BILL_UPDATE
        
        # Test committee update event types
        assert event_manager._get_category_from_type(EventType.COMMITTEE_MEETING_SCHEDULED) == EventCategory.COMMITTEE_UPDATE
        
        # Test member update event types
        assert event_manager._get_category_from_type(EventType.MEMBER_STATEMENT_AVAILABLE) == EventCategory.MEMBER_UPDATE
        
        # Test document update event types
        assert event_manager._get_category_from_type(EventType.DOCUMENT_AVAILABLE) == EventCategory.DOCUMENT_UPDATE
        
        # Test system event types
        assert event_manager._get_category_from_type(EventType.SYSTEM_STARTUP) == EventCategory.SYSTEM
    
    async def test_dispatch_event_no_subscribers(self, event_manager, sample_event):
        """Test dispatching an event with no subscribers."""
        # Dispatch the event
        await event_manager.dispatch_event(sample_event)
        
        # Verify the event was processed
        assert sample_event.processed_at is not None
    
    async def test_dispatch_event_with_subscribers(self, event_manager, sample_event):
        """Test dispatching an event with subscribers."""
        # Create mock subscribers
        sync_subscriber = MagicMock()
        async_subscriber = AsyncMock()
        
        # Add subscribers
        event_manager.subscribe(sync_subscriber, event_type=sample_event.event_type)
        event_manager.subscribe(async_subscriber, category=sample_event.category)
        
        # Add an error-raising subscriber to test error handling
        error_subscriber = MagicMock(side_effect=Exception("Test error"))
        event_manager.subscribe(error_subscriber)
        
        # Dispatch the event
        await event_manager.dispatch_event(sample_event)
        
        # Verify subscribers were called
        sync_subscriber.assert_called_once_with(sample_event)
        async_subscriber.assert_called_once_with(sample_event)
        error_subscriber.assert_called_once_with(sample_event)
    
    def test_get_subscribers_for_event(self, event_manager, sample_event):
        """Test getting subscribers for an event."""
        # Create mock subscribers
        type_subscriber = MagicMock()
        category_subscriber = MagicMock()
        global_subscriber = MagicMock()
        
        # Add subscribers
        event_manager.subscribe(type_subscriber, event_type=sample_event.event_type)
        event_manager.subscribe(category_subscriber, category=sample_event.category)
        event_manager.subscribe(global_subscriber)
        
        # Get subscribers for the event
        subscribers = event_manager._get_subscribers_for_event(sample_event)
        
        # Verify all subscribers were returned
        assert len(subscribers) == 3
        assert type_subscriber in subscribers
        assert category_subscriber in subscribers
        assert global_subscriber in subscribers
    
    def test_subscribe_and_unsubscribe(self, event_manager):
        """Test subscribing and unsubscribing."""
        # Create mock subscribers
        type_subscriber = MagicMock()
        category_subscriber = MagicMock()
        global_subscriber = MagicMock()
        
        # Subscribe
        event_manager.subscribe(type_subscriber, event_type=EventType.FLOOR_PROCEEDINGS_UPDATE)
        event_manager.subscribe(category_subscriber, category=EventCategory.FLOOR_UPDATE)
        event_manager.subscribe(global_subscriber)
        
        # Verify subscriptions
        assert type_subscriber in event_manager._subscribers[EventType.FLOOR_PROCEEDINGS_UPDATE]
        assert category_subscriber in event_manager._category_subscribers[EventCategory.FLOOR_UPDATE]
        assert global_subscriber in event_manager._global_subscribers
        
        # Unsubscribe
        assert event_manager.unsubscribe(type_subscriber, event_type=EventType.FLOOR_PROCEEDINGS_UPDATE)
        assert event_manager.unsubscribe(category_subscriber, category=EventCategory.FLOOR_UPDATE)
        assert event_manager.unsubscribe(global_subscriber)
        
        # Verify subscriptions were removed
        assert type_subscriber not in event_manager._subscribers[EventType.FLOOR_PROCEEDINGS_UPDATE]
        assert category_subscriber not in event_manager._category_subscribers[EventCategory.FLOOR_UPDATE]
        assert global_subscriber not in event_manager._global_subscribers
        
        # Test unsubscribing a non-existent subscriber
        assert not event_manager.unsubscribe(MagicMock())
    
    def test_get_event(self, event_manager, sample_event):
        """Test getting event by ID."""
        # Store the event
        event_manager._event_history[sample_event.id] = sample_event
        
        # Get the event
        event = event_manager.get_event(sample_event.id)
        
        # Verify the event was returned
        assert event == sample_event
        
        # Test getting a non-existent event
        assert event_manager.get_event(uuid.uuid4()) is None
    
    def test_get_events_by_type(self, event_manager, sample_event):
        """Test getting events by type."""
        # Store the event
        event_manager._event_history[sample_event.id] = sample_event
        
        # Create and store another event of a different type
        other_event = Event(
            event_type=EventType.VOTE_COMPLETED,
            category=EventCategory.VOTE_UPDATE,
            payload=EventPayload(
                source=ApiSource.CONGRESS,
                source_id="456",
                resource_type="test"
            )
        )
        event_manager._event_history[other_event.id] = other_event
        
        # Get events by type
        events = event_manager.get_events_by_type(sample_event.event_type)
        
        # Verify only the matching event was returned
        assert len(events) == 1
        assert events[0] == sample_event
    
    def test_get_events_by_category(self, event_manager, sample_event):
        """Test getting events by category."""
        # Store the event
        event_manager._event_history[sample_event.id] = sample_event
        
        # Create and store another event of a different category
        other_event = Event(
            event_type=EventType.VOTE_COMPLETED,
            category=EventCategory.VOTE_UPDATE,
            payload=EventPayload(
                source=ApiSource.CONGRESS,
                source_id="456",
                resource_type="test"
            )
        )
        event_manager._event_history[other_event.id] = other_event
        
        # Get events by category
        events = event_manager.get_events_by_category(sample_event.category)
        
        # Verify only the matching event was returned
        assert len(events) == 1
        assert events[0] == sample_event
    
    def test_clear_history(self, event_manager, sample_event):
        """Test clearing event history."""
        # Store an event
        event_manager._event_history[sample_event.id] = sample_event
        
        # Verify event is in history
        assert len(event_manager._event_history) == 1
        
        # Clear history
        event_manager.clear_history()
        
        # Verify history is empty
        assert len(event_manager._event_history) == 0
    
    def test_get_event_manager(self):
        """Test getting the global event manager."""
        # Reset the global event manager
        import pygovpub.events.event_manager
        pygovpub.events.event_manager._event_manager = None
        
        # Get the event manager
        event_manager1 = get_event_manager()
        event_manager2 = get_event_manager()
        
        # Verify the same instance is returned each time
        assert event_manager1 is event_manager2
        assert isinstance(event_manager1, EventManager)