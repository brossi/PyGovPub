"""
API contract testing module for PyGovPub mock server.

This module provides utilities to validate API contracts through
the mock server, ensuring requests and responses adhere to defined schemas.
"""

import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import jsonschema
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field

from pygovpub.config import config
from pygovpub.validation.test_contract import (
    ApiSource, 
    ContractValidator,
    validate_request,
    validate_response
)

logger = logging.getLogger(__name__)


class ContractViolation(BaseModel):
    """Model for API contract violations."""
    
    timestamp: str = Field(..., description="ISO timestamp when the violation occurred")
    api_source: str = Field(..., description="API source (congress, govinfo, internal)")
    endpoint: str = Field(..., description="API endpoint path")
    violation_type: str = Field(..., description="Type of violation (request, response)")
    errors: List[str] = Field(..., description="List of validation errors")
    data: Dict[str, Any] = Field(..., description="The data that violated the contract")


class ContractMonitor:
    """Monitor for API contracts in the mock server."""
    
    def __init__(self, violations_dir: Optional[str] = None):
        """Initialize the contract monitor.
        
        Args:
            violations_dir: Directory to store contract violations
        """
        if violations_dir:
            self.violations_dir = Path(violations_dir)
        else:
            # Default to a violations directory in the current directory
            self.violations_dir = Path.cwd() / "contract_violations"
            
        # Ensure the directory exists
        os.makedirs(self.violations_dir, exist_ok=True)
        
        # Initialize the validator
        self.validator = ContractValidator()
        
        # Track the violations seen in this session
        self.violations: List[ContractViolation] = []
        
    async def validate_request_contract(
        self, 
        api_source: Union[str, ApiSource],
        endpoint: str,
        request: Request
    ) -> Tuple[bool, List[str]]:
        """Validate an API request against its contract.
        
        Args:
            api_source: API source (congress, govinfo, internal)
            endpoint: API endpoint path
            request: FastAPI request object
            
        Returns:
            Tuple of (is_valid, error_messages)
            
        Raises:
            HTTPException: If contract validation is enabled and fails
        """
        # Normalize API source
        if isinstance(api_source, ApiSource):
            api_source = api_source.value
            
        # Get request data
        if request.method in ("GET", "DELETE"):
            # For GET/DELETE, use query parameters
            request_data = dict(request.query_params)
        else:
            # For POST/PUT/PATCH, use JSON body
            try:
                request_data = await request.json()
            except:
                request_data = {}
                
        # Add URL path parameters to request data
        # These are already extracted by FastAPI but we add them to the validation data
        request_data.update(request.path_params)
        
        # Validate the request
        is_valid, errors = await validate_request(api_source, endpoint, request_data)
        
        # Check if strict validation is enabled in config
        strict_validation = getattr(config.mock, "strict_contract_validation", False)
        
        if not is_valid:
            # Record the violation
            violation = ContractViolation(
                timestamp=datetime.now(timezone.utc).isoformat(),
                api_source=api_source,
                endpoint=endpoint,
                violation_type="request",
                errors=errors,
                data=request_data
            )
            self.record_violation(violation)
            
            # If strict validation is enabled, raise an exception
            if strict_validation:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "API contract violation in request",
                        "errors": errors
                    }
                )
                
        return is_valid, errors
    
    def validate_response_contract(
        self,
        api_source: Union[str, ApiSource],
        endpoint: str,
        response_data: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate an API response against its contract.
        
        Args:
            api_source: API source (congress, govinfo, internal)
            endpoint: API endpoint path
            response_data: Response data to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
            
        Raises:
            HTTPException: If contract validation is enabled and fails
        """
        # Normalize API source
        if isinstance(api_source, ApiSource):
            api_source = api_source.value
            
        # Validate the response
        is_valid, errors = validate_response(api_source, endpoint, response_data)
        
        # Check if strict validation is enabled in config
        strict_validation = getattr(config.mock, "strict_contract_validation", False)
        
        if not is_valid:
            # Record the violation
            violation = ContractViolation(
                timestamp=datetime.now(timezone.utc).isoformat(),
                api_source=api_source,
                endpoint=endpoint,
                violation_type="response",
                errors=errors,
                data=response_data
            )
            self.record_violation(violation)
            
            # If strict validation is enabled, raise an exception
            if strict_validation:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "API contract violation in response",
                        "errors": errors
                    }
                )
                
        return is_valid, errors
    
    def record_violation(self, violation: ContractViolation) -> str:
        """Record a contract violation.
        
        Args:
            violation: The contract violation to record
            
        Returns:
            Path to the violation file
        """
        # Add to in-memory tracking
        self.violations.append(violation)
        
        # Create a filename with timestamp
        timestamp = datetime.fromisoformat(violation.timestamp.replace("Z", "+00:00"))
        filename = f"{timestamp.strftime('%Y%m%d%H%M%S')}_{violation.api_source}_{violation.endpoint.replace('/', '_')}_{violation.violation_type}.json"
        file_path = self.violations_dir / filename
        
        # Write to file
        with open(file_path, "w") as f:
            f.write(violation.model_dump_json(indent=2))
            
        logger.warning(
            f"API contract violation: {violation.api_source}:{violation.endpoint} "
            f"({violation.violation_type}): {', '.join(violation.errors)}"
        )
        
        return str(file_path)
    
    def get_violations(
        self,
        api_source: Optional[str] = None,
        endpoint: Optional[str] = None,
        violation_type: Optional[str] = None
    ) -> List[ContractViolation]:
        """Get recorded contract violations.
        
        Args:
            api_source: Filter by API source
            endpoint: Filter by endpoint
            violation_type: Filter by violation type
            
        Returns:
            List of matching violations
        """
        filtered = self.violations
        
        if api_source:
            filtered = [v for v in filtered if v.api_source == api_source]
        if endpoint:
            filtered = [v for v in filtered if v.endpoint == endpoint]
        if violation_type:
            filtered = [v for v in filtered if v.violation_type == violation_type]
            
        return filtered
    
    def clear_violations(self) -> int:
        """Clear all recorded violations.
        
        Returns:
            Number of violations cleared
        """
        count = len(self.violations)
        self.violations = []
        return count
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a report of contract violations.
        
        Returns:
            Report data
        """
        api_sources = set(v.api_source for v in self.violations)
        endpoints = set(v.endpoint for v in self.violations)
        
        # Counters
        request_violations = len([v for v in self.violations if v.violation_type == "request"])
        response_violations = len([v for v in self.violations if v.violation_type == "response"])
        
        # Group by API source
        by_api = {}
        for api in api_sources:
            api_violations = [v for v in self.violations if v.api_source == api]
            by_api[api] = {
                "total": len(api_violations),
                "request": len([v for v in api_violations if v.violation_type == "request"]),
                "response": len([v for v in api_violations if v.violation_type == "response"]),
                "endpoints": list(set(v.endpoint for v in api_violations))
            }
            
        # Most common errors
        error_counts = {}
        for v in self.violations:
            for error in v.errors:
                error_counts[error] = error_counts.get(error, 0) + 1
                
        most_common_errors = sorted(
            error_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]  # Top 10
        
        return {
            "total_violations": len(self.violations),
            "unique_api_sources": len(api_sources),
            "unique_endpoints": len(endpoints),
            "request_violations": request_violations,
            "response_violations": response_violations,
            "by_api": by_api,
            "most_common_errors": [
                {"error": error, "count": count}
                for error, count in most_common_errors
            ],
            "first_violation": self.violations[0].timestamp if self.violations else None,
            "last_violation": self.violations[-1].timestamp if self.violations else None
        }


# Singleton instance for the monitor
_monitor: Optional[ContractMonitor] = None


def get_monitor() -> ContractMonitor:
    """Get the singleton monitor instance.
    
    Returns:
        Contract monitor instance
    """
    global _monitor
    if _monitor is None:
        _monitor = ContractMonitor()
    return _monitor


async def validate_request(
    api_source: Union[str, ApiSource],
    endpoint: str,
    request: Request
) -> Tuple[bool, List[str]]:
    """Validate an API request against its contract.
    
    Args:
        api_source: API source (congress, govinfo, internal)
        endpoint: API endpoint path
        request: FastAPI request object
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    monitor = get_monitor()
    return await monitor.validate_request_contract(api_source, endpoint, request)


def validate_response(
    api_source: Union[str, ApiSource],
    endpoint: str,
    response_data: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """Validate an API response against its contract.
    
    Args:
        api_source: API source (congress, govinfo, internal)
        endpoint: API endpoint path
        response_data: Response data to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    monitor = get_monitor()
    return monitor.validate_response_contract(api_source, endpoint, response_data)


def get_report() -> Dict[str, Any]:
    """Get a contract violations report.
    
    Returns:
        Report data
    """
    monitor = get_monitor()
    return monitor.generate_report()


def clear_violations() -> int:
    """Clear all recorded violations.
    
    Returns:
        Number of violations cleared
    """
    monitor = get_monitor()
    return monitor.clear_violations()