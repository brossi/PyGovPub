"""
Test suite for legislative database models.

This module tests the SQLModel-based database models for legislative data.
"""

import pytest
from datetime import date, datetime
from sqlmodel import Field, SQLModel, Session, create_engine, select
from typing import Optional, List

from pygovpub.models.legislative_db import (
    Congress, Bill, BillVersion, BillAction, BillSponsor, 
    Committee, Member, DocumentReference
)
from pygovpub.auth.models import ApiSource


def test_congress_model():
    """Test that the Congress model works as expected."""
    # Create a Congress instance
    congress = Congress(
        congress_id=118,
        start_date=date(2023, 1, 3),
        end_date=date(2025, 1, 3)
    )
    
    # Check that the fields are set correctly
    assert congress.congress_id == 118
    assert congress.start_date == date(2023, 1, 3)
    assert congress.end_date == date(2025, 1, 3)
    assert congress.created_at is not None


def test_bill_model():
    """Test that the Bill model works as expected."""
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
    
    # Check that the fields are set correctly
    assert bill.bill_id == "118-hr1"
    assert bill.congress_id == 118
    assert bill.bill_type == "hr"
    assert bill.bill_number == 1
    assert bill.title == "Test Bill"
    assert bill.introduced_date == date(2023, 1, 4)
    assert bill.status == "introduced"
    assert bill.last_action_date == date(2023, 1, 4)
    assert bill.source_system == "congress"
    assert bill.created_at is not None
    assert bill.updated_at is not None


def test_bill_version_model():
    """Test that the BillVersion model works as expected."""
    # Create a BillVersion instance
    version = BillVersion(
        version_id="118-hr1-ih",
        bill_id="118-hr1",
        version_code="ih",
        published_date=date(2023, 1, 4),
        govinfo_package_id="BILLS-118hr1ih"
    )
    
    # Check that the fields are set correctly
    assert version.version_id == "118-hr1-ih"
    assert version.bill_id == "118-hr1"
    assert version.version_code == "ih"
    assert version.published_date == date(2023, 1, 4)
    assert version.govinfo_package_id == "BILLS-118hr1ih"
    assert version.created_at is not None


def test_bill_action_model():
    """Test that the BillAction model works as expected."""
    # Create a BillAction instance
    action = BillAction(
        bill_id="118-hr1",
        action_date=date(2023, 1, 4),
        action_text="Introduced in House",
        action_type="introduced",
        chamber="house"
    )
    
    # Check that the fields are set correctly
    assert action.bill_id == "118-hr1"
    assert action.action_date == date(2023, 1, 4)
    assert action.action_text == "Introduced in House"
    assert action.action_type == "introduced"
    assert action.chamber == "house"
    assert action.created_at is not None


def test_bill_sponsor_model():
    """Test that the BillSponsor model works as expected."""
    # Create a BillSponsor instance
    sponsor = BillSponsor(
        bill_id="118-hr1",
        bioguide_id="A000001",
        sponsor_type="sponsor",
        sponsor_date=date(2023, 1, 4)
    )
    
    # Check that the fields are set correctly
    assert sponsor.bill_id == "118-hr1"
    assert sponsor.bioguide_id == "A000001"
    assert sponsor.sponsor_type == "sponsor"
    assert sponsor.sponsor_date == date(2023, 1, 4)
    assert sponsor.created_at is not None


def test_committee_model():
    """Test that the Committee model works as expected."""
    # Create a Committee instance
    committee = Committee(
        committee_id="HSJU",
        congress_id=118,
        name="Committee on the Judiciary",
        chamber="house"
    )
    
    # Check that the fields are set correctly
    assert committee.committee_id == "HSJU"
    assert committee.congress_id == 118
    assert committee.name == "Committee on the Judiciary"
    assert committee.chamber == "house"
    assert committee.created_at is not None
    assert committee.updated_at is not None


def test_member_model():
    """Test that the Member model works as expected."""
    # Create a Member instance
    member = Member(
        bioguide_id="A000001",
        first_name="John",
        last_name="Smith",
        state="NY",
        party="Democrat",
        active=True
    )
    
    # Check that the fields are set correctly
    assert member.bioguide_id == "A000001"
    assert member.first_name == "John"
    assert member.last_name == "Smith"
    assert member.state == "NY"
    assert member.party == "Democrat"
    assert member.active is True
    assert member.created_at is not None
    assert member.updated_at is not None


def test_document_reference_model():
    """Test that the DocumentReference model works as expected."""
    # Create a DocumentReference instance
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


def test_relationships():
    """Test relationships between models."""
    # Create an in-memory SQLite engine
    engine = create_engine("sqlite:///:memory:")
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    # Test creating related objects
    with Session(engine) as session:
        # Create a Congress
        congress = Congress(
            congress_id=118,
            start_date=date(2023, 1, 3),
            end_date=date(2025, 1, 3)
        )
        session.add(congress)
        
        # Create a Bill linked to the Congress
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
        session.add(bill)
        
        # Create a BillVersion linked to the Bill
        version = BillVersion(
            version_id="118-hr1-ih",
            bill_id="118-hr1",
            version_code="ih",
            published_date=date(2023, 1, 4),
            govinfo_package_id="BILLS-118hr1ih"
        )
        session.add(version)
        
        # Create a Member
        member = Member(
            bioguide_id="A000001",
            first_name="John",
            last_name="Smith",
            state="NY",
            party="Democrat",
            active=True
        )
        session.add(member)
        
        # Create a BillSponsor linking the Bill and Member
        sponsor = BillSponsor(
            bill_id="118-hr1",
            bioguide_id="A000001",
            sponsor_type="sponsor",
            sponsor_date=date(2023, 1, 4)
        )
        session.add(sponsor)
        
        # Create a Committee
        committee = Committee(
            committee_id="HSJU",
            congress_id=118,
            name="Committee on the Judiciary",
            chamber="house"
        )
        session.add(committee)
        
        # Create a BillAction linking the Bill and Committee
        action = BillAction(
            bill_id="118-hr1",
            action_date=date(2023, 1, 5),
            action_text="Referred to the Committee on the Judiciary",
            action_type="referral",
            chamber="house",
            committee_id="HSJU"
        )
        session.add(action)
        
        session.commit()
        
        # Test querying relationships
        # Query bill and check versions
        bill_query = select(Bill).where(Bill.bill_id == "118-hr1")
        result_bill = session.exec(bill_query).one()
        
        # Test relationship navigation from bill to versions
        assert len(result_bill.versions) == 1
        assert result_bill.versions[0].version_code == "ih"
        
        # Test relationship navigation from bill to sponsors
        assert len(result_bill.sponsors) == 1
        assert result_bill.sponsors[0].bioguide_id == "A000001"
        
        # Test relationship navigation from bill to actions
        assert len(result_bill.actions) == 1
        assert result_bill.actions[0].action_text == "Referred to the Committee on the Judiciary"
        
        # Test relationship navigation from congress to bills
        congress_query = select(Congress).where(Congress.congress_id == 118)
        result_congress = session.exec(congress_query).one()
        assert len(result_congress.bills) == 1
        assert result_congress.bills[0].bill_id == "118-hr1"
        
        # Test relationship navigation from member to sponsored bills
        member_query = select(Member).where(Member.bioguide_id == "A000001")
        result_member = session.exec(member_query).one()
        assert len(result_member.sponsored_bills) == 1
        assert result_member.sponsored_bills[0].bill_id == "118-hr1"