"""
Tests for the citation models.

This module tests the models used for representing citations and cross-references
between different types of documents and entities.
"""

import unittest
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from enum import Enum
import pytest
from pydantic import ValidationError, BaseModel

from pygovpub.models.documents import DocumentType, SourceReference
from pygovpub.auth.models import ApiSource
from pygovpub.models.citation import (
    CitationType,
    Citation,
    ReferenceResolution,
    BidirectionalLink
)


class TestCitationModels:
    """Tests for the citation models."""

    def test_citation_creation(self):
        """Test creating a citation model."""
        # Arrange
        citation_data = {
            "citation_id": "cit-12345",
            "citation_type": CitationType.BILL,
            "text": "H.R. at section 101(a)",
            "source_entity_id": "bill-123",
            "source_entity_type": "bill",
            "target_entity_id": "bill-456",
            "target_entity_type": "bill",
            "location_in_source": {
                "section": "101",
                "paragraph": "a"
            }
        }

        # Act
        citation = Citation(**citation_data)

        # Assert
        assert citation.citation_id == "cit-12345"
        assert citation.citation_type == CitationType.BILL
        assert citation.text == "H.R. at section 101(a)"
        assert citation.source_entity_id == "bill-123"
        assert citation.target_entity_id == "bill-456"
        assert citation.location_in_source["section"] == "101"
        assert citation.location_in_source["paragraph"] == "a"

    def test_reference_resolution(self):
        """Test reference resolution model."""
        # Arrange
        resolution_data = {
            "resolution_id": "res-12345",
            "citation_id": "cit-12345",
            "resolution_status": "RESOLVED",
            "resolution_method": "AUTOMATIC",
            "confidence_score": 0.95,
            "target_information": {
                "title": "H.R. 456 - Sample Bill",
                "url": "https://example.gov/bill/456"
            },
            "resolution_date": "2023-05-15T14:30:00Z"
        }

        # Act
        resolution = ReferenceResolution(**resolution_data)

        # Assert
        assert resolution.resolution_id == "res-12345"
        assert resolution.citation_id == "cit-12345"
        assert resolution.resolution_status == "RESOLVED"
        assert resolution.confidence_score == 0.95
        assert resolution.target_information["title"] == "H.R. 456 - Sample Bill"
        assert resolution.resolution_date is not None

    def test_bidirectional_link(self):
        """Test bidirectional link model."""
        # Arrange
        link_data = {
            "link_id": "link-12345",
            "entity_a_id": "bill-123", 
            "entity_a_type": "bill",
            "entity_b_id": "bill-456",
            "entity_b_type": "bill", 
            "relationship_type": "REFERENCES",
            "citations": ["cit-12345", "cit-67890"],
            "properties": {
                "count": 5,
                "first_occurrence": "Section 101",
                "importance": "HIGH"
            }
        }

        # Act
        link = BidirectionalLink(**link_data)

        # Assert
        assert link.link_id == "link-12345"
        assert link.entity_a_id == "bill-123"
        assert link.entity_b_id == "bill-456"
        assert link.relationship_type == "REFERENCES"
        assert len(link.citations) == 2
        assert link.properties["importance"] == "HIGH"

    def test_citation_type_enum(self):
        """Test the CitationType enum."""
        # Assert
        assert CitationType.BILL.name == "BILL"
        assert CitationType.CFR.name == "CFR"
        assert CitationType.USC.name == "USC"
        assert CitationType.COURT_CASE.name == "COURT_CASE"
        assert CitationType.FEDERAL_REGISTER.name == "FEDERAL_REGISTER"