"""
Tests for event dispatchers.

This module tests the event dispatcher base class and its functionality.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import uuid

from pygovpub.auth.models import ApiSource
from pygovpub.events.dispatchers.base import EventDispatcherBase
from pygovpub.events.event_types import (
    Event, EventCategory, EventType, EventPayload
)


class TestEventDispatcher(EventDispatcherBase):
    """Test implementation of EventDispatcherBase."""
    
    def __init__(self, name="test_dispatcher", should_fail=False):
        """Initialize test dispatcher.
        
        Args:
            name: Dispatcher name
            should_fail: Whether dispatch should fail
        """
        super().__init__(name)
        self.dispatched_events = []
        self.should_fail = should_fail
        
    async def dispatch(self, event: Event) -> bool:
        """Implement abstract dispatch method.
        
        Args:
            event: Event to dispatch
            
        Returns:
            True if dispatch succeeded, False otherwise
        """
        self.dispatched_events.append(event)
        
        if self.should_fail:
            error = "Test dispatch failure"
            self.record_dispatch_attempt(event, False, error)
            return False
        
        # Simulate successful dispatch
        self.record_dispatch_attempt(event, True)
        return True


class TestEventDispatcherBase:
    """Tests for the event dispatcher base class."""
    
    @pytest.fixture
    def sample_event(self):
        """Create a sample event for testing."""
        payload = EventPayload(
            source=ApiSource.CONGRESS,
            source_id="123",
            resource_type="bill"
        )
        return Event(
            event_type=EventType.BILL_INTRODUCED,
            category=EventCategory.BILL_UPDATE,
            payload=payload
        )
    
    @pytest.fixture
    def dispatcher(self):
        """Create a test dispatcher."""
        return TestEventDispatcher()
    
    @pytest.fixture
    def failing_dispatcher(self):
        """Create a test dispatcher that fails."""
        return TestEventDispatcher(name="failing_dispatcher", should_fail=True)
        
    async def test_successful_dispatch(self, dispatcher, sample_event):
        """Test successful event dispatch."""
        # Dispatch the event
        result = await dispatcher.dispatch(sample_event)
        
        # Verify dispatch succeeded
        assert result is True
        assert len(dispatcher.dispatched_events) == 1
        assert dispatcher.dispatched_events[0] == sample_event
        
        # Verify dispatch was recorded
        history = dispatcher.get_dispatch_history(str(sample_event.id))
        assert history is not None
        assert history["success"] is True
        assert history["attempts"] == 1
        assert history["errors"] == []
        
        # Verify event was updated
        assert sample_event.delivered_at is not None
        assert sample_event.delivery_attempts == 0  # Not incremented on success
    
    async def test_failed_dispatch(self, failing_dispatcher, sample_event):
        """Test failed event dispatch."""
        # Dispatch the event
        result = await failing_dispatcher.dispatch(sample_event)
        
        # Verify dispatch failed
        assert result is False
        assert len(failing_dispatcher.dispatched_events) == 1
        assert failing_dispatcher.dispatched_events[0] == sample_event
        
        # Verify dispatch was recorded
        history = failing_dispatcher.get_dispatch_history(str(sample_event.id))
        assert history is not None
        assert history["success"] is False
        assert history["attempts"] == 1
        assert len(history["errors"]) == 1
        assert history["errors"][0]["message"] == "Test dispatch failure"
        
        # Verify event was updated
        assert sample_event.delivered_at is None
        assert sample_event.delivery_attempts == 1
        assert sample_event.last_delivery_attempt is not None
        assert sample_event.error_message == "Test dispatch failure"
    
    async def test_multiple_dispatch_attempts(self, failing_dispatcher, sample_event):
        """Test multiple dispatch attempts."""
        # Attempt dispatch twice
        await failing_dispatcher.dispatch(sample_event)
        await failing_dispatcher.dispatch(sample_event)
        
        # Verify dispatch was recorded properly
        history = failing_dispatcher.get_dispatch_history(str(sample_event.id))
        assert history is not None
        assert history["success"] is False
        assert history["attempts"] == 2
        assert len(history["errors"]) == 2
        
        # Verify event was updated
        assert sample_event.delivery_attempts == 2
    
    def test_record_dispatch_attempt(self, dispatcher, sample_event):
        """Test recording a dispatch attempt."""
        # Record a success
        dispatcher.record_dispatch_attempt(sample_event, True)
        
        # Verify success was recorded
        history = dispatcher.get_dispatch_history(str(sample_event.id))
        assert history is not None
        assert history["success"] is True
        assert history["attempts"] == 1
        assert "last_attempt" in history
        
        # Record a failure with error
        dispatcher.record_dispatch_attempt(sample_event, False, "Test error")
        
        # Verify failure was recorded
        history = dispatcher.get_dispatch_history(str(sample_event.id))
        assert history["success"] is False
        assert history["attempts"] == 2
        assert len(history["errors"]) == 1
        assert history["errors"][0]["message"] == "Test error"
    
    def test_get_dispatch_history(self, dispatcher, sample_event):
        """Test getting dispatch history for an event."""
        # Record a dispatch attempt
        dispatcher.record_dispatch_attempt(sample_event, True)
        
        # Get history for the event
        history = dispatcher.get_dispatch_history(str(sample_event.id))
        
        # Verify history is returned
        assert history is not None
        assert history["event_type"] == sample_event.event_type.value
        assert history["attempts"] == 1
        assert history["success"] is True
        
        # Test for non-existent event
        assert dispatcher.get_dispatch_history("nonexistent") is None
    
    async def test_dispatcher_logs_events(self, dispatcher, sample_event):
        """Test that dispatcher logs events properly."""
        # Mock the logger
        with patch('pygovpub.events.dispatchers.base.logger') as mock_logger:
            # Dispatch the event
            await dispatcher.dispatch(sample_event)
            
            # Verify log was created
            mock_logger.debug.assert_called_with(
                f"Dispatch attempt for event {sample_event.id} via test_dispatcher: success"
            )
    
    async def test_dispatcher_records_event_changes(self, dispatcher, sample_event):
        """Test that dispatcher records changes to event state."""
        # Store the initial state
        initial_delivery_attempts = sample_event.delivery_attempts
        initial_delivered_at = sample_event.delivered_at
        
        # Dispatch the event
        await dispatcher.dispatch(sample_event)
        
        # Verify event state was changed
        assert sample_event.delivery_attempts == initial_delivery_attempts  # Not incremented on success
        assert sample_event.delivered_at is not None
        assert sample_event.delivered_at != initial_delivered_at