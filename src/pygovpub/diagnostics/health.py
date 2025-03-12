"""
Health check and validation module for PyGovPub SDK.

This module provides functions to verify the SDK's configuration,
connections to external APIs, and system environment.
"""

import asyncio
import importlib.metadata
import os
import platform
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from pygovpub import __version__
from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.config import config
from pygovpub.exceptions import (
    AuthenticationError,
    RateLimitExceededError,
    ResourceNotFoundError,
    NetworkError,
    PyGovPubException
)
from pygovpub.recovery import CircuitBreakerRegistry


async def check_api_connectivity() -> List[Dict[str, Any]]:
    """
    Check connectivity to each configured API.

    Returns:
        List of API status information dictionaries
    """
    results = []
    auth_manager = AuthManager()

    # Define test endpoints for each API
    test_endpoints = {
        ApiSource.CONGRESS: "/v3/bill",
        ApiSource.GOVINFO: "/collections"
    }

    # Check each API
    for api_source in (ApiSource.CONGRESS, ApiSource.GOVINFO):
        api_result = {"name": api_source.value}
        
        try:
            # Time the request
            start_time = time.time()
            
            # Use a basic endpoint that should always work
            endpoint = test_endpoints[api_source]
            response = await auth_manager.execute_request_async(
                api_source=api_source,
                endpoint=endpoint,
                method="GET",
                params={"limit": 1},
                timeout=5.0
            )
            
            # Calculate response time
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            # Check status code
            if response.status_code == 200:
                api_result["status"] = "connected"
                api_result["latency_ms"] = latency_ms
            else:
                api_result["status"] = "error"
                api_result["message"] = f"Unexpected status code: {response.status_code}"
                api_result["latency_ms"] = latency_ms
                
        except AuthenticationError as e:
            api_result["status"] = "error"
            api_result["message"] = f"Authentication error: {str(e)}"
            
        except RateLimitExceededError as e:
            api_result["status"] = "rate_limited"
            api_result["message"] = f"Rate limit exceeded: {str(e)}"
            if hasattr(e, "retry_after") and e.retry_after:
                api_result["retry_after"] = e.retry_after
                
        except ResourceNotFoundError as e:
            api_result["status"] = "error"
            api_result["message"] = f"Resource not found: {str(e)}"
            
        except NetworkError as e:
            api_result["status"] = "error"
            api_result["message"] = f"Network error: {str(e)}"
            
        except Exception as e:
            api_result["status"] = "error"
            api_result["message"] = f"Unexpected error: {str(e)}"
        
        results.append(api_result)
    
    return results


def check_configuration() -> Dict[str, Any]:
    """
    Check the configuration for the SDK.

    Verifies environment variables, API keys, and other configuration settings.

    Returns:
        Dictionary with configuration status information
    """
    result = {
        "valid": True,
        "environment": config.environment,
        "api_configs": {},
        "issues": []
    }
    
    # Check API configurations
    for api_name, api_config in config.apis.items():
        api_result = {
            "base_url": api_config.base_url,
            "has_api_key": bool(api_config.api_key)
        }
        
        # Track issues if found
        if not api_config.api_key:
            result["valid"] = False
            result["issues"].append(f"Missing api_key for {api_name}")
        
        if not api_config.base_url:
            result["valid"] = False
            result["issues"].append(f"Missing base_url for {api_name}")
            
        result["api_configs"][api_name] = api_result
    
    # Check for required environment variables
    required_env_vars = [
        "PYGOVPUB_ENVIRONMENT"
    ]
    for var in required_env_vars:
        if var not in os.environ:
            result["valid"] = False
            result["issues"].append(f"Missing environment variable: {var}")
    
    return result


def check_system_info() -> Dict[str, Any]:
    """
    Gather system information for diagnostics.

    Returns:
        Dictionary with system information
    """
    result = {
        "python_version": platform.python_version(),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine()
        },
        "packages": {}
    }
    
    # Get package versions
    key_packages = [
        "pygovpub",
        "requests",
        "aiohttp",
        "fastapi",
        "pydantic",
        "sqlmodel",
        "structlog"
    ]
    
    for package in key_packages:
        try:
            version = importlib.metadata.version(package)
            result["packages"][package] = version
        except importlib.metadata.PackageNotFoundError:
            result["packages"][package] = "not installed"
    
    # Get memory information if psutil is available
    if HAS_PSUTIL:
        try:
            virtual_memory = psutil.virtual_memory()
            result["memory"] = {
                "total_gb": round(virtual_memory.total / (1024**3), 2),
                "available_gb": round(virtual_memory.available / (1024**3), 2),
                "percent_used": virtual_memory.percent
            }
        except Exception:
            pass
    
    return result


async def check_performance() -> Dict[str, Any]:
    """
    Measure performance metrics and resource usage.

    Returns:
        Dictionary with performance metrics
    """
    result = {
        "memory_usage_mb": 0,
        "cpu_percent": 0,
        "response_times_ms": {}
    }
    
    # Get memory usage of the current process
    if HAS_PSUTIL:
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            result["memory_usage_mb"] = round(memory_info.rss / (1024**2), 2)
            result["cpu_percent"] = process.cpu_percent(interval=0.1)
        except Exception:
            pass
    
    # Measure API response times
    try:
        api_results = await check_api_connectivity()
        for api_result in api_results:
            if api_result["status"] == "connected" and "latency_ms" in api_result:
                result["response_times_ms"][api_result["name"]] = api_result["latency_ms"]
    except Exception:
        pass
    
    return result


def get_status_summary(
    api_results: List[Dict[str, Any]], 
    config_results: Dict[str, Any],
    circuit_breaker_results: Optional[Dict[str, Any]] = None
) -> str:
    """
    Determine overall health status from component checks.

    Args:
        api_results: Results from API connectivity checks
        config_results: Results from configuration checks
        circuit_breaker_results: Results from circuit breaker checks

    Returns:
        Status string: "healthy", "degraded", "unhealthy", or "critical"
    """
    # If config is invalid, status is at least unhealthy
    if not config_results.get("valid", False):
        return "unhealthy"
    
    # Count API statuses
    statuses = {
        "connected": 0,
        "rate_limited": 0,
        "error": 0
    }
    
    for api in api_results:
        status = api.get("status", "error")
        if status in statuses:
            statuses[status] += 1
    
    # All APIs are in error state: critical
    if statuses["error"] == len(api_results) and len(api_results) > 0:
        return "critical"
    
    # At least one API has an error: unhealthy
    if statuses["error"] > 0:
        return "unhealthy"
    
    # Check circuit breaker status if available
    if circuit_breaker_results:
        # If any circuit is open, consider the system at least degraded
        open_circuits = circuit_breaker_results.get("state_counts", {}).get("open", 0)
        half_open_circuits = circuit_breaker_results.get("state_counts", {}).get("half_open", 0)
        
        # If more than 50% of circuits are open, consider the system unhealthy
        total_circuits = circuit_breaker_results.get("total_circuits", 0)
        if total_circuits > 0 and open_circuits > 0:
            open_percentage = (open_circuits / total_circuits) * 100
            if open_percentage >= 50:
                return "unhealthy"
            else:
                # At least one circuit is open, consider the system degraded
                return "degraded"
        
        # If any circuit is half-open, consider the system at least degraded
        if half_open_circuits > 0:
            return "degraded"
    
    # At least one API is rate limited: degraded
    if statuses["rate_limited"] > 0:
        return "degraded"
    
    # Everything is working correctly
    return "healthy"


def check_circuit_breakers() -> Dict[str, Any]:
    """
    Check the status of all circuit breakers in the system.
    
    Returns:
        Dictionary with circuit breaker status information
    """
    # Get the circuit breaker registry
    registry = CircuitBreakerRegistry()
    
    # Get status of all circuit breakers
    circuit_breakers = registry.get_all_statuses()
    
    # Count circuit breakers by state
    state_counts = {"closed": 0, "open": 0, "half_open": 0}
    critical_circuits = []
    
    for name, status in circuit_breakers.items():
        state = status.get("state", "unknown")
        if state in state_counts:
            state_counts[state] += 1
        
        # Track open/half-open circuits as potential issues
        if state in ("open", "half_open"):
            critical_circuits.append({
                "name": name,
                "state": state,
                "failure_count": status.get("failure_count", 0),
                "last_failure": status.get("last_failure"),
                "reset_time": status.get("reset_time", 0)
            })
    
    return {
        "total_circuits": len(circuit_breakers),
        "state_counts": state_counts,
        "critical_circuits": critical_circuits,
        "all_circuits": circuit_breakers
    }


def run_health_check() -> Dict[str, Any]:
    """
    Run a complete health check on the PyGovPub SDK.

    Returns:
        Dictionary with comprehensive health check results
    """
    # Create asyncio event loop
    loop = asyncio.new_event_loop()
    
    try:
        # Run API connectivity check
        api_results = loop.run_until_complete(check_api_connectivity())
        
        # Run configuration check
        config_results = check_configuration()
        
        # Run system check
        system_results = check_system_info()
        
        # Run performance check
        performance_results = loop.run_until_complete(check_performance())
        
        # Check circuit breakers
        circuit_breaker_results = check_circuit_breakers()
        
        # Check storage security
        try:
            from pygovpub.diagnostics.security_monitor import check_storage_security
            storage_security_results = check_storage_security()
        except ImportError:
            storage_security_results = {"secure": False, "error": "Security monitoring not installed"}
        except Exception as e:
            storage_security_results = {"secure": False, "error": str(e), "issues": ["Failed to run security check"]}
            
        # Get overall status (considering circuit breakers and security)
        status = get_status_summary(api_results, config_results, circuit_breaker_results)
        
        # Security issues take precedence and always result in unhealthy/critical status
        if not storage_security_results.get("secure", True):
            if storage_security_results.get("issues") and any("tamper" in str(issue).lower() for issue in storage_security_results.get("issues", [])):
                status = "critical"  # Possible tampering is critical
            else:
                status = "unhealthy"  # Other security issues are unhealthy
        
        # Build results dictionary
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "version": __version__,
            "apis": api_results,
            "configuration": config_results,
            "system": system_results,
            "performance": performance_results,
            "circuit_breakers": circuit_breaker_results,
            "storage_security": storage_security_results
        }
    finally:
        # Ensure the event loop is closed
        loop.close()