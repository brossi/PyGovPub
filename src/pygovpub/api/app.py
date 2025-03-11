"""
PyGovPub FastAPI Application.

This module provides a FastAPI application for accessing PyGovPub data through
RESTful endpoints. It handles routing, error handling, and response formatting.
"""

import logging
from typing import Dict, Any, Optional

import fastapi
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from pygovpub.auth.auth_manager import AuthManager
from pygovpub.api.router import ApiRouter
from pygovpub.api.clients import CongressClient, GovInfoClient
from pygovpub.exceptions import (
    ApiError, RateLimitExceededError, RouterError, 
    SourceUnavailableError, RouteNotFoundError, AuthenticationError,
    PyGovPubException
)

# Import routers
from pygovpub.api.routers import (
    bills_router,
    committees_router,
    congress_router,
    documents_router,
    members_router,
    webhooks_router
)

# Configure logging
logger = logging.getLogger("pygovpub.api.app")

# Create FastAPI app
app = FastAPI(
    title="PyGovPub API",
    description="Unified access to U.S. Federal Government public data",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create API router
api_router = ApiRouter()


# Rate limit tracking middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for tracking rate limits."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request and track rate limit usage."""
        try:
            response = await call_next(request)
            return response
        except RateLimitExceededError as e:
            logger.warning(f"Rate limit exceeded: {e}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RateLimitExceeded",
                    "detail": str(e),
                    "retry_after": e.retry_after
                },
                headers={"Retry-After": str(e.retry_after)}
            )
        except Exception as e:
            logger.error(f"Unhandled error in middleware: {e}")
            raise


# Add middleware
app.add_middleware(RateLimitMiddleware)


# Exception handlers
@app.exception_handler(PyGovPubException)
async def pygovpub_exception_handler(request: Request, exc: PyGovPubException):
    """Handle PyGovPub exceptions."""
    status_code = getattr(exc, "status_code", 500)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": exc.__class__.__name__,
            "detail": str(exc)
        }
    )


@app.exception_handler(AuthenticationError)
async def auth_error_handler(request: Request, exc: AuthenticationError):
    """Handle authentication errors."""
    return JSONResponse(
        status_code=401,
        content={
            "error": "AuthenticationError",
            "detail": str(exc)
        }
    )


@app.exception_handler(RateLimitExceededError)
async def rate_limit_error_handler(request: Request, exc: RateLimitExceededError):
    """Handle rate limit errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "RateLimitExceeded",
            "detail": str(exc),
            "retry_after": exc.retry_after
        },
        headers={"Retry-After": str(exc.retry_after)}
    )


@app.exception_handler(SourceUnavailableError)
async def source_unavailable_handler(request: Request, exc: SourceUnavailableError):
    """Handle source unavailable errors."""
    return JSONResponse(
        status_code=503,
        content={
            "error": "SourceUnavailable",
            "detail": str(exc)
        }
    )


@app.exception_handler(RouteNotFoundError)
async def route_not_found_handler(request: Request, exc: RouteNotFoundError):
    """Handle route not found errors."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "RouteNotFound",
            "detail": str(exc)
        }
    )


# Dependencies
def get_auth_manager():
    """Get authentication manager."""
    return AuthManager()


def get_api_router(auth_manager: AuthManager = Depends(get_auth_manager)):
    """Get API router with required clients."""
    # Create router if not already in state
    if not hasattr(app, "state") or not hasattr(app.state, "api_router"):
        # Create clients
        congress_client = CongressClient(auth_manager=auth_manager)
        govinfo_client = GovInfoClient(auth_manager=auth_manager)
        
        # Create router
        router = ApiRouter()
        
        # Register clients
        router.register_client(congress_client)
        router.register_client(govinfo_client)
        
        # Store router in app state
        if not hasattr(app, "state"):
            app.state = type("AppState", (), {})()
        app.state.api_router = router
        
    return app.state.api_router


# Startup event
@app.on_event("startup")
async def startup():
    """Initialize resources on startup."""
    logger.info("Starting PyGovPub API")
    
    # Create auth manager and clients
    auth_manager = AuthManager()
    congress_client = CongressClient(auth_manager=auth_manager)
    govinfo_client = GovInfoClient(auth_manager=auth_manager)
    
    # Create router
    router = ApiRouter()
    
    # Register clients with router
    router.register_client(congress_client)
    router.register_client(govinfo_client)
    
    # Store router in app state
    app.state.api_router = router
    
    logger.info("PyGovPub API started")


# Shutdown event
@app.on_event("shutdown")
async def shutdown():
    """Clean up resources on shutdown."""
    logger.info("Shutting down PyGovPub API")
    # Add any cleanup code here
    

# Function to set up the routers
def setup_routers():
    """Set up all routers and attach them to the application."""
    from pygovpub.api.routers import (
        bills_router,
        committees_router,
        documents_router,
        members_router,
        cfr_router,
        court_opinions_router
    )
    
    # Add dependency to each router
    for router in [bills_router, committees_router, documents_router, members_router, 
                  cfr_router, court_opinions_router]:
        for route in router.routes:
            if hasattr(route, "dependant"):
                # Add the get_api_router dependency if it's not already there
                found = False
                for dep in route.dependant.dependencies:
                    if getattr(dep.call, "__name__", None) == "get_api_router":
                        found = True
                        break
                
                if not found:
                    route.dependant.dependencies.append(
                        fastapi.params.Depends(get_api_router)
                    )
    
    # Register all routers
    app.include_router(bills_router)
    app.include_router(committees_router)
    app.include_router(congress_router)
    app.include_router(documents_router)
    app.include_router(members_router)
    app.include_router(webhooks_router)
    app.include_router(cfr_router)
    app.include_router(court_opinions_router)

# Set up the routers
setup_routers()


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint returning API info."""
    return {
        "name": "PyGovPub API",
        "description": "Unified access to U.S. Federal Government public data",
        "version": "0.1.0",
        "documentation": "/docs",
        "endpoints": {
            "bills": "/bills",
            "committees": "/committees",
            "congress": "/congress",
            "documents": "/documents",
            "members": "/members",
            "webhooks": "/webhooks",
            "cfr": "/cfr",
            "court_opinions": "/court-opinions",
        }
    }


# Health check
@app.get("/health")
async def health_check(
    router: ApiRouter = Depends(get_api_router)
):
    """Health check endpoint."""
    from pygovpub.auth.models import ApiSource
    
    # Check availability of sources
    congress_available = router.is_source_available(ApiSource.CONGRESS)
    govinfo_available = router.is_source_available(ApiSource.GOVINFO)
    
    # Check rate limits
    congress_rate_limit = await router.check_rate_limit(ApiSource.CONGRESS) if congress_available else False
    govinfo_rate_limit = await router.check_rate_limit(ApiSource.GOVINFO) if govinfo_available else False
    
    # Determine overall status
    if congress_available and govinfo_available:
        if congress_rate_limit and govinfo_rate_limit:
            status = "healthy"
        else:
            status = "degraded"
    elif congress_available or govinfo_available:
        status = "degraded"
    else:
        status = "unhealthy"
    
    return {
        "status": status,
        "sources": {
            "congress": {
                "available": congress_available,
                "rate_limit_available": congress_rate_limit if congress_available else False
            },
            "govinfo": {
                "available": govinfo_available,
                "rate_limit_available": govinfo_rate_limit if govinfo_available else False
            }
        }
    }