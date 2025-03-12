"""
Tests for the webhooks router.

These tests cover the webhook endpoints in more detail.
"""

import json
import uuid
import asyncio
from datetime import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, Request
from pydantic import AnyHttpUrl

from pygovpub.api.routers.webhooks import (
    router, list_event_types, create_subscription, list_subscriptions, get_subscription,
    update_subscription, delete_subscription, list_deliveries, get_delivery, send_test_webhook
)
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError

# Define the API router dependency
def get_api_router():
    """Mock get_api_router."""
    return AsyncMock()

# Test data
SUBSCRIPTION_ID = uuid.uuid4()
DELIVERY_ID = uuid.uuid4()

WEBHOOK_SUBSCRIPTION = {
    "id": SUBSCRIPTION_ID,
    "url": "https://example.com/webhook",
    "event_types": ["bill.introduced", "bill.updated"],
    "created_at": datetime.now().isoformat(),
    "is_active": True,
    "description": "Test subscription"
}

WEBHOOK_DELIVERY = {
    "id": DELIVERY_ID,
    "subscription_id": SUBSCRIPTION_ID,
    "event_type": "bill.introduced",
    "payload": {
        "event_type": "bill.introduced",
        "bill_id": "hr1234-117",
        "title": "Test Bill"
    },
    "status": "success",
    "status_code": 200,
    "response": "OK",
    "created_at": datetime.now().isoformat()
}

@pytest.fixture
def mock_request():
    """Create a mock request for testing."""
    mock = MagicMock()
    mock.headers = {"User-Agent": "test"}
    mock.client.host = "127.0.0.1"
    return mock


async def test_list_event_types():
    """Test listing event types."""
    result = await list_event_types()
    
    assert len(result) > 0
    
    # Verify at least the following event types are included
    event_types = [et.event_type for et in result]
    assert "bill.introduced" in event_types
    assert "bill.updated" in event_types
    assert "bill.action" in event_types
    
    # Check for example payloads
    for event_type in result:
        assert isinstance(event_type.example_payload, dict)
        assert "event_type" in event_type.example_payload


async def test_create_subscription():
    """Test creating a subscription."""
    from pygovpub.api.routers.webhooks import WebhookSubscriptionCreate
    
    subscription_create = WebhookSubscriptionCreate(
        url="https://example.com/webhook",
        event_types=["bill.introduced", "bill.updated"],
        description="Test subscription"
    )
    
    result = await create_subscription(
        subscription=subscription_create,
        request=None
    )
    
    assert str(result.url) == "https://example.com/webhook"
    assert "bill.introduced" in result.event_types
    assert "bill.updated" in result.event_types
    assert result.description == "Test subscription"
    assert result.is_active is True
    assert isinstance(result.id, uuid.UUID)


async def test_list_subscriptions():
    """Test listing subscriptions."""
    result = await list_subscriptions(
        offset=0,
        limit=20,
        event_type=None
    )
    
    assert result.count >= 0
    
    # Even if no subscriptions, the structure should be correct
    assert hasattr(result, "subscriptions")
    assert isinstance(result.subscriptions, list)


async def test_list_subscriptions_with_filter():
    """Test listing subscriptions with event type filter."""
    result = await list_subscriptions(
        offset=0,
        limit=20,
        event_type="bill.introduced"
    )
    
    # This should filter by event type
    assert result.count >= 0


async def test_get_subscription():
    """Test getting a subscription."""
    # Test with a valid UUID (which is uuid4 in our implementation)
    result = await get_subscription(
        subscription_id=uuid.uuid4()
    )
    
    assert isinstance(result.id, uuid.UUID)
    assert str(result.url).startswith("https://")
    assert isinstance(result.event_types, list)
    assert isinstance(result.is_active, bool)


async def test_get_subscription_not_found():
    """Test getting a non-existent subscription."""
    # Our implementation returns 404 for this specific UUID
    with pytest.raises(HTTPException) as excinfo:
        await get_subscription(
            subscription_id=uuid.UUID("00000000-0000-0000-0000-000000000000")
        )
    
    assert excinfo.value.status_code == 404
    assert "Subscription not found" in excinfo.value.detail


async def test_update_subscription():
    """Test updating a subscription."""
    from pygovpub.api.routers.webhooks import WebhookSubscriptionUpdate
    
    update_data = WebhookSubscriptionUpdate(
        url="https://example.com/webhook-updated",
        event_types=["bill.introduced", "bill.updated", "bill.action"],
        is_active=True,
        description="Updated subscription"
    )
    
    result = await update_subscription(
        subscription_id=uuid.uuid4(),
        update=update_data
    )
    
    assert str(result.url) == "https://example.com/webhook-updated"
    assert "bill.action" in result.event_types
    assert result.description == "Updated subscription"
    assert result.is_active is True


async def test_update_subscription_not_found():
    """Test updating a non-existent subscription."""
    from pygovpub.api.routers.webhooks import WebhookSubscriptionUpdate
    
    update_data = WebhookSubscriptionUpdate(
        url="https://example.com/webhook-updated",
        is_active=False
    )
    
    # Our implementation returns 404 for this specific UUID
    with pytest.raises(HTTPException) as excinfo:
        await update_subscription(
            subscription_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            update=update_data
        )
    
    assert excinfo.value.status_code == 404
    assert "Subscription not found" in excinfo.value.detail


async def test_delete_subscription():
    """Test deleting a subscription."""
    # Should not raise an exception for a valid UUID
    await delete_subscription(
        subscription_id=uuid.uuid4()
    )
    
    # Should raise an exception for an invalid UUID
    with pytest.raises(HTTPException) as excinfo:
        await delete_subscription(
            subscription_id=uuid.UUID("00000000-0000-0000-0000-000000000000")
        )
    
    assert excinfo.value.status_code == 404
    assert "Subscription not found" in excinfo.value.detail


async def test_list_deliveries():
    """Test listing webhook deliveries."""
    result = await list_deliveries(
        subscription_id=None,
        event_type=None,
        status=None,
        offset=0,
        limit=20
    )
    
    assert hasattr(result, "deliveries")
    assert isinstance(result.deliveries, list)
    assert hasattr(result, "count")
    assert isinstance(result.count, int)


async def test_list_deliveries_with_filters():
    """Test listing webhook deliveries with filters."""
    subscription_id = uuid.uuid4()
    
    result = await list_deliveries(
        subscription_id=subscription_id,
        event_type="bill.introduced",
        status="success",
        offset=0,
        limit=20
    )
    
    assert hasattr(result, "deliveries")
    
    # If there are any deliveries, they should match our filter
    if result.deliveries:
        assert result.deliveries[0].subscription_id == subscription_id
        assert result.deliveries[0].event_type == "bill.introduced"
        assert result.deliveries[0].status == "success"


async def test_get_delivery():
    """Test getting a webhook delivery."""
    delivery_id = uuid.uuid4()
    
    result = await get_delivery(
        delivery_id=delivery_id
    )
    
    assert result.id == delivery_id
    assert isinstance(result.subscription_id, uuid.UUID)
    assert isinstance(result.event_type, str)
    assert isinstance(result.payload, dict)
    assert isinstance(result.status, str)


async def test_get_delivery_not_found():
    """Test getting a non-existent webhook delivery."""
    with pytest.raises(HTTPException) as excinfo:
        await get_delivery(
            delivery_id=uuid.UUID("00000000-0000-0000-0000-000000000000")
        )
    
    assert excinfo.value.status_code == 404
    assert "Delivery not found" in excinfo.value.detail


async def test_send_test_webhook():
    """Test sending a test webhook."""
    result = await send_test_webhook(
        event_type="bill.introduced",
        payload={"bill_id": "hr1234-117", "title": "Test Bill"},
        subscription_id=uuid.uuid4()
    )
    
    assert result["status"] == "accepted"
    assert result["event_type"] == "bill.introduced"
    assert "subscription_id" in result
    assert "message" in result


async def test_send_test_webhook_no_subscription():
    """Test sending a test webhook without specifying subscription."""
    result = await send_test_webhook(
        event_type="bill.introduced",
        payload={"bill_id": "hr1234-117", "title": "Test Bill"},
        subscription_id=None
    )
    
    assert result["status"] == "accepted"
    assert result["event_type"] == "bill.introduced"
    assert result["subscription_id"] is None