"""
Webhooks API Router.

This module provides FastAPI routes for webhook management and event subscriptions.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, Request
from pydantic import BaseModel, Field, AnyHttpUrl, validator

from pygovpub.api.router import ApiRouter
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError

# Define the API router dependency (will be registered from app.py later)
def get_api_router():
    """Get API router.
    
    This is a dependency function that will be overridden by app.py.
    """
    raise NotImplementedError("get_api_router not registered - this is a placeholder")

# Configure logging
logger = logging.getLogger("pygovpub.api.routers.webhooks")

# Create router
router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
    responses={
        404: {"description": "Not found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source unavailable"}
    }
)


# Models for webhook management
class EventType(BaseModel):
    """Event type model."""
    
    event_type: str = Field(..., description="Event type (e.g., bill.introduced, bill.updated)")
    description: str = Field(..., description="Description of the event type")
    example_payload: Dict[str, Any] = Field({}, description="Example payload for this event type")


class WebhookSubscription(BaseModel):
    """Webhook subscription model."""
    
    id: UUID = Field(default_factory=uuid4, description="Unique identifier for the subscription")
    url: AnyHttpUrl = Field(..., description="URL to send webhook events to")
    event_types: List[str] = Field(..., description="List of event types to subscribe to")
    created_at: datetime = Field(default_factory=datetime.now, description="When subscription was created")
    updated_at: Optional[datetime] = Field(None, description="When subscription was last updated")
    is_active: bool = Field(True, description="Whether the subscription is active")
    secret: Optional[str] = Field(None, description="Secret for signing webhook payloads")
    description: Optional[str] = Field(None, description="Description of the subscription")
    
    @validator('event_types')
    def validate_event_types(cls, v):
        """Validate event types."""
        valid_types = [
            "bill.introduced",
            "bill.updated",
            "bill.action",
            "committee.hearing",
            "committee.report",
            "member.update",
            "fr.document"
        ]
        for event_type in v:
            if event_type not in valid_types:
                raise ValueError(f"Invalid event type: {event_type}. Must be one of: {', '.join(valid_types)}")
        return v


class WebhookSubscriptionCreate(BaseModel):
    """Webhook subscription creation model."""
    
    url: AnyHttpUrl = Field(..., description="URL to send webhook events to")
    event_types: List[str] = Field(..., description="List of event types to subscribe to")
    secret: Optional[str] = Field(None, description="Secret for signing webhook payloads")
    description: Optional[str] = Field(None, description="Description of the subscription")


class WebhookSubscriptionUpdate(BaseModel):
    """Webhook subscription update model."""
    
    url: Optional[AnyHttpUrl] = Field(None, description="URL to send webhook events to")
    event_types: Optional[List[str]] = Field(None, description="List of event types to subscribe to")
    is_active: Optional[bool] = Field(None, description="Whether the subscription is active")
    secret: Optional[str] = Field(None, description="Secret for signing webhook payloads")
    description: Optional[str] = Field(None, description="Description of the subscription")


class WebhookSubscriptionList(BaseModel):
    """Webhook subscription list model."""
    
    subscriptions: List[WebhookSubscription] = Field(..., description="List of webhook subscriptions")
    count: int = Field(..., description="Total count of webhook subscriptions")


class WebhookDelivery(BaseModel):
    """Webhook delivery model."""
    
    id: UUID = Field(default_factory=uuid4, description="Unique identifier for the delivery")
    subscription_id: UUID = Field(..., description="Subscription ID")
    event_type: str = Field(..., description="Event type")
    payload: Dict[str, Any] = Field(..., description="Payload that was sent")
    status: str = Field(..., description="Delivery status (success, failed)")
    status_code: Optional[int] = Field(None, description="HTTP status code from webhook target")
    response: Optional[str] = Field(None, description="Response from webhook target")
    created_at: datetime = Field(default_factory=datetime.now, description="When delivery was made")
    error: Optional[str] = Field(None, description="Error message if delivery failed")


class WebhookDeliveryList(BaseModel):
    """Webhook delivery list model."""
    
    deliveries: List[WebhookDelivery] = Field(..., description="List of webhook deliveries")
    count: int = Field(..., description="Total count of webhook deliveries")


@router.get("/event-types", response_model=List[EventType])
async def list_event_types() -> List[EventType]:
    """List event types.
    
    Returns a list of available event types for webhook subscriptions.
    
    Returns:
        List of event types
    """
    event_types = [
        EventType(
            event_type="bill.introduced",
            description="Triggered when a new bill is introduced",
            example_payload={
                "event_type": "bill.introduced",
                "bill_id": "hr1234-117",
                "title": "Example Bill",
                "introduced_date": "2023-01-01",
                "source_url": "https://www.congress.gov/bill/117th-congress/house-bill/1234"
            }
        ),
        EventType(
            event_type="bill.updated",
            description="Triggered when a bill is updated",
            example_payload={
                "event_type": "bill.updated",
                "bill_id": "hr1234-117",
                "title": "Example Bill",
                "update_type": "text",
                "updated_date": "2023-01-15",
                "source_url": "https://www.congress.gov/bill/117th-congress/house-bill/1234"
            }
        ),
        EventType(
            event_type="bill.action",
            description="Triggered when a bill has a new action",
            example_payload={
                "event_type": "bill.action",
                "bill_id": "hr1234-117",
                "title": "Example Bill",
                "action_date": "2023-01-10",
                "action_text": "Referred to Committee on Example",
                "source_url": "https://www.congress.gov/bill/117th-congress/house-bill/1234"
            }
        ),
        EventType(
            event_type="committee.hearing",
            description="Triggered when a committee schedules a hearing",
            example_payload={
                "event_type": "committee.hearing",
                "committee_id": "HSXX",
                "committee_name": "Example Committee",
                "hearing_date": "2023-02-01",
                "title": "Example Hearing",
                "source_url": "https://www.congress.gov/committee/example-committee/HSXX"
            }
        ),
        EventType(
            event_type="fr.document",
            description="Triggered when a new Federal Register document is published",
            example_payload={
                "event_type": "fr.document",
                "document_id": "2023-12345",
                "title": "Example FR Document",
                "publication_date": "2023-01-20",
                "source_url": "https://www.federalregister.gov/documents/2023/01/20/2023-12345/example-fr-document"
            }
        )
    ]
    
    return event_types


@router.post("/subscriptions", response_model=WebhookSubscription, status_code=201)
async def create_subscription(
    subscription: WebhookSubscriptionCreate = Body(...),
    request: Request = None
) -> WebhookSubscription:
    """Create a webhook subscription.
    
    Creates a new webhook subscription for receiving event notifications.
    
    Args:
        subscription: Subscription details
    
    Returns:
        Created subscription
    """
    # In a real implementation, this would store the subscription in a database
    # For now, we'll just return a mock response
    
    new_subscription = WebhookSubscription(
        url=subscription.url,
        event_types=subscription.event_types,
        secret=subscription.secret,
        description=subscription.description
    )
    
    logger.info(f"Created webhook subscription: {new_subscription.id}")
    
    return new_subscription


@router.get("/subscriptions", response_model=WebhookSubscriptionList)
async def list_subscriptions(
    offset: int = Query(0, description="Offset for pagination"),
    limit: int = Query(20, description="Maximum number of subscriptions to return"),
    event_type: Optional[str] = Query(None, description="Filter by event type")
) -> WebhookSubscriptionList:
    """List webhook subscriptions.
    
    Returns a list of webhook subscriptions with pagination.
    
    Args:
        offset: Offset for pagination
        limit: Maximum number of subscriptions to return
        event_type: Filter by event type
    
    Returns:
        List of webhook subscriptions
    """
    # Mock response for now
    return WebhookSubscriptionList(
        subscriptions=[
            WebhookSubscription(
                id=uuid4(),
                url="https://example.com/webhook",
                event_types=["bill.introduced", "bill.updated"],
                created_at=datetime.now(),
                is_active=True,
                description="Example subscription"
            )
        ],
        count=1
    )


@router.get("/subscriptions/{subscription_id}", response_model=WebhookSubscription)
async def get_subscription(
    subscription_id: UUID = Path(..., description="Subscription ID")
) -> WebhookSubscription:
    """Get webhook subscription.
    
    Returns details about a specific webhook subscription.
    
    Args:
        subscription_id: Subscription ID
    
    Returns:
        Webhook subscription details
    
    Raises:
        HTTPException: If subscription not found
    """
    # In a real implementation, this would retrieve the subscription from a database
    # For now, return a mock response
    
    # Simulate not found for an invalid UUID
    if str(subscription_id) == "00000000-0000-0000-0000-000000000000":
        raise HTTPException(
            status_code=404,
            detail=f"Subscription not found: {subscription_id}"
        )
    
    return WebhookSubscription(
        id=subscription_id,
        url="https://example.com/webhook",
        event_types=["bill.introduced", "bill.updated"],
        created_at=datetime.now(),
        is_active=True,
        description="Example subscription"
    )


@router.patch("/subscriptions/{subscription_id}", response_model=WebhookSubscription)
async def update_subscription(
    subscription_id: UUID = Path(..., description="Subscription ID"),
    update: WebhookSubscriptionUpdate = Body(...)
) -> WebhookSubscription:
    """Update webhook subscription.
    
    Updates an existing webhook subscription.
    
    Args:
        subscription_id: Subscription ID
        update: Subscription update details
    
    Returns:
        Updated subscription
    
    Raises:
        HTTPException: If subscription not found
    """
    # Simulate not found for an invalid UUID
    if str(subscription_id) == "00000000-0000-0000-0000-000000000000":
        raise HTTPException(
            status_code=404,
            detail=f"Subscription not found: {subscription_id}"
        )
    
    # Mock response
    return WebhookSubscription(
        id=subscription_id,
        url=update.url or "https://example.com/webhook-updated",
        event_types=update.event_types or ["bill.introduced", "bill.updated", "bill.action"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        is_active=update.is_active if update.is_active is not None else True,
        secret=update.secret,
        description=update.description or "Updated example subscription"
    )


@router.delete("/subscriptions/{subscription_id}", status_code=204)
async def delete_subscription(
    subscription_id: UUID = Path(..., description="Subscription ID")
) -> None:
    """Delete webhook subscription.
    
    Deletes a webhook subscription.
    
    Args:
        subscription_id: Subscription ID
    
    Raises:
        HTTPException: If subscription not found
    """
    # Simulate not found for an invalid UUID
    if str(subscription_id) == "00000000-0000-0000-0000-000000000000":
        raise HTTPException(
            status_code=404,
            detail=f"Subscription not found: {subscription_id}"
        )
    
    # In a real implementation, this would delete the subscription from a database
    logger.info(f"Deleted webhook subscription: {subscription_id}")
    
    # No content response


@router.get("/deliveries", response_model=WebhookDeliveryList)
async def list_deliveries(
    subscription_id: Optional[UUID] = Query(None, description="Filter by subscription ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    status: Optional[str] = Query(None, description="Filter by status (success, failed)"),
    offset: int = Query(0, description="Offset for pagination"),
    limit: int = Query(20, description="Maximum number of deliveries to return")
) -> WebhookDeliveryList:
    """List webhook deliveries.
    
    Returns a list of webhook delivery attempts with pagination.
    
    Args:
        subscription_id: Filter by subscription ID
        event_type: Filter by event type
        status: Filter by status (success, failed)
        offset: Offset for pagination
        limit: Maximum number of deliveries to return
    
    Returns:
        List of webhook deliveries
    """
    # Mock response
    return WebhookDeliveryList(
        deliveries=[
            WebhookDelivery(
                id=uuid4(),
                subscription_id=subscription_id or uuid4(),
                event_type="bill.introduced",
                payload={
                    "event_type": "bill.introduced",
                    "bill_id": "hr1234-117",
                    "title": "Example Bill"
                },
                status="success",
                status_code=200,
                response="OK",
                created_at=datetime.now()
            )
        ],
        count=1
    )


@router.get("/deliveries/{delivery_id}", response_model=WebhookDelivery)
async def get_delivery(
    delivery_id: UUID = Path(..., description="Delivery ID")
) -> WebhookDelivery:
    """Get webhook delivery.
    
    Returns details about a specific webhook delivery attempt.
    
    Args:
        delivery_id: Delivery ID
    
    Returns:
        Webhook delivery details
    
    Raises:
        HTTPException: If delivery not found
    """
    # Simulate not found for an invalid UUID
    if str(delivery_id) == "00000000-0000-0000-0000-000000000000":
        raise HTTPException(
            status_code=404,
            detail=f"Delivery not found: {delivery_id}"
        )
    
    # Mock response
    return WebhookDelivery(
        id=delivery_id,
        subscription_id=uuid4(),
        event_type="bill.introduced",
        payload={
            "event_type": "bill.introduced",
            "bill_id": "hr1234-117",
            "title": "Example Bill"
        },
        status="success",
        status_code=200,
        response="OK",
        created_at=datetime.now()
    )


@router.post("/test", status_code=202)
async def send_test_webhook(
    event_type: str = Body(..., embed=True),
    payload: Dict[str, Any] = Body({}, embed=True),
    subscription_id: Optional[UUID] = Body(None, embed=True)
) -> Dict[str, Any]:
    """Send test webhook.
    
    Sends a test webhook event to the specified subscription.
    
    Args:
        event_type: Event type to send
        payload: Custom payload (optional)
        subscription_id: Subscription ID (optional, if not provided, sends to all active subscriptions)
    
    Returns:
        Test result
    """
    # In a real implementation, this would validate the event type and send a test webhook
    logger.info(f"Sending test webhook: {event_type}")
    
    # Simulate processing
    return {
        "status": "accepted",
        "message": "Test webhook queued for delivery",
        "event_type": event_type,
        "subscription_id": subscription_id
    }