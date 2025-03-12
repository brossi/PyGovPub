"""
Factory for creating search managers.

This module provides a factory for creating search managers.
"""

import logging
from typing import Optional, List

from pygovpub.api.clients.congress import CongressClient
from pygovpub.api.clients.govinfo import GovInfoClient
from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.search.core import SearchManager
from pygovpub.search.providers import (
    LocalProvider,
    GovInfoProvider,
    CongressProvider
)

logger = logging.getLogger("pygovpub.search.factory")


async def create_search_manager(
    auth_manager: Optional[AuthManager] = None,
    include_local: bool = True,
    include_govinfo: bool = True,
    include_congress: bool = True
) -> SearchManager:
    """Create a search manager with specified providers.
    
    Args:
        auth_manager: Authentication manager
        include_local: Whether to include local provider
        include_govinfo: Whether to include GovInfo provider
        include_congress: Whether to include Congress provider
        
    Returns:
        Search manager
    """
    # Create manager
    manager = SearchManager()
    
    # Add local provider if specified
    if include_local:
        local_provider = LocalProvider()
        manager.register_provider(local_provider)
    
    # Add GovInfo provider if specified
    if include_govinfo and auth_manager:
        # Get client from auth manager
        try:
            auth_request = await auth_manager.authenticate_request(
                source=ApiSource.GOVINFO,
                endpoint="/"
            )
            
            if auth_request and hasattr(auth_request, 'api_key') and auth_request.api_key:
                govinfo_client = GovInfoClient(auth_manager=auth_manager)
                govinfo_provider = GovInfoProvider(client=govinfo_client)
                manager.register_provider(govinfo_provider)
            else:
                logger.warning("GovInfo API key not available, GovInfo provider not registered")
        except Exception as e:
            logger.exception(f"Error registering GovInfo provider: {e}")
    
    # Add Congress provider if specified
    if include_congress and auth_manager:
        # Get client from auth manager
        try:
            auth_request = await auth_manager.authenticate_request(
                source=ApiSource.CONGRESS,
                endpoint="/"
            )
            
            if auth_request and hasattr(auth_request, 'api_key') and auth_request.api_key:
                congress_client = CongressClient(auth_manager=auth_manager)
                congress_provider = CongressProvider(client=congress_client)
                manager.register_provider(congress_provider)
            else:
                logger.warning("Congress API key not available, Congress provider not registered")
        except Exception as e:
            logger.exception(f"Error registering Congress provider: {e}")
    
    # Initialize
    await manager.initialize()
    
    return manager


async def create_local_search_manager() -> SearchManager:
    """Create a search manager with only the local provider.
    
    Returns:
        Search manager
    """
    return await create_search_manager(
        include_local=True,
        include_govinfo=False,
        include_congress=False
    )