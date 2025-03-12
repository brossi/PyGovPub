"""
Tests for the advanced metadata models.

This module tests the models used for representing advanced metadata including
version history, audit trails, provenance, and access control.
"""

import unittest
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from enum import Enum
import pytest
from pydantic import ValidationError, BaseModel

from pygovpub.models.documents import DocumentType, SourceReference
from pygovpub.auth.models import ApiSource
from pygovpub.models.advanced_metadata import (
    VersionHistory,
    AuditTrail,
    ProvenanceRecord,
    AccessControl,
    VersionAction,
    AuditAction,
    ProvenanceAgent,
    AccessLevel
)


class TestAdvancedMetadataModels:
    """Tests for the advanced metadata models."""

    def test_version_history_creation(self):
        """Test creating a version history model."""
        # Arrange
        data = {
            "entity_id": "bill-123",
            "entity_type": "bill",
            "current_version": "v3",
            "versions": [
                {
                    "version_id": "v1",
                    "timestamp": "2023-01-15T10:00:00Z",
                    "action": VersionAction.CREATE,
                    "user_id": "user-456",
                    "changes": ["Initial creation"]
                },
                {
                    "version_id": "v2",
                    "timestamp": "2023-02-10T14:30:00Z",
                    "action": VersionAction.UPDATE,
                    "user_id": "user-789",
                    "changes": ["Updated section 3", "Added new sponsor"]
                },
                {
                    "version_id": "v3",
                    "timestamp": "2023-03-05T09:15:00Z",
                    "action": VersionAction.UPDATE,
                    "user_id": "user-456",
                    "changes": ["Updated status", "Added committee referral"]
                }
            ]
        }

        # Act
        history = VersionHistory(**data)

        # Assert
        assert history.entity_id == "bill-123"
        assert history.entity_type == "bill"
        assert history.current_version == "v3"
        assert len(history.versions) == 3
        assert history.versions[0]["version_id"] == "v1"
        assert history.versions[0]["action"] == VersionAction.CREATE
        assert history.versions[1]["changes"] == ["Updated section 3", "Added new sponsor"]
        assert history.versions[2]["user_id"] == "user-456"

    def test_audit_trail_creation(self):
        """Test creating an audit trail model."""
        # Arrange
        data = {
            "entity_id": "bill-123",
            "entity_type": "bill",
            "audit_records": [
                {
                    "record_id": "audit-1",
                    "timestamp": "2023-01-15T10:05:00Z",
                    "action": AuditAction.VIEW,
                    "user_id": "user-101",
                    "metadata": {"ip": "192.168.1.1", "user_agent": "Mozilla/5.0"}
                },
                {
                    "record_id": "audit-2",
                    "timestamp": "2023-01-16T15:30:00Z",
                    "action": AuditAction.EDIT,
                    "user_id": "user-202",
                    "metadata": {"ip": "192.168.1.2", "section": "summary"}
                }
            ]
        }

        # Act
        audit = AuditTrail(**data)

        # Assert
        assert audit.entity_id == "bill-123"
        assert audit.entity_type == "bill"
        assert len(audit.audit_records) == 2
        assert audit.audit_records[0]["record_id"] == "audit-1"
        assert audit.audit_records[0]["action"] == AuditAction.VIEW
        assert audit.audit_records[1]["user_id"] == "user-202"
        assert audit.audit_records[1]["metadata"]["section"] == "summary"

    def test_provenance_record_creation(self):
        """Test creating a provenance record model."""
        # Arrange
        data = {
            "provenance_id": "prov-12345",
            "entity_id": "bill-123",
            "entity_type": "bill",
            "source_system": "congress.gov",
            "attribution": {
                "agent_id": "agent-456",
                "agent_type": ProvenanceAgent.ORGANIZATION,
                "agent_name": "Library of Congress"
            },
            "derived_from": ["source-789", "source-101"],
            "generation_time": "2023-01-15T10:00:00Z",
            "methodology": "Official API data extraction",
            "confidence_level": 0.95
        }

        # Act
        provenance = ProvenanceRecord(**data)

        # Assert
        assert provenance.provenance_id == "prov-12345"
        assert provenance.entity_id == "bill-123"
        assert provenance.entity_type == "bill"
        assert provenance.source_system == "congress.gov"
        assert provenance.attribution["agent_id"] == "agent-456"
        assert provenance.attribution["agent_type"] == ProvenanceAgent.ORGANIZATION
        assert len(provenance.derived_from) == 2
        assert provenance.confidence_level == 0.95

    def test_access_control_creation(self):
        """Test creating an access control model."""
        # Arrange
        data = {
            "entity_id": "bill-123",
            "entity_type": "bill",
            "owner_id": "user-456",
            "access_level": AccessLevel.PUBLIC,
            "permissions": [
                {"user_id": "user-789", "permission": "READ"},
                {"group_id": "group-101", "permission": "READ_WRITE"}
            ],
            "embargo_until": "2023-05-01T00:00:00Z",
            "restrictions": ["No redistribution", "Attribution required"]
        }

        # Act
        access = AccessControl(**data)

        # Assert
        assert access.entity_id == "bill-123"
        assert access.entity_type == "bill"
        assert access.owner_id == "user-456"
        assert access.access_level == AccessLevel.PUBLIC
        assert len(access.permissions) == 2
        assert access.permissions[0]["user_id"] == "user-789"
        assert access.permissions[1]["permission"] == "READ_WRITE"
        assert access.embargo_until == "2023-05-01T00:00:00Z"
        assert "Attribution required" in access.restrictions