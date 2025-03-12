"""Tests for storage security integration with CORE-002 error handling."""
import os
import pytest
from unittest.mock import patch, MagicMock

from pygovpub.storage.security import StorageSecurity
from pygovpub.exceptions import (
    PyGovPubException, 
    AuthenticationError, 
    RateLimitError,
    APIError,
    ResourceNotFoundError,
    ValidationError
)


@pytest.fixture
def security():
    """Create a StorageSecurity instance with encryption enabled."""
    return StorageSecurity(encryption_enabled=True)


@pytest.mark.parametrize("scenario,error_input,expected_exception,expected_attributes", [
    # Scenario 1: Authentication failures
    (
        "authentication_failure",
        {
            "error_type": "AuthError", 
            "message": "Invalid credentials", 
            "provider": "lancedb"
        },
        AuthenticationError,
        {
            "provider": "lancedb",
            "error_code": "AUTH_INVALID_CREDENTIALS",
            "retry_possible": True
        }
    ),
    # Scenario 2: Rate limit violations
    (
        "rate_limit_violation",
        {
            "error_type": "RateLimitExceeded", 
            "message": "Too many requests", 
            "provider": "pinecone",
            "retry_after": 30
        },
        RateLimitError,
        {
            "provider": "pinecone",
            "error_code": "RATE_LIMIT_EXCEEDED", 
            "retry_after": 30,
            "retry_possible": True
        }
    ),
    # Scenario 3: Network failures
    (
        "network_failure",
        {
            "error_type": "ConnectionError", 
            "message": "Connection refused", 
            "provider": "lancedb"
        },
        APIError,
        {
            "provider": "lancedb",
            "error_code": "CONNECTION_ERROR",
            "retry_possible": True,
            "category": "network"
        }
    ),
    # Scenario 4: Resource not found
    (
        "resource_not_found",
        {
            "error_type": "NotFoundError", 
            "message": "Table not found", 
            "provider": "supabase",
            "resource_id": "legislative_bills"
        },
        ResourceNotFoundError,
        {
            "provider": "supabase",
            "error_code": "RESOURCE_NOT_FOUND",
            "resource_type": "table",
            "resource_id": "legislative_bills"
        }
    ),
    # Scenario 5: Data validation failures
    (
        "validation_failure",
        {
            "error_type": "ValidationError", 
            "message": "Invalid data format", 
            "provider": "pinecone",
            "field": "embedding",
            "details": "Vector dimension mismatch"
        },
        ValidationError,
        {
            "provider": "pinecone",
            "error_code": "VALIDATION_ERROR",
            "field": "embedding",
            "details": "Vector dimension mismatch"
        }
    ),
])
def test_error_mapping_integration(
    security, scenario, error_input, expected_exception, expected_attributes
):
    """Test integration with CORE-002 error handling for various scenarios."""
    # Mock the internal storage error
    storage_error = MagicMock()
    storage_error.to_dict.return_value = error_input
    
    # Test the error mapping
    with pytest.raises(expected_exception) as excinfo:
        security.map_storage_error(storage_error)
    
    # Verify the exception attributes
    for attr_name, attr_value in expected_attributes.items():
        assert hasattr(excinfo.value, attr_name), f"Exception missing attribute: {attr_name}"
        assert getattr(excinfo.value, attr_name) == attr_value, \
            f"Expected {attr_name}={attr_value}, got {getattr(excinfo.value, attr_name)}"


def test_error_propagation_from_encryption():
    """Test error propagation from encryption operations."""
    # Test with invalid key format
    with patch.dict(os.environ, {"PYGOVPUB_ENCRYPTION_KEY_V1": "invalid_key_format"}):
        with pytest.raises(PyGovPubException) as excinfo:
            security = StorageSecurity(encryption_enabled=True)
        
        assert "encryption key" in str(excinfo.value).lower()
        assert hasattr(excinfo.value, "error_code")
        assert excinfo.value.error_code == "ENCRYPTION_KEY_ERROR"


def test_credential_access_error_mapping():
    """Test mapping of credential access errors."""
    security = StorageSecurity(encryption_enabled=False)
    
    # Mock a credential access error
    with patch.object(security, '_get_credential_from_env', side_effect=KeyError("MISSING_KEY")):
        with pytest.raises(AuthenticationError) as excinfo:
            security.get_credential("some_missing_credential")
        
        assert "credential" in str(excinfo.value).lower()
        assert hasattr(excinfo.value, "error_code")
        assert excinfo.value.error_code == "CREDENTIAL_NOT_FOUND"


def test_tamper_detection_error_mapping():
    """Test mapping of tamper detection errors."""
    security = StorageSecurity(encryption_enabled=True)
    
    # Create tampered data
    tampered_data = {
        "field": "__ENC_V1__:gAAAAABh6tX7lQ==:invalid_hmac" 
    }
    
    with pytest.raises(ValidationError) as excinfo:
        security.decrypt_metadata(tampered_data)
    
    assert "tampered" in str(excinfo.value).lower()
    assert hasattr(excinfo.value, "error_code")
    assert excinfo.value.error_code == "DATA_INTEGRITY_ERROR"
    assert hasattr(excinfo.value, "field")
    assert excinfo.value.field == "field"


def test_error_context_preservation():
    """Test preservation of error context through mapping."""
    security = StorageSecurity(encryption_enabled=False)
    
    # Create an error with context
    original_error = ValueError("Original message")
    original_error.context = {
        "operation": "vector_search",
        "query_id": "test-query-123",
        "timestamp": "2025-03-12T12:34:56.789Z"
    }
    
    # Map the error
    try:
        security.map_storage_error(original_error)
    except Exception as mapped_error:
        # Check context preservation
        assert hasattr(mapped_error, "context")
        assert mapped_error.context["operation"] == "vector_search"
        assert mapped_error.context["query_id"] == "test-query-123"
        assert "original_error" in mapped_error.context
        assert isinstance(mapped_error.context["original_error"], ValueError)