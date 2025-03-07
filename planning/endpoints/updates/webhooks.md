# Real-time Updates & Webhooks API

## Overview

The Real-time Updates & Webhooks API enables clients to receive immediate notifications about changes in legislative data from both Congress.gov and GovInfo.gov. This endpoint manages webhook subscriptions, event filtering, and delivery of real-time updates for bills, amendments, committee activities, and document authentications.

## Models

### Core Models

```python
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship
from pydantic import validator, constr, UUID4
from .base import BaseModel
from .errors import WebhookError
from .logging import LogContext
from .metrics import record_metric
import hmac
import hashlib
import json
import httpx

# Base Models
class WebhookSubscriptionBase(BaseModel):
    """Base model for webhook subscription data"""
    callback_url: constr(regex=r'^https://') = Field(
        ...,
        description="HTTPS URL to receive webhook events"
    )
    is_active: bool = Field(
        default=True,
        description="Whether subscription is active"
    )
    error_count: int = Field(
        default=0,
        description="Number of consecutive delivery errors"
    )

    @validator("callback_url")
    def validate_callback_url(cls, v):
        if not v.startswith("https://"):
            raise WebhookError("Callback URL must use HTTPS")
        return v

# Database Models
class WebhookSubscription(WebhookSubscriptionBase, table=True):
    """Database model for webhook subscriptions"""
    __tablename__ = "webhook_subscriptions"

    subscription_id: UUID4 = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        description="Unique subscription identifier"
    )
    secret_key: str = Field(
        ...,
        description="Secret key for signature verification"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Record creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
        description="Last update timestamp"
    )
    last_ping_at: Optional[datetime] = Field(
        None,
        description="Last successful ping timestamp"
    )

    # Relationships with lazy loading
    events: List["SubscriptionEvent"] = Relationship(
        back_populates="subscription",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    deliveries: List["EventDelivery"] = Relationship(
        back_populates="subscription",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    class Config:
        orm_mode = True

class EventType(SQLModel, table=True):
    """Database model for event types"""
    __tablename__ = "event_types"

    event_type_id: int = Field(default=None, primary_key=True)
    name: str = Field(
        ...,
        max_length=50,
        description="Event type name",
        sa_column_kwargs={"unique": True}
    )
    description: Optional[str] = Field(None, description="Event description")
    source_system: str = Field(
        ...,
        description="Source system for events",
        sa_column_kwargs={"check": "source_system IN ('congress', 'govinfo')"}
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    subscriptions: List["SubscriptionEvent"] = Relationship(back_populates="event_type")

class SubscriptionEvent(SQLModel, table=True):
    """Database model for subscription event types"""
    __tablename__ = "subscription_events"

    subscription_id: UUID4 = Field(
        foreign_key="webhook_subscriptions.subscription_id",
        primary_key=True,
        description="Associated subscription ID"
    )
    event_type_id: int = Field(
        foreign_key="event_types.event_type_id",
        primary_key=True,
        description="Associated event type ID"
    )
    filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Event filters as JSON"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
async def register_webhook(
    self,
    callback_url: str,
    event_types: List[str],
    filters: Optional[Dict[str, Any]] = None
) -> WebhookSubscription:
    """
    Register a webhook for real-time updates

    Args:
        callback_url (str): HTTPS URL to receive webhook events
        event_types (List[str]): Types of events to receive
        filters (Optional[Dict]): Filters to apply to events

    Returns:
        WebhookSubscription: Webhook configuration and secret key
    """
```

#### Source APIs Used

1. Congress.gov:
   - Endpoint: `/subscriptions`
   - Rate Limit: Part of 5,000 requests/hour
   - Used for: Legislative update notifications

2. GovInfo.gov:
   - Endpoint: `/packages/notifications`
   - Rate Limit: Part of 1,000 requests/hour
   - Used for: Document update notifications

#### Database Schema

```sql
-- Webhook Subscriptions
CREATE TABLE webhook_subscriptions (
    subscription_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    callback_url TEXT NOT NULL,
    secret_key TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_ping_at TIMESTAMPTZ,
    error_count INTEGER DEFAULT 0,
    CONSTRAINT valid_callback_url CHECK (callback_url ~ '^https://')
);

-- Event Types
CREATE TABLE event_types (
    event_type_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    source_system VARCHAR(10) CHECK (source_system IN ('congress', 'govinfo')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Subscription Events
CREATE TABLE subscription_events (
    subscription_id UUID REFERENCES webhook_subscriptions(subscription_id),
    event_type_id INTEGER REFERENCES event_types(event_type_id),
    filters JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (subscription_id, event_type_id)
);

-- Event Delivery History
CREATE TABLE event_deliveries (
    delivery_id SERIAL PRIMARY KEY,
    subscription_id UUID REFERENCES webhook_subscriptions(subscription_id),
    event_type_id INTEGER REFERENCES event_types(event_type_id),
    payload JSONB NOT NULL,
    status VARCHAR(20),
    attempt_count INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### Implementation

```python
class WebhookService:
    def __init__(self, client: Client):
        self.client = client
        self.pg = client.pg
        self.congress_api = client.congress_api
        self.govinfo_api = client.govinfo_api

    async def register_webhook(
        self,
        callback_url: str,
        event_types: List[str],
        filters: Optional[Dict[str, Any]] = None
    ) -> WebhookSubscription:
        """Register a new webhook subscription"""
        # Validate callback URL and generate secret
        if not callback_url.startswith('https://'):
            raise InvalidCallbackError("Callback URL must use HTTPS")

        secret_key = self._generate_secret_key()

        async with self.pg.transaction():
            # Create subscription
            subscription_id = await self.pg.fetchval("""
                INSERT INTO webhook_subscriptions (
                    callback_url, secret_key
                ) VALUES ($1, $2)
                RETURNING subscription_id
            """, callback_url, secret_key)

            # Register event types
            for event_type in event_types:
                await self.pg.execute("""
                    INSERT INTO subscription_events (
                        subscription_id, event_type_id, filters
                    ) VALUES (
                        $1,
                        (SELECT event_type_id FROM event_types WHERE name = $2),
                        $3
                    )
                """, subscription_id, event_type, filters)

            # Register with source APIs if needed
            if any(et.startswith('congress.') for et in event_types):
                await self._register_congress_subscription(
                    subscription_id,
                    callback_url,
                    event_types
                )

            if any(et.startswith('govinfo.') for et in event_types):
                await self._register_govinfo_subscription(
                    subscription_id,
                    callback_url,
                    event_types
                )

        return await self._get_subscription(subscription_id)

    async def process_event(
        self,
        event_type: str,
        payload: Dict[str, Any]
    ) -> None:
        """Process and deliver an event to subscribers"""
        # Find matching subscriptions
        subscriptions = await self.pg.fetch("""
            SELECT ws.subscription_id, ws.callback_url, ws.secret_key,
                   se.filters
            FROM webhook_subscriptions ws
            JOIN subscription_events se
                ON ws.subscription_id = se.subscription_id
            JOIN event_types et
                ON se.event_type_id = et.event_type_id
            WHERE et.name = $1 AND ws.is_active = true
        """, event_type)

        # Deliver to each subscriber
        for sub in subscriptions:
            if self._matches_filters(payload, sub['filters']):
                await self._deliver_event(
                    sub['subscription_id'],
                    event_type,
                    payload,
                    sub['callback_url'],
                    sub['secret_key']
                )

    async def _deliver_event(
        self,
        subscription_id: UUID,
        event_type: str,
        payload: Dict[str, Any],
        callback_url: str,
        secret_key: str
    ) -> None:
        """Deliver event to subscriber with retries"""
        delivery_id = await self.pg.fetchval("""
            INSERT INTO event_deliveries (
                subscription_id,
                event_type_id,
                payload,
                status
            ) VALUES (
                $1,
                (SELECT event_type_id FROM event_types WHERE name = $2),
                $3,
                'pending'
            ) RETURNING delivery_id
        """, subscription_id, event_type, json.dumps(payload))

        try:
            # Sign payload
            signature = self._generate_signature(payload, secret_key)

            # Deliver with retries
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    callback_url,
                    json=payload,
                    headers={
                        'X-PyGovPub-Event': event_type,
                        'X-PyGovPub-Signature': signature,
                        'X-PyGovPub-Delivery': str(delivery_id)
                    }
                )

                if response.status_code == 200:
                    await self._mark_delivery_success(delivery_id)
                else:
                    raise WebhookDeliveryError(
                        f"Delivery failed: {response.status_code}"
                    )

        except Exception as e:
            await self._handle_delivery_failure(
                delivery_id,
                subscription_id,
                str(e)
            )

    def _generate_signature(
        self,
        payload: Dict[str, Any],
        secret_key: str
    ) -> str:
        """Generate HMAC signature for payload"""
        message = json.dumps(payload, sort_keys=True)
        return hmac.new(
            secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
```

### Usage Example

```python
from pygovpub import Client

client = Client(
    congress_key="your_congress_key",
    govinfo_key="your_govinfo_key"
)

# Register webhook for bill updates
subscription = await client.register_webhook(
    callback_url="https://api.yourapp.com/webhooks/legislative",
    event_types=[
        "congress.bill.introduced",
        "congress.bill.action",
        "govinfo.bill.published"
    ],
    filters={
        "congress": 117,
        "bill_types": ["hr", "s"],
        "committees": ["HSAG", "SSAF"]
    }
)

print(f"Webhook Secret: {subscription.secret_key}")

# Verify webhook signature
def verify_webhook(headers: dict, body: str, secret_key: str) -> bool:
    signature = headers.get('X-PyGovPub-Signature')
    expected = hmac.new(
        secret_key.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

## Testing

```python
async def test_webhook_registration():
    """Test webhook registration and delivery"""
    client = Client(congress_key="test_key", govinfo_key="test_key")

    # Test registration
    subscription = await client.register_webhook(
        "https://test.com/webhook",
        ["congress.bill.introduced"]
    )
    assert subscription.subscription_id is not None
    assert subscription.secret_key is not None

    # Test event delivery
    event = {
        "type": "congress.bill.introduced",
        "data": {"bill_id": "HR1234"}
    }
    await client.process_event(event['type'], event['data'])

    # Verify delivery record
    delivery = await client.pg.fetchrow("""
        SELECT * FROM event_deliveries
        WHERE subscription_id = $1
    """, subscription.subscription_id)
    assert delivery['status'] == 'success'
```

## Error Handling

```python
class WebhookError(Exception):
    """Base class for webhook errors"""
    pass

class InvalidCallbackError(WebhookError):
    """Raised when callback URL is invalid"""
    pass

class WebhookDeliveryError(WebhookError):
    """Raised when event delivery fails"""
    pass

async def handle_webhook_error(
    self,
    error: Exception,
    subscription_id: UUID
) -> None:
    """Handle webhook-related errors"""
    await self.pg.execute("""
        UPDATE webhook_subscriptions
        SET error_count = error_count + 1
        WHERE subscription_id = $1
    """, subscription_id)

    if isinstance(error, WebhookDeliveryError):
        # Disable webhook if too many errors
        await self.pg.execute("""
            UPDATE webhook_subscriptions
            SET is_active = false
            WHERE subscription_id = $1
            AND error_count >= 100
        """, subscription_id)

    await self.pg.execute("""
        INSERT INTO sync_errors (
            source_system,
            entity_type,
            entity_id,
            error_message,
            error_time
        ) VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
    """, 'webhook', 'webhook', str(subscription_id), str(error))
```

### FastAPI Implementation

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Body
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
from pygovpub import Client, get_client

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

class WebhookRegistration(BaseModel):
    callback_url: HttpUrl
    event_types: List[str]
    filters: Optional[Dict[str, Any]] = None

class WebhookResponse(BaseModel):
    subscription_id: str
    callback_url: HttpUrl
    secret_key: str
    event_types: List[str]

@router.post("/register", response_model=WebhookResponse)
async def register_webhook(
    webhook: WebhookRegistration,
    background_tasks: BackgroundTasks,
    client: Client = Depends(get_client)
):
    """Register a new webhook subscription"""
    try:
        subscription = await client.register_webhook(
            callback_url=str(webhook.callback_url),
            event_types=webhook.event_types,
            filters=webhook.filters
        )

        # Test the webhook in background
        background_tasks.add_task(
            client.test_webhook_delivery,
            subscription.subscription_id
        )

        return subscription
    except InvalidCallbackError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/events/{event_type}")
async def process_event(
    event_type: str,
    payload: Dict[str, Any] = Body(...),
    background_tasks: BackgroundTasks,
    client: Client = Depends(get_client)
):
    """Process and deliver an event to subscribers"""
    # Process event delivery in background
    background_tasks.add_task(
        client.process_event,
        event_type,
        payload
    )
    return {"status": "processing"}

# Webhook callback receiver endpoint
@router.post("/callback")
async def webhook_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    client: Client = Depends(get_client)
):
    """Receive webhook callbacks from external systems"""
    # Verify signature
    signature = request.headers.get("X-PyGovPub-Signature")
    event_type = request.headers.get("X-PyGovPub-Event")

    body = await request.json()

    # Process in background
    background_tasks.add_task(
        client.process_external_webhook,
        event_type,
        body,
        signature
    )

    return {"status": "received"}
```
