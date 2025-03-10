"""
Test suite for member and vote database models.

This module tests the SQLModel-based database models for congressional members,
roles, and voting data.
"""

import pytest
from datetime import date, datetime
from sqlmodel import Field, SQLModel, Session, create_engine, select
from typing import Optional, List

from pygovpub.models.members import Member, Role, Vote, CommitteeMember
from pygovpub.auth.models import ApiSource


def test_member_model():
    """Test that the Member model works as expected."""
    # Create a Member instance (already tested in test_legislative_db_models.py)
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


def test_role_model():
    """Test that the Role model works as expected."""
    # Create a Role instance
    role = Role(
        role_id="A000001-118",
        bioguide_id="A000001",
        congress_id=118,
        chamber="house",
        state="NY",
        district="1",
        party="Democrat",
        leadership_title="Speaker",
        start_date=date(2023, 1, 3),
        end_date=date(2025, 1, 3)
    )
    
    # Check that the fields are set correctly
    assert role.role_id == "A000001-118"
    assert role.bioguide_id == "A000001"
    assert role.congress_id == 118
    assert role.chamber == "house"
    assert role.state == "NY"
    assert role.district == "1"
    assert role.party == "Democrat"
    assert role.leadership_title == "Speaker"
    assert role.start_date == date(2023, 1, 3)
    assert role.end_date == date(2025, 1, 3)
    assert role.created_at is not None


def test_vote_model():
    """Test that the Vote model works as expected."""
    # Create a Vote instance
    vote = Vote(
        vote_id="118-house-vote1",
        congress_id=118,
        chamber="house",
        vote_number=1,
        vote_date=date(2023, 1, 5),
        question="On Passage of the Bill",
        vote_type="roll_call",
        bill_id="118-hr1",
        result="passed"
    )
    
    # Check that the fields are set correctly
    assert vote.vote_id == "118-house-vote1"
    assert vote.congress_id == 118
    assert vote.chamber == "house"
    assert vote.vote_number == 1
    assert vote.vote_date == date(2023, 1, 5)
    assert vote.question == "On Passage of the Bill"
    assert vote.vote_type == "roll_call"
    assert vote.bill_id == "118-hr1"
    assert vote.result == "passed"
    assert vote.created_at is not None


def test_committee_member_model():
    """Test that the CommitteeMember model works as expected."""
    # Create a CommitteeMember instance
    committee_member = CommitteeMember(
        committee_id="HSJU",
        bioguide_id="A000001",
        role="Chair",
        start_date=date(2023, 1, 3),
        end_date=date(2025, 1, 3)
    )
    
    # Check that the fields are set correctly
    assert committee_member.committee_id == "HSJU"
    assert committee_member.bioguide_id == "A000001"
    assert committee_member.role == "Chair"
    assert committee_member.start_date == date(2023, 1, 3)
    assert committee_member.end_date == date(2025, 1, 3)
    assert committee_member.created_at is not None


def test_member_role_relationship():
    """Test relationship between Member and Role models."""
    # Create an in-memory SQLite engine
    engine = create_engine("sqlite:///:memory:")
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    # Test creating related objects
    with Session(engine) as session:
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
        
        # Create multiple roles for the member
        role1 = Role(
            role_id="A000001-117",
            bioguide_id="A000001",
            congress_id=117,
            chamber="house",
            state="NY",
            district="1",
            party="Democrat",
            start_date=date(2021, 1, 3),
            end_date=date(2023, 1, 3)
        )
        session.add(role1)
        
        role2 = Role(
            role_id="A000001-118",
            bioguide_id="A000001",
            congress_id=118,
            chamber="house",
            state="NY",
            district="1",
            party="Democrat",
            leadership_title="Speaker",
            start_date=date(2023, 1, 3),
            end_date=date(2025, 1, 3)
        )
        session.add(role2)
        
        session.commit()
        
        # Test querying relationships
        # Query member and check roles
        member_query = select(Member).where(Member.bioguide_id == "A000001")
        result_member = session.exec(member_query).one()
        
        # Test relationship navigation from member to roles
        assert len(result_member.roles) == 2
        
        # Check that roles are sorted chronologically
        assert result_member.roles[0].congress_id == 117
        assert result_member.roles[1].congress_id == 118
        
        # Check that the leadership role is correctly stored
        assert any(r.leadership_title == "Speaker" for r in result_member.roles)


def test_member_vote_relationship():
    """Test relationship between Member, Vote, and MemberVote models."""
    # Create an in-memory SQLite engine
    engine = create_engine("sqlite:///:memory:")
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    # Test creating related objects
    with Session(engine) as session:
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
        
        # Create a Vote
        vote = Vote(
            vote_id="118-house-vote1",
            congress_id=118,
            chamber="house",
            vote_number=1,
            vote_date=date(2023, 1, 5),
            question="On Passage of the Bill",
            vote_type="roll_call",
            bill_id="118-hr1",
            result="passed"
        )
        session.add(vote)
        
        # Create a MemberVote (link table with additional fields)
        from pygovpub.models.members import MemberVote
        member_vote = MemberVote(
            vote_id="118-house-vote1",
            bioguide_id="A000001",
            vote_position="Yea",
            vote_cast_time=datetime.now()
        )
        session.add(member_vote)
        
        session.commit()
        
        # Test querying relationships
        # Query member and check votes
        member_query = select(Member).where(Member.bioguide_id == "A000001")
        result_member = session.exec(member_query).one()
        
        # Test relationship navigation from member to votes
        assert len(result_member.votes) == 1
        assert result_member.votes[0].vote_id == "118-house-vote1"
        
        # Check the vote position from the link table
        assert result_member.member_votes[0].vote_position == "Yea"
        
        # Query vote and check members
        vote_query = select(Vote).where(Vote.vote_id == "118-house-vote1")
        result_vote = session.exec(vote_query).one()
        
        # Test relationship navigation from vote to members
        assert len(result_vote.members) == 1
        assert result_vote.members[0].bioguide_id == "A000001"
        
        # Check the vote position from the link table
        assert result_vote.member_votes[0].vote_position == "Yea"


def test_committee_membership_relationship():
    """Test relationship between committees and members."""
    # Create an in-memory SQLite engine
    engine = create_engine("sqlite:///:memory:")
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    # Test creating related objects
    with Session(engine) as session:
        # Create a Committee
        from pygovpub.models.legislative_db import Committee
        committee = Committee(
            committee_id="HSJU",
            congress_id=118,
            name="Committee on the Judiciary",
            chamber="house"
        )
        session.add(committee)
        
        # Create Members
        member1 = Member(
            bioguide_id="A000001",
            first_name="John",
            last_name="Smith",
            state="NY",
            party="Democrat",
            active=True
        )
        session.add(member1)
        
        member2 = Member(
            bioguide_id="B000001",
            first_name="Jane",
            last_name="Doe",
            state="CA",
            party="Republican",
            active=True
        )
        session.add(member2)
        
        # Create CommitteeMember links
        cm1 = CommitteeMember(
            committee_id="HSJU",
            bioguide_id="A000001",
            role="Chair",
            start_date=date(2023, 1, 3)
        )
        session.add(cm1)
        
        cm2 = CommitteeMember(
            committee_id="HSJU",
            bioguide_id="B000001",
            role="Ranking Member",
            start_date=date(2023, 1, 3)
        )
        session.add(cm2)
        
        session.commit()
        
        # Test querying relationships
        # Query committee and check members
        committee_query = select(Committee).where(Committee.committee_id == "HSJU")
        result_committee = session.exec(committee_query).one()
        
        # Test relationship navigation from committee to members
        assert len(result_committee.members) == 2
        
        # Check committee roles
        committee_roles = {cm.bioguide_id: cm.role for cm in result_committee.committee_members}
        assert committee_roles["A000001"] == "Chair"
        assert committee_roles["B000001"] == "Ranking Member"
        
        # Query member and check committees
        member_query = select(Member).where(Member.bioguide_id == "A000001")
        result_member = session.exec(member_query).one()
        
        # Test relationship navigation from member to committees
        assert len(result_member.committees) == 1
        assert result_member.committees[0].committee_id == "HSJU"
        
        # Check member's role in the committee
        assert result_member.committee_memberships[0].role == "Chair"