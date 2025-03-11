"""
Integration tests for real-time update functionality.

These tests verify the real-time update features of PyGovPub, including
event detection, webhook delivery, and data synchronization.
"""

import asyncio
import json
import pytest
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from pygovpub.api.clients.congress import CongressClient
from pygovpub.api.clients.govinfo import GovInfoClient
from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.events.event_manager import EventManager, get_event_manager
from pygovpub.events.event_types import (
    Event, EventCategory, EventType, EventPayload,
    FloorUpdatePayload, BillUpdatePayload, DocumentPublishedPayload
)
from pygovpub.webhooks.manager import (
    WebhookManager, get_webhook_manager,
    WebhookStatus, WebhookDeliveryStatus,
    Webhook, WebhookDelivery, WebhookDispatcher
)
from pygovpub.sync.manager import SyncManager, get_sync_manager, SyncStatus


class TestRealTimeUpdates:
    """Integration tests for real-time update features."""
    
    @pytest.fixture
    def event_payload(self):
        """Create a test event payload."""
        return EventPayload(
            source=ApiSource.CONGRESS,
            source_id="bill/117/hr1234",
            source_url="https://api.congress.gov/v3/bill/117/hr/1234",
            resource_type="bill",
            data={
                "congress": 117,
                "type": "hr",
                "number": 1234,
                "title": "Test Bill",
                "introducedDate": "2023-03-15",
                "sponsors": [
                    {"bioguideId": "A000000", "fullName": "Rep. Test", "state": "XX"}
                ],
                "actions": [
                    {"actionDate": "2023-03-15", "text": "Introduced in House"}
                ]
            }
        )
    
    @pytest.fixture
    def event_manager(self):
        """Create an event manager."""
        manager = EventManager()
        # Clear any existing events
        manager._event_history = {}
        manager._subscribers = {}
        manager._category_subscribers = {}
        manager._global_subscribers = []
        return manager
    
    @pytest.fixture
    def webhook_manager(self):
        """Create a webhook manager."""
        with patch('pygovpub.webhooks.manager.get_event_manager'):
            manager = WebhookManager()
            # Clear any existing webhooks/deliveries
            manager._webhooks = {}
            manager._deliveries = {}
            manager._webhook_events = {}
            return manager
    
    @pytest.fixture
    def sync_manager(self, event_manager):
        """Create a sync manager."""
        with patch('pygovpub.sync.manager.get_event_manager', return_value=event_manager):
            manager = SyncManager()
            # Clear any existing data
            manager._sync_history = {}
            manager._entity_tracker._entities = {}
            return manager
    
    @pytest.fixture
    def mock_auth_manager(self):
        """Create a mock auth manager."""
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.execute_request = AsyncMock()
        return auth_manager
    
    @pytest.fixture
    def congress_client(self, mock_auth_manager, event_manager):
        """Create a Congress.gov API client."""
        client = CongressClient(auth_manager=mock_auth_manager)
        client._event_manager = event_manager
        return client
    
    @pytest.fixture
    def govinfo_client(self, mock_auth_manager, event_manager):
        """Create a GovInfo.gov API client."""
        client = GovInfoClient(auth_manager=mock_auth_manager)
        client._event_manager = event_manager
        return client
    
    @pytest.fixture
    def webhook_dispatcher(self, webhook_manager):
        """Create a webhook dispatcher."""
        dispatcher = WebhookDispatcher(webhook_manager)
        dispatcher.client = AsyncMock()
        # Mock the client response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        dispatcher.client.post.return_value = mock_response
        return dispatcher
    
    @pytest.fixture
    def active_webhook(self, webhook_manager):
        """Create an active webhook subscription."""
        webhook = webhook_manager.register_webhook(
            url="https://example.com/webhook",
            event_types=[EventType.BILL_INTRODUCED, EventType.BILL_STATUS_CHANGE]
        )
        webhook.status = WebhookStatus.ACTIVE
        webhook_manager._save_webhook(webhook)
        return webhook
    
    async def test_event_detection_to_dispatch(self, event_manager, webhook_manager, 
                                          webhook_dispatcher, active_webhook, 
                                          congress_client, event_payload):
        """Test complete flow from event detection to webhook dispatch."""
        # Link the webhook manager to our event manager
        webhook_manager._event_manager = event_manager
        
        # Create a bill introduced event
        event = Event(
            event_type=EventType.BILL_INTRODUCED,
            category=EventCategory.BILL_UPDATE,
            payload=event_payload
        )
        
        # Setup a tracking list to capture events being processed
        events_received = []
        
        # Define a subscriber for the webhook manager
        async def webhook_subscriber(event):
            events_received.append(event)
            # We'll manually trigger the dispatcher since we're mocking
            await webhook_dispatcher.dispatch(event)
        
        # Subscribe the webhook manager to bill events
        event_manager.subscribe(webhook_subscriber, category=EventCategory.BILL_UPDATE)
        
        # Emit the event
        await event_manager.emit_event(event)
        
        # Verify event was received by the webhook subscriber
        assert len(events_received) == 1
        assert events_received[0].event_type == EventType.BILL_INTRODUCED
        
        # Verify a delivery was created for our webhook
        deliveries = webhook_manager.list_deliveries()
        assert len(deliveries) == 1
        assert deliveries[0].webhook_id == active_webhook.id
        assert deliveries[0].event_id == event.id
        
        # Verify the webhook dispatcher actually tried to send it
        webhook_dispatcher.client.post.assert_called_once()
        call_args = webhook_dispatcher.client.post.call_args
        assert str(call_args[0][0]) == "https://example.com/webhook"
        
        # Verify the webhook was updated with delivery information
        updated_webhook = webhook_manager.get_webhook(active_webhook.id)
        assert updated_webhook.last_delivery_at is not None
    
    async def test_api_update_to_event_generation(self, congress_client, event_manager):
        """Test API update detection generating events."""
        # Mock Congress API returning floor update data
        mock_floor_updates = {
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
                    "text": "Consideration of HR 1234, Test Bill",
                    "url": "https://www.congress.gov/floor-updates/house"
                }
            ]
        }
        congress_client.auth_manager.execute_request.return_value = mock_floor_updates
        
        # Track events that are emitted
        events_emitted = []
        
        async def track_event(event):
            events_emitted.append(event)
        
        # Subscribe to floor update events
        event_manager.subscribe(track_event, category=EventCategory.FLOOR_UPDATE)
        
        # Call the floor updates endpoint
        updates = await congress_client.get_floor_updates(chamber="house")
        
        # Verify floor updates were returned
        assert len(updates) == 2
        
        # Verify events were generated
        assert len(events_emitted) == 2
        assert events_emitted[0].event_type == EventType.FLOOR_PROCEEDINGS_UPDATE
        assert events_emitted[0].category == EventCategory.FLOOR_UPDATE
        assert events_emitted[0].payload.source == ApiSource.CONGRESS
        
        # Verify the payload content
        assert isinstance(events_emitted[0].payload, FloorUpdatePayload)
        assert "House" in events_emitted[0].payload.chamber.upper()
        assert "met at 10:00" in events_emitted[0].payload.description
    
    async def test_data_sync_on_cross_source_updates(self, event_manager, sync_manager, 
                                                congress_client, govinfo_client):
        """Test data synchronization on updates from multiple sources."""
        # Mock the entity tracker so we can verify it's called
        original_track_update = sync_manager._entity_tracker.track_update
        sync_manager._entity_tracker.track_update = AsyncMock(wraps=original_track_update)
        
        # Create and emit a bill event from Congress.gov
        bill_data = {
            "congress": 117,
            "type": "hr",
            "number": 1234,
            "title": "Test Bill",
            "introducedDate": "2023-03-15"
        }
        
        await congress_client._emit_bill_event(
            event_type=EventType.BILL_INTRODUCED,
            bill_data=bill_data
        )
        
        # Verify entity tracking was called
        sync_manager._entity_tracker.track_update.assert_called_once()
        first_call_args = sync_manager._entity_tracker.track_update.call_args[1]
        assert first_call_args["entity_type"] == "bill"
        assert first_call_args["entity_id"] == "117hr1234"
        assert first_call_args["source"] == ApiSource.CONGRESS
        
        # Reset the mock
        sync_manager._entity_tracker.track_update.reset_mock()
        
        # Create and emit a document event from GovInfo.gov
        document_data = {
            "packageId": "BILLS-117hr1234ih",
            "title": "Test Bill",
            "congress": "117",
            "dateIssued": "2023-03-15",
            "category": "Bills",
            "docClass": "hr",
            "docNumber": "1234"
        }
        
        doc_payload = DocumentPublishedPayload(
            event_time=datetime.utcnow(),
            source=ApiSource.GOVINFO,
            source_id=f"document/{document_data['packageId']}",
            source_url=f"https://api.govinfo.gov/packages/{document_data['packageId']}",
            resource_type="bill_document",
            document_id=document_data["packageId"],
            document_type="bill",
            title=document_data["title"],
            data=document_data
        )
        
        # Emit document event
        await event_manager.create_and_emit_event(
            event_type=EventType.DOCUMENT_PUBLISHED,
            payload=doc_payload
        )
        
        # Verify entity tracking was called again
        sync_manager._entity_tracker.track_update.assert_called_once()
        second_call_args = sync_manager._entity_tracker.track_update.call_args[1]
        assert second_call_args["entity_type"] == "document"
        assert second_call_args["entity_id"] == "BILLS-117hr1234ih"
        assert second_call_args["source"] == ApiSource.GOVINFO
        
        # Verify synchronization is recorded in history - we need to give the async
        # consistency checks a moment to complete
        await asyncio.sleep(0.1)
        
        # Verify there's a sync record
        sync_records = list(sync_manager._sync_history.values())
        assert len(sync_records) >= 1
        
        # Find the record for our bill entity
        bill_syncs = [r for r in sync_records if r["entity_type"] == "bill" and r["entity_id"] == "117hr1234"]
        assert len(bill_syncs) >= 1
        
        # Verify sources are tracked in the sync record
        assert len(bill_syncs[0]["sources"]) == 2
        assert ApiSource.CONGRESS in bill_syncs[0]["sources"]
        assert ApiSource.GOVINFO in bill_syncs[0]["sources"]
    
    async def test_webhook_batched_delivery(self, event_manager, webhook_manager, 
                                       webhook_dispatcher, active_webhook):
        """Test webhook delivery batching multiple events."""
        # Setup mock for tracking HTTP requests
        webhook_dispatcher.client.post.reset_mock()
        
        # Generate multiple events in rapid succession
        events = []
        for i in range(3):
            payload = EventPayload(
                source=ApiSource.CONGRESS,
                source_id=f"bill/117/hr{1234+i}",
                source_url=f"https://api.congress.gov/v3/bill/117/hr/{1234+i}",
                resource_type="bill",
                data={
                    "congress": 117,
                    "type": "hr",
                    "number": 1234 + i,
                    "title": f"Test Bill {i+1}"
                }
            )
            
            event = Event(
                event_type=EventType.BILL_INTRODUCED,
                category=EventCategory.BILL_UPDATE,
                payload=payload
            )
            events.append(event)
        
        # Setup a tracking list to capture events being processed
        events_received = []
        
        # Define a subscriber for the webhook manager
        async def webhook_subscriber(event):
            events_received.append(event)
            # We'll manually trigger the dispatcher
            await webhook_dispatcher.dispatch(event)
        
        # Subscribe the webhook manager to bill events
        event_manager.subscribe(webhook_subscriber, category=EventCategory.BILL_UPDATE)
        
        # Emit all events
        for event in events:
            await event_manager.emit_event(event)
        
        # Verify all events were received by the webhook subscriber
        assert len(events_received) == 3
        
        # Verify deliveries were created for our webhook
        deliveries = webhook_manager.list_deliveries()
        assert len(deliveries) == 3
        
        # Verify the webhook dispatcher made HTTP calls
        assert webhook_dispatcher.client.post.call_count == 3
        
        # Verify the webhook was updated with delivery information
        updated_webhook = webhook_manager.get_webhook(active_webhook.id)
        assert updated_webhook.last_delivery_at is not None
    
    async def test_failed_webhook_retry(self, event_manager, webhook_manager, 
                                   webhook_dispatcher, active_webhook, event_payload):
        """Test webhook delivery retry on failure."""
        # Setup mock to simulate HTTP failure then success
        mock_fail_response = MagicMock()
        mock_fail_response.status_code = 500
        mock_fail_response.text = "Internal Server Error"
        
        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.text = "OK"
        
        # Make the first call fail, second call succeed
        webhook_dispatcher.client.post.side_effect = [mock_fail_response, mock_success_response]
        
        # Create an event
        event = Event(
            event_type=EventType.BILL_INTRODUCED,
            category=EventCategory.BILL_UPDATE,
            payload=event_payload
        )
        
        # Setup webhook subscriber
        async def webhook_subscriber(event):
            await webhook_dispatcher.dispatch(event)
        
        # Subscribe to events
        event_manager.subscribe(webhook_subscriber, category=EventCategory.BILL_UPDATE)
        
        # Emit the event (first delivery will fail)
        await event_manager.emit_event(event)
        
        # Verify a delivery was created and marked for retry
        deliveries = webhook_manager.list_deliveries()
        assert len(deliveries) == 1
        assert deliveries[0].status == WebhookDeliveryStatus.RETRYING
        assert deliveries[0].attempt_count == 1
        assert deliveries[0].response_code == 500
        
        # Now simulate retry
        await webhook_dispatcher._retry_delivery(deliveries[0])
        
        # Verify the delivery was successful after retry
        updated_delivery = webhook_manager.get_delivery(deliveries[0].id)
        assert updated_delivery.status == WebhookDeliveryStatus.SUCCESS
        assert updated_delivery.attempt_count == 2
        assert updated_delivery.response_code == 200
        
        # Verify the webhook state was updated
        updated_webhook = webhook_manager.get_webhook(active_webhook.id)
        assert updated_webhook.failure_count == 0  # Reset on success
        
        # Verify two HTTP calls were made
        assert webhook_dispatcher.client.post.call_count == 2


async def test_end_to_end_update_flow(event_manager, sync_manager, webhook_manager, webhook_dispatcher):
    """Test the full end-to-end update flow."""
    # Setup managers
    webhook_manager._event_manager = event_manager  
    sync_manager._event_manager = event_manager
    
    # Create active webhook
    webhook = webhook_manager.register_webhook(
        url="https://example.com/webhook",
        event_types=[EventType.BILL_INTRODUCED, EventType.DOCUMENT_PUBLISHED]
    )
    webhook.status = WebhookStatus.ACTIVE
    webhook_manager._save_webhook(webhook)
    
    # Create webhook subscriber
    async def webhook_subscriber(event):
        await webhook_dispatcher.dispatch(event)
    
    # Subscribe to relevant event categories
    event_manager.subscribe(webhook_subscriber, category=EventCategory.BILL_UPDATE)
    event_manager.subscribe(webhook_subscriber, category=EventCategory.DOCUMENT_UPDATE)
    
    # Create bill introduced event
    bill_payload = EventPayload(
        event_time=datetime.utcnow(),
        source=ApiSource.CONGRESS,
        source_id="bill/117/hr5000",
        source_url="https://api.congress.gov/v3/bill/117/hr/5000",
        resource_type="bill",
        data={
            "congress": 117,
            "type": "hr",
            "number": 5000,
            "title": "End-to-End Test Bill",
            "introducedDate": "2023-03-20"
        }
    )
    
    # Emit bill event
    await event_manager.create_and_emit_event(
        event_type=EventType.BILL_INTRODUCED,
        payload=bill_payload
    )
    
    # Create document published event
    doc_payload = DocumentPublishedPayload(
        event_time=datetime.utcnow(),
        source=ApiSource.GOVINFO,
        source_id="document/BILLS-117hr5000ih",
        source_url="https://api.govinfo.gov/packages/BILLS-117hr5000ih",
        resource_type="bill_document",
        document_id="BILLS-117hr5000ih",
        document_type="bill",
        title="End-to-End Test Bill",
        related_bills=["117hr5000"],
        data={
            "packageId": "BILLS-117hr5000ih",
            "title": "End-to-End Test Bill",
            "congress": "117",
            "docNumber": "5000"
        }
    )
    
    # Emit document event
    await event_manager.create_and_emit_event(
        event_type=EventType.DOCUMENT_PUBLISHED,
        payload=doc_payload
    )
    
    # Give sync manager time to process the events
    await asyncio.sleep(0.1)
    
    # Verify webhook deliveries
    deliveries = webhook_manager.list_deliveries()
    assert len(deliveries) == 2  # One for each event
    
    # Verify entities were tracked and synchronized
    bill_entity_id = "117hr5000"
    doc_entity_id = "BILLS-117hr5000ih"
    
    bill_updates = await sync_manager._entity_tracker.get_updates("bill", bill_entity_id)
    doc_updates = await sync_manager._entity_tracker.get_updates("document", doc_entity_id)
    
    assert len(bill_updates) == 1
    assert len(doc_updates) == 1
    assert bill_updates[0]["source"] == ApiSource.CONGRESS
    assert doc_updates[0]["source"] == ApiSource.GOVINFO
    
    # Verify sync record exists
    sync_records = list(sync_manager._sync_history.values())
    assert len(sync_records) >= 1
    
    # Find the bill entity record
    bill_syncs = [r for r in sync_records if r["entity_id"] == bill_entity_id]
    assert len(bill_syncs) >= 1
    assert bill_syncs[0]["status"] == SyncStatus.COMPLETED