"""
Tests for legislative data models.

This module tests the Pydantic models used for legislative data types
such as bills, amendments, committees, and members.
"""

import pytest
from datetime import date, datetime
from pydantic import ValidationError, HttpUrl

from pygovpub.auth.models import ApiSource
from pygovpub.models.legislative import (
    Bill, 
    BillStatus, 
    BillType, 
    BillVersion, 
    BillVersionCode,
    BillAction,
    BillSponsor,
    BillSummary,
    Chamber,
    Committee,
    Member,
    PolicyArea,
    SourceReference
)


class TestSourceReference:
    """Tests for SourceReference model."""
    
    def test_create_source_reference(self):
        """Test creation of a source reference."""
        source_ref = SourceReference(
            source=ApiSource.CONGRESS,
            source_id="HR117-1234",
            source_url="https://api.congress.gov/v3/bill/117/hr/1234",
            last_updated=datetime(2023, 5, 15)
        )
        
        assert source_ref.source == ApiSource.CONGRESS
        assert source_ref.source_id == "HR117-1234"
        assert str(source_ref.source_url) == "https://api.congress.gov/v3/bill/117/hr/1234"
        assert source_ref.last_updated == datetime(2023, 5, 15)
    
    def test_create_minimal_source_reference(self):
        """Test creation with minimal fields."""
        source_ref = SourceReference(
            source=ApiSource.GOVINFO,
            source_id="BILLS-117hr1234ih"
        )
        
        assert source_ref.source == ApiSource.GOVINFO
        assert source_ref.source_id == "BILLS-117hr1234ih"
        assert source_ref.source_url is None
        assert source_ref.last_updated is None


class TestBill:
    """Tests for Bill model."""
    
    def test_create_bill(self):
        """Test creation of a bill."""
        source_ref = SourceReference(
            source=ApiSource.CONGRESS,
            source_id="HR117-1234"
        )
        
        bill = Bill(
            bill_id="hr117-1234",
            congress=117,
            bill_type=BillType.HOUSE_BILL,
            bill_number=1234,
            title="Test Bill Title",
            introduced_date=date(2023, 1, 15),
            latest_action_date=date(2023, 5, 1),
            status=BillStatus.INTRODUCED,
            origin_chamber=Chamber.HOUSE,
            source_reference=source_ref
        )
        
        assert bill.bill_id == "hr117-1234"
        assert bill.congress == 117
        assert bill.bill_type == BillType.HOUSE_BILL
        assert bill.bill_number == 1234
        assert bill.title == "Test Bill Title"
        assert bill.introduced_date == date(2023, 1, 15)
        assert bill.status == BillStatus.INTRODUCED
        assert bill.origin_chamber == Chamber.HOUSE
        assert bill.source_reference == source_ref
        assert bill.cosponsors == []
        assert bill.versions == []
        assert bill.actions == []
    
    def test_bill_with_sponsor(self):
        """Test creation of a bill with sponsor."""
        source_ref = SourceReference(
            source=ApiSource.CONGRESS,
            source_id="HR117-1234"
        )
        
        sponsor = BillSponsor(
            bioguide_id="S000148",
            full_name="Bernie Sanders",
            first_name="Bernie",
            last_name="Sanders",
            party="Independent",
            state="VT",
            sponsor_date=date(2023, 1, 15)
        )
        
        bill = Bill(
            bill_id="s117-1234",
            congress=117,
            bill_type=BillType.SENATE_BILL,
            bill_number=1234,
            title="Test Senate Bill",
            origin_chamber=Chamber.SENATE,
            sponsor=sponsor,
            source_reference=source_ref
        )
        
        assert bill.sponsor == sponsor
        assert bill.sponsor.bioguide_id == "S000148"
        assert bill.sponsor.full_name == "Bernie Sanders"
        assert bill.sponsor.party == "Independent"
    
    def test_bill_with_versions(self):
        """Test creation of a bill with versions."""
        source_ref = SourceReference(
            source=ApiSource.CONGRESS,
            source_id="HR117-1234"
        )
        
        version1 = BillVersion(
            version_code=BillVersionCode.INTRODUCED_HOUSE,
            version_name="Introduced in House",
            publish_date=date(2023, 1, 15),
            govinfo_package_id="BILLS-117hr1234ih",
            pdf_url="https://api.govinfo.gov/packages/BILLS-117hr1234ih/pdf"
        )
        
        version2 = BillVersion(
            version_code=BillVersionCode.REPORTED_HOUSE,
            version_name="Reported in House",
            publish_date=date(2023, 2, 20),
            govinfo_package_id="BILLS-117hr1234rh",
            pdf_url="https://api.govinfo.gov/packages/BILLS-117hr1234rh/pdf"
        )
        
        bill = Bill(
            bill_id="hr117-1234",
            congress=117,
            bill_type=BillType.HOUSE_BILL,
            bill_number=1234,
            title="Test Bill Title",
            origin_chamber=Chamber.HOUSE,
            versions=[version1, version2],
            source_reference=source_ref
        )
        
        assert len(bill.versions) == 2
        assert bill.versions[0].version_code == BillVersionCode.INTRODUCED_HOUSE
        assert bill.versions[0].publish_date == date(2023, 1, 15)
        assert bill.versions[1].version_code == BillVersionCode.REPORTED_HOUSE
        assert bill.versions[1].publish_date == date(2023, 2, 20)
    
    def test_bill_validation(self):
        """Test validation of required bill fields."""
        source_ref = SourceReference(
            source=ApiSource.CONGRESS,
            source_id="HR117-1234"
        )
        
        # Missing required fields
        with pytest.raises(ValidationError):
            Bill(
                bill_id="hr117-1234",
                congress=117,
                # Missing bill_type
                bill_number=1234,
                title="Test Bill Title",
                origin_chamber=Chamber.HOUSE,
                source_reference=source_ref
            )
            
        # Invalid bill_type
        with pytest.raises(ValidationError):
            Bill(
                bill_id="hr117-1234",
                congress=117,
                bill_type="invalid_type",  # Invalid type
                bill_number=1234,
                title="Test Bill Title",
                origin_chamber=Chamber.HOUSE,
                source_reference=source_ref
            )
            
        # Invalid chamber
        with pytest.raises(ValidationError):
            Bill(
                bill_id="hr117-1234",
                congress=117,
                bill_type=BillType.HOUSE_BILL,
                bill_number=1234,
                title="Test Bill Title",
                origin_chamber="invalid_chamber",  # Invalid chamber
                source_reference=source_ref
            )


class TestMember:
    """Tests for Member model."""
    
    def test_create_member(self):
        """Test creation of a member."""
        source_ref = SourceReference(
            source=ApiSource.CONGRESS,
            source_id="S000148"
        )
        
        member = Member(
            bioguide_id="S000148",
            first_name="Bernie",
            last_name="Sanders",
            full_name="Bernard Sanders",
            state="VT",
            party="Independent",
            chamber=Chamber.SENATE,
            term_start=date(2019, 1, 3),
            term_end=date(2024, 1, 3),
            birth_year=1941,
            official_url="https://www.sanders.senate.gov/",
            source_reference=source_ref
        )
        
        assert member.bioguide_id == "S000148"
        assert member.first_name == "Bernie"
        assert member.last_name == "Sanders"
        assert member.full_name == "Bernard Sanders"
        assert member.state == "VT"
        assert member.party == "Independent"
        assert member.chamber == Chamber.SENATE
        assert member.term_start == date(2019, 1, 3)
        assert member.term_end == date(2024, 1, 3)
        assert member.birth_year == 1941
        assert str(member.official_url) == "https://www.sanders.senate.gov/"
        assert member.source_reference == source_ref
        assert member.is_active is True
    
    def test_member_validation(self):
        """Test validation of required member fields."""
        source_ref = SourceReference(
            source=ApiSource.CONGRESS,
            source_id="S000148"
        )
        
        # Missing required fields
        with pytest.raises(ValidationError):
            Member(
                bioguide_id="S000148",
                # Missing first_name
                last_name="Sanders",
                state="VT",
                party="Independent",
                source_reference=source_ref
            )


class TestCommittee:
    """Tests for Committee model."""
    
    def test_create_committee(self):
        """Test creation of a committee."""
        source_ref = SourceReference(
            source=ApiSource.CONGRESS,
            source_id="hspw00"
        )
        
        committee = Committee(
            committee_id="hspw00",
            name="House Transportation and Infrastructure Committee",
            chamber=Chamber.HOUSE,
            committee_type="Standing",
            is_current=True,
            congress=117,
            source_reference=source_ref
        )
        
        assert committee.committee_id == "hspw00"
        assert committee.name == "House Transportation and Infrastructure Committee"
        assert committee.chamber == Chamber.HOUSE
        assert committee.committee_type == "Standing"
        assert committee.is_current is True
        assert committee.congress == 117
        assert committee.source_reference == source_ref
        assert committee.subcommittees == []
    
    def test_create_subcommittee(self):
        """Test creation of a subcommittee."""
        source_ref = SourceReference(
            source=ApiSource.CONGRESS,
            source_id="hspw01"
        )
        
        subcommittee = Committee(
            committee_id="hspw01",
            name="Subcommittee on Aviation",
            chamber=Chamber.HOUSE,
            parent_committee_id="hspw00",
            committee_type="Standing",
            is_current=True,
            congress=117,
            source_reference=source_ref
        )
        
        assert subcommittee.committee_id == "hspw01"
        assert subcommittee.parent_committee_id == "hspw00"
        assert subcommittee.name == "Subcommittee on Aviation"
        assert subcommittee.chamber == Chamber.HOUSE