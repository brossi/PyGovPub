"""
GovInfo.gov API client.

This module provides a client for interacting with the GovInfo.gov API,
including endpoints for collections, packages, granules, and document retrieval.
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
    DocumentPublishedPayload, DocumentUpdatedPayload
)
from pygovpub.exceptions import ApiError, GovInfoApiError, AuthenticationError
from pygovpub.models.documents import (
    DocumentFormat, DocumentType, Collection,
    Granule, Package, SourceReference
)

# Configure logging
logger = logging.getLogger("pygovpub.api.govinfo")


class GovInfoClient(BaseApiClient):
    """Client for the GovInfo.gov API."""
    
    def __init__(self, auth_manager: Optional[AuthManager] = None):
        """Initialize GovInfo.gov API client.
        
        Args:
            auth_manager: Authentication manager instance
        """
        super().__init__(auth_manager, ApiSource.GOVINFO)
        self._event_manager = get_event_manager()
    
    # Collection endpoints
    
    async def list_collections(self) -> List[Collection]:
        """Get list of available collections.
        
        Returns:
            List of collections
            
        Raises:
            ApiError: If request fails
        """
        endpoint = "/collections"
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["collections"]):
            raise GovInfoApiError("Invalid collections response format", status_code=400, endpoint=endpoint)
            
        return self._transform_collections_response(response)
    
    async def get_collection(
        self,
        collection_code: str,
        start_date: Optional[Union[str, date, datetime]] = None,
        end_date: Optional[Union[str, date, datetime]] = None,
        offset: int = 0,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """Get collection contents.
        
        Args:
            collection_code: Collection code (e.g., BILLS, FR)
            start_date: Start date for filtering
            end_date: End date for filtering
            offset: Result offset for pagination
            page_size: Maximum number of results per page
            
        Returns:
            Dictionary with collection packages and pagination info
            
        Raises:
            ApiError: If request fails
        """
        # Construct date parameters
        date_params = ""
        if start_date and end_date:
            # Format dates as ISO strings if they aren't already
            start_str = start_date if isinstance(start_date, str) else self._format_date(start_date)
            end_str = end_date if isinstance(end_date, str) else self._format_date(end_date)
            date_params = f"/{start_str}/{end_str}"
        
        endpoint = f"/collections/{collection_code}{date_params}"
        params = {
            "offset": offset,
            "pageSize": page_size
        }
        
        response = await self.execute_request(endpoint=endpoint, params=params)
        
        # Validate response
        if not self.validate_response(response, ["packages"]):
            raise GovInfoApiError("Invalid collection response format", status_code=400, endpoint=endpoint)
            
        return self._transform_collection_response(response, collection_code)
    
    # Package endpoints
    
    async def get_package_summary(self, package_id: str) -> Package:
        """Get summary information about a package.
        
        Args:
            package_id: Package ID (e.g., BILLS-115hr1625enr)
            
        Returns:
            Package object with summary information
            
        Raises:
            ApiError: If request fails
        """
        endpoint = f"/packages/{package_id}/summary"
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["download", "dateIssued"]):
            raise GovInfoApiError("Invalid package summary response format", status_code=400, endpoint=endpoint)
            
        return self._transform_package_summary_response(response, package_id)
    
    async def get_package_content(
        self,
        package_id: str,
        content_type: DocumentFormat = DocumentFormat.PDF
    ) -> bytes:
        """Get package content in specified format.
        
        Args:
            package_id: Package ID
            content_type: Content format (PDF, XML, etc.)
            
        Returns:
            Binary content data
            
        Raises:
            ApiError: If request fails
        """
        # Map format to API content type
        format_map = {
            DocumentFormat.PDF: "pdf",
            DocumentFormat.XML: "xml",
            DocumentFormat.HTML: "html",
            DocumentFormat.MODS: "mods"
        }
        
        format_str = format_map.get(content_type, "pdf")
        endpoint = f"/packages/{package_id}/{format_str}"
        
        # Use binary response handling
        auth_request = self.auth_manager.authenticate_request(
            source=self.api_source,
            endpoint=endpoint
        )
        
        try:
            # This is a placeholder for binary content retrieval
            # In a real implementation, we would handle binary data properly
            # For now, return an empty bytes object
            return bytes()
        except Exception as e:
            raise GovInfoApiError(
                f"Failed to retrieve package content: {e}",
                status_code=500,
                endpoint=endpoint
            )
    
    # Granule endpoints
    
    async def list_package_granules(
        self,
        package_id: str,
        offset: int = 0,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """List granules in a package.
        
        Args:
            package_id: Package ID
            offset: Result offset for pagination
            page_size: Maximum number of results per page
            
        Returns:
            Dictionary with granules and pagination info
            
        Raises:
            ApiError: If request fails
        """
        endpoint = f"/packages/{package_id}/granules"
        params = {
            "offset": offset,
            "pageSize": page_size
        }
        
        response = await self.execute_request(endpoint=endpoint, params=params)
        
        # Validate response
        if not self.validate_response(response, ["granules"]):
            raise GovInfoApiError("Invalid granules response format", status_code=400, endpoint=endpoint)
            
        return self._transform_granules_response(response, package_id)
    
    async def get_granule_summary(self, package_id: str, granule_id: str) -> Granule:
        """Get summary information about a granule.
        
        Args:
            package_id: Package ID
            granule_id: Granule ID
            
        Returns:
            Granule object with summary information
            
        Raises:
            ApiError: If request fails
        """
        endpoint = f"/packages/{package_id}/granules/{granule_id}/summary"
        response = await self.execute_request(endpoint=endpoint)
        
        # Validate response
        if not self.validate_response(response, ["download"]):
            raise GovInfoApiError("Invalid granule summary response format", status_code=400, endpoint=endpoint)
            
        return self._transform_granule_summary_response(response, package_id, granule_id)
    
    async def get_granule_content(
        self,
        package_id: str,
        granule_id: str,
        content_type: DocumentFormat = DocumentFormat.PDF
    ) -> bytes:
        """Get granule content in specified format.
        
        Args:
            package_id: Package ID
            granule_id: Granule ID
            content_type: Content format (PDF, XML, etc.)
            
        Returns:
            Binary content data
            
        Raises:
            ApiError: If request fails
        """
        # Map format to API content type
        format_map = {
            DocumentFormat.PDF: "pdf",
            DocumentFormat.XML: "xml",
            DocumentFormat.HTML: "html",
            DocumentFormat.MODS: "mods"
        }
        
        format_str = format_map.get(content_type, "pdf")
        endpoint = f"/packages/{package_id}/granules/{granule_id}/{format_str}"
        
        # Use binary response handling
        auth_request = self.auth_manager.authenticate_request(
            source=self.api_source,
            endpoint=endpoint
        )
        
        try:
            # This is a placeholder for binary content retrieval
            # In a real implementation, we would handle binary data properly
            # For now, return an empty bytes object
            return bytes()
        except Exception as e:
            raise GovInfoApiError(
                f"Failed to retrieve granule content: {e}",
                status_code=500,
                endpoint=endpoint
            )
    
    # Package ID resolution methods
    
    async def resolve_bill_package_id(
        self,
        congress: int,
        bill_type: str,
        bill_number: int,
        version_code: str
    ) -> str:
        """Resolve bill package ID from components.
        
        Args:
            congress: Congress number (e.g., 117)
            bill_type: Type of bill (e.g., 'hr', 's')
            bill_number: Bill number
            version_code: Version code (e.g., 'enr', 'ih')
            
        Returns:
            Package ID string
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Validate inputs
        if not (congress and bill_type and bill_number and version_code):
            raise ValueError("All parameters are required")
            
        # Construct bill package ID
        return f"BILLS-{congress}{bill_type}{bill_number}{version_code}"
    
    async def resolve_fr_package_id(self, date_str: str, fr_doc_number: str) -> str:
        """Resolve Federal Register package ID from components.
        
        Args:
            date_str: Date in YYYY-MM-DD format
            fr_doc_number: Federal Register document number
            
        Returns:
            Package ID string
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Validate inputs
        if not (date_str and fr_doc_number):
            raise ValueError("Date and document number are required")
            
        # Construct FR package ID
        return f"FR-{date_str}_{fr_doc_number}"
    
    # Transformation methods
    
    def _transform_collections_response(self, response: Dict[str, Any]) -> List[Collection]:
        """Transform collections response.
        
        Args:
            response: API response
            
        Returns:
            List of collection objects
        """
        collections = []
        
        # Extract collection data
        for collection_data in response.get("collections", []):
            collection = Collection(
                code=collection_data.get("collectionCode", ""),
                name=collection_data.get("collectionName", ""),
                member_count=collection_data.get("collectionSize", 0),
                last_updated=self._parse_datetime(collection_data.get("lastModified"))
            )
            collections.append(collection)
        
        return collections
    
    def _transform_collection_response(
        self,
        response: Dict[str, Any],
        collection_code: str
    ) -> Dict[str, Any]:
        """Transform collection response.
        
        Args:
            response: API response
            collection_code: Collection code
            
        Returns:
            Dictionary with packages and pagination info
        """
        packages = []
        
        # Extract package data
        for package_data in response.get("packages", []):
            # Create source reference
            source_ref = SourceReference(
                source=self.api_source,
                source_id=package_data.get("packageId", ""),
                source_url=package_data.get("packageLink", ""),
                last_updated=self._parse_datetime(package_data.get("lastModified"))
            )
            
            # Create package with minimal data
            package = Package(
                package_id=package_data.get("packageId", ""),
                collection_code=collection_code,
                last_modified=self._parse_datetime(package_data.get("lastModified")),
                source_reference=source_ref
            )
            
            packages.append(package)
        
        # Extract pagination info
        pagination = {
            "count": response.get("count", 0),
            "next_page": response.get("nextPage"),
            "previous_page": response.get("previousPage")
        }
        
        return {
            "packages": packages,
            "pagination": pagination
        }
    
    def _transform_package_summary_response(
        self,
        response: Dict[str, Any],
        package_id: str
    ) -> Package:
        """Transform package summary response.
        
        Args:
            response: API response
            package_id: Package ID
            
        Returns:
            Package object
        """
        # Extract collection code from package ID
        collection_code = package_id.split("-")[0] if "-" in package_id else ""
        
        # Create source reference
        source_ref = SourceReference(
            source=self.api_source,
            source_id=package_id,
            source_url=response.get("download", {}).get("pdfLink", ""),
            last_updated=self._parse_datetime(response.get("lastModified"))
        )
        
        # Get available formats
        formats = []
        if response.get("download", {}).get("pdfLink"):
            formats.append(DocumentFormat.PDF)
        if response.get("download", {}).get("xmlLink"):
            formats.append(DocumentFormat.XML)
        if response.get("download", {}).get("modsLink"):
            formats.append(DocumentFormat.MODS)
        
        # Create package object
        package = Package(
            package_id=package_id,
            collection_code=collection_code,
            title=response.get("title", ""),
            date_issued=self._parse_date(response.get("dateIssued")),
            last_modified=self._parse_datetime(response.get("lastModified")),
            pdf_url=response.get("download", {}).get("pdfLink", ""),
            xml_url=response.get("download", {}).get("xmlLink", ""),
            mods_url=response.get("download", {}).get("modsLink", ""),
            details=response,
            formats=formats,
            source_reference=source_ref
        )
        
        # Emit document event
        self._emit_document_event(package)
        
        return package
    
    def _transform_granules_response(
        self,
        response: Dict[str, Any],
        package_id: str
    ) -> Dict[str, Any]:
        """Transform granules response.
        
        Args:
            response: API response
            package_id: Package ID
            
        Returns:
            Dictionary with granules and pagination info
        """
        granules = []
        
        # Extract granule data
        for granule_data in response.get("granules", []):
            granule_id = granule_data.get("granuleId", "")
            
            # Create source reference
            source_ref = SourceReference(
                source=self.api_source,
                source_id=f"{package_id}/{granule_id}",
                source_url=granule_data.get("granuleLink", ""),
                last_updated=self._parse_datetime(granule_data.get("lastModified"))
            )
            
            # Create granule with minimal data
            granule = Granule(
                granule_id=granule_id,
                package_id=package_id,
                title=granule_data.get("title", ""),
                last_modified=self._parse_datetime(granule_data.get("lastModified")),
                source_reference=source_ref
            )
            
            granules.append(granule)
        
        # Extract pagination info
        pagination = {
            "count": response.get("count", 0),
            "next_page": response.get("nextPage"),
            "previous_page": response.get("previousPage")
        }
        
        return {
            "granules": granules,
            "pagination": pagination
        }
    
    def _transform_granule_summary_response(
        self,
        response: Dict[str, Any],
        package_id: str,
        granule_id: str
    ) -> Granule:
        """Transform granule summary response.
        
        Args:
            response: API response
            package_id: Package ID
            granule_id: Granule ID
            
        Returns:
            Granule object
        """
        # Create source reference
        source_ref = SourceReference(
            source=self.api_source,
            source_id=f"{package_id}/{granule_id}",
            source_url=response.get("download", {}).get("pdfLink", ""),
            last_updated=self._parse_datetime(response.get("lastModified"))
        )
        
        # Get available formats
        formats = []
        if response.get("download", {}).get("pdfLink"):
            formats.append(DocumentFormat.PDF)
        if response.get("download", {}).get("xmlLink"):
            formats.append(DocumentFormat.XML)
        if response.get("download", {}).get("modsLink"):
            formats.append(DocumentFormat.MODS)
        
        # Create granule object
        granule = Granule(
            granule_id=granule_id,
            package_id=package_id,
            title=response.get("title", ""),
            date_issued=self._parse_date(response.get("dateIssued")),
            last_modified=self._parse_datetime(response.get("lastModified")),
            pdf_url=response.get("download", {}).get("pdfLink", ""),
            xml_url=response.get("download", {}).get("xmlLink", ""),
            mods_url=response.get("download", {}).get("modsLink", ""),
            details=response,
            formats=formats,
            source_reference=source_ref
        )
        
        # Emit document event
        self._emit_granule_event(granule)
        
        return granule
    
    # Event emission methods
    
    def _emit_document_event(self, package: Package) -> None:
        """Emit document event for package.
        
        Args:
            package: Package object
        """
        # Only emit events asynchronously in a production context
        # This is synchronous to simplify the implementation
        
        # Create payload
        payload = DocumentPublishedPayload(
            event_time=datetime.utcnow(),
            source=self.api_source,
            source_id=package.package_id,
            source_url=package.source_reference.source_url if package.source_reference else "",
            resource_type="document",
            document_id=package.package_id,
            document_type=self._get_document_type(package.package_id),
            title=package.title,
            published_date=package.date_issued,
            data=package.model_dump()
        )
        
        # In a real implementation, we would await this call
        # self._event_manager.create_and_emit_event(
        #     event_type=EventType.DOCUMENT_PUBLISHED,
        #     payload=payload
        # )
    
    def _emit_granule_event(self, granule: Granule) -> None:
        """Emit document event for granule.
        
        Args:
            granule: Granule object
        """
        # Only emit events asynchronously in a production context
        # This is synchronous to simplify the implementation
        
        # Create payload
        payload = DocumentPublishedPayload(
            event_time=datetime.utcnow(),
            source=self.api_source,
            source_id=f"{granule.package_id}/{granule.granule_id}",
            source_url=granule.source_reference.source_url if granule.source_reference else "",
            resource_type="granule",
            document_id=granule.granule_id,
            document_type=self._get_document_type(granule.package_id),
            title=granule.title,
            published_date=granule.date_issued,
            data=granule.model_dump()
        )
        
        # In a real implementation, we would await this call
        # self._event_manager.create_and_emit_event(
        #     event_type=EventType.DOCUMENT_PUBLISHED,
        #     payload=payload
        # )
    
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
            return None
            
        try:
            if "T" in datetime_str:
                return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            return datetime.combine(date.fromisoformat(datetime_str), datetime.min.time())
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse datetime: {datetime_str}")
            return None
    
    def _format_date(self, date_obj: Union[date, datetime]) -> str:
        """Format date object as ISO string.
        
        Args:
            date_obj: Date or datetime object
            
        Returns:
            ISO format date string
        """
        if isinstance(date_obj, datetime):
            return date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")
        return date_obj.strftime("%Y-%m-%d")
    
    def _get_document_type(self, package_id: str) -> DocumentType:
        """Determine document type from package ID.
        
        Args:
            package_id: Package ID
            
        Returns:
            Document type
        """
        if package_id.startswith("BILLS-"):
            return DocumentType.BILL
        if package_id.startswith("FR-"):
            return DocumentType.FEDERAL_REGISTER
        if package_id.startswith("CREC-"):
            return DocumentType.CONGRESSIONAL_RECORD
        if package_id.startswith("CFR-"):
            return DocumentType.CODE_OF_FEDERAL_REGULATIONS
        if package_id.startswith("STATUTE-"):
            return DocumentType.STATUTE
        if package_id.startswith("PLAW-"):
            return DocumentType.PUBLIC_LAW
        if package_id.startswith("CHRG-"):
            return DocumentType.CONGRESSIONAL_HEARING
        if package_id.startswith("CPRT-"):
            return DocumentType.CONGRESSIONAL_REPORT
        if package_id.startswith("CDOC-"):
            return DocumentType.CONGRESSIONAL_DOCUMENT
        if package_id.startswith("USCOURTS-"):
            return DocumentType.COURT_OPINION
        return DocumentType.OTHER