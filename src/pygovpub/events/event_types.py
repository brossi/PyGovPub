"""
Event type definitions for PyGovPub.

This module defines the event types and payload structures for
legislative and regulatory real-time updates.
"""

from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from pygovpub.auth.models import ApiSource


class EventCategory(str, Enum):
    """Categories of events in the system."""
    
    FLOOR_UPDATE = "floor_update"
    VOTE_UPDATE = "vote_update"
    CALENDAR_UPDATE = "calendar_update"
    HEARING_UPDATE = "hearing_update"
    BILL_UPDATE = "bill_update"
    COMMITTEE_UPDATE = "committee_update"
    MEMBER_UPDATE = "member_update"
    DOCUMENT_UPDATE = "document_update"
    SYSTEM = "system"


class EventPriority(str, Enum):
    """Priority levels for events."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(str, Enum):
    """Specific event types within categories."""
    
    # Floor updates
    FLOOR_PROCEEDINGS_UPDATE = "floor_proceedings_update"
    FLOOR_ACTION = "floor_action"
    
    # Vote updates
    VOTE_SCHEDULED = "vote_scheduled"
    VOTE_STARTED = "vote_started"
    VOTE_COMPLETED = "vote_completed"
    VOTE_MODIFIED = "vote_modified"
    
    # Calendar updates
    CALENDAR_ITEM_ADDED = "calendar_item_added"
    CALENDAR_ITEM_MODIFIED = "calendar_item_modified"
    CALENDAR_ITEM_REMOVED = "calendar_item_removed"
    
    # Hearing updates
    HEARING_SCHEDULED = "hearing_scheduled"
    HEARING_MODIFIED = "hearing_modified"
    HEARING_CANCELED = "hearing_canceled"
    HEARING_DOCUMENTS_ADDED = "hearing_documents_added"
    
    # Bill updates
    BILL_INTRODUCED = "bill_introduced"
    BILL_MODIFIED = "bill_modified"
    BILL_STATUS_CHANGE = "bill_status_change"
    BILL_TEXT_AVAILABLE = "bill_text_available"
    
    # Committee updates
    COMMITTEE_MEETING_SCHEDULED = "committee_meeting_scheduled"
    COMMITTEE_DOCUMENT_AVAILABLE = "committee_document_available"
    
    # Member updates
    MEMBER_STATEMENT_AVAILABLE = "member_statement_available"
    
    # Document updates
    DOCUMENT_AVAILABLE = "document_available"
    DOCUMENT_MODIFIED = "document_modified"
    
    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    RATE_LIMIT_WARNING = "rate_limit_warning"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class EventPayload(BaseModel):
    """Base payload for all events."""
    
    event_time: datetime = Field(default_factory=datetime.utcnow)
    """Time the event occurred."""
    
    source: ApiSource
    """Source of the event data."""
    
    source_id: str
    """Identifier at the source."""
    
    source_url: Optional[str] = None
    """URL to access the resource at the source."""
    
    resource_type: str
    """Type of resource this event relates to."""
    
    data: Dict[str, Any] = Field(default_factory=dict)
    """Event-specific data payload."""


class Event(BaseModel):
    """Event notification."""
    
    id: UUID = Field(default_factory=uuid4)
    """Unique identifier for the event."""
    
    event_type: EventType
    """Type of event."""
    
    category: EventCategory
    """Category of event."""
    
    priority: EventPriority = EventPriority.MEDIUM
    """Priority of event."""
    
    payload: EventPayload
    """Event data payload."""
    
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    """Time the event occurred."""
    
    processed_at: Optional[datetime] = None
    """Time the event was processed."""
    
    delivery_attempts: int = 0
    """Number of delivery attempts."""
    
    last_delivery_attempt: Optional[datetime] = None
    """Time of last delivery attempt."""
    
    delivered_at: Optional[datetime] = None
    """Time the event was successfully delivered."""
    
    error_message: Optional[str] = None
    """Error message if delivery failed."""


# Specialized event payloads

class FloorUpdatePayload(EventPayload):
    """Payload for floor update events."""
    
    chamber: str
    """Chamber where the floor activity occurred."""
    
    action_time: datetime
    """Time the floor action occurred."""
    
    description: str
    """Description of the floor action."""
    
    related_bills: List[str] = Field(default_factory=list)
    """List of bill IDs related to the floor action."""
    
    related_members: List[str] = Field(default_factory=list)
    """List of member IDs related to the floor action."""


class VoteUpdatePayload(EventPayload):
    """Payload for vote update events."""
    
    vote_id: str
    """Identifier for the vote."""
    
    chamber: str
    """Chamber where the vote occurred."""
    
    vote_time: datetime
    """Time the vote occurred or was scheduled."""
    
    question: str
    """Question being voted on."""
    
    description: str
    """Description of the vote."""
    
    result: Optional[str] = None
    """Result of the vote if completed."""
    
    related_bills: List[str] = Field(default_factory=list)
    """List of bill IDs related to the vote."""


class CalendarUpdatePayload(EventPayload):
    """Payload for calendar update events."""
    
    chamber: str
    """Chamber the calendar item belongs to."""
    
    calendar_id: str
    """Identifier for the calendar."""
    
    scheduled_time: datetime
    """Time the calendar item is scheduled for."""
    
    description: str
    """Description of the calendar item."""
    
    related_bills: List[str] = Field(default_factory=list)
    """List of bill IDs related to the calendar item."""


class HearingUpdatePayload(EventPayload):
    """Payload for hearing update events."""
    
    committee_id: str
    """Identifier for the committee holding the hearing."""
    
    hearing_id: str
    """Identifier for the hearing."""
    
    title: str
    """Title of the hearing."""
    
    scheduled_time: datetime
    """Time the hearing is scheduled for."""
    
    location: str
    """Location of the hearing."""
    
    description: Optional[str] = None
    """Description of the hearing."""
    
    related_bills: List[str] = Field(default_factory=list)
    """List of bill IDs related to the hearing."""
    
    witnesses: List[str] = Field(default_factory=list)
    """List of witnesses scheduled to appear."""
    
    documents: List[Dict[str, str]] = Field(default_factory=list)
    """List of documents related to the hearing."""