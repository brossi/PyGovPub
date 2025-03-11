"""
PyGovPub API routers package.

This package contains FastAPI routers for different parts of the API.
"""

from pygovpub.api.routers.bills import router as bills_router
from pygovpub.api.routers.committees import router as committees_router
from pygovpub.api.routers.documents import router as documents_router
from pygovpub.api.routers.members import router as members_router

__all__ = [
    "bills_router",
    "committees_router",
    "documents_router",
    "members_router",
]