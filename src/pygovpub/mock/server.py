"""
Mock server implementation for PyGovPub SDK.

This module provides a FastAPI application that mimics the behavior of
the Congress.gov and GovInfo.gov APIs for development and testing.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import httpx
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pygovpub.config import config


class MockServer:
    """Mock server for Congress.gov and GovInfo.gov APIs."""
    
    def __init__(self, fixtures_path: str = "fixtures"):
        """Initialize the mock server.
        
        Args:
            fixtures_path: Path to fixture files
        """
        self.fixtures_path = fixtures_path
        self.rate_limits = {
            "congress": {
                "limit": 5000,
                "remaining": 5000,
                "reset": int(time.time()) + 3600
            },
            "govinfo": {
                "limit": 1000,
                "remaining": 1000,
                "reset": int(time.time()) + 3600
            }
        }
        self.record_mode = config.mock.record_mode
        self.simulate_rate_limits = config.mock.simulate_rate_limits
        self.latency_ms = config.mock.latency_ms
        self.app = FastAPI(title="PyGovPub Mock Server")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Call setup_routes directly in the constructor
        # This avoids using deprecated event handlers
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Set up API routes for the mock server."""
        # Congress.gov API routes
        self.app.get("/congress/v3/bill/{congress}/{bill_type}/{bill_number}", 
                     response_model=Dict[str, Any])(self._handle_congress_bill)
        self.app.get("/congress/v3/amendment/{congress}/{amendment_type}/{amendment_number}", 
                     response_model=Dict[str, Any])(self._handle_congress_amendment)
        self.app.get("/congress/v3/member/{bioguide_id}", 
                     response_model=Dict[str, Any])(self._handle_congress_member)
        self.app.get("/congress/v3/committee/{congress}/{chamber}/{committee_code}", 
                     response_model=Dict[str, Any])(self._handle_congress_committee)
        
        # GovInfo.gov API routes
        self.app.get("/collections", 
                     response_model=Dict[str, Any])(self._handle_govinfo_collections)
        self.app.get("/packages/{package_id}", 
                     response_model=Dict[str, Any])(self._handle_govinfo_package)
        self.app.get("/packages/{package_id}/summary", 
                     response_model=Dict[str, Any])(self._handle_govinfo_package_summary)
        self.app.get("/packages/{package_id}/content", 
                     response_class=Response)(self._handle_govinfo_package_content)
        
        # Health check route
        self.app.get("/health")(self._handle_health_check)
    
    async def _handle_congress_bill(
        self, 
        congress: str, 
        bill_type: str, 
        bill_number: str,
        request: Request,
        x_api_key: Optional[str] = Header(None)
    ) -> Dict[str, Any]:
        """Handle Congress.gov bill request.
        
        Args:
            congress: Congress number
            bill_type: Bill type
            bill_number: Bill number
            request: FastAPI request object
            x_api_key: API key header
        
        Returns:
            Bill data as JSON
        """
        await self._simulate_latency()
        self._check_auth("congress", x_api_key)
        
        if self.record_mode:
            return await self._record_response(
                "congress", 
                f"bill/{congress}/{bill_type}/{bill_number}",
                request
            )
        
        fixture_path = Path(self.fixtures_path) / "congress" / "bill" / f"{congress}_{bill_type}_{bill_number}.json"
        return self._load_fixture(fixture_path, default_fixture="congress_bill.json")
    
    async def _handle_congress_amendment(
        self, 
        congress: str, 
        amendment_type: str, 
        amendment_number: str,
        request: Request,
        x_api_key: Optional[str] = Header(None)
    ) -> Dict[str, Any]:
        """Handle Congress.gov amendment request."""
        await self._simulate_latency()
        self._check_auth("congress", x_api_key)
        
        if self.record_mode:
            return await self._record_response(
                "congress", 
                f"amendment/{congress}/{amendment_type}/{amendment_number}",
                request
            )
        
        fixture_path = Path(self.fixtures_path) / "congress" / "amendment" / f"{congress}_{amendment_type}_{amendment_number}.json"
        return self._load_fixture(fixture_path, default_fixture="congress_amendment.json")
    
    async def _handle_congress_member(
        self, 
        bioguide_id: str,
        request: Request,
        x_api_key: Optional[str] = Header(None)
    ) -> Dict[str, Any]:
        """Handle Congress.gov member request."""
        await self._simulate_latency()
        self._check_auth("congress", x_api_key)
        
        if self.record_mode:
            return await self._record_response(
                "congress", 
                f"member/{bioguide_id}",
                request
            )
        
        fixture_path = Path(self.fixtures_path) / "congress" / "member" / f"{bioguide_id}.json"
        return self._load_fixture(fixture_path, default_fixture="congress_member.json")
    
    async def _handle_congress_committee(
        self, 
        congress: str,
        chamber: str,
        committee_code: str,
        request: Request,
        x_api_key: Optional[str] = Header(None)
    ) -> Dict[str, Any]:
        """Handle Congress.gov committee request."""
        await self._simulate_latency()
        self._check_auth("congress", x_api_key)
        
        if self.record_mode:
            return await self._record_response(
                "congress", 
                f"committee/{congress}/{chamber}/{committee_code}",
                request
            )
        
        fixture_path = Path(self.fixtures_path) / "congress" / "committee" / f"{congress}_{chamber}_{committee_code}.json"
        return self._load_fixture(fixture_path, default_fixture="congress_committee.json")
    
    async def _handle_govinfo_collections(
        self,
        request: Request,
        api_key: Optional[str] = Query(None)
    ) -> Dict[str, Any]:
        """Handle GovInfo.gov collections request."""
        await self._simulate_latency()
        self._check_auth("govinfo", api_key, param=True)
        
        if self.record_mode:
            return await self._record_response(
                "govinfo", 
                "collections",
                request
            )
        
        fixture_path = Path(self.fixtures_path) / "govinfo" / "collections.json"
        return self._load_fixture(fixture_path, default_fixture="govinfo_collections.json")
    
    async def _handle_govinfo_package(
        self,
        package_id: str,
        request: Request,
        api_key: Optional[str] = Query(None)
    ) -> Dict[str, Any]:
        """Handle GovInfo.gov package request."""
        await self._simulate_latency()
        self._check_auth("govinfo", api_key, param=True)
        
        if self.record_mode:
            return await self._record_response(
                "govinfo", 
                f"packages/{package_id}",
                request
            )
        
        fixture_path = Path(self.fixtures_path) / "govinfo" / "packages" / f"{package_id}.json"
        return self._load_fixture(fixture_path, default_fixture="govinfo_package.json")
    
    async def _handle_govinfo_package_summary(
        self,
        package_id: str,
        request: Request,
        api_key: Optional[str] = Query(None)
    ) -> Dict[str, Any]:
        """Handle GovInfo.gov package summary request."""
        await self._simulate_latency()
        self._check_auth("govinfo", api_key, param=True)
        
        if self.record_mode:
            return await self._record_response(
                "govinfo", 
                f"packages/{package_id}/summary",
                request
            )
        
        fixture_path = Path(self.fixtures_path) / "govinfo" / "packages" / f"{package_id}_summary.json"
        return self._load_fixture(fixture_path, default_fixture="govinfo_package_summary.json")
    
    async def _handle_govinfo_package_content(
        self,
        package_id: str,
        request: Request,
        api_key: Optional[str] = Query(None),
        content_type: str = Query("pdf")
    ) -> Response:
        """Handle GovInfo.gov package content request."""
        await self._simulate_latency()
        self._check_auth("govinfo", api_key, param=True)
        
        if self.record_mode:
            # Record binary content (like PDF)
            client = httpx.AsyncClient()
            real_url = f"{config.apis.get('govinfo', {}).get('base_url', 'https://api.govinfo.gov')}/packages/{package_id}/content"
            params = dict(request.query_params)
            if config.apis.get("govinfo", {}).get("api_key"):
                params["api_key"] = config.apis.get("govinfo", {}).get("api_key")
            
            response = await client.get(real_url, params=params)
            
            # Save the content
            content_dir = Path(self.fixtures_path) / "govinfo" / "content"
            content_dir.mkdir(parents=True, exist_ok=True)
            
            file_ext = content_type or "pdf"
            content_path = content_dir / f"{package_id}.{file_ext}"
            content_path.write_bytes(response.content)
            
            return Response(
                content=response.content,
                media_type=response.headers.get("content-type", "application/pdf"),
                headers=dict(response.headers)
            )
        
        # Serve mock content
        content_type = content_type or "pdf"
        fixture_path = Path(self.fixtures_path) / "govinfo" / "content" / f"{package_id}.{content_type}"
        
        # Default to sample PDF if specific fixture doesn't exist
        if not fixture_path.exists():
            fixture_path = Path(self.fixtures_path) / "govinfo" / "content" / "sample.pdf"
        
        if not fixture_path.exists():
            raise HTTPException(status_code=404, detail="Content not found")
        
        content = fixture_path.read_bytes()
        media_type = "application/pdf" if content_type == "pdf" else "application/xml"
        
        return Response(
            content=content,
            media_type=media_type
        )
    
    async def _handle_health_check(self) -> Dict[str, Any]:
        """Handle health check request."""
        return {
            "status": "ok",
            "version": "1.0.0",
            "apis": {
                "congress": {
                    "status": "ok",
                    "rate_limit": self.rate_limits["congress"]
                },
                "govinfo": {
                    "status": "ok",
                    "rate_limit": self.rate_limits["govinfo"]
                }
            }
        }
    
    async def _simulate_latency(self) -> None:
        """Simulate API latency."""
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000)
    
    def _check_auth(
        self, 
        api: str, 
        api_key: Optional[str],
        param: bool = False
    ) -> None:
        """Check API authentication.
        
        Args:
            api: API name ("congress" or "govinfo")
            api_key: API key value
            param: If True, API key was in URL parameter (GovInfo style)
        
        Raises:
            HTTPException: If authentication fails
        """
        # In mock mode, we don't strictly require valid API keys
        if api_key is None:
            raise HTTPException(
                status_code=401,
                detail=f"Missing API key for {api}.gov API" + 
                       (f" (required query parameter: api_key)" if param else 
                        f" (required header: X-API-Key)")
            )
        
        # Simulate rate limits if configured
        if self.simulate_rate_limits:
            if self.rate_limits[api]["remaining"] <= 0:
                retry_after = self.rate_limits[api]["reset"] - int(time.time())
                if retry_after < 0:
                    # Reset the rate limit if expired
                    self.rate_limits[api]["remaining"] = self.rate_limits[api]["limit"]
                    self.rate_limits[api]["reset"] = int(time.time()) + 3600
                else:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded for {api}.gov API",
                        headers={"Retry-After": str(retry_after)}
                    )
            
            # Decrement remaining rate limit
            self.rate_limits[api]["remaining"] -= 1
    
    def _load_fixture(
        self, 
        fixture_path: Path,
        default_fixture: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load fixture data from file.
        
        Args:
            fixture_path: Path to fixture file
            default_fixture: Fallback fixture file if specific one doesn't exist
        
        Returns:
            Fixture data as dict
            
        Raises:
            HTTPException: If fixture file not found
        """
        if fixture_path.exists():
            try:
                with open(fixture_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=500,
                    detail=f"Invalid JSON in fixture: {fixture_path}"
                )
        
        # Try default fixture if specific one doesn't exist
        if default_fixture:
            default_path = Path(self.fixtures_path) / "defaults" / default_fixture
            if default_path.exists():
                try:
                    with open(default_path, "r") as f:
                        return json.load(f)
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Invalid JSON in default fixture: {default_path}"
                    )
        
        # If no fixture found, return a minimal valid response
        if "bill" in str(fixture_path):
            return {"bill": {"congress": 117, "type": "hr", "number": "1234", "title": "Mock Bill"}}
        elif "amendment" in str(fixture_path):
            return {"amendment": {"congress": 117, "type": "hamdt", "number": "123"}}
        elif "member" in str(fixture_path):
            return {"member": {"bioguideId": "M000000", "name": "Mock Member"}}
        elif "committee" in str(fixture_path):
            return {"committee": {"congress": 117, "chamber": "house", "systemCode": "hsju"}}
        elif "collections" in str(fixture_path):
            return {"collections": [{"collectionCode": "BILLS", "name": "Congressional Bills"}]}
        elif "package" in str(fixture_path):
            return {"package": {"packageId": "BILLS-117hr1234enr", "title": "Mock Bill"}}
        
        # Generic fallback
        return {"mock": True, "message": "No specific fixture found"}
    
    async def _record_response(
        self, 
        api: str, 
        endpoint: str,
        request: Request
    ) -> Dict[str, Any]:
        """Record a real API response to a fixture file.
        
        Args:
            api: API name ("congress" or "govinfo")
            endpoint: API endpoint
            request: FastAPI request object
        
        Returns:
            API response as dict
        """
        if api not in config.apis:
            raise HTTPException(
                status_code=500,
                detail=f"No configuration for {api} API in record mode"
            )
        
        # Build the real request
        client = httpx.AsyncClient()
        real_url = f"{config.apis[api].base_url}/{endpoint}"
        
        # Forward query parameters
        params = dict(request.query_params)
        
        # Add API key as needed
        if api == "govinfo":
            params["api_key"] = config.apis[api].api_key
        
        # Forward headers (except host)
        headers = dict(request.headers)
        headers.pop("host", None)
        
        if api == "congress":
            headers["X-API-Key"] = config.apis[api].api_key
        
        try:
            response = await client.get(real_url, params=params, headers=headers)
            response.raise_for_status()
            
            # Parse JSON response
            response_data = response.json()
            
            # Save to fixture file
            fixture_dir = Path(self.fixtures_path) / api / endpoint.split("/")[0]
            fixture_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename based on endpoint
            parts = endpoint.split("/")
            if len(parts) == 1:
                fixture_name = f"{parts[0]}.json"
            else:
                fixture_name = f"{parts[1:]}.json".replace("/", "_")
            
            fixture_path = fixture_dir / fixture_name
            
            with open(fixture_path, "w") as f:
                json.dump(response_data, f, indent=2)
            
            return response_data
            
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error from {api} API: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error communicating with {api} API: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error in record mode: {str(e)}"
            )


def create_app() -> FastAPI:
    """Create a FastAPI app for the mock server.
    
    Returns:
        FastAPI app instance
    """
    fixtures_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "fixtures"
    )
    server = MockServer(fixtures_path=fixtures_path)
    return server.app


# Global server instance for start/stop functions
_server_process = None


async def start_mock_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    log_level: str = "info"
) -> None:
    """Start the mock server in a separate process.
    
    Args:
        host: Server host
        port: Server port
        log_level: Logging level
    """
    global _server_process
    
    if _server_process is not None:
        return  # Server already running
    
    # Create a config object for uvicorn
    config = uvicorn.Config(
        "pygovpub.mock.server:create_app",
        host=host,
        port=port,
        log_level=log_level,
        factory=True
    )
    
    # Start the server in a new process
    server = uvicorn.Server(config)
    _server_process = asyncio.create_task(server.serve())


async def stop_mock_server() -> None:
    """Stop the mock server."""
    global _server_process
    
    if _server_process is not None:
        # Cancel the task
        _server_process.cancel()
        # Set to None explicitly rather than waiting for completion
        # This makes the function more testable and achieves the same result
        _server_process = None