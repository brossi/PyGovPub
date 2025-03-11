"""
API Router for directing requests to appropriate data sources.

This module provides routing capabilities to direct requests to either
Congress.gov or GovInfo.gov APIs based on request type and content needs.
It also handles normalization of responses from different sources.
"""

import logging
from datetime import datetime, date
from typing import Any, Dict, Optional, Union, List, Callable, TypeVar, Type

from pydantic import BaseModel

from pygovpub.api.clients import CongressClient, GovInfoClient
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import (
    ApiError, RateLimitExceededError, RouterError, 
    SourceUnavailableError, RouteNotFoundError, ApiErrorSource
)
from pygovpub.models.legislative import Bill, Member, Committee, Amendment
from pygovpub.models.documents import DocumentType
from pygovpub.models.legislative import Chamber, BillType, BillStatus, BillSponsor

# Configure logging
logger = logging.getLogger("pygovpub.api.router")


class ApiRouter:
    """Router for directing requests to appropriate API sources."""
    
    def __init__(self):
        """Initialize the API router."""
        self.clients = {}
        self._initialize_routing_rules()
        
    def register_client(self, source: ApiSource, client: Any) -> None:
        """Register an API client with the router.
        
        Args:
            source: API source
            client: API client
        """
        self.clients[source] = client
    
    def _initialize_routing_rules(self):
        """Initialize routing rules for different request types."""
        # Define the primary source for each request type
        self.primary_sources = {
            # Bill data primarily from Congress.gov
            "bill": ApiSource.CONGRESS,
            # Document data primarily from GovInfo.gov
            "document": ApiSource.GOVINFO,
            # Member data primarily from Congress.gov
            "member": ApiSource.CONGRESS,
            # Committee data primarily from Congress.gov
            "committee": ApiSource.CONGRESS,
            # Collection data primarily from GovInfo.gov
            "collection": ApiSource.GOVINFO,
        }
        
        # Define method mappings for each request type
        self.method_mappings = {
            "bill": {
                # Congress.gov methods
                ApiSource.CONGRESS: {
                    "get_bill": "get_bill",
                    "search_bills": "search_bills",
                    "get_bill_status": "get_bill_status",
                    "get_bill_actions": "get_bill_actions",
                    "get_bill_amendments": "get_bill_amendments",
                    "get_bill_cosponsors": "get_bill_cosponsors",
                },
                # GovInfo.gov methods (fallback or document-specific)
                ApiSource.GOVINFO: {
                    "get_bill_text": "get_package_content",
                    "get_bill_summary": "get_package_summary",
                }
            },
            "document": {
                # GovInfo.gov methods
                ApiSource.GOVINFO: {
                    "get_package_summary": "get_package_summary",
                    "get_package_content": "get_package_content",
                    "list_package_granules": "list_package_granules",
                    "get_granule_summary": "get_granule_summary",
                    "get_granule_content": "get_granule_content",
                },
                # No Congress.gov methods for documents
                ApiSource.CONGRESS: {}
            },
            "member": {
                # Congress.gov methods
                ApiSource.CONGRESS: {
                    "get_member": "get_member",
                    "search_members": "search_members",
                    "get_member_sponsored_bills": "get_member_sponsored_bills",
                    "get_member_cosponsored_bills": "get_member_cosponsored_bills",
                },
                # No GovInfo.gov methods for members
                ApiSource.GOVINFO: {}
            },
            "committee": {
                # Congress.gov methods
                ApiSource.CONGRESS: {
                    "get_committee": "get_committee",
                    "list_committees": "list_committees",
                    "get_committee_hearings": "get_committee_hearings",
                    "get_committee_reports": "get_committee_reports",
                },
                # No GovInfo.gov methods for committees
                ApiSource.GOVINFO: {}
            },
            "collection": {
                # GovInfo.gov methods
                ApiSource.GOVINFO: {
                    "list_collections": "list_collections",
                    "get_collection": "get_collection",
                },
                # No Congress.gov methods for collections
                ApiSource.CONGRESS: {}
            }
        }
    
    def register_client(self, client: Union[CongressClient, GovInfoClient]) -> None:
        """Register an API client with the router.
        
        Args:
            client: API client to register (Congress or GovInfo)
        """
        if not hasattr(client, 'api_source'):
            raise ValueError("Client must have api_source attribute")
        
        self.clients[client.api_source] = client
        logger.debug(f"Registered client for source: {client.api_source}")
    
    def is_source_available(self, source: str) -> bool:
        """Check if a source is available.
        
        Args:
            source: API source to check
            
        Returns:
            True if source is available, False otherwise
        """
        return source in self.clients
    
    def get_client(self, source: str) -> Union[CongressClient, GovInfoClient]:
        """Get client for a source.
        
        Args:
            source: API source
            
        Returns:
            API client for the source
            
        Raises:
            SourceUnavailableError: If source is not available
        """
        if not self.is_source_available(source):
            raise SourceUnavailableError(
                f"Source {source} is not available", 
                source=source
            )
        
        return self.clients[source]
    
    async def route_request(
        self,
        request_type: str,
        method: str,
        **kwargs
    ) -> Any:
        """Route a request to the appropriate API client.
        
        Args:
            request_type: Type of request (bill, document, etc.)
            method: Method to call
            **kwargs: Arguments to pass to the method
            
        Returns:
            Response from the API client
            
        Raises:
            RouterError: If routing fails
            SourceUnavailableError: If required source is not available
        """
        # Check if request type is valid
        if request_type not in self.primary_sources:
            raise RouterError(
                f"Unknown request type: {request_type}",
                request_details={"request_type": request_type, "method": method}
            )
        
        # Get primary source for this request type
        primary_source = self.primary_sources[request_type]
        
        # Check if primary source is available
        if not self.is_source_available(primary_source):
            # Primary source is not available, check if we have a fallback
            sources = list(self.method_mappings[request_type].keys())
            sources.remove(primary_source)
            
            if not sources or not any(self.is_source_available(s) for s in sources):
                raise SourceUnavailableError(
                    f"Primary source {primary_source} is not available and no fallbacks exist",
                    source=primary_source
                )
            
            # Use the first available fallback source
            for source in sources:
                if self.is_source_available(source):
                    # Check if this method exists in the fallback source
                    if method not in self.method_mappings[request_type][source]:
                        continue
                    
                    # Use this source instead
                    primary_source = source
                    break
        
        # Check if method exists for this source
        if method not in self.method_mappings[request_type][primary_source]:
            raise RouteNotFoundError(
                f"No route found for {request_type}.{method}",
                request_type=request_type,
                method=method
            )
        
        # Get client method name (could be different from requested method)
        client_method_name = self.method_mappings[request_type][primary_source][method]
        
        # Get client
        client = self.get_client(primary_source)
        
        # Check if client has the method
        if not hasattr(client, client_method_name):
            raise RouterError(
                f"Client for {primary_source} does not have method {client_method_name}",
                request_details={"source": primary_source, "method": client_method_name}
            )
        
        # Get method
        client_method = getattr(client, client_method_name)
        
        # Execute method
        try:
            logger.debug(f"Routing {request_type}.{method} to {primary_source}.{client_method_name}")
            result = await client_method(**kwargs)
            return result
        except RateLimitExceededError as e:
            # In a more advanced implementation, we could try a fallback source
            # if rate limit is exceeded on the primary source
            logger.warning(f"Rate limit exceeded on {primary_source}: {str(e)}")
            raise
        except ApiError as e:
            logger.error(f"API error on {primary_source}: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Error executing {primary_source}.{client_method_name}: {str(e)}")
            raise
    
    async def route_document_request(
        self,
        document_type: str,
        **kwargs
    ) -> Any:
        """Route a document request based on criteria rather than direct method.
        
        This method selects the appropriate document retrieval method based on
        the document type and other parameters.
        
        Args:
            document_type: Type of document (bill, fr, etc.)
            **kwargs: Document criteria (congress, bill_type, etc.)
            
        Returns:
            Document data from the appropriate source
            
        Raises:
            RouterError: If routing fails
        """
        # For now, route all document requests to GovInfo
        if document_type == "bill":
            # Check for required bill parameters
            required = ["congress", "bill_type", "bill_number"]
            if not all(param in kwargs for param in required):
                raise RouterError(
                    f"Missing required parameters for bill document: {', '.join(required)}"
                )
            
            # Resolve bill package ID first
            client = self.get_client(ApiSource.GOVINFO)
            package_id = await client.resolve_bill_package_id(
                congress=kwargs["congress"],
                bill_type=kwargs["bill_type"],
                bill_number=kwargs["bill_number"],
                version_code=kwargs.get("version_code", "ih")  # Default to introduced version
            )
            
            # Get bill summary
            return await self.route_request(
                request_type="document",
                method="get_package_summary",
                package_id=package_id
            )
        
        # For other document types, implement similar logic
        raise RouterError(
            f"Document type not supported: {document_type}",
            request_details={"document_type": document_type}
        )
        
    # Response normalization methods
    
    async def get_normalized_bill(
        self,
        congress: int,
        bill_type: str,
        bill_number: int,
        source: Optional[ApiSource] = None
    ) -> Dict[str, Any]:
        """Get a normalized bill representation.
        
        This method retrieves a bill from the specified source (or the default source)
        and normalizes the response to a common format.
        
        Args:
            congress: Congress number
            bill_type: Type of bill (e.g., 'hr', 's')
            bill_number: Bill number
            source: Specific source to use (optional)
            
        Returns:
            Normalized bill data
            
        Raises:
            RouterError: If routing fails
        """
        # Use specified source or default to Congress.gov
        if source is None:
            source = ApiSource.CONGRESS
        
        # Check if source is available
        if not self.is_source_available(source):
            raise SourceUnavailableError(
                f"Source {source} is not available", 
                source=source
            )
        
        # Get client for the source
        client = self.get_client(source)
        
        # Retrieve bill data from the appropriate source
        if source == ApiSource.CONGRESS:
            # Use Congress.gov API
            bill_data = await client.get_bill(
                congress=congress,
                bill_type=bill_type,
                bill_number=bill_number
            )
            
            # Normalize Congress.gov response
            return self._normalize_congress_bill(bill_data)
        else:
            # Use GovInfo.gov API
            # First, resolve the package ID
            package_id = await client.resolve_bill_package_id(
                congress=congress,
                bill_type=bill_type,
                bill_number=bill_number,
                version_code="ih"  # Default to introduced version
            )
            
            # Get bill summary
            bill_data = await client.get_package_summary(package_id=package_id)
            
            # Normalize GovInfo.gov response
            return self._normalize_govinfo_bill(bill_data)
    
    async def get_bill_model(
        self,
        congress: int,
        bill_type: str,
        bill_number: int,
        source: Optional[ApiSource] = None
    ) -> Bill:
        """Get a bill as a fully-typed model.
        
        This method retrieves a bill and converts it to a Pydantic model.
        
        Args:
            congress: Congress number
            bill_type: Type of bill (e.g., 'hr', 's')
            bill_number: Bill number
            source: Specific source to use (optional)
            
        Returns:
            Bill model object
            
        Raises:
            RouterError: If routing fails
        """
        # Get normalized bill data
        normalized_data = await self.get_normalized_bill(
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            source=source
        )
        
        # Convert to a Bill model
        return self._convert_to_model(normalized_data, Bill)
    
    # Normalization helper methods
    
    def _normalize_congress_bill(self, bill_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Congress.gov bill data.
        
        Args:
            bill_data: Raw bill data from Congress.gov
            
        Returns:
            Normalized bill data
        """
        # Create a normalized structure
        normalized = {
            "id": f"{bill_data.get('bill_type', '')}{bill_data.get('bill_number', '')}-{bill_data.get('congress', '')}",
            "title": bill_data.get("title", ""),
            "introduced_date": bill_data.get("introduced_date"),
            "source": "congress",
            "source_url": bill_data.get("congress_gov_url", ""),
            "sponsor": bill_data.get("sponsor", {}),
            "status": bill_data.get("status", ""),
            "latest_action": {}
        }
        
        # Handle latest action if available
        if "latest_action" in bill_data:
            normalized["latest_action"] = {
                "date": bill_data["latest_action"].get("date", ""),
                "text": bill_data["latest_action"].get("text", "")
            }
        
        return normalized
    
    def _normalize_govinfo_bill(self, bill_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize GovInfo.gov bill data.
        
        Args:
            bill_data: Raw bill data from GovInfo.gov
            
        Returns:
            Normalized bill data
        """
        # Extract bill type, number, and congress from package ID if available
        bill_type = bill_data.get("billType", "")
        bill_number = str(bill_data.get("billNumber", ""))
        congress = str(bill_data.get("congress", ""))
        
        # Create a normalized structure
        normalized = {
            "id": f"{bill_type}{bill_number}-{congress}",
            "title": bill_data.get("title", ""),
            "introduced_date": None,  # May need to extract from dateIssued
            "source": "govinfo",
            "source_url": bill_data.get("download", {}).get("pdfLink", ""),
            "sponsor": {},  # GovInfo doesn't typically include sponsor details
            "status": "",
            "latest_action": {}
        }
        
        # Extract date issued if available
        if "dateIssued" in bill_data:
            normalized["introduced_date"] = bill_data["dateIssued"]
        
        # Handle latest action if available
        if "lastAction" in bill_data:
            normalized["latest_action"] = {
                "date": bill_data["lastAction"].get("actionDate", ""),
                "text": bill_data["lastAction"].get("actionDesc", "")
            }
        
        return normalized
    
    def _convert_to_model(self, data: Dict[str, Any], model_class: Type) -> Any:
        """Convert dictionary data to a model instance.
        
        Args:
            data: Dictionary data
            model_class: Model class to instantiate
            
        Returns:
            Model instance
        """
        try:
            # For Bill model specifically, need to handle some field conversions
            if model_class == Bill:
                # Create source reference
                source_reference = {
                    "source": ApiSource.CONGRESS if data.get("source") == "congress" else ApiSource.GOVINFO,
                    "source_id": data.get("id", ""),
                    "source_url": data.get("source_url", ""),
                    "last_updated": datetime.now()  # Use current time as fallback
                }
                
                # Extract bill ID parts
                bill_id_parts = data.get("id", "").split("-")
                bill_number_type = bill_id_parts[0] if len(bill_id_parts) > 0 else ""
                
                # Split bill number and type if combined (e.g., "hr123")
                import re
                bill_type_match = re.match(r"([a-z]+)(\d+)", bill_number_type)
                bill_type = bill_type_match.group(1) if bill_type_match else ""
                bill_number = int(bill_type_match.group(2)) if bill_type_match else 0
                
                # Congress is the second part of the ID
                congress = int(bill_id_parts[1]) if len(bill_id_parts) > 1 else 0
                
                # Create bill sponsor if available
                sponsor_data = data.get("sponsor", {})
                sponsor = None
                if sponsor_data:
                    try:
                        sponsor = BillSponsor(
                            bioguide_id=sponsor_data.get("bioguide_id", "S000000"),  # Default value
                            name=sponsor_data.get("name", ""),
                            state=sponsor_data.get("state", ""),
                            party=sponsor_data.get("party", ""),
                            url=sponsor_data.get("url", ""),
                            full_name=sponsor_data.get("name", "")  # Use name as full_name if not provided
                        )
                    except Exception as e:
                        logger.warning(f"Error creating sponsor: {e}")
                        sponsor = None
                
                # Determine chamber from bill type
                chamber = Chamber.HOUSE if bill_type.startswith('h') else Chamber.SENATE
                
                # Convert bill type string to enum if possible
                try:
                    bill_type_enum = BillType(bill_type)
                except ValueError:
                    # Default to house bill if can't match
                    bill_type_enum = BillType.HOUSE_BILL if bill_type.startswith('h') else BillType.SENATE_BILL
                
                # Create model with extracted data
                return Bill(
                    bill_id=data.get("id", ""),
                    congress=congress,
                    bill_type=bill_type_enum,
                    bill_number=bill_number,
                    title=data.get("title", ""),
                    introduced_date=data.get("introduced_date"),
                    source_reference=source_reference,
                    origin_chamber=chamber,
                    sponsor=sponsor,
                    cosponsors=[],
                    committees=[],
                    versions=[],
                    actions=[],
                    summaries=[],
                    subjects=[]
                )
            
            # For other models, just pass the data directly
            return model_class(**data)
        except Exception as e:
            logger.error(f"Error converting to model {model_class.__name__}: {str(e)}")
            # Return the model with minimal required fields
            return model_class(**{k: data.get(k, "") for k in model_class.__annotations__})
            
    # Rate limit awareness methods
    
    async def check_rate_limit(self, source: ApiSource) -> bool:
        """Check if a source is within rate limits.
        
        Args:
            source: API source to check
            
        Returns:
            True if within rate limits, False otherwise
            
        Raises:
            SourceUnavailableError: If source is not available
        """
        # Get client for source
        client = self.get_client(source)
        
        # Check rate limit
        return await client.auth_manager.check_rate_limit(source)
    
    async def get_bill_with_rate_limit_aware_routing(
        self,
        congress: int,
        bill_type: str,
        bill_number: int
    ) -> Dict[str, Any]:
        """Get a bill using rate limit aware routing.
        
        This method will attempt to retrieve a bill from the primary source,
        but will fall back to an alternative source if the primary is rate limited.
        
        Args:
            congress: Congress number
            bill_type: Type of bill (e.g., 'hr', 's')
            bill_number: Bill number
            
        Returns:
            Bill data from the selected source
            
        Raises:
            RateLimitExceededError: If all sources are rate limited
            SourceUnavailableError: If required sources are not available
        """
        # Check if primary source (Congress.gov) is available
        primary_source = ApiSource.CONGRESS
        if not self.is_source_available(primary_source):
            raise SourceUnavailableError(
                f"Primary source {primary_source} is not available", 
                source=primary_source
            )
        
        # Check if fallback source (GovInfo.gov) is available
        fallback_source = ApiSource.GOVINFO
        if not self.is_source_available(fallback_source):
            raise SourceUnavailableError(
                f"Fallback source {fallback_source} is not available", 
                source=fallback_source
            )
        
        # Check rate limits for primary source
        primary_client = self.get_client(primary_source)
        primary_within_limits = await self.check_rate_limit(primary_source)
        
        if primary_within_limits:
            # Use primary source
            bill_data = await primary_client.get_bill(
                congress=congress,
                bill_type=bill_type,
                bill_number=bill_number
            )
            
            # Normalize and return
            return self._normalize_congress_bill(bill_data)
        
        # Primary source is rate limited, check fallback
        fallback_client = self.get_client(fallback_source)
        fallback_within_limits = await self.check_rate_limit(fallback_source)
        
        if fallback_within_limits:
            # Use fallback source
            package_id = await fallback_client.resolve_bill_package_id(
                congress=congress,
                bill_type=bill_type,
                bill_number=bill_number,
                version_code="ih"  # Default to introduced version
            )
            
            bill_data = await fallback_client.get_package_summary(package_id=package_id)
            
            # Normalize and return
            return self._normalize_govinfo_bill(bill_data)
        
        # All sources are rate limited
        raise RateLimitExceededError(
            "All sources are rate limited",
            api_source=ApiErrorSource.INTERNAL,
            retry_after=60  # Default retry after 60 seconds
        )