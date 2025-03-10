"""
Unit tests for the Congress.gov API client.
"""

import asyncio
import json
from datetime import date, datetime
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from pygovpub.api.clients.congress import CongressClient
from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import ApiError, CongressApiError, GovInfoApiError, AuthenticationError, RateLimitExceededError
from pygovpub.models.legislative import (
    Bill, BillAction, BillSponsor, BillVersion, BillVersionCode, Chamber,
    Committee, Member, PolicyArea, SourceReference
)


class TestCongressClient:
    """Tests for the Congress.gov API client."""
    
    @pytest.fixture
    def mock_auth_manager(self):
        """Create a mock auth manager."""
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.execute_request = AsyncMock()
        return auth_manager
    
    @pytest.fixture
    def client(self, mock_auth_manager):
        """Create a client with mock auth manager."""
        return CongressClient(auth_manager=mock_auth_manager)
    
    @pytest.fixture
    def mock_bill_response(self):
        """Create a mock bill response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/bill/117/hr/1234"
            },
            "results": [
                {
                    "congress": 117,
                    "type": "hr",
                    "number": 1234,
                    "title": "Test Bill",
                    "shortTitle": "Test Bill Short Title",
                    "introducedDate": "2023-01-15",
                    "updateDate": "2023-02-01",
                    "originChamber": "House",
                    "latestAction": {
                        "actionDate": "2023-01-20",
                        "text": "Referred to Committee"
                    },
                    "sponsors": [
                        {
                            "bioguideId": "A000001",
                            "fullName": "Representative Test Person",
                            "firstName": "Test",
                            "lastName": "Person",
                            "party": "D",
                            "state": "CA",
                            "district": "1",
                            "sponsorshipDate": "2023-01-15"
                        }
                    ],
                    "policyArea": {
                        "name": "Health",
                        "code": "HEA"
                    },
                    "actions": [
                        {
                            "actionDate": "2023-01-15",
                            "text": "Introduced in House",
                            "chamber": "House",
                            "actionCode": "I",
                            "type": "IntroReferral"
                        },
                        {
                            "actionDate": "2023-01-20",
                            "text": "Referred to Committee",
                            "chamber": "House",
                            "actionCode": "RH",
                            "type": "IntroReferral"
                        }
                    ]
                }
            ]
        }
    
    @pytest.fixture
    def mock_bill_search_response(self):
        """Create a mock bill search response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/bill?query=health"
            },
            "pagination": {
                "count": 2,
                "next": None
            },
            "results": [
                {
                    "congress": 117,
                    "type": "hr",
                    "number": 1234,
                    "title": "Health Bill 1",
                    "introducedDate": "2023-01-15",
                    "updateDate": "2023-02-01",
                    "originChamber": "House",
                    "latestAction": {
                        "actionDate": "2023-01-20",
                        "text": "Referred to Committee"
                    }
                },
                {
                    "congress": 117,
                    "type": "s",
                    "number": 5678,
                    "title": "Health Bill 2",
                    "introducedDate": "2023-02-10",
                    "updateDate": "2023-02-15",
                    "originChamber": "Senate",
                    "latestAction": {
                        "actionDate": "2023-02-10",
                        "text": "Introduced in Senate"
                    }
                }
            ]
        }
    
    @pytest.fixture
    def mock_bill_actions_response(self):
        """Create a mock bill actions response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/bill/117/hr/1234/actions"
            },
            "results": [
                {
                    "actions": [
                        {
                            "actionDate": "2023-01-15",
                            "text": "Introduced in House",
                            "chamber": "House",
                            "actionCode": "I",
                            "type": "IntroReferral"
                        },
                        {
                            "actionDate": "2023-01-20",
                            "text": "Referred to Committee",
                            "chamber": "House",
                            "actionCode": "RH",
                            "type": "IntroReferral"
                        }
                    ]
                }
            ]
        }
    
    @pytest.fixture
    def mock_bill_cosponsors_response(self):
        """Create a mock bill cosponsors response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/bill/117/hr/1234/cosponsors"
            },
            "results": [
                {
                    "cosponsors": [
                        {
                            "bioguideId": "B000001",
                            "fullName": "Representative Test Cosponsor",
                            "firstName": "Test",
                            "lastName": "Cosponsor",
                            "party": "R",
                            "state": "TX",
                            "district": "2",
                            "sponsorshipDate": "2023-01-20"
                        },
                        {
                            "bioguideId": "C000001",
                            "fullName": "Representative Another Cosponsor",
                            "firstName": "Another",
                            "lastName": "Cosponsor",
                            "party": "D",
                            "state": "CA",
                            "district": "3",
                            "sponsorshipDate": "2023-01-21"
                        }
                    ]
                }
            ]
        }
    
    @pytest.fixture
    def mock_bill_subjects_response(self):
        """Create a mock bill subjects response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/bill/117/hr/1234/subjects"
            },
            "results": [
                {
                    "subjects": [
                        {"name": "Health"},
                        {"name": "Public health"},
                        {"name": "Medicare"}
                    ]
                }
            ]
        }
    
    @pytest.fixture
    def mock_bill_versions_response(self):
        """Create a mock bill versions response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/bill/117/hr/1234/text"
            },
            "results": [
                {
                    "textVersions": [
                        {
                            "type": "ih",
                            "typeName": "Introduced in House",
                            "date": "2023-01-15",
                            "formats": {
                                "pdf": {
                                    "url": "https://www.congress.gov/bill/117/hr/1234/text.pdf",
                                    "packageId": "BILLS-117hr1234ih"
                                },
                                "xml": {
                                    "url": "https://www.congress.gov/bill/117/hr/1234/text.xml"
                                },
                                "html": {
                                    "url": "https://www.congress.gov/bill/117/hr/1234/text.html"
                                }
                            }
                        },
                        {
                            "type": "rh",
                            "typeName": "Reported in House",
                            "date": "2023-02-15",
                            "formats": {
                                "pdf": {
                                    "url": "https://www.congress.gov/bill/117/hr/1234/text-reported.pdf",
                                    "packageId": "BILLS-117hr1234rh"
                                },
                                "xml": {
                                    "url": "https://www.congress.gov/bill/117/hr/1234/text-reported.xml"
                                },
                                "html": {
                                    "url": "https://www.congress.gov/bill/117/hr/1234/text-reported.html"
                                }
                            }
                        }
                    ]
                }
            ]
        }
    
    @pytest.fixture
    def mock_committees_response(self):
        """Create a mock committees response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/committee/117"
            },
            "results": [
                {
                    "congress": 117,
                    "chamber": "House",
                    "systemCode": "AG",
                    "name": "Committee on Agriculture",
                    "type": "standing",
                    "updateDate": "2023-02-01"
                },
                {
                    "congress": 117,
                    "chamber": "Senate",
                    "systemCode": "BU",
                    "name": "Committee on Budget",
                    "type": "standing",
                    "updateDate": "2023-02-01"
                }
            ]
        }
    
    @pytest.fixture
    def mock_member_response(self):
        """Create a mock member response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/member/A000001"
            },
            "results": [
                {
                    "bioguideId": "A000001",
                    "firstName": "Test",
                    "lastName": "Person",
                    "fullName": "Representative Test Person",
                    "state": "CA",
                    "party": "D",
                    "chamber": "House",
                    "district": "1",
                    "termStart": "2023-01-03",
                    "termEnd": "2025-01-03",
                    "updateDate": "2023-02-01",
                    "birthYear": 1970,
                    "officialUrl": "https://testperson.house.gov",
                    "terms": [
                        {
                            "congress": 118,
                            "chamber": "House",
                            "state": "CA",
                            "district": "1",
                            "party": "D",
                            "startDate": "2023-01-03",
                            "endDate": "2025-01-03"
                        },
                        {
                            "congress": 117,
                            "chamber": "House",
                            "state": "CA",
                            "district": "1",
                            "party": "D",
                            "startDate": "2021-01-03",
                            "endDate": "2023-01-03"
                        }
                    ]
                }
            ]
        }
    
    @pytest.fixture
    def mock_members_response(self):
        """Create a mock members response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/member/117"
            },
            "results": [
                {
                    "bioguideId": "A000001",
                    "firstName": "Test",
                    "lastName": "Person",
                    "fullName": "Representative Test Person",
                    "state": "CA",
                    "party": "D",
                    "chamber": "House",
                    "district": "1",
                    "updateDate": "2023-02-01"
                },
                {
                    "bioguideId": "B000002",
                    "firstName": "Another",
                    "lastName": "Member",
                    "fullName": "Senator Another Member",
                    "state": "NY",
                    "party": "R",
                    "chamber": "Senate",
                    "updateDate": "2023-02-01"
                }
            ]
        }
    
    @pytest.fixture
    def mock_member_legislation_response(self):
        """Create a mock member sponsored legislation response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/member/A000001/sponsored-legislation/117"
            },
            "pagination": {
                "count": 2,
                "next": None
            },
            "results": [
                {
                    "congress": 117,
                    "type": "hr",
                    "number": 1234,
                    "title": "Health Bill 1",
                    "introducedDate": "2023-01-15",
                    "updateDate": "2023-02-01",
                    "originChamber": "House"
                },
                {
                    "congress": 117,
                    "type": "hr",
                    "number": 5678,
                    "title": "Education Bill",
                    "introducedDate": "2023-02-10",
                    "updateDate": "2023-02-15",
                    "originChamber": "House"
                }
            ]
        }
    
    @pytest.fixture
    def mock_committee_response(self):
        """Create a mock committee response."""
        return {
            "request": {
                "url": "https://api.congress.gov/v3/committee/117/house/AG"
            },
            "results": [
                {
                    "congress": 117,
                    "chamber": "House",
                    "systemCode": "AG",
                    "name": "Committee on Agriculture",
                    "type": "standing",
                    "updateDate": "2023-02-01",
                    "subcommittees": [
                        {
                            "systemCode": "AG01",
                            "name": "Subcommittee on Nutrition"
                        },
                        {
                            "systemCode": "AG02",
                            "name": "Subcommittee on Commodity Markets"
                        }
                    ]
                }
            ]
        }
    
    async def test_get_bill(self, client, mock_auth_manager, mock_bill_response):
        """Test getting a bill."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_bill_response
        
        # Call the method under test
        bill = await client.get_bill(congress=117, bill_type="hr", bill_number=1234)
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/bill/117/hr/1234",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned object is correct
        assert isinstance(bill, Bill)
        assert bill.bill_id == "hr1234"
        assert bill.congress == 117
        assert bill.bill_type == "hr"
        assert bill.bill_number == 1234
        assert bill.title == "Test Bill"
        assert bill.short_title == "Test Bill Short Title"
        assert bill.introduced_date == date(2023, 1, 15)
        assert bill.latest_action_date == date(2023, 1, 20)
        assert bill.origin_chamber == Chamber.HOUSE
        
        # Verify sponsor
        assert bill.sponsor is not None
        assert bill.sponsor.bioguide_id == "A000001"
        assert bill.sponsor.full_name == "Representative Test Person"
        
        # Verify policy area
        assert bill.policy_area is not None
        assert bill.policy_area.name == "Health"
        assert bill.policy_area.code == "HEA"
        
        # Verify actions
        assert len(bill.actions) == 2
        assert bill.actions[0].action_date == date(2023, 1, 15)
        assert bill.actions[0].text == "Introduced in House"
        assert bill.actions[1].chamber == Chamber.HOUSE
        
        # Verify source reference
        assert bill.source_reference.source == ApiSource.CONGRESS
        assert bill.source_reference.source_id == "117/hr/1234"
    
    async def test_search_bills(self, client, mock_auth_manager, mock_bill_search_response):
        """Test searching bills."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_bill_search_response
        
        # Call the method under test
        results = await client.search_bills(query="health", congress=117, limit=10, offset=0)
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/bill/117",
            method="GET",
            params={"query": "health", "limit": 10, "offset": 0},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned object is correct
        assert "bills" in results
        assert "pagination" in results
        assert len(results["bills"]) == 2
        assert results["pagination"]["count"] == 2
        
        # Verify first bill
        bill1 = results["bills"][0]
        assert isinstance(bill1, Bill)
        assert bill1.bill_id == "hr1234"
        assert bill1.title == "Health Bill 1"
        assert bill1.origin_chamber == Chamber.HOUSE
        
        # Verify second bill
        bill2 = results["bills"][1]
        assert isinstance(bill2, Bill)
        assert bill2.bill_id == "s5678"
        assert bill2.title == "Health Bill 2"
        assert bill2.origin_chamber == Chamber.SENATE
        
    async def test_search_bills_without_optional_params(self, client, mock_auth_manager, mock_bill_search_response):
        """Test searching bills without optional parameters."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_bill_search_response
        
        # Call the method under test without optional parameters
        results = await client.search_bills(limit=10, offset=5)
        
        # Verify the auth manager was called correctly with only required params
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/bill",
            method="GET",
            params={"limit": 10, "offset": 5},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we get valid results
        assert "bills" in results
        assert "pagination" in results
        
    async def test_search_bills_with_bill_type(self, client, mock_auth_manager, mock_bill_search_response):
        """Test searching bills with bill_type parameter."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_bill_search_response
        
        # Call the method under test with bill_type parameter
        results = await client.search_bills(bill_type="hr", limit=10)
        
        # Verify the auth manager was called correctly with bill_type param
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/bill",
            method="GET",
            params={"billType": "hr", "limit": 10, "offset": 0},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we get valid results
        assert "bills" in results
        assert "pagination" in results
    
    async def test_get_member(self, client, mock_auth_manager, mock_member_response):
        """Test getting a member."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_member_response
        
        # Call the method under test
        member = await client.get_member(bioguide_id="A000001")
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/member/A000001",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned object is correct
        assert isinstance(member, Member)
        assert member.bioguide_id == "A000001"
        assert member.first_name == "Test"
        assert member.last_name == "Person"
        assert member.full_name == "Representative Test Person"
        assert member.state == "CA"
        assert member.party == "D"
        assert member.chamber == Chamber.HOUSE
        assert member.district == "1"
        assert member.term_start == date(2023, 1, 3)
        assert member.term_end == date(2025, 1, 3)
        assert member.birth_year == 1970
        assert str(member.official_url).rstrip('/') == "https://testperson.house.gov"
        
        # Verify terms
        assert len(member.terms) == 2
        assert member.terms[0]["congress"] == 118
        assert member.terms[1]["congress"] == 117
        
        # Verify source reference
        assert member.source_reference.source == ApiSource.CONGRESS
        assert member.source_reference.source_id == "A000001"
    
    async def test_get_committee(self, client, mock_auth_manager, mock_committee_response):
        """Test getting a committee."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_committee_response
        
        # Call the method under test
        committee = await client.get_committee(congress=117, chamber="house", committee_code="AG")
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/committee/117/house/AG",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned object is correct
        assert isinstance(committee, Committee)
        assert committee.committee_id == "AG"
        assert committee.name == "Committee on Agriculture"
        assert committee.chamber == Chamber.HOUSE
        assert committee.committee_type == "standing"
        assert committee.congress == 117
        
        # Verify subcommittees
        assert len(committee.subcommittees) == 2
        assert committee.subcommittees[0]["committee_id"] == "AG01"
        assert committee.subcommittees[0]["name"] == "Subcommittee on Nutrition"
        assert committee.subcommittees[1]["committee_id"] == "AG02"
        assert committee.subcommittees[1]["name"] == "Subcommittee on Commodity Markets"
        
        # Verify source reference
        assert committee.source_reference.source == ApiSource.CONGRESS
        assert committee.source_reference.source_id == "117/House/AG"
    
    async def test_get_bill_actions(self, client, mock_auth_manager, mock_bill_actions_response):
        """Test getting bill actions."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_bill_actions_response
        
        # Call the method under test
        actions = await client.get_bill_actions(congress=117, bill_type="hr", bill_number=1234)
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/bill/117/hr/1234/actions",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned objects
        assert len(actions) == 2
        assert isinstance(actions[0], BillAction)
        assert actions[0].action_date == date(2023, 1, 15)
        assert actions[0].text == "Introduced in House"
        assert actions[0].chamber == Chamber.HOUSE
        assert actions[0].action_code == "I"
        assert actions[0].action_type == "IntroReferral"
        
        assert actions[1].action_date == date(2023, 1, 20)
        assert actions[1].text == "Referred to Committee"
        assert actions[1].chamber == Chamber.HOUSE
        assert actions[1].action_code == "RH"
        assert actions[1].action_type == "IntroReferral"
    
    async def test_get_bill_cosponsors(self, client, mock_auth_manager, mock_bill_cosponsors_response):
        """Test getting bill cosponsors."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_bill_cosponsors_response
        
        # Call the method under test
        cosponsors = await client.get_bill_cosponsors(congress=117, bill_type="hr", bill_number=1234)
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/bill/117/hr/1234/cosponsors",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned objects
        assert len(cosponsors) == 2
        assert isinstance(cosponsors[0], BillSponsor)
        
        # First cosponsor
        assert cosponsors[0].bioguide_id == "B000001"
        assert cosponsors[0].full_name == "Representative Test Cosponsor"
        assert cosponsors[0].first_name == "Test"
        assert cosponsors[0].last_name == "Cosponsor"
        assert cosponsors[0].party == "R"
        assert cosponsors[0].state == "TX"
        assert cosponsors[0].district == "2"
        assert cosponsors[0].sponsor_type == "cosponsor"
        assert cosponsors[0].sponsor_date == date(2023, 1, 20)
        
        # Second cosponsor
        assert cosponsors[1].bioguide_id == "C000001"
        assert cosponsors[1].full_name == "Representative Another Cosponsor"
        assert cosponsors[1].sponsor_type == "cosponsor"
    
    async def test_get_bill_subjects(self, client, mock_auth_manager, mock_bill_subjects_response):
        """Test getting bill subjects."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_bill_subjects_response
        
        # Call the method under test
        subjects = await client.get_bill_subjects(congress=117, bill_type="hr", bill_number=1234)
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/bill/117/hr/1234/subjects",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned objects
        assert len(subjects) == 3
        assert "Health" in subjects
        assert "Public health" in subjects
        assert "Medicare" in subjects
    
    async def test_get_bill_text_versions(self, client, mock_auth_manager, mock_bill_versions_response):
        """Test getting bill text versions."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_bill_versions_response
        
        # Call the method under test
        versions = await client.get_bill_text_versions(congress=117, bill_type="hr", bill_number=1234)
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/bill/117/hr/1234/text",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned objects
        assert len(versions) == 2
        assert isinstance(versions[0], BillVersion)
        
        # First version
        assert versions[0].version_code == BillVersionCode.INTRODUCED_HOUSE
        assert versions[0].version_name == "Introduced in House"
        assert versions[0].publish_date == date(2023, 1, 15)
        assert versions[0].govinfo_package_id == "BILLS-117hr1234ih"
        assert str(versions[0].pdf_url) == "https://www.congress.gov/bill/117/hr/1234/text.pdf"
        assert str(versions[0].xml_url) == "https://www.congress.gov/bill/117/hr/1234/text.xml"
        assert str(versions[0].html_url) == "https://www.congress.gov/bill/117/hr/1234/text.html"
        
        # Second version
        assert versions[1].version_code == BillVersionCode.REPORTED_HOUSE
        assert versions[1].version_name == "Reported in House"
        assert versions[1].govinfo_package_id == "BILLS-117hr1234rh"
    
    async def test_list_committees(self, client, mock_auth_manager, mock_committees_response):
        """Test listing committees."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_committees_response
        
        # Call the method under test
        committees = await client.list_committees(congress=117)
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/committee/117",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned objects
        assert len(committees) == 2
        assert isinstance(committees[0], Committee)
        
        # First committee
        assert committees[0].committee_id == "AG"
        assert committees[0].name == "Committee on Agriculture"
        assert committees[0].chamber == Chamber.HOUSE
        assert committees[0].committee_type == "standing"
        assert committees[0].congress == 117
        
        # Second committee
        assert committees[1].committee_id == "BU"
        assert committees[1].name == "Committee on Budget"
        assert committees[1].chamber == Chamber.SENATE
        assert committees[1].committee_type == "standing"
        assert committees[1].congress == 117
        
    async def test_list_committees_without_congress(self, client, mock_auth_manager, mock_committees_response):
        """Test listing committees without specifying congress."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_committees_response
        
        # Call the method under test without congress
        committees = await client.list_committees()
        
        # Verify the auth manager was called correctly with default endpoint
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/committee",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we get valid results
        assert len(committees) == 2
    
    async def test_list_members(self, client, mock_auth_manager, mock_members_response):
        """Test listing members."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_members_response
        
        # Call the method under test
        members = await client.list_members(congress=117)
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/member/117",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned objects
        assert len(members) == 2
        assert isinstance(members[0], Member)
        
        # First member
        assert members[0].bioguide_id == "A000001"
        assert members[0].first_name == "Test"
        assert members[0].last_name == "Person"
        assert members[0].full_name == "Representative Test Person"
        assert members[0].state == "CA"
        assert members[0].party == "D"
        assert members[0].chamber == Chamber.HOUSE
        assert members[0].district == "1"
        
        # Second member
        assert members[1].bioguide_id == "B000002"
        assert members[1].full_name == "Senator Another Member"
        assert members[1].chamber == Chamber.SENATE
        
    async def test_list_members_without_congress(self, client, mock_auth_manager, mock_members_response):
        """Test listing members without specifying congress."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_members_response
        
        # Call the method under test without congress
        members = await client.list_members()
        
        # Verify the auth manager was called correctly with default endpoint
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/member",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we get valid results
        assert len(members) == 2
    
    async def test_get_member_sponsored_legislation(self, client, mock_auth_manager, mock_member_legislation_response):
        """Test getting member sponsored legislation."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_member_legislation_response
        
        # Call the method under test
        result = await client.get_member_sponsored_legislation(
            bioguide_id="A000001",
            congress=117,
            limit=10,
            offset=0
        )
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/member/A000001/sponsored-legislation/117",
            method="GET",
            params={"limit": 10, "offset": 0},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned objects
        assert "sponsored_bills" in result
        assert "pagination" in result
        assert len(result["sponsored_bills"]) == 2
        assert result["pagination"]["count"] == 2
        
        # First bill
        bill1 = result["sponsored_bills"][0]
        assert isinstance(bill1, Bill)
        assert bill1.bill_id == "hr1234"
        assert bill1.title == "Health Bill 1"
        assert bill1.congress == 117
        assert bill1.bill_type == "hr"
        assert bill1.introduced_date == date(2023, 1, 15)
        
        # Second bill
        bill2 = result["sponsored_bills"][1]
        assert bill2.bill_id == "hr5678"
        assert bill2.title == "Education Bill"
        
    async def test_get_member_sponsored_legislation_without_congress(self, client, mock_auth_manager, mock_member_legislation_response):
        """Test getting member sponsored legislation without congress parameter."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_member_legislation_response
        
        # Call the method under test without congress
        result = await client.get_member_sponsored_legislation(
            bioguide_id="A000001",
            limit=10,
            offset=0
        )
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/member/A000001/sponsored-legislation",
            method="GET",
            params={"limit": 10, "offset": 0},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we get valid results
        assert "sponsored_bills" in result
        assert "pagination" in result
    
    async def test_error_handling(self, client, mock_auth_manager):
        """Test error handling."""
        # Make the mock raise an error
        mock_auth_manager.execute_request.side_effect = CongressApiError("API error", status_code=500)
        
        # Verify that the error is propagated
        with pytest.raises(CongressApiError):
            await client.get_bill(congress=117, bill_type="hr", bill_number=1234)
    
    async def test_invalid_response_validation(self, client, mock_auth_manager):
        """Test invalid response validation."""
        # Create a mock response missing required fields
        mock_response = {
            "request": {"url": "https://api.congress.gov/v3/bill/117/hr/1234"}
            # Missing 'results' field
        }
        
        # Setup mock
        mock_auth_manager.execute_request.return_value = mock_response
        
        # Test bill endpoint validation
        with pytest.raises(CongressApiError, match="Invalid bill response format"):
            await client.get_bill(congress=117, bill_type="hr", bill_number=1234)
    
    async def test_all_endpoint_validations(self, client, mock_auth_manager):
        """Test validation errors for all endpoints."""
        # Create a mock invalid response
        mock_response = {
            "request": {"url": "https://api.congress.gov/v3/endpoint"}
            # Missing required fields
        }
        
        # Setup mock
        mock_auth_manager.execute_request.return_value = mock_response
        
        # Test bill search endpoint validation
        with pytest.raises(CongressApiError, match="Invalid bill search response format"):
            await client.search_bills(query="test")
            
        # Test bill actions endpoint validation
        with pytest.raises(CongressApiError, match="Invalid bill actions response format"):
            await client.get_bill_actions(congress=117, bill_type="hr", bill_number=1234)
            
        # Test bill cosponsors endpoint validation
        with pytest.raises(CongressApiError, match="Invalid bill cosponsors response format"):
            await client.get_bill_cosponsors(congress=117, bill_type="hr", bill_number=1234)
            
        # Test bill subjects endpoint validation
        with pytest.raises(CongressApiError, match="Invalid bill subjects response format"):
            await client.get_bill_subjects(congress=117, bill_type="hr", bill_number=1234)
            
        # Test bill text versions endpoint validation
        with pytest.raises(CongressApiError, match="Invalid bill text versions response format"):
            await client.get_bill_text_versions(congress=117, bill_type="hr", bill_number=1234)
            
        # Test committees endpoint validation
        with pytest.raises(CongressApiError, match="Invalid committees response format"):
            await client.list_committees()
            
        # Test committee endpoint validation
        with pytest.raises(CongressApiError, match="Invalid committee response format"):
            await client.get_committee(congress=117, chamber="house", committee_code="AG")
            
        # Test members endpoint validation
        with pytest.raises(CongressApiError, match="Invalid members response format"):
            await client.list_members()
            
        # Test member endpoint validation
        with pytest.raises(CongressApiError, match="Invalid member response format"):
            await client.get_member(bioguide_id="A000001")
            
        # Test member sponsored legislation endpoint validation
        with pytest.raises(CongressApiError, match="Invalid member sponsored legislation response format"):
            await client.get_member_sponsored_legislation(bioguide_id="A000001")
    
    def test_parse_date(self, client, monkeypatch):
        """Test date parsing."""
        # Save the original warning method
        import logging
        original_warning = logging.Logger.warning
        
        # Replace with a no-op for our test
        def mock_warning(self, msg, *args, **kwargs):
            # Don't do anything
            pass
            
        # Apply the monkeypatch
        monkeypatch.setattr(logging.Logger, "warning", mock_warning)
        
        try:
            # Test ISO date
            assert client._parse_date("2023-01-15") == date(2023, 1, 15)
            
            # Test ISO datetime
            assert client._parse_date("2023-01-15T12:34:56Z") == date(2023, 1, 15)
            
            # Test None
            assert client._parse_date(None) is None
            
            # Test invalid date - now without warning
            assert client._parse_date("not-a-date") is None
        finally:
            # Restore the original warning method
            monkeypatch.setattr(logging.Logger, "warning", original_warning)
    
    def test_parse_chamber(self, client):
        """Test chamber parsing."""
        # Test valid chambers
        assert client._parse_chamber("House") == Chamber.HOUSE
        assert client._parse_chamber("Senate") == Chamber.SENATE
        assert client._parse_chamber("Both") == Chamber.JOINT
        assert client._parse_chamber("house") == Chamber.HOUSE
        assert client._parse_chamber("senate") == Chamber.SENATE
        assert client._parse_chamber("joint") == Chamber.JOINT
        
        # Test None
        assert client._parse_chamber(None) is None
        
        # Test invalid chamber
        assert client._parse_chamber("invalid") is None
    
    def test_transform_bill_actions_response(self, client):
        """Test transforming bill actions response."""
        # Create test response
        response = {
            "results": [{
                "actions": [
                    {
                        "actionDate": "2023-01-15",
                        "text": "Introduced in House",
                        "chamber": "House",
                        "actionCode": "I",
                        "type": "IntroReferral"
                    }
                ]
            }]
        }
        
        # Call transform method
        actions = client._transform_bill_actions_response(response)
        
        # Verify results
        assert len(actions) == 1
        assert isinstance(actions[0], BillAction)
        assert actions[0].action_date == date(2023, 1, 15)
        assert actions[0].text == "Introduced in House"
        assert actions[0].chamber == Chamber.HOUSE
        assert actions[0].action_code == "I"
        assert actions[0].action_type == "IntroReferral"
    
    def test_transform_bill_cosponsors_response(self, client):
        """Test transforming bill cosponsors response."""
        # Create test response
        response = {
            "results": [{
                "cosponsors": [
                    {
                        "bioguideId": "B000001",
                        "fullName": "Representative Test Cosponsor",
                        "firstName": "Test",
                        "lastName": "Cosponsor",
                        "party": "R",
                        "state": "TX",
                        "district": "2",
                        "sponsorshipDate": "2023-01-20"
                    }
                ]
            }]
        }
        
        # Call transform method
        cosponsors = client._transform_bill_cosponsors_response(response)
        
        # Verify results
        assert len(cosponsors) == 1
        assert isinstance(cosponsors[0], BillSponsor)
        assert cosponsors[0].bioguide_id == "B000001"
        assert cosponsors[0].full_name == "Representative Test Cosponsor"
        assert cosponsors[0].sponsor_type == "cosponsor"
        assert cosponsors[0].sponsor_date == date(2023, 1, 20)
    
    def test_transform_bill_subjects_response(self, client):
        """Test transforming bill subjects response."""
        # Create test response
        response = {
            "results": [{
                "subjects": [
                    {"name": "Health"},
                    {"name": "Public health"}
                ]
            }]
        }
        
        # Call transform method
        subjects = client._transform_bill_subjects_response(response)
        
        # Verify results
        assert len(subjects) == 2
        assert subjects[0] == "Health"
        assert subjects[1] == "Public health"
    
    def test_transform_bill_versions_response(self, client):
        """Test transforming bill versions response."""
        # Create test response
        response = {
            "results": [{
                "textVersions": [
                    {
                        "type": "ih",
                        "typeName": "Introduced in House",
                        "date": "2023-01-15",
                        "formats": {
                            "pdf": {
                                "url": "https://www.congress.gov/bill/117/hr/1234/text.pdf",
                                "packageId": "BILLS-117hr1234ih"
                            },
                            "xml": {
                                "url": "https://www.congress.gov/bill/117/hr/1234/text.xml"
                            },
                            "html": {
                                "url": "https://www.congress.gov/bill/117/hr/1234/text.html"
                            }
                        }
                    }
                ]
            }]
        }
        
        # Call transform method
        versions = client._transform_bill_versions_response(response)
        
        # Verify results
        assert len(versions) == 1
        assert isinstance(versions[0], BillVersion)
        assert versions[0].version_code == BillVersionCode.INTRODUCED_HOUSE
        assert versions[0].version_name == "Introduced in House"
        assert versions[0].publish_date == date(2023, 1, 15)
        assert versions[0].govinfo_package_id == "BILLS-117hr1234ih"
        assert str(versions[0].pdf_url) == "https://www.congress.gov/bill/117/hr/1234/text.pdf"
    
    def test_transform_committees_response(self, client):
        """Test transforming committees response."""
        # Create test response
        response = {
            "request": {"url": "https://api.congress.gov/v3/committee"},
            "results": [
                {
                    "congress": 117,
                    "chamber": "House",
                    "systemCode": "AG",
                    "name": "Committee on Agriculture",
                    "type": "standing",
                    "updateDate": "2023-02-01"
                }
            ]
        }
        
        # Call transform method
        committees = client._transform_committees_response(response)
        
        # Verify results
        assert len(committees) == 1
        assert isinstance(committees[0], Committee)
        assert committees[0].committee_id == "AG"
        assert committees[0].name == "Committee on Agriculture"
        assert committees[0].chamber == Chamber.HOUSE
        assert committees[0].committee_type == "standing"
        assert committees[0].congress == 117
    
    def test_transform_members_response(self, client):
        """Test transforming members response."""
        # Create test response
        response = {
            "request": {"url": "https://api.congress.gov/v3/member"},
            "results": [
                {
                    "bioguideId": "A000001",
                    "firstName": "Test",
                    "lastName": "Person",
                    "fullName": "Representative Test Person",
                    "state": "CA",
                    "party": "D",
                    "chamber": "House",
                    "district": "1",
                    "updateDate": "2023-02-01"
                }
            ]
        }
        
        # Call transform method
        members = client._transform_members_response(response)
        
        # Verify results
        assert len(members) == 1
        assert isinstance(members[0], Member)
        assert members[0].bioguide_id == "A000001"
        assert members[0].first_name == "Test"
        assert members[0].last_name == "Person"
        assert members[0].full_name == "Representative Test Person"
        assert members[0].chamber == Chamber.HOUSE
    
    def test_transform_member_legislation_response(self, client):
        """Test transforming member legislation response."""
        # Create test response
        response = {
            "request": {"url": "https://api.congress.gov/v3/member/A000001/sponsored-legislation"},
            "pagination": {"count": 1},
            "results": [
                {
                    "congress": 117,
                    "type": "hr",
                    "number": 1234,
                    "title": "Test Bill",
                    "introducedDate": "2023-01-15",
                    "updateDate": "2023-02-01",
                    "originChamber": "House"
                }
            ]
        }
        
        # Call transform method
        result = client._transform_member_legislation_response(response)
        
        # Verify results
        assert "sponsored_bills" in result
        assert "pagination" in result
        assert len(result["sponsored_bills"]) == 1
        assert isinstance(result["sponsored_bills"][0], Bill)
        assert result["sponsored_bills"][0].bill_id == "hr1234"
        assert result["sponsored_bills"][0].title == "Test Bill"
        
    def test_transform_bill_response_with_missing_fields(self, client):
        """Test transforming bill response with missing policy area and sponsor."""
        # Create test response with missing policy area and sponsor
        response = {
            "request": {
                "url": "https://api.congress.gov/v3/bill/117/hr/1234"
            },
            "results": [{
                "congress": 117,
                "type": "hr",
                "number": 1234,
                "title": "Test Bill with Missing Fields",
                "introducedDate": "2023-01-15",
                "updateDate": "2023-02-01",
                "originChamber": "House",
                "latestAction": {
                    "actionDate": "2023-01-20",
                    "text": "Referred to Committee"
                }
                # No policy area or sponsor data
            }]
        }
        
        # Call transform method
        bill = client._transform_bill_response(response)
        
        # Verify results
        assert isinstance(bill, Bill)
        assert bill.bill_id == "hr1234"
        assert bill.congress == 117
        assert bill.policy_area is None  # Should handle missing policy area
        assert bill.sponsor is None      # Should handle missing sponsor