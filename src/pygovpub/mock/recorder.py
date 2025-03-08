"""
Recording module for capturing API responses.

This module provides utilities for recording and replaying real API responses,
allowing developers to create and update test fixtures without manual intervention.
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import httpx
from fastapi import Request, Response
from pydantic import BaseModel

from pygovpub.config import config

logger = logging.getLogger(__name__)


class RecordingSession(BaseModel):
    """A session for recording API responses."""
    
    recording_id: str
    start_time: datetime
    api_name: str
    base_url: str
    requests: List[Dict[str, Any]] = []
    storage_path: str


class Recorder:
    """API response recorder for creating fixtures."""
    
    def __init__(self, fixtures_dir: str = "fixtures"):
        """Initialize the recorder.
        
        Args:
            fixtures_dir: Directory to store fixtures
        """
        self.fixtures_dir = fixtures_dir
        self.sessions: Dict[str, RecordingSession] = {}
        self.active_session: Optional[str] = None
    
    async def start_session(self, api_name: str) -> str:
        """Start a new recording session.
        
        Args:
            api_name: Name of the API to record ("congress" or "govinfo")
        
        Returns:
            Session ID
        """
        if api_name not in ["congress", "govinfo"]:
            raise ValueError(f"Invalid API name: {api_name}")
        
        if api_name not in config.apis:
            raise ValueError(f"No configuration found for {api_name} API")
        
        # Create session ID
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        session_id = f"{api_name}_{timestamp}"
        
        # Create storage directory
        storage_path = os.path.join(self.fixtures_dir, "recordings", session_id)
        os.makedirs(storage_path, exist_ok=True)
        
        # Create session
        self.sessions[session_id] = RecordingSession(
            recording_id=session_id,
            start_time=datetime.utcnow(),
            api_name=api_name,
            base_url=config.apis[api_name].base_url,
            storage_path=storage_path
        )
        
        self.active_session = session_id
        logger.info(f"Started recording session {session_id} for {api_name} API")
        
        return session_id
    
    async def record_request(
        self, 
        endpoint: str, 
        method: str = "GET",
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a request to the API and save the response.
        
        Args:
            endpoint: API endpoint (relative to base URL)
            method: HTTP method
            params: Query parameters
            headers: HTTP headers
            session_id: Session ID (defaults to active session)
        
        Returns:
            API response data
        """
        session_id = session_id or self.active_session
        if not session_id:
            raise ValueError("No active recording session")
        
        if session_id not in self.sessions:
            raise ValueError(f"Invalid session ID: {session_id}")
        
        session = self.sessions[session_id]
        
        # Prepare request
        client = httpx.AsyncClient()
        url = f"{session.base_url}/{endpoint.lstrip('/')}"
        
        # Add authentication
        params = params or {}
        headers = headers or {}
        
        if session.api_name == "congress":
            headers["X-API-Key"] = config.apis["congress"].api_key
        elif session.api_name == "govinfo":
            params["api_key"] = config.apis["govinfo"].api_key
        
        # Make request
        try:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            
            # Store request and response
            request_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "method": method,
                "endpoint": endpoint,
                "params": params,
                "headers": {k: v for k, v in headers.items() if k.lower() != "x-api-key"},
                "response": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                }
            }
            
            # Add response data (handle both JSON and binary)
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                request_data["response"]["data"] = response.json()
                
                # Save as JSON fixture
                fixture_path = os.path.join(
                    session.storage_path,
                    f"{endpoint.replace('/', '_')}.json"
                )
                with open(fixture_path, "w") as f:
                    json.dump(response.json(), f, indent=2)
                
                # Return JSON data
                return response.json()
            else:
                # Binary content (like PDF)
                request_data["response"]["content_type"] = content_type
                request_data["response"]["size"] = len(response.content)
                
                # Save as binary fixture
                ext = "pdf" if "pdf" in content_type else "bin"
                fixture_path = os.path.join(
                    session.storage_path,
                    f"{endpoint.replace('/', '_')}.{ext}"
                )
                with open(fixture_path, "wb") as f:
                    f.write(response.content)
                
                # Return content info
                return {
                    "content_type": content_type,
                    "size": len(response.content),
                    "path": fixture_path
                }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Error recording {endpoint}: {e}")
            raise
        finally:
            # Update session
            session.requests.append(request_data)
            await client.aclose()
    
    async def end_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """End a recording session and save metadata.
        
        Args:
            session_id: Session ID (defaults to active session)
        
        Returns:
            Session metadata
        """
        session_id = session_id or self.active_session
        if not session_id:
            raise ValueError("No active recording session")
        
        if session_id not in self.sessions:
            raise ValueError(f"Invalid session ID: {session_id}")
        
        session = self.sessions[session_id]
        
        # Save session metadata
        metadata_path = os.path.join(session.storage_path, "metadata.json")
        metadata = {
            "recording_id": session.recording_id,
            "api_name": session.api_name,
            "base_url": session.base_url,
            "start_time": session.start_time.isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "request_count": len(session.requests),
            "requests": session.requests
        }
        
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Clean up
        if self.active_session == session_id:
            self.active_session = None
        
        logger.info(f"Ended recording session {session_id} with {len(session.requests)} requests")
        
        return metadata
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all recording sessions.
        
        Returns:
            List of session metadata
        """
        sessions = []
        recordings_dir = os.path.join(self.fixtures_dir, "recordings")
        if not os.path.exists(recordings_dir):
            return sessions
        
        for session_dir in os.listdir(recordings_dir):
            metadata_path = os.path.join(recordings_dir, session_dir, "metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, "r") as f:
                    try:
                        metadata = json.load(f)
                        sessions.append(metadata)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid metadata file: {metadata_path}")
        
        return sorted(sessions, key=lambda s: s.get("start_time", ""), reverse=True)
    
    async def save_fixture(
        self, 
        session_id: str,
        endpoint: str,
        fixture_type: str,
        destination: Optional[str] = None
    ) -> str:
        """Save a recorded response as a fixture.
        
        Args:
            session_id: Recording session ID
            endpoint: API endpoint for the fixture
            fixture_type: Type of fixture ("default" or "specific")
            destination: Destination path (optional)
        
        Returns:
            Path to saved fixture
        """
        recordings_dir = os.path.join(self.fixtures_dir, "recordings")
        session_dir = os.path.join(recordings_dir, session_id)
        
        if not os.path.exists(session_dir):
            raise ValueError(f"Recording session not found: {session_id}")
        
        # Find the recorded response
        source_file = None
        for filename in os.listdir(session_dir):
            if filename.startswith(endpoint.replace("/", "_")) and filename.endswith(".json"):
                source_file = os.path.join(session_dir, filename)
                break
        
        if not source_file:
            raise ValueError(f"No recorded response found for {endpoint}")
        
        # Determine destination path
        if not destination:
            api_name = session_id.split("_")[0]
            if fixture_type == "default":
                destination = os.path.join(
                    self.fixtures_dir, 
                    "defaults",
                    f"{api_name}_{endpoint.split('/')[0]}.json"
                )
            else:
                path_parts = endpoint.split("/")
                if len(path_parts) > 1:
                    endpoint_dir = os.path.join(self.fixtures_dir, api_name, path_parts[0])
                    os.makedirs(endpoint_dir, exist_ok=True)
                    destination = os.path.join(
                        endpoint_dir,
                        f"{path_parts[1:]}.json".replace("/", "_")
                    )
                else:
                    destination = os.path.join(
                        self.fixtures_dir,
                        api_name,
                        f"{endpoint}.json"
                    )
        
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        # Copy the file
        with open(source_file, "r") as src, open(destination, "w") as dst:
            content = json.load(src)
            json.dump(content, dst, indent=2)
        
        logger.info(f"Saved fixture from {source_file} to {destination}")
        return destination


@asynccontextmanager
async def recording_session(api_name: str):
    """Context manager for recording API sessions.
    
    Args:
        api_name: Name of the API to record
    
    Yields:
        Recorder instance
    """
    recorder = Recorder()
    session_id = await recorder.start_session(api_name)
    try:
        yield recorder
    finally:
        await recorder.end_session(session_id)