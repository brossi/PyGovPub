"""
Test suite for document database models.

This module tests the SQLModel-based database models for document handling,
including document references and versions.
"""

import pytest
from datetime import date, datetime
from sqlmodel import Field, SQLModel, Session, create_engine, select
from typing import Optional, List

from pygovpub.models.documents import DocumentVersion, DocumentAuthentication, DocumentReference
from pygovpub.auth.models import ApiSource


def test_document_reference_model():
    """Test that the DocumentReference model works as expected."""
    # Create a DocumentReference instance
    doc_ref = DocumentReference(
        document_id="DOC123",
        document_type="bill",
        source_id="118-hr1",
        source_type="bill",
        source_system=ApiSource.GOVINFO.value,
        bill_id="118-hr1",
        pdf_url="https://example.com/doc.pdf",
        xml_url="https://example.com/doc.xml",
        html_url="https://example.com/doc.html"
    )
    
    # Check that the fields are set correctly
    assert doc_ref.document_id == "DOC123"
    assert doc_ref.document_type == "bill"
    assert doc_ref.source_id == "118-hr1"
    assert doc_ref.source_type == "bill"
    assert doc_ref.source_system == ApiSource.GOVINFO.value
    assert doc_ref.pdf_url == "https://example.com/doc.pdf"
    assert doc_ref.xml_url == "https://example.com/doc.xml"
    assert doc_ref.html_url == "https://example.com/doc.html"
    assert doc_ref.created_at is not None


def test_document_version_model():
    """Test that the DocumentVersion model works as expected."""
    # Create a DocumentVersion instance
    doc_version = DocumentVersion(
        version_id="DOC123-v1",
        document_id="DOC123",
        version_code="v1",
        published_date=date(2023, 1, 4),
        govinfo_package_id="BILLS-118hr1ih",
        pdf_url="https://example.com/doc-v1.pdf",
        xml_url="https://example.com/doc-v1.xml"
    )
    
    # Check that the fields are set correctly
    assert doc_version.version_id == "DOC123-v1"
    assert doc_version.document_id == "DOC123"
    assert doc_version.version_code == "v1"
    assert doc_version.published_date == date(2023, 1, 4)
    assert doc_version.govinfo_package_id == "BILLS-118hr1ih"
    assert doc_version.pdf_url == "https://example.com/doc-v1.pdf"
    assert doc_version.xml_url == "https://example.com/doc-v1.xml"
    assert doc_version.created_at is not None


def test_document_authentication_model():
    """Test that the DocumentAuthentication model works as expected."""
    # Create a DocumentAuthentication instance
    auth = DocumentAuthentication(
        authentication_id=1,
        document_id="DOC123",
        digital_signature="abc123signature",
        signature_verified=True,
        verification_date=datetime.now(),
        authentication_status="verified"
    )
    
    # Check that the fields are set correctly
    assert auth.authentication_id == 1
    assert auth.document_id == "DOC123"
    assert auth.digital_signature == "abc123signature"
    assert auth.signature_verified is True
    assert isinstance(auth.verification_date, datetime)
    assert auth.authentication_status == "verified"
    assert auth.created_at is not None


def test_document_relationships():
    """Test relationships between document models."""
    # Create an in-memory SQLite engine
    engine = create_engine("sqlite:///:memory:")
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    # Test creating related objects
    with Session(engine) as session:
        # Create a DocumentReference
        doc_ref = DocumentReference(
            document_id="DOC123",
            document_type="bill",
            source_id="118-hr1",
            source_type="bill",
            source_system=ApiSource.GOVINFO.value,
            pdf_url="https://example.com/doc.pdf",
            xml_url="https://example.com/doc.xml",
            html_url="https://example.com/doc.html"
        )
        session.add(doc_ref)
        
        # Create multiple DocumentVersions for the document
        version1 = DocumentVersion(
            version_id="DOC123-v1",
            document_id="DOC123",
            version_code="v1",
            published_date=date(2023, 1, 4),
            govinfo_package_id="BILLS-118hr1ih",
            pdf_url="https://example.com/doc-v1.pdf",
            xml_url="https://example.com/doc-v1.xml"
        )
        session.add(version1)
        
        version2 = DocumentVersion(
            version_id="DOC123-v2",
            document_id="DOC123",
            version_code="v2",
            published_date=date(2023, 1, 10),
            govinfo_package_id="BILLS-118hr1eh",
            pdf_url="https://example.com/doc-v2.pdf",
            xml_url="https://example.com/doc-v2.xml"
        )
        session.add(version2)
        
        # Create DocumentAuthentication for the document
        auth = DocumentAuthentication(
            document_id="DOC123",
            digital_signature="abc123signature",
            signature_verified=True,
            verification_date=datetime.now(),
            authentication_status="verified"
        )
        session.add(auth)
        
        session.commit()
        
        # Test querying relationships
        # Query document and check versions and authentication
        doc_query = select(DocumentReference).where(DocumentReference.document_id == "DOC123")
        result_doc = session.exec(doc_query).one()
        
        # Test relationship navigation from document to versions
        assert len(result_doc.versions) == 2
        
        # Test versions are sorted by published date
        assert result_doc.versions[0].published_date < result_doc.versions[1].published_date
        assert result_doc.versions[0].version_code == "v1"
        assert result_doc.versions[1].version_code == "v2"
        
        # Test relationship navigation from document to authentication
        assert result_doc.authentication is not None
        assert result_doc.authentication.signature_verified is True
        assert result_doc.authentication.authentication_status == "verified"
        
        # Test relationship from version to document
        version_query = select(DocumentVersion).where(DocumentVersion.version_id == "DOC123-v1")
        result_version = session.exec(version_query).one()
        assert result_version.document is not None
        assert result_version.document.document_id == "DOC123"
        assert result_version.document.document_type == "bill"


def test_bill_document_relationship():
    """Test relationship between Bill and DocumentReference models."""
    # Check relationship attributes exist
    from pygovpub.models.legislative_db import Bill
    
    # Create a Bill instance
    bill = Bill(
        bill_id="118-hr1",
        congress_id=118,
        bill_type="hr",
        bill_number=1,
        title="Test Bill",
        introduced_date=date(2023, 1, 4),
        status="introduced",
        last_action_date=date(2023, 1, 4),
        source_system="congress"
    )
    
    # Create a DocumentReference instance
    doc_ref = DocumentReference(
        document_id="DOC123",
        document_type="bill",
        source_id="118-hr1",
        source_type="bill",
        source_system=ApiSource.GOVINFO.value,
        bill_id="118-hr1",
        pdf_url="https://example.com/doc.pdf",
        xml_url="https://example.com/doc.xml",
        html_url="https://example.com/doc.html"
    )
    
    # Verify relationship attributes exist
    assert hasattr(bill, "documents")
    assert hasattr(doc_ref, "bill")
    
    # Just verify that attributes exist (we've already created instances successfully)
    # No further validation needed for the relationship type itself