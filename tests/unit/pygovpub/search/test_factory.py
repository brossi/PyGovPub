"""
Unit tests for the search factory module.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.api.clients.congress import CongressClient
from pygovpub.api.clients.govinfo import GovInfoClient
from pygovpub.search.core import SearchManager
from pygovpub.search.factory import create_search_manager, create_local_search_manager
from pygovpub.search.providers import LocalProvider, GovInfoProvider, CongressProvider


class TestSearchFactory:
    """Tests for the search factory module."""
    
    @pytest.fixture
    def auth_manager(self):
        """Create a mock auth manager for testing."""
        auth_manager = MagicMock(spec=AuthManager)
        return auth_manager
    
    @pytest.fixture
    def auth_request_govinfo(self):
        """Create a mock auth request for GovInfo."""
        auth_request = MagicMock()
        auth_request.api_key = "test_govinfo_key"
        return auth_request
    
    @pytest.fixture
    def auth_request_congress(self):
        """Create a mock auth request for Congress."""
        auth_request = MagicMock()
        auth_request.api_key = "test_congress_key"
        return auth_request
    
    async def test_create_local_search_manager(self):
        """Test creating a search manager with only local provider."""
        # Call the factory function
        manager = await create_local_search_manager()
        
        # Check that it's a SearchManager instance
        assert isinstance(manager, SearchManager)
        
        # Check that it has only the local provider
        assert len(manager.providers) == 1
        assert "local" in manager.providers
        assert isinstance(manager.providers["local"], LocalProvider)
        
        # Check that it's initialized
        assert manager.initialized is True
    
    async def test_create_search_manager_all_providers(self, auth_manager, auth_request_govinfo, auth_request_congress):
        """Test creating a search manager with all providers."""
        # Setup auth manager to return valid auth requests
        auth_manager.authenticate_request = AsyncMock()
        
        # Configure AsyncMock to return correct auth requests based on source
        async def mock_authenticate_request(source, endpoint):
            if source == ApiSource.GOVINFO:
                return auth_request_govinfo
            else:
                return auth_request_congress
                
        auth_manager.authenticate_request.side_effect = mock_authenticate_request
        
        # Call the factory function
        with patch('pygovpub.search.factory.GovInfoClient') as mock_govinfo_client, \
             patch('pygovpub.search.factory.CongressClient') as mock_congress_client:
            # Setup mock clients
            mock_govinfo_instance = MagicMock(spec=GovInfoClient)
            mock_congress_instance = MagicMock(spec=CongressClient)
            mock_govinfo_client.return_value = mock_govinfo_instance
            mock_congress_client.return_value = mock_congress_instance
            
            # Create manager
            manager = await create_search_manager(
                auth_manager=auth_manager,
                include_local=True,
                include_govinfo=True,
                include_congress=True
            )
        
        # Check that it's a SearchManager instance
        assert isinstance(manager, SearchManager)
        
        # Check that it has all three providers
        assert len(manager.providers) == 3
        assert "local" in manager.providers
        assert "govinfo" in manager.providers
        assert "congress" in manager.providers
        
        # Check the types of providers
        assert isinstance(manager.providers["local"], LocalProvider)
        assert isinstance(manager.providers["govinfo"], GovInfoProvider)
        assert isinstance(manager.providers["congress"], CongressProvider)
        
        # Check that it's initialized
        assert manager.initialized is True
    
    async def test_create_search_manager_selective_providers(self, auth_manager, auth_request_govinfo):
        """Test creating a search manager with selective providers."""
        # Setup auth manager to return valid auth requests
        auth_manager.authenticate_request = AsyncMock()
        
        # Configure AsyncMock to return the GovInfo auth request
        async def mock_authenticate_request(source, endpoint):
            return auth_request_govinfo
                
        auth_manager.authenticate_request.side_effect = mock_authenticate_request
        
        # Call the factory function with only GovInfo provider
        with patch('pygovpub.search.factory.GovInfoClient') as mock_govinfo_client:
            # Setup mock client
            mock_govinfo_instance = MagicMock(spec=GovInfoClient)
            mock_govinfo_client.return_value = mock_govinfo_instance
            
            # Create manager
            manager = await create_search_manager(
                auth_manager=auth_manager,
                include_local=False,
                include_govinfo=True,
                include_congress=False
            )
        
        # Check that it only has the GovInfo provider
        assert len(manager.providers) == 1
        assert "govinfo" in manager.providers
        assert "local" not in manager.providers
        assert "congress" not in manager.providers
    
    async def test_create_search_manager_missing_auth(self, auth_manager):
        """Test creating a search manager with missing auth."""
        # Setup auth manager to return None for auth requests
        auth_manager.authenticate_request = AsyncMock()
        
        # Configure AsyncMock to return None
        async def mock_authenticate_none(source, endpoint):
            return None
                
        auth_manager.authenticate_request.side_effect = mock_authenticate_none
        
        # Call the factory function
        manager = await create_search_manager(
            auth_manager=auth_manager,
            include_local=True,
            include_govinfo=True,
            include_congress=True
        )
        
        # Check that it only has the local provider
        assert len(manager.providers) == 1
        assert "local" in manager.providers
        assert "govinfo" not in manager.providers
        assert "congress" not in manager.providers
    
    async def test_create_search_manager_missing_api_key(self, auth_manager):
        """Test creating a search manager with auth requests missing API keys."""
        # Create auth requests without API keys
        auth_request_no_key = MagicMock()
        auth_request_no_key.api_key = None
        
        # Setup auth manager to return auth requests without keys
        auth_manager.authenticate_request = AsyncMock()
        
        # Configure AsyncMock to return auth request without key
        async def mock_authenticate_no_key(source, endpoint):
            return auth_request_no_key
                
        auth_manager.authenticate_request.side_effect = mock_authenticate_no_key
        
        # Call the factory function
        manager = await create_search_manager(
            auth_manager=auth_manager,
            include_local=True,
            include_govinfo=True,
            include_congress=True
        )
        
        # Check that it only has the local provider
        assert len(manager.providers) == 1
        assert "local" in manager.providers
        assert "govinfo" not in manager.providers
        assert "congress" not in manager.providers
    
    async def test_create_search_manager_auth_error(self, auth_manager):
        """Test creating a search manager with auth errors."""
        # Setup auth manager to raise exceptions
        auth_manager.authenticate_request = AsyncMock()
        
        # Configure AsyncMock to raise exception
        async def mock_auth_error(source, endpoint):
            raise Exception("Auth error")
                
        auth_manager.authenticate_request.side_effect = mock_auth_error
        
        # Call the factory function
        manager = await create_search_manager(
            auth_manager=auth_manager,
            include_local=True,
            include_govinfo=True,
            include_congress=True
        )
        
        # Check that it only has the local provider
        assert len(manager.providers) == 1
        assert "local" in manager.providers
        assert "govinfo" not in manager.providers
        assert "congress" not in manager.providers
    
    async def test_create_search_manager_no_auth_manager(self):
        """Test creating a search manager without an auth manager."""
        # Call the factory function without auth manager
        manager = await create_search_manager(
            auth_manager=None,
            include_local=True,
            include_govinfo=True,
            include_congress=True
        )
        
        # Check that it only has the local provider
        assert len(manager.providers) == 1
        assert "local" in manager.providers
        assert "govinfo" not in manager.providers
        assert "congress" not in manager.providers


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])