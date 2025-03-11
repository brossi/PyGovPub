"""
PyGovPub API routers package.

This package contains FastAPI routers for different parts of the API.
"""

from pygovpub.api.routers.bills import router as bills_router
from pygovpub.api.routers.committees import router as committees_router
from pygovpub.api.routers.congress import router as congress_router
from pygovpub.api.routers.documents import router as documents_router
from pygovpub.api.routers.members import router as members_router
from pygovpub.api.routers.webhooks import router as webhooks_router
from pygovpub.api.routers.cfr import router as cfr_router
from pygovpub.api.routers.court_opinions import router as court_opinions_router
from pygovpub.api.routers.search import router as search_router

__all__ = [
    "bills_router",
    "committees_router",
    "congress_router",
    "documents_router",
    "members_router",
    "webhooks_router",
    "cfr_router",
    "court_opinions_router",
    "search_router",
]