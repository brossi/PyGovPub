"""
Tests for the regulatory models.

This module tests the models used for representing regulatory content
from the Code of Federal Regulations (CFR), Federal Register (FR), 
and court opinions.
"""

import unittest
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from enum import Enum
import pytest
from pydantic import ValidationError, BaseModel

from pygovpub.models.documents import DocumentType, SourceReference
from pygovpub.auth.models import ApiSource
from pygovpub.models.regulatory import (
    CfrTitle, 
    CfrChapter,
    CfrPart,
    CfrSection,
    CourtType,
    CourtOpinion,
    FederalRegisterDocument,
    RegulatoryProcess
)


class TestCfrModels:
    """Tests for the Code of Federal Regulations models."""

    def test_cfr_title_creation(self):
        """Test creating a CFR title model."""
        # Arrange
        title_data = {
            "title_number": 40,
            "title_name": "Protection of Environment",
            "chapters": [
                {
                    "chapter_number": "I",
                    "chapter_name": "Environmental Protection Agency"
                }
            ],
            "source_reference": {
                "source": ApiSource.GOVINFO,
                "source_id": "title40",
                "source_url": "https://www.govinfo.gov/app/collection/cfr/2023/title40"
            }
        }

        # Act
        title = CfrTitle(**title_data)

        # Assert
        assert title.title_number == 40
        assert title.title_name == "Protection of Environment"
        assert len(title.chapters) == 1
        assert title.chapters[0].chapter_number == "I"
        assert title.chapters[0].chapter_name == "Environmental Protection Agency"
        assert title.source_reference.source_id == "title40"
        assert title.source_reference.source == ApiSource.GOVINFO

    def test_cfr_title_validation(self):
        """Test CFR title validation."""
        # Arrange
        invalid_title_data = {
            "title_number": 51,  # Invalid, should be 1-50
            "title_name": "Invalid Title",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            CfrTitle(**invalid_title_data)

    def test_cfr_part_creation(self):
        """Test creating a CFR part model."""
        # Arrange
        part_data = {
            "part_number": 50,
            "part_name": "Wildlife and Fisheries Protection",
            "title_number": 40,
            "chapter_number": "I",
            "sections": [
                {
                    "section_number": "50.1",
                    "section_heading": "Definitions",
                    "section_content": "This section defines terms used in this part.",
                    "part_number": 50,
                    "title_number": 40
                }
            ],
            "source_reference": {
                "source": ApiSource.GOVINFO,
                "source_id": "title40-part50",
                "source_url": "https://www.govinfo.gov/app/details/CFR-2023-title40-vol1/CFR-2023-title40-vol1-part50"
            }
        }

        # Act
        part = CfrPart(**part_data)

        # Assert
        assert part.part_number == 50
        assert part.part_name == "Wildlife and Fisheries Protection"
        assert part.title_number == 40
        assert part.chapter_number == "I"
        assert len(part.sections) == 1
        assert part.sections[0].section_number == "50.1"

    def test_cfr_section_creation(self):
        """Test creating a CFR section model."""
        # Arrange
        section_data = {
            "section_number": "50.1",
            "section_heading": "Definitions",
            "section_content": "This section defines terms used in this part.",
            "part_number": 50,
            "title_number": 40,
            "source_reference": {
                "source": ApiSource.GOVINFO,
                "source_id": "title40-section50.1",
                "source_url": "https://www.govinfo.gov/app/details/CFR-2023-title40-vol1/CFR-2023-title40-vol1-sec50-1"
            }
        }

        # Act
        section = CfrSection(**section_data)

        # Assert
        assert section.section_number == "50.1"
        assert section.section_heading == "Definitions"
        assert section.part_number == 50
        assert section.title_number == 40


class TestCourtOpinionModels:
    """Tests for the Court Opinion models."""

    def test_court_type_enum(self):
        """Test the CourtType enum."""
        # Assert
        assert CourtType.SCOTUS.name == "SCOTUS"
        assert CourtType.CADC.name == "CADC"
        assert CourtType.CA1.name == "CA1"

    def test_court_opinion_creation(self):
        """Test creating a court opinion model."""
        # Arrange
        opinion_data = {
            "package_id": "USCOURTS-ca1-12-1234",
            "title": "Example Opinion Title",
            "court": CourtType.CA1,
            "docket_number": "12-1234",
            "date_issued": "2023-01-15",
            "source_reference": {
                "source": ApiSource.GOVINFO,
                "source_id": "USCOURTS-ca1-12-1234",
                "source_url": "https://www.govinfo.gov/app/details/USCOURTS-ca1-12-1234"
            },
            "content_urls": {
                "pdf": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/pdf/USCOURTS-ca1-12-1234.pdf",
                "xml": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/xml/USCOURTS-ca1-12-1234.xml",
                "html": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/html/USCOURTS-ca1-12-1234.htm"
            }
        }

        # Act
        opinion = CourtOpinion(**opinion_data)

        # Assert
        assert opinion.package_id == "USCOURTS-ca1-12-1234"
        assert opinion.title == "Example Opinion Title"
        assert opinion.court == CourtType.CA1
        assert opinion.docket_number == "12-1234"
        assert opinion.date_issued == "2023-01-15"
        assert opinion.content_urls["pdf"].endswith(".pdf")


class TestFederalRegisterModels:
    """Tests for the Federal Register models."""

    def test_federal_register_document_creation(self):
        """Test creating a Federal Register document model."""
        # Arrange
        fr_doc_data = {
            "document_number": "2023-12345",
            "title": "Environmental Protection Standards",
            "type": "Rule",
            "agency": "EPA",
            "publication_date": "2023-05-15",
            "effective_date": "2023-06-15",
            "cfr_references": [
                {
                    "title": 40,
                    "part": 50
                }
            ],
            "source_reference": {
                "source": ApiSource.GOVINFO,
                "source_id": "FR-2023-12345",
                "source_url": "https://www.govinfo.gov/app/details/FR-2023-12345"
            }
        }

        # Act
        fr_doc = FederalRegisterDocument(**fr_doc_data)

        # Assert
        assert fr_doc.document_number == "2023-12345"
        assert fr_doc.title == "Environmental Protection Standards"
        assert fr_doc.type == "Rule"
        assert fr_doc.agency == "EPA"
        assert fr_doc.publication_date == "2023-05-15"
        assert fr_doc.effective_date == "2023-06-15"
        assert len(fr_doc.cfr_references) == 1
        assert fr_doc.cfr_references[0]["title"] == 40


class TestRegulatoryProcessModels:
    """Tests for the Regulatory Process models."""

    def test_regulatory_process_creation(self):
        """Test creating a regulatory process model."""
        # Arrange
        process_data = {
            "process_id": "EPA-HQ-OAR-2023-0001",
            "title": "National Ambient Air Quality Standards Review",
            "agency": "EPA",
            "status": "Open",
            "start_date": "2023-01-10",
            "documents": [
                {
                    "document_number": "2023-12345",
                    "title": "Proposed Rule",
                    "type": "Proposed Rule",
                    "publication_date": "2023-01-15"
                }
            ],
            "cfr_impacts": [
                {
                    "title": 40,
                    "part": 50,
                    "impact_type": "Revision"
                }
            ],
            "source_reference": {
                "source": ApiSource.GOVINFO,
                "source_id": "EPA-HQ-OAR-2023-0001",
                "source_url": "https://www.regulations.gov/docket/EPA-HQ-OAR-2023-0001"
            }
        }

        # Act
        process = RegulatoryProcess(**process_data)

        # Assert
        assert process.process_id == "EPA-HQ-OAR-2023-0001"
        assert process.title == "National Ambient Air Quality Standards Review"
        assert process.agency == "EPA"
        assert process.status == "Open"
        assert process.start_date == "2023-01-10"
        assert len(process.documents) == 1
        assert process.documents[0]["title"] == "Proposed Rule"
        assert len(process.cfr_impacts) == 1
        assert process.cfr_impacts[0]["title"] == 40