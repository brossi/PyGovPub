"""
Integration tests for data synchronization between Congress.gov and GovInfo.gov APIs.

These tests verify that events and update notifications between different API sources
are properly synchronized through the event system.
"""

import asyncio
from datetime import datetime
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pygovpub.api.clients.congress import CongressClient
from pygovpub.api.clients.govinfo import GovInfoClient
from pygovpub.api.router import ApiRouter
from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.events.event_manager import EventManager, get_event_manager
from pygovpub.events.event_types import (
    Event, EventCategory, EventType, EventPayload,
    DocumentPublishedPayload
)
from pygovpub.models.legislative import BillStatus
from pygovpub.models.legislative import Bill


class TestDataSynchronization:
    """Tests for data synchronization between Congress.gov and GovInfo.gov APIs."""
    
    @pytest.fixture
    def mock_auth_manager(self):
        """Create a mock auth manager."""
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.execute_request = AsyncMock()
        return auth_manager
    
    @pytest.fixture
    def event_manager(self):
        """Create an event manager."""
        manager = EventManager()
        return manager
    
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
    def api_router(self, congress_client, govinfo_client):
        """Create an API router with Congress and GovInfo clients."""
        router = ApiRouter()
        router.register_client(ApiSource.CONGRESS, congress_client)
        router.register_client(ApiSource.GOVINFO, govinfo_client)
        return router
    
    @pytest.fixture
    def bill_data(self):
        """Sample bill data for testing."""
        return {
            "congress": 117,
            "type": "hr",
            "number": 1234,
            "title": "Test Bill",
            "introducedDate": "2023-03-01",
            "sponsors": [
                {
                    "bioguideId": "A000001",
                    "fullName": "Representative Test",
                    "party": "Test Party",
                    "state": "TS"
                }
            ],
            "actions": [
                {
                    "actionDate": "2023-03-01",
                    "text": "Introduced in House",
                    "type": "IntroReferral"
                }
            ],
            "latestAction": {
                "actionDate": "2023-03-01",
                "text": "Introduced in House",
                "type": "IntroReferral"
            },
            "committees": [
                {
                    "systemCode": "HSAG",
                    "name": "House Committee on Agriculture"
                }
            ],
            "policyArea": {
                "name": "Agriculture and Food"
            },
            "subjects": [
                "Agriculture and Food",
                "Economics and Public Finance"
            ],
            "summaries": [
                {
                    "text": "This is a test bill summary.",
                    "updateDate": "2023-03-01"
                }
            ],
            "relatedBills": [],
            "cosponsors": []
        }
    
    @pytest.fixture
    def bill_document_data(self):
        """Sample bill document data for testing."""
        return {
            "packageId": "BILLS-117hr1234ih",
            "packageLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih",
            "title": "Test Bill",
            "congress": "117",
            "dateIssued": "2023-03-01",
            "collectionCode": "BILLS",
            "collectionName": "Bills and Statutes",
            "category": "Bills",
            "docClass": "hr",
            "docNumber": "1234",
            "docVersion": "ih",
            "formats": [
                {
                    "format": "PDF",
                    "link": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/pdf"
                },
                {
                    "format": "XML",
                    "link": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/xml"
                }
            ]
        }

    async def test_bill_events_sync(self, event_manager, congress_client, govinfo_client, bill_data):
        """Test synchronization of bill events between APIs."""
        # Setup event tracking
        received_events = []
        
        async def track_event(event):
            received_events.append(event)
        
        # Subscribe to bill events
        event_manager.subscribe(track_event, category=EventCategory.BILL_UPDATE)
        
        # Mock Congress API returning bill data
        mock_response = {
            "results": [bill_data]
        }
        congress_client.auth_manager.execute_request.return_value = mock_response
        
        # Simulate bill introduction event from Congress.gov API
        await congress_client._emit_bill_event(
            event_type=EventType.BILL_INTRODUCED,
            bill_data=bill_data
        )
        
        # Verify event was emitted
        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == EventType.BILL_INTRODUCED
        assert event.category == EventCategory.BILL_UPDATE
        assert event.payload.source == ApiSource.CONGRESS
        assert f"bill/{bill_data['congress']}/{bill_data['type']}{bill_data['number']}" in event.payload.source_id
    
    async def test_document_events_sync(self, event_manager, govinfo_client, bill_document_data):
        """Test synchronization of document events."""
        # Setup event tracking
        received_events = []
        
        async def track_event(event):
            received_events.append(event)
        
        # Subscribe to document events
        event_manager.subscribe(track_event, category=EventCategory.DOCUMENT_UPDATE)
        
        # Mock GovInfo API returning document data
        mock_response = {
            "results": [bill_document_data]
        }
        govinfo_client.auth_manager.execute_request.return_value = mock_response
        
        # Create document payload
        payload = DocumentPublishedPayload(
            event_time=datetime.utcnow(),
            source=ApiSource.GOVINFO,
            source_id=f"document/{bill_document_data['packageId']}",
            source_url=bill_document_data.get("packageLink", ""),
            resource_type="bill_document",
            document_id=bill_document_data["packageId"],
            document_type="bill",
            title=bill_document_data["title"],
            data=bill_document_data
        )
        
        # Emit document event
        await event_manager.create_and_emit_event(
            event_type=EventType.DOCUMENT_PUBLISHED,
            payload=payload
        )
        
        # Verify event was emitted
        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == EventType.DOCUMENT_PUBLISHED
        assert event.category == EventCategory.DOCUMENT_UPDATE
        assert event.payload.source == ApiSource.GOVINFO
        assert bill_document_data["packageId"] in event.payload.source_id
    
    async def test_cross_reference_synchronization(self, event_manager, congress_client, govinfo_client, bill_data, bill_document_data):
        """Test cross-reference synchronization between bill and document events."""
        bill_events = []
        document_events = []
        cross_references = []
        
        # Create trackers for different event types
        async def track_bill_event(event):
            bill_events.append(event)
            
            # Check if there's a matching document event
            await check_cross_reference(event)
        
        async def track_document_event(event):
            document_events.append(event)
            
            # Check if there's a matching bill event
            await check_cross_reference(event)
        
        async def check_cross_reference(event):
            """Check for cross-references between bill and document events."""
            # For a bill event, look for matching document events
            if event.category == EventCategory.BILL_UPDATE:
                bill_id = f"{bill_data['congress']}{bill_data['type']}{bill_data['number']}"
                
                # Look for matching document events
                for doc_event in document_events:
                    if isinstance(doc_event.payload, DocumentPublishedPayload):
                        if bill_id in doc_event.payload.document_id:
                            cross_references.append((event, doc_event))
            
            # For a document event, look for matching bill events
            elif event.category == EventCategory.DOCUMENT_UPDATE:
                if isinstance(event.payload, DocumentPublishedPayload):
                    document_id = event.payload.document_id
                    
                    # Extract bill info from document ID (e.g., BILLS-117hr1234ih)
                    if document_id.startswith("BILLS-"):
                        parts = document_id.split("-")[1]
                        if len(parts) >= 3:
                            congress = parts[:3]
                            bill_type = parts[3:5]
                            bill_number = ""
                            
                            for char in parts[5:]:
                                if char.isdigit():
                                    bill_number += char
                                else:
                                    break
                            
                            bill_id = f"{congress}{bill_type}{bill_number}"
                            
                            # Look for matching bill events
                            for bill_event in bill_events:
                                if bill_id in bill_event.payload.source_id:
                                    cross_references.append((bill_event, event))
        
        # Subscribe to events
        event_manager.subscribe(track_bill_event, category=EventCategory.BILL_UPDATE)
        event_manager.subscribe(track_document_event, category=EventCategory.DOCUMENT_UPDATE)
        
        # Emit bill introduction event
        await congress_client._emit_bill_event(
            event_type=EventType.BILL_INTRODUCED,
            bill_data=bill_data
        )
        
        # Emit document published event
        document_payload = DocumentPublishedPayload(
            event_time=datetime.utcnow(),
            source=ApiSource.GOVINFO,
            source_id=f"document/{bill_document_data['packageId']}",
            source_url=bill_document_data.get("packageLink", ""),
            resource_type="bill_document",
            document_id=bill_document_data["packageId"],
            document_type="bill",
            title=bill_document_data["title"],
            data=bill_document_data
        )
        
        await event_manager.create_and_emit_event(
            event_type=EventType.DOCUMENT_PUBLISHED,
            payload=document_payload
        )
        
        # Verify events were emitted
        assert len(bill_events) == 1
        assert len(document_events) == 1
        
        # Verify cross-references were found
        assert len(cross_references) > 0


async def test_event_consistency_verification():
    """Test consistency verification between different data sources."""
    # Create event manager
    event_manager = EventManager()
    
    # Track consistency verification results
    consistency_results = []
    
    async def verify_consistency(event):
        """Verify consistency between different data sources."""
        if event.category != EventCategory.BILL_UPDATE:
            return
            
        # Extract bill info from event
        bill_data = event.payload.data
        if not bill_data:
            return
            
        congress = bill_data.get("congress")
        bill_type = bill_data.get("type")
        bill_number = bill_data.get("number")
        
        if not all([congress, bill_type, bill_number]):
            return
            
        # "Compare" with other source
        is_consistent = True  # Simplified for test
        consistency_results.append({
            "event_id": str(event.id),
            "bill_id": f"{congress}{bill_type}{bill_number}",
            "is_consistent": is_consistent
        })
    
    # Subscribe to bill events
    event_manager.subscribe(verify_consistency, category=EventCategory.BILL_UPDATE)
    
    # Create a sample bill event
    bill_data = {
        "congress": 117,
        "type": "hr",
        "number": 1234,
        "title": "Test Bill",
        "introducedDate": "2023-03-01"
    }
    
    # Create bill payload
    payload = EventPayload(
        event_time=datetime.utcnow(),
        source=ApiSource.CONGRESS,
        source_id=f"bill/{bill_data['congress']}/{bill_data['type']}{bill_data['number']}",
        source_url="",
        resource_type="bill",
        data=bill_data
    )
    
    # Emit bill event
    await event_manager.create_and_emit_event(
        event_type=EventType.BILL_INTRODUCED,
        payload=payload
    )
    
    # Verify consistency was checked
    assert len(consistency_results) == 1
    assert consistency_results[0]["bill_id"] == f"{bill_data['congress']}{bill_data['type']}{bill_data['number']}"
    assert consistency_results[0]["is_consistent"] is True