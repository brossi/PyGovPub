"""
Congress.gov API client.

This module provides a client for interacting with the Congress.gov API,
including endpoints for bills, members, committees, and votes.
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Union, Any
from urllib.parse import urljoin
import logging

from pygovpub.api.base import BaseApiClient
from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.events.event_manager import get_event_manager
from pygovpub.events.event_types import (
    Event, EventCategory, EventType, EventPayload,
    FloorUpdatePayload, VoteUpdatePayload, CalendarUpdatePayload, HearingUpdatePayload
)
from pygovpub.exceptions import ApiError, CongressApiError
from pygovpub.models.legislative import (
    Bill, BillAction, BillSponsor, BillSummary, BillType, BillVersion,
    Chamber, Committee, Member, PolicyArea, SourceReference
)

# Configure logging
logger = logging.getLogger("pygovpub.api.congress")


class CongressClient(BaseApiClient):
    """Client for the Congress.gov API."""
    
    def __init__(self, auth_manager: Optional[AuthManager] = None):
        """Initialize Congress.gov API client.
        
        Args:
            auth_manager: Authentication manager instance
        """
        super().__init__(auth_manager, ApiSource.CONGRESS)
        self._event_manager = get_event_manager()
    
    # Bill endpoints
    
    async def get_bill(self, congress: int, bill_type: str, bill_number: int) -> Bill:
        """Get information about a specific bill.
        
        Args:
            congress: Congress number (e.g., 117)
            bill_type: Type of bill (e.g., 'hr', 's')
            bill_number: Bill number
            
        Returns:
            Bill object with bill details
            
        Raises:
            ApiError: If request fails
        """
        endpoint = f"/bill/{congress}/{bill_type}/{bill_number}"
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid bill response format", status_code=400, endpoint=endpoint)
            
        return self._transform_bill_response(response)
    
    async def search_bills(
        self,
        query: Optional[str] = None,
        congress: Optional[int] = None,
        bill_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search for bills matching criteria.
        
        Args:
            query: Search query
            congress: Congress number to filter by
            bill_type: Bill type to filter by
            limit: Maximum number of results
            offset: Result offset for pagination
            
        Returns:
            Dictionary with search results and pagination info
            
        Raises:
            ApiError: If request fails
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if query:
            params["query"] = query
        
        if bill_type:
            params["billType"] = bill_type
            
        endpoint = "/bill"
        if congress:
            endpoint = f"/bill/{congress}"
            
        response = await self.execute_request(endpoint=endpoint, params=params)
        
        # Validate response
        if not self.validate_response(response, ["results", "pagination"]):
            raise CongressApiError("Invalid bill search response format", status_code=400, endpoint=endpoint)
            
        return self._transform_bill_search_response(response)
    
    async def get_bill_actions(self, congress: int, bill_type: str, bill_number: int) -> List[BillAction]:
        """Get actions for a specific bill.
        
        Args:
            congress: Congress number
            bill_type: Bill type
            bill_number: Bill number
            
        Returns:
            List of bill actions
            
        Raises:
            ApiError: If request fails
        """
        endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/actions"
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid bill actions response format", status_code=400, endpoint=endpoint)
            
        return self._transform_bill_actions_response(response)
    
    async def get_bill_cosponsors(self, congress: int, bill_type: str, bill_number: int) -> List[BillSponsor]:
        """Get cosponsors for a specific bill.
        
        Args:
            congress: Congress number
            bill_type: Bill type
            bill_number: Bill number
            
        Returns:
            List of bill cosponsors
            
        Raises:
            ApiError: If request fails
        """
        endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/cosponsors"
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid bill cosponsors response format", status_code=400, endpoint=endpoint)
            
        return self._transform_bill_cosponsors_response(response)
    
    async def get_bill_subjects(self, congress: int, bill_type: str, bill_number: int) -> List[str]:
        """Get subjects for a specific bill.
        
        Args:
            congress: Congress number
            bill_type: Bill type
            bill_number: Bill number
            
        Returns:
            List of bill subjects
            
        Raises:
            ApiError: If request fails
        """
        endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/subjects"
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid bill subjects response format", status_code=400, endpoint=endpoint)
            
        return self._transform_bill_subjects_response(response)
    
    async def get_bill_text_versions(self, congress: int, bill_type: str, bill_number: int) -> List[BillVersion]:
        """Get text versions for a specific bill.
        
        Args:
            congress: Congress number
            bill_type: Bill type
            bill_number: Bill number
            
        Returns:
            List of bill text versions
            
        Raises:
            ApiError: If request fails
        """
        endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/text"
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid bill text versions response format", status_code=400, endpoint=endpoint)
            
        return self._transform_bill_versions_response(response)
    
    # Committee endpoints
    
    async def list_committees(self, congress: Optional[int] = None) -> List[Committee]:
        """Get list of committees.
        
        Args:
            congress: Optional congress number to filter by
            
        Returns:
            List of committees
            
        Raises:
            ApiError: If request fails
        """
        endpoint = "/committee"
        if congress:
            endpoint = f"/committee/{congress}"
            
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid committees response format", status_code=400, endpoint=endpoint)
            
        return self._transform_committees_response(response)
    
    async def get_committee(self, congress: int, chamber: str, committee_code: str) -> Committee:
        """Get details for a specific committee.
        
        Args:
            congress: Congress number
            chamber: Chamber (house, senate, joint)
            committee_code: Committee code
            
        Returns:
            Committee object
            
        Raises:
            ApiError: If request fails
        """
        endpoint = f"/committee/{congress}/{chamber}/{committee_code}"
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid committee response format", status_code=400, endpoint=endpoint)
            
        return self._transform_committee_response(response)
    
    # Member endpoints
    
    async def list_members(self, congress: Optional[int] = None) -> List[Member]:
        """Get list of members.
        
        Args:
            congress: Optional congress number to filter by
            
        Returns:
            List of members
            
        Raises:
            ApiError: If request fails
        """
        endpoint = "/member"
        if congress:
            endpoint = f"/member/{congress}"
            
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid members response format", status_code=400, endpoint=endpoint)
            
        return self._transform_members_response(response)
    
    async def get_member(self, bioguide_id: str) -> Member:
        """Get details for a specific member.
        
        Args:
            bioguide_id: Bioguide ID
            
        Returns:
            Member object
            
        Raises:
            ApiError: If request fails
        """
        endpoint = f"/member/{bioguide_id}"
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid member response format", status_code=400, endpoint=endpoint)
            
        return self._transform_member_response(response)
    
    async def get_member_sponsored_legislation(
        self,
        bioguide_id: str,
        congress: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get legislation sponsored by a member.
        
        Args:
            bioguide_id: Bioguide ID
            congress: Optional congress number to filter by
            limit: Maximum number of results
            offset: Result offset for pagination
            
        Returns:
            Dictionary with sponsored legislation
            
        Raises:
            ApiError: If request fails
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        endpoint = f"/member/{bioguide_id}/sponsored-legislation"
        if congress:
            endpoint = f"/member/{bioguide_id}/sponsored-legislation/{congress}"
            
        response = await self.execute_request(endpoint=endpoint, params=params)
        
        # Validate response
        if not self.validate_response(response, ["results", "pagination"]):
            raise CongressApiError("Invalid member sponsored legislation response format", status_code=400, endpoint=endpoint)
            
        return self._transform_member_legislation_response(response)
    
    # Helper transformation methods
    
    def _transform_bill_response(self, response: Dict[str, Any]) -> Bill:
        """Transform API response to Bill model.
        
        Args:
            response: API response
            
        Returns:
            Bill object
        """
        # Extract bill data from response
        bill_data = response.get("results", [{}])[0]
        
        # Create source reference
        base_url = response.get("request", {}).get("url", "")
        
        source_ref = SourceReference(
            source=self.api_source,
            source_id=f"{bill_data.get('congress')}/{bill_data.get('type')}/{bill_data.get('number')}",
            source_url=base_url,
            last_updated=self._parse_date(bill_data.get("updateDate"))
        )
        
        # Create policy area
        policy_area = None
        if bill_data.get("policyArea"):
            policy_area = PolicyArea(
                name=bill_data.get("policyArea", {}).get("name", ""),
                code=bill_data.get("policyArea", {}).get("code", "")
            )
        
        # Create sponsor
        sponsor = None
        if bill_data.get("sponsors") and bill_data.get("sponsors")[0]:
            sponsor_data = bill_data.get("sponsors")[0]
            sponsor = BillSponsor(
                bioguide_id=sponsor_data.get("bioguideId", ""),
                full_name=sponsor_data.get("fullName", ""),
                first_name=sponsor_data.get("firstName", ""),
                last_name=sponsor_data.get("lastName", ""),
                party=sponsor_data.get("party", ""),
                state=sponsor_data.get("state", ""),
                district=sponsor_data.get("district", ""),
                sponsor_type="sponsor",
                sponsor_date=self._parse_date(sponsor_data.get("sponsorshipDate"))
            )
        
        # Extract bill actions
        actions = []
        if bill_data.get("actions"):
            for action_data in bill_data.get("actions", []):
                action = BillAction(
                    action_date=self._parse_date(action_data.get("actionDate")),
                    text=action_data.get("text", ""),
                    chamber=self._parse_chamber(action_data.get("chamber")),
                    action_code=action_data.get("actionCode", ""),
                    action_type=action_data.get("type", "")
                )
                actions.append(action)
        
        # Create bill object
        bill = Bill(
            bill_id=f"{bill_data.get('type')}{bill_data.get('number')}",
            congress=bill_data.get("congress"),
            bill_type=bill_data.get("type"),
            bill_number=bill_data.get("number"),
            title=bill_data.get("title", ""),
            short_title=bill_data.get("shortTitle", ""),
            introduced_date=self._parse_date(bill_data.get("introducedDate")),
            latest_action_date=self._parse_date(bill_data.get("latestAction", {}).get("actionDate")),
            origin_chamber=self._parse_chamber(bill_data.get("originChamber")),
            sponsor=sponsor,
            policy_area=policy_area,
            actions=actions,
            source_reference=source_ref
        )
        
        return bill
    
    def _transform_bill_search_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Transform bill search response.
        
        Args:
            response: API response
            
        Returns:
            Dictionary with bills and pagination info
        """
        bills = []
        
        # Extract bill data from response
        for bill_data in response.get("results", []):
            # Create source reference
            source_ref = SourceReference(
                source=self.api_source,
                source_id=f"{bill_data.get('congress')}/{bill_data.get('type')}/{bill_data.get('number')}",
                source_url=response.get("request", {}).get("url", ""),
                last_updated=self._parse_date(bill_data.get("updateDate"))
            )
            
            # Create bill object with minimal data
            bill = Bill(
                bill_id=f"{bill_data.get('type')}{bill_data.get('number')}",
                congress=bill_data.get("congress"),
                bill_type=bill_data.get("type"),
                bill_number=bill_data.get("number"),
                title=bill_data.get("title", ""),
                introduced_date=self._parse_date(bill_data.get("introducedDate")),
                latest_action_date=self._parse_date(bill_data.get("latestAction", {}).get("actionDate")),
                origin_chamber=self._parse_chamber(bill_data.get("originChamber")),
                source_reference=source_ref
            )
            
            bills.append(bill)
        
        # Extract pagination info
        pagination = response.get("pagination", {})
        
        return {
            "bills": bills,
            "pagination": pagination
        }
    
    def _transform_bill_actions_response(self, response: Dict[str, Any]) -> List[BillAction]:
        """Transform bill actions response.
        
        Args:
            response: API response
            
        Returns:
            List of bill actions
        """
        actions = []
        
        # Extract action data from response
        for action_data in response.get("results", [{}])[0].get("actions", []):
            action = BillAction(
                action_date=self._parse_date(action_data.get("actionDate")),
                text=action_data.get("text", ""),
                chamber=self._parse_chamber(action_data.get("chamber")),
                action_code=action_data.get("actionCode", ""),
                action_type=action_data.get("type", "")
            )
            actions.append(action)
        
        return actions
    
    def _transform_bill_cosponsors_response(self, response: Dict[str, Any]) -> List[BillSponsor]:
        """Transform bill cosponsors response.
        
        Args:
            response: API response
            
        Returns:
            List of bill cosponsors
        """
        cosponsors = []
        
        # Extract cosponsor data from response
        for cosponsor_data in response.get("results", [{}])[0].get("cosponsors", []):
            cosponsor = BillSponsor(
                bioguide_id=cosponsor_data.get("bioguideId", ""),
                full_name=cosponsor_data.get("fullName", ""),
                first_name=cosponsor_data.get("firstName", ""),
                last_name=cosponsor_data.get("lastName", ""),
                party=cosponsor_data.get("party", ""),
                state=cosponsor_data.get("state", ""),
                district=cosponsor_data.get("district", ""),
                sponsor_type="cosponsor",
                sponsor_date=self._parse_date(cosponsor_data.get("sponsorshipDate"))
            )
            cosponsors.append(cosponsor)
        
        return cosponsors
    
    def _transform_bill_subjects_response(self, response: Dict[str, Any]) -> List[str]:
        """Transform bill subjects response.
        
        Args:
            response: API response
            
        Returns:
            List of bill subjects
        """
        subjects = []
        
        # Extract subject data from response
        for subject_data in response.get("results", [{}])[0].get("subjects", []):
            subjects.append(subject_data.get("name", ""))
        
        return subjects
    
    def _transform_bill_versions_response(self, response: Dict[str, Any]) -> List[BillVersion]:
        """Transform bill versions response.
        
        Args:
            response: API response
            
        Returns:
            List of bill versions
        """
        versions = []
        
        # Extract version data from response
        for version_data in response.get("results", [{}])[0].get("textVersions", []):
            version = BillVersion(
                version_code=version_data.get("type", ""),
                version_name=version_data.get("typeName", ""),
                publish_date=self._parse_date(version_data.get("date")),
                govinfo_package_id=version_data.get("formats", {}).get("pdf", {}).get("packageId", ""),
                pdf_url=version_data.get("formats", {}).get("pdf", {}).get("url", ""),
                xml_url=version_data.get("formats", {}).get("xml", {}).get("url", ""),
                html_url=version_data.get("formats", {}).get("html", {}).get("url", "")
            )
            versions.append(version)
        
        return versions
    
    def _transform_committees_response(self, response: Dict[str, Any]) -> List[Committee]:
        """Transform committees response.
        
        Args:
            response: API response
            
        Returns:
            List of committees
        """
        committees = []
        
        # Extract committee data from response
        for committee_data in response.get("results", []):
            # Create source reference
            source_ref = SourceReference(
                source=self.api_source,
                source_id=f"{committee_data.get('congress')}/{committee_data.get('chamber')}/{committee_data.get('systemCode')}",
                source_url=response.get("request", {}).get("url", ""),
                last_updated=self._parse_date(committee_data.get("updateDate"))
            )
            
            # Create committee object
            committee = Committee(
                committee_id=committee_data.get("systemCode", ""),
                name=committee_data.get("name", ""),
                chamber=self._parse_chamber(committee_data.get("chamber")),
                committee_type=committee_data.get("type", ""),
                congress=committee_data.get("congress"),
                source_reference=source_ref
            )
            
            committees.append(committee)
        
        return committees
    
    def _transform_committee_response(self, response: Dict[str, Any]) -> Committee:
        """Transform committee response.
        
        Args:
            response: API response
            
        Returns:
            Committee object
        """
        # Extract committee data from response
        committee_data = response.get("results", [{}])[0]
        
        # Create source reference
        source_ref = SourceReference(
            source=self.api_source,
            source_id=f"{committee_data.get('congress')}/{committee_data.get('chamber')}/{committee_data.get('systemCode')}",
            source_url=response.get("request", {}).get("url", ""),
            last_updated=self._parse_date(committee_data.get("updateDate"))
        )
        
        # Extract subcommittees
        subcommittees = []
        for subcommittee_data in committee_data.get("subcommittees", []):
            subcommittee = {
                "committee_id": subcommittee_data.get("systemCode", ""),
                "name": subcommittee_data.get("name", ""),
                "committee_type": "subcommittee"
            }
            subcommittees.append(subcommittee)
        
        # Create committee object
        committee = Committee(
            committee_id=committee_data.get("systemCode", ""),
            name=committee_data.get("name", ""),
            chamber=self._parse_chamber(committee_data.get("chamber")),
            committee_type=committee_data.get("type", ""),
            congress=committee_data.get("congress"),
            subcommittees=subcommittees,
            source_reference=source_ref
        )
        
        return committee
    
    def _transform_members_response(self, response: Dict[str, Any]) -> List[Member]:
        """Transform members response.
        
        Args:
            response: API response
            
        Returns:
            List of members
        """
        members = []
        
        # Extract member data from response
        for member_data in response.get("results", []):
            # Create source reference
            source_ref = SourceReference(
                source=self.api_source,
                source_id=member_data.get("bioguideId", ""),
                source_url=response.get("request", {}).get("url", ""),
                last_updated=self._parse_date(member_data.get("updateDate"))
            )
            
            # Create member object
            member = Member(
                bioguide_id=member_data.get("bioguideId", ""),
                first_name=member_data.get("firstName", ""),
                last_name=member_data.get("lastName", ""),
                full_name=member_data.get("fullName", ""),
                state=member_data.get("state", ""),
                party=member_data.get("party", ""),
                chamber=self._parse_chamber(member_data.get("chamber")),
                district=member_data.get("district", ""),
                source_reference=source_ref
            )
            
            members.append(member)
        
        return members
    
    def _transform_member_response(self, response: Dict[str, Any]) -> Member:
        """Transform member response.
        
        Args:
            response: API response
            
        Returns:
            Member object
        """
        # Extract member data from response
        member_data = response.get("results", [{}])[0]
        
        # Create source reference
        source_ref = SourceReference(
            source=self.api_source,
            source_id=member_data.get("bioguideId", ""),
            source_url=response.get("request", {}).get("url", ""),
            last_updated=self._parse_date(member_data.get("updateDate"))
        )
        
        # Extract terms
        terms = []
        for term_data in member_data.get("terms", []):
            term = {
                "congress": term_data.get("congress"),
                "chamber": term_data.get("chamber", ""),
                "state": term_data.get("state", ""),
                "district": term_data.get("district", ""),
                "party": term_data.get("party", ""),
                "start_date": self._parse_date(term_data.get("startDate")),
                "end_date": self._parse_date(term_data.get("endDate"))
            }
            terms.append(term)
        
        # Create member object
        member = Member(
            bioguide_id=member_data.get("bioguideId", ""),
            first_name=member_data.get("firstName", ""),
            last_name=member_data.get("lastName", ""),
            full_name=member_data.get("fullName", ""),
            state=member_data.get("state", ""),
            party=member_data.get("party", ""),
            chamber=self._parse_chamber(member_data.get("chamber")),
            district=member_data.get("district", ""),
            term_start=self._parse_date(member_data.get("termStart")),
            term_end=self._parse_date(member_data.get("termEnd")),
            birth_year=member_data.get("birthYear"),
            death_year=member_data.get("deathYear"),
            official_url=member_data.get("officialUrl", ""),
            terms=terms,
            source_reference=source_ref
        )
        
        return member
    
    def _transform_member_legislation_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Transform member legislation response.
        
        Args:
            response: API response
            
        Returns:
            Dictionary with sponsored legislation
        """
        bills = []
        
        # Extract bill data from response
        for bill_data in response.get("results", []):
            # Create source reference
            source_ref = SourceReference(
                source=self.api_source,
                source_id=f"{bill_data.get('congress')}/{bill_data.get('type')}/{bill_data.get('number')}",
                source_url=response.get("request", {}).get("url", ""),
                last_updated=self._parse_date(bill_data.get("updateDate"))
            )
            
            # Create bill object with minimal data
            bill = Bill(
                bill_id=f"{bill_data.get('type')}{bill_data.get('number')}",
                congress=bill_data.get("congress"),
                bill_type=bill_data.get("type"),
                bill_number=bill_data.get("number"),
                title=bill_data.get("title", ""),
                introduced_date=self._parse_date(bill_data.get("introducedDate")),
                origin_chamber=self._parse_chamber(bill_data.get("originChamber")),
                source_reference=source_ref
            )
            
            bills.append(bill)
        
        # Extract pagination info
        pagination = response.get("pagination", {})
        
        return {
            "sponsored_bills": bills,
            "pagination": pagination
        }
    
    # Real-time update endpoints
    
    async def get_floor_updates(self, chamber: str, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get floor updates for a specific chamber.
        
        Args:
            chamber: Chamber (house, senate)
            date_str: Optional date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            List of floor updates
            
        Raises:
            ApiError: If request fails
        """
        params = {}
        if date_str:
            params["date"] = date_str
            
        endpoint = f"/floor/{chamber}"
        response = await self.execute_request(endpoint=endpoint, params=params)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid floor updates response format", status_code=400, endpoint=endpoint)
            
        updates = response.get("results", [])
        
        # Emit events for each update
        await self._emit_floor_update_events(chamber, updates)
        
        return updates
    
    async def get_vote_updates(self, chamber: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent vote updates.
        
        Args:
            chamber: Optional chamber (house, senate) to filter by
            
        Returns:
            List of vote updates
            
        Raises:
            ApiError: If request fails
        """
        params = {}
        endpoint = "/votes"
        
        if chamber:
            endpoint = f"/votes/{chamber}"
            
        response = await self.execute_request(endpoint=endpoint, params=params)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid vote updates response format", status_code=400, endpoint=endpoint)
            
        votes = response.get("results", [])
        
        # Emit events for each vote
        await self._emit_vote_update_events(votes)
        
        return votes
    
    async def get_calendar_updates(self, chamber: str) -> List[Dict[str, Any]]:
        """Get calendar updates for a specific chamber.
        
        Args:
            chamber: Chamber (house, senate)
            
        Returns:
            List of calendar updates
            
        Raises:
            ApiError: If request fails
        """
        endpoint = f"/calendar/{chamber}"
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid calendar updates response format", status_code=400, endpoint=endpoint)
            
        calendar_items = response.get("results", [])
        
        # Emit events for each calendar item
        await self._emit_calendar_update_events(chamber, calendar_items)
        
        return calendar_items
    
    async def get_hearing_updates(self, committee_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get hearing updates.
        
        Args:
            committee_id: Optional committee ID to filter by
            
        Returns:
            List of hearing updates
            
        Raises:
            ApiError: If request fails
        """
        params = {}
        endpoint = "/hearings"
        
        if committee_id:
            params["committee"] = committee_id
            
        response = await self.execute_request(endpoint=endpoint, params=params)
        
        # Validate response
        if not self.validate_response(response, ["results"]):
            raise CongressApiError("Invalid hearing updates response format", status_code=400, endpoint=endpoint)
            
        hearings = response.get("results", [])
        
        # Emit events for each hearing
        await self._emit_hearing_update_events(hearings)
        
        return hearings
    
    # Event emission methods
    
    async def _emit_floor_update_events(self, chamber: str, updates: List[Dict[str, Any]]) -> None:
        """Emit events for floor updates.
        
        Args:
            chamber: Chamber (house, senate)
            updates: List of floor updates
        """
        for update in updates:
            # Create payload
            payload = FloorUpdatePayload(
                event_time=self._parse_datetime(update.get("timestamp")),
                source=self.api_source,
                source_id=f"floor/{chamber}/{update.get('id', '')}",
                source_url=update.get("url", ""),
                resource_type="floor_update",
                chamber=chamber,
                action_time=self._parse_datetime(update.get("timestamp")),
                description=update.get("text", ""),
                data=update
            )
            
            # Emit event
            await self._event_manager.create_and_emit_event(
                event_type=EventType.FLOOR_PROCEEDINGS_UPDATE,
                payload=payload
            )
    
    async def _emit_vote_update_events(self, votes: List[Dict[str, Any]]) -> None:
        """Emit events for vote updates.
        
        Args:
            votes: List of vote updates
        """
        for vote in votes:
            # Create payload
            chamber = vote.get("chamber", "")
            vote_id = vote.get("voteNumber", "")
            congress = vote.get("congress", "")
            
            payload = VoteUpdatePayload(
                event_time=self._parse_datetime(vote.get("date")),
                source=self.api_source,
                source_id=f"vote/{congress}/{chamber}/{vote_id}",
                source_url=vote.get("url", ""),
                resource_type="vote",
                vote_id=vote_id,
                chamber=chamber,
                vote_time=self._parse_datetime(vote.get("date")),
                question=vote.get("question", ""),
                description=vote.get("title", ""),
                result=vote.get("result", ""),
                data=vote
            )
            
            # Emit event
            await self._event_manager.create_and_emit_event(
                event_type=EventType.VOTE_COMPLETED,
                payload=payload
            )
    
    async def _emit_calendar_update_events(self, chamber: str, calendar_items: List[Dict[str, Any]]) -> None:
        """Emit events for calendar updates.
        
        Args:
            chamber: Chamber (house, senate)
            calendar_items: List of calendar items
        """
        for item in calendar_items:
            # Create payload
            item_id = item.get("id", "")
            
            payload = CalendarUpdatePayload(
                event_time=datetime.utcnow(),
                source=self.api_source,
                source_id=f"calendar/{chamber}/{item_id}",
                source_url=item.get("url", ""),
                resource_type="calendar_item",
                chamber=chamber,
                calendar_id=item_id,
                scheduled_time=self._parse_datetime(item.get("scheduledAt")),
                description=item.get("description", ""),
                data=item
            )
            
            # Emit event
            await self._event_manager.create_and_emit_event(
                event_type=EventType.CALENDAR_ITEM_ADDED,
                payload=payload
            )
    
    async def _emit_hearing_update_events(self, hearings: List[Dict[str, Any]]) -> None:
        """Emit events for hearing updates.
        
        Args:
            hearings: List of hearing updates
        """
        for hearing in hearings:
            # Create payload
            committee_id = hearing.get("committee", {}).get("systemCode", "")
            hearing_id = hearing.get("id", "")
            
            payload = HearingUpdatePayload(
                event_time=datetime.utcnow(),
                source=self.api_source,
                source_id=f"hearing/{committee_id}/{hearing_id}",
                source_url=hearing.get("url", ""),
                resource_type="hearing",
                committee_id=committee_id,
                hearing_id=hearing_id,
                title=hearing.get("title", ""),
                scheduled_time=self._parse_datetime(hearing.get("scheduledAt")),
                location=hearing.get("location", ""),
                description=hearing.get("description", ""),
                data=hearing
            )
            
            # Emit event
            await self._event_manager.create_and_emit_event(
                event_type=EventType.HEARING_SCHEDULED,
                payload=payload
            )
    
    # Utility methods
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object.
        
        Args:
            date_str: Date string in ISO format
            
        Returns:
            Date object or None if parsing fails
        """
        if not date_str:
            return None
            
        try:
            if "T" in date_str:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
            return date.fromisoformat(date_str)
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse date: {date_str}")
            return None
    
    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object.
        
        Args:
            datetime_str: Datetime string in ISO format
            
        Returns:
            Datetime object or None if parsing fails
        """
        if not datetime_str:
            return datetime.utcnow()
            
        try:
            if "T" in datetime_str:
                return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            return datetime.combine(date.fromisoformat(datetime_str), datetime.min.time())
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse datetime: {datetime_str}")
            return datetime.utcnow()
    
    def _parse_chamber(self, chamber_str: Optional[str]) -> Optional[Chamber]:
        """Parse chamber string to Chamber enum.
        
        Args:
            chamber_str: Chamber string
            
        Returns:
            Chamber enum or None if parsing fails
        """
        if not chamber_str:
            return None
            
        chamber_map = {
            "House": Chamber.HOUSE,
            "Senate": Chamber.SENATE,
            "Both": Chamber.JOINT,
            "house": Chamber.HOUSE,
            "senate": Chamber.SENATE,
            "joint": Chamber.JOINT
        }
        
        return chamber_map.get(chamber_str)
        
    async def _emit_bill_event(self, event_type: EventType, bill_data: Dict[str, Any]) -> None:
        """Emit a bill event for testing.
        
        Args:
            event_type: Type of bill event
            bill_data: Bill data
        """
        congress = bill_data.get("congress")
        bill_type = bill_data.get("type")
        bill_number = bill_data.get("number")
        
        if not all([congress, bill_type, bill_number]):
            logger.error("Missing required bill identifiers")
            return
            
        # Create payload
        payload = EventPayload(
            event_time=datetime.utcnow(),
            source=self.api_source,
            source_id=f"bill/{congress}/{bill_type}{bill_number}",
            source_url=f"https://api.congress.gov/v3/bill/{congress}/{bill_type}/{bill_number}",
            resource_type="bill",
            data=bill_data
        )
        
        # Emit event
        await self._event_manager.create_and_emit_event(
            event_type=event_type,
            payload=payload
        )