"""
Webhook management for PyGovPub.

This module provides functionality for registering,
validating, and managing webhooks for event delivery.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field, HttpUrl, field_validator

from pygovpub.events.event_types import Event, EventCategory, EventType
from pygovpub.events.event_manager import get_event_manager
from pygovpub.events.dispatchers.base import EventDispatcherBase

# Configure logging
logger = logging.getLogger("pygovpub.webhooks")


class WebhookStatus(str, Enum):
    """Status of a webhook."""
    
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    DISABLED = "disabled"
    EXPIRED = "expired"


class WebhookDeliveryStatus(str, Enum):
    """Status of a webhook delivery."""
    
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    DROPPED = "dropped"


class Webhook(BaseModel):
    """Webhook registration."""
    
    id: UUID = Field(default_factory=uuid4)
    """Unique identifier for the webhook."""
    
    url: HttpUrl
    """URL to deliver webhook events to."""
    
    secret: str = Field(default_factory=lambda: secrets.token_hex(32))
    """Secret for signing webhook payloads."""
    
    description: Optional[str] = None
    """Description of the webhook."""
    
    event_types: List[EventType] = Field(default_factory=list)
    """Event types to deliver to this webhook."""
    
    event_categories: List[EventCategory] = Field(default_factory=list)
    """Event categories to deliver to this webhook."""
    
    status: WebhookStatus = WebhookStatus.PENDING
    """Status of the webhook."""
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    """Time the webhook was created."""
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    """Time the webhook was last updated."""
    
    last_delivery_at: Optional[datetime] = None
    """Time of last successful delivery."""
    
    expiry_date: Optional[datetime] = None
    """Optional expiry date for the webhook."""
    
    failure_count: int = 0
    """Count of failed deliveries."""
    
    headers: Dict[str, str] = Field(default_factory=dict)
    """Additional headers to send with webhook requests."""
    
    @field_validator("event_types", "event_categories", mode="before")
    @classmethod
    def validate_unique_values(cls, v):
        """Ensure event_types and event_categories contain unique values."""
        if isinstance(v, list):
            return list(set(v))
        return v


class WebhookDelivery(BaseModel):
    """Record of a webhook delivery attempt."""
    
    id: UUID = Field(default_factory=uuid4)
    """Unique identifier for the delivery."""
    
    webhook_id: UUID
    """ID of the webhook."""
    
    event_id: UUID
    """ID of the event."""
    
    status: WebhookDeliveryStatus = WebhookDeliveryStatus.PENDING
    """Status of the delivery."""
    
    attempt_count: int = 0
    """Number of delivery attempts."""
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    """Time the delivery was created."""
    
    last_attempt_at: Optional[datetime] = None
    """Time of the last delivery attempt."""
    
    completed_at: Optional[datetime] = None
    """Time the delivery was completed."""
    
    next_attempt_at: Optional[datetime] = None
    """Time of the next scheduled attempt."""
    
    response_code: Optional[int] = None
    """HTTP response code from the last attempt."""
    
    response_body: Optional[str] = None
    """Response body from the last attempt."""
    
    error_message: Optional[str] = None
    """Error message from the last attempt."""


class WebhookDispatcher(EventDispatcherBase):
    """Dispatches events to webhooks."""
    
    def __init__(self, webhook_manager: "WebhookManager"):
        """Initialize webhook dispatcher.
        
        Args:
            webhook_manager: Webhook manager
        """
        super().__init__("webhook_dispatcher")
        self.webhook_manager = webhook_manager
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def dispatch(self, event: Event) -> bool:
        """Dispatch event to webhooks.
        
        Args:
            event: Event to dispatch
            
        Returns:
            True if at least one webhook delivery succeeded, False otherwise
        """
        try:
            # Get webhooks that should receive this event
            webhooks = self.webhook_manager.get_webhooks_for_event(event)
            
            if not webhooks:
                logger.debug(f"No webhooks for event {event.id}")
                self.record_dispatch_attempt(event, True)
                return True
            
            # Track delivery success
            success_count = 0
            
            # Create deliveries for each webhook
            delivery_tasks = []
            for webhook in webhooks:
                delivery = self.webhook_manager.create_delivery(webhook.id, event.id)
                delivery_tasks.append(self._deliver_to_webhook(event, webhook, delivery))
            
            # Execute all deliveries concurrently
            results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error during webhook delivery: {result}")
                elif result:
                    success_count += 1
            
            # Record dispatch success if at least one webhook delivery succeeded
            success = success_count > 0
            self.record_dispatch_attempt(
                event, 
                success, 
                None if success else f"Failed to deliver to all {len(webhooks)} webhooks"
            )
            
            return success
        except Exception as e:
            error_msg = f"Error dispatching event {event.id} to webhooks: {e}"
            logger.error(error_msg)
            self.record_dispatch_attempt(event, False, error_msg)
            return False
    
    async def _deliver_to_webhook(
        self, event: Event, webhook: Webhook, delivery: WebhookDelivery
    ) -> bool:
        """Deliver event to a specific webhook.
        
        Args:
            event: Event to deliver
            webhook: Webhook to deliver to
            delivery: Delivery record
            
        Returns:
            True if delivery succeeded, False otherwise
        """
        try:
            # Create payload
            payload = {
                "id": str(delivery.id),
                "event_id": str(event.id),
                "event_type": event.event_type.value,
                "event_category": event.category.value,
                "timestamp": event.occurred_at.isoformat(),
                "data": {
                    "payload": event.payload.model_dump(),
                    "meta": {
                        "priority": event.priority.value,
                        "processed_at": event.processed_at.isoformat() if event.processed_at else None
                    }
                }
            }
            
            payload_json = json.dumps(payload)
            
            # Create signature
            signature = self._create_signature(webhook.secret, payload_json)
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "PyGovPub-Webhook/1.0",
                "X-PyGovPub-Delivery": str(delivery.id),
                "X-PyGovPub-Event": event.event_type.value,
                "X-PyGovPub-Signature": signature
            }
            
            # Add custom headers
            headers.update(webhook.headers)
            
            # Update delivery record
            delivery.attempt_count += 1
            delivery.last_attempt_at = datetime.utcnow()
            delivery.status = WebhookDeliveryStatus.PENDING
            
            # Perform delivery
            start_time = datetime.utcnow()
            response = await self.client.post(
                str(webhook.url),
                headers=headers,
                content=payload_json
            )
            end_time = datetime.utcnow()
            
            # Update delivery record
            delivery.response_code = response.status_code
            delivery.response_body = response.text[:1000]  # Limit response body size
            
            # Check response status
            success = 200 <= response.status_code < 300
            
            if success:
                delivery.status = WebhookDeliveryStatus.SUCCESS
                delivery.completed_at = end_time
                webhook.last_delivery_at = end_time
                webhook.failure_count = 0
            else:
                delivery.status = WebhookDeliveryStatus.FAILED
                delivery.error_message = f"HTTP {response.status_code}: {response.text[:100]}"
                webhook.failure_count += 1
                
                # Set up retry if needed
                if delivery.attempt_count < self.webhook_manager.max_retries:
                    retry_delay = self._calculate_retry_delay(delivery.attempt_count)
                    delivery.next_attempt_at = datetime.utcnow() + retry_delay
                    delivery.status = WebhookDeliveryStatus.RETRYING
                else:
                    delivery.status = WebhookDeliveryStatus.DROPPED
            
            # Update webhook status based on failures
            if webhook.failure_count >= self.webhook_manager.max_failures:
                webhook.status = WebhookStatus.FAILED
            
            # Save updated delivery and webhook
            self.webhook_manager._save_delivery(delivery)
            self.webhook_manager._save_webhook(webhook)
            
            return success
        except Exception as e:
            logger.error(f"Error delivering event {event.id} to webhook {webhook.id}: {e}")
            
            # Update delivery record
            delivery.attempt_count += 1
            delivery.last_attempt_at = datetime.utcnow()
            delivery.status = WebhookDeliveryStatus.FAILED
            delivery.error_message = str(e)
            
            # Set up retry if needed
            if delivery.attempt_count < self.webhook_manager.max_retries:
                retry_delay = self._calculate_retry_delay(delivery.attempt_count)
                delivery.next_attempt_at = datetime.utcnow() + retry_delay
                delivery.status = WebhookDeliveryStatus.RETRYING
            else:
                delivery.status = WebhookDeliveryStatus.DROPPED
            
            # Update webhook
            webhook.failure_count += 1
            if webhook.failure_count >= self.webhook_manager.max_failures:
                webhook.status = WebhookStatus.FAILED
            
            # Save updated delivery and webhook
            self.webhook_manager._save_delivery(delivery)
            self.webhook_manager._save_webhook(webhook)
            
            return False
    
    def _create_signature(self, secret: str, payload: str) -> str:
        """Create HMAC signature for payload.
        
        Args:
            secret: Webhook secret
            payload: JSON payload
            
        Returns:
            Signature string
        """
        hmac_obj = hmac.new(
            key=secret.encode(),
            msg=payload.encode(),
            digestmod=hashlib.sha256
        )
        return f"sha256={hmac_obj.hexdigest()}"
    
    def _calculate_retry_delay(self, attempt: int) -> timedelta:
        """Calculate exponential backoff delay.
        
        Args:
            attempt: Attempt number
            
        Returns:
            Delay timedelta
        """
        # Exponential backoff: 2^attempt seconds with 10s minimum, 3h maximum
        seconds = max(10, min(10800, 2 ** attempt))
        return timedelta(seconds=seconds)


class WebhookManager:
    """Manager for webhooks and webhook deliveries."""
    
    def __init__(self):
        """Initialize webhook manager."""
        self._webhooks: Dict[UUID, Webhook] = {}
        self._deliveries: Dict[UUID, WebhookDelivery] = {}
        self._webhook_events: Dict[UUID, Set[UUID]] = {}  # webhook_id -> set of event_ids
        self.dispatcher = WebhookDispatcher(self)
        self.max_retries = 5
        self.max_failures = 10
        
        # Register dispatcher with event manager
        self._event_manager = get_event_manager()
        self._event_manager.subscribe(self._handle_event)
    
    async def _handle_event(self, event: Event) -> None:
        """Handle an event by dispatching to webhooks.
        
        Args:
            event: Event to handle
        """
        await self.dispatcher.dispatch(event)
    
    def register_webhook(
        self,
        url: str,
        description: Optional[str] = None,
        event_types: Optional[List[EventType]] = None,
        event_categories: Optional[List[EventCategory]] = None,
        headers: Optional[Dict[str, str]] = None,
        expiry_date: Optional[datetime] = None
    ) -> Webhook:
        """Register a new webhook.
        
        Args:
            url: Webhook URL
            description: Optional webhook description
            event_types: Optional list of event types to deliver
            event_categories: Optional list of event categories to deliver
            headers: Optional custom headers to send with requests
            expiry_date: Optional expiry date for the webhook
            
        Returns:
            Registered webhook
        """
        # Create webhook
        webhook = Webhook(
            url=url,
            description=description,
            event_types=event_types or [],
            event_categories=event_categories or [],
            headers=headers or {},
            expiry_date=expiry_date,
            status=WebhookStatus.PENDING
        )
        
        # Save webhook
        self._save_webhook(webhook)
        
        # Initialize event tracking
        self._webhook_events[webhook.id] = set()
        
        logger.info(f"Registered webhook {webhook.id} for URL {url}")
        return webhook
    
    def update_webhook(
        self,
        webhook_id: UUID,
        url: Optional[str] = None,
        description: Optional[str] = None,
        event_types: Optional[List[EventType]] = None,
        event_categories: Optional[List[EventCategory]] = None,
        headers: Optional[Dict[str, str]] = None,
        expiry_date: Optional[datetime] = None,
        status: Optional[WebhookStatus] = None
    ) -> Optional[Webhook]:
        """Update an existing webhook.
        
        Args:
            webhook_id: ID of webhook to update
            url: Optional new webhook URL
            description: Optional new webhook description
            event_types: Optional new list of event types to deliver
            event_categories: Optional new list of event categories to deliver
            headers: Optional new custom headers to send with requests
            expiry_date: Optional new expiry date for the webhook
            status: Optional new webhook status
            
        Returns:
            Updated webhook or None if webhook not found
        """
        # Get webhook
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            logger.warning(f"Webhook {webhook_id} not found for update")
            return None
        
        # Update fields
        if url:
            webhook.url = url
        if description is not None:
            webhook.description = description
        if event_types is not None:
            webhook.event_types = event_types
        if event_categories is not None:
            webhook.event_categories = event_categories
        if headers is not None:
            webhook.headers = headers
        if expiry_date is not None:
            webhook.expiry_date = expiry_date
        if status is not None:
            webhook.status = status
        
        # Update timestamp
        webhook.updated_at = datetime.utcnow()
        
        # Save webhook
        self._save_webhook(webhook)
        
        logger.info(f"Updated webhook {webhook_id}")
        return webhook
    
    def delete_webhook(self, webhook_id: UUID) -> bool:
        """Delete a webhook.
        
        Args:
            webhook_id: ID of webhook to delete
            
        Returns:
            True if webhook was deleted, False if not found
        """
        if webhook_id not in self._webhooks:
            logger.warning(f"Webhook {webhook_id} not found for deletion")
            return False
        
        # Remove webhook
        del self._webhooks[webhook_id]
        
        # Clean up event tracking
        if webhook_id in self._webhook_events:
            del self._webhook_events[webhook_id]
        
        logger.info(f"Deleted webhook {webhook_id}")
        return True
    
    def get_webhook(self, webhook_id: UUID) -> Optional[Webhook]:
        """Get a webhook by ID.
        
        Args:
            webhook_id: ID of webhook to get
            
        Returns:
            Webhook if found, None otherwise
        """
        return self._webhooks.get(webhook_id)
    
    def list_webhooks(
        self,
        status: Optional[WebhookStatus] = None,
        event_type: Optional[EventType] = None,
        event_category: Optional[EventCategory] = None
    ) -> List[Webhook]:
        """List webhooks with optional filtering.
        
        Args:
            status: Optional status to filter by
            event_type: Optional event type to filter by
            event_category: Optional event category to filter by
            
        Returns:
            List of matching webhooks
        """
        webhooks = list(self._webhooks.values())
        
        # Apply filters
        if status:
            webhooks = [w for w in webhooks if w.status == status]
        if event_type:
            webhooks = [w for w in webhooks if event_type in w.event_types]
        if event_category:
            webhooks = [w for w in webhooks if event_category in w.event_categories]
        
        return webhooks
    
    def create_delivery(self, webhook_id: UUID, event_id: UUID) -> WebhookDelivery:
        """Create a delivery record.
        
        Args:
            webhook_id: ID of webhook
            event_id: ID of event
            
        Returns:
            Created delivery record
        """
        delivery = WebhookDelivery(
            webhook_id=webhook_id,
            event_id=event_id
        )
        
        # Save delivery
        self._save_delivery(delivery)
        
        # Track event for webhook
        if webhook_id in self._webhook_events:
            self._webhook_events[webhook_id].add(event_id)
        
        return delivery
    
    def get_delivery(self, delivery_id: UUID) -> Optional[WebhookDelivery]:
        """Get a delivery by ID.
        
        Args:
            delivery_id: ID of delivery to get
            
        Returns:
            Delivery if found, None otherwise
        """
        return self._deliveries.get(delivery_id)
    
    def list_deliveries(
        self,
        webhook_id: Optional[UUID] = None,
        event_id: Optional[UUID] = None,
        status: Optional[WebhookDeliveryStatus] = None
    ) -> List[WebhookDelivery]:
        """List deliveries with optional filtering.
        
        Args:
            webhook_id: Optional webhook ID to filter by
            event_id: Optional event ID to filter by
            status: Optional status to filter by
            
        Returns:
            List of matching deliveries
        """
        deliveries = list(self._deliveries.values())
        
        # Apply filters
        if webhook_id:
            deliveries = [d for d in deliveries if d.webhook_id == webhook_id]
        if event_id:
            deliveries = [d for d in deliveries if d.event_id == event_id]
        if status:
            deliveries = [d for d in deliveries if d.status == status]
        
        return deliveries
    
    def get_webhooks_for_event(self, event: Event) -> List[Webhook]:
        """Get webhooks that should receive an event.
        
        Args:
            event: Event to check
            
        Returns:
            List of webhooks that should receive the event
        """
        # Start with active webhooks
        webhooks = [w for w in self._webhooks.values() if w.status == WebhookStatus.ACTIVE]
        
        # Filter for matches
        matches = []
        for webhook in webhooks:
            # Check if webhook has expired
            if webhook.expiry_date and webhook.expiry_date < datetime.utcnow():
                webhook.status = WebhookStatus.EXPIRED
                self._save_webhook(webhook)
                continue
            
            # Check if webhook should receive this event
            if (not webhook.event_types and not webhook.event_categories):
                # Webhook subscribed to all events
                matches.append(webhook)
            elif event.event_type in webhook.event_types:
                # Event type match
                matches.append(webhook)
            elif event.category in webhook.event_categories:
                # Event category match
                matches.append(webhook)
        
        return matches
    
    def _save_webhook(self, webhook: Webhook) -> None:
        """Save a webhook to storage.
        
        Args:
            webhook: Webhook to save
        """
        self._webhooks[webhook.id] = webhook
    
    def _save_delivery(self, delivery: WebhookDelivery) -> None:
        """Save a delivery to storage.
        
        Args:
            delivery: Delivery to save
        """
        self._deliveries[delivery.id] = delivery


# Global webhook manager instance
_webhook_manager = None


def get_webhook_manager() -> WebhookManager:
    """Get the global webhook manager instance.
    
    Returns:
        Global webhook manager instance
    """
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager