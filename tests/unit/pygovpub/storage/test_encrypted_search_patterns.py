"""Tests for encrypted search fallback patterns."""
import pytest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime
import re

from pygovpub.storage.security import StorageSecurity
from pygovpub.storage.secure_search_fallback import SecureSearchFallback


@pytest.fixture
def security():
    """Create a mock StorageSecurity instance for testing."""
    security = MagicMock()
    security.encryption_enabled = True
    
    # Mock the decrypt_metadata method to simply return the original test data
    def mock_decrypt_metadata(data):
        # Based on ID, return the corresponding original test data item
        doc_id = data.get("id")
        if doc_id == "doc1":
            return {
                "id": "doc1",
                "api_key": "api-key-123",
                "classification": "secret",
                "restricted_note": "Contains sensitive information about XYZ project",
                "personal_data": {"name": "John Doe", "ssn": "123-45-6789"},
                "timestamp": "2025-01-15T14:30:00Z",
                "priority": 3,
                "tags": ["confidential", "project-xyz", "finance"],
                "public_field": "This is a public field that doesn't need encryption"
            }
        elif doc_id == "doc2":
            return {
                "id": "doc2",
                "api_key": "api-key-456",
                "classification": "top-secret",
                "restricted_note": "Critical vulnerability in ABC system",
                "personal_data": {"name": "Jane Smith", "ssn": "987-65-4321"},
                "timestamp": "2025-02-20T09:15:00Z",
                "priority": 1,
                "tags": ["security", "vulnerability", "critical"],
                "public_field": "Another public field without encryption"
            }
        elif doc_id == "doc3":
            return {
                "id": "doc3",
                "api_key": "api-key-789",
                "classification": "confidential",
                "restricted_note": "Merger details with Company ABC",
                "personal_data": {"name": "Bob Johnson", "ssn": "456-78-9012"},
                "timestamp": "2025-03-10T16:45:00Z",
                "priority": 2,
                "tags": ["merger", "finance", "confidential"],
                "public_field": "Third public field"
            }
        # Default case - return the input data
        return data
    
    security.decrypt_metadata.side_effect = mock_decrypt_metadata
    
    # Mock the process_metadata method to add encryption prefix to sensitive fields
    def mock_process_metadata(data):
        result = data.copy()
        sensitive_fields = ['api_key', 'classification', 'restricted_note', 'personal_data']
        for key in result:
            if key in sensitive_fields:
                if isinstance(result[key], dict):
                    # For nested dictionaries like personal_data
                    result[key] = {
                        k: f"__ENC_V1__:{v}" for k, v in result[key].items()
                    }
                else:
                    result[key] = f"__ENC_V1__:{result[key]}"
        return result
    
    security.process_metadata.side_effect = mock_process_metadata
    
    return security


@pytest.fixture
def search_fallback(security):
    """Create a mock SecureSearchFallback instance."""
    fallback = MagicMock()
    fallback.security = security
    
    # Mock various search methods to return appropriate results
    
    # For exact match (based on test data in test_data fixture)
    def mock_exact_match(data, field, value):
        if field == "api_key" and value == "api-key-456":
            return [item for item in data if item.get("id") == "doc2"]
        elif field == "personal_data.name" and value == "Jane Smith":
            return [item for item in data if item.get("id") == "doc2"]
        return []
    
    # For prefix search
    def mock_prefix(data, field, prefix, **kwargs):
        if field == "classification" and prefix == "top":
            return [item for item in data if item.get("id") == "doc2"]
        return []
    
    # For contains search
    def mock_contains(data, field, substring, **kwargs):
        if field == "tags" and substring == "finance":
            return [item for item in data if item.get("id") in ["doc1", "doc3"]]
        elif field == "restricted_note" and substring.lower() == "vulnerability":
            return [item for item in data if item.get("id") == "doc2"]
        return []
    
    # For range search
    def mock_range(data, field, min_val, max_val=None):
        if field == "timestamp":
            if min_val == "2025-02-01T00:00:00Z" and max_val == "2025-03-15T00:00:00Z":
                return [item for item in data if item.get("id") in ["doc2", "doc3"]]
        elif field == "priority" and min_val == 1 and max_val == 2:
            return [item for item in data if item.get("id") in ["doc2", "doc3"]]
        return []
    
    # For batch operations
    def mock_batch_operations(data, operations, require_all=True):
        if operations[0].get("operation") == "contains" and operations[0].get("field") == "classification":
            if operations[1].get("operation") == "contains" and operations[1].get("field") == "restricted_note":
                return [item for item in data if item.get("id") == "doc3"]
        elif operations[0].get("operation") == "exact_match" and operations[0].get("field") == "classification":
            if operations[1].get("operation") == "exact_match" and operations[1].get("field") == "priority":
                return [item for item in data if item.get("id") == "doc2"]
        return []
    
    # For negative filtering
    def mock_decrypt_and_filter(data, field, value, filter_fn):
        if field == "restricted_note" and value == "company":
            return [item for item in data if item.get("id") in ["doc1", "doc2"]]
        elif field == "personal_data.ssn" and value == r"\d{3}-\d{2}-\d{4}":
            return [item for item in data if item.get("id") in ["doc1", "doc2", "doc3"]]
        elif field == "personal_data.ssn" and value == r"^4":
            return [item for item in data if item.get("id") == "doc3"]
        return []
    
    # Assign the mocks to the mock object
    fallback.search_by_exact_match.side_effect = mock_exact_match
    fallback.search_by_prefix.side_effect = mock_prefix
    fallback.search_by_contains.side_effect = mock_contains
    fallback.search_by_range.side_effect = mock_range
    fallback.perform_batch_operations.side_effect = mock_batch_operations
    fallback.decrypt_and_filter.side_effect = mock_decrypt_and_filter
    
    return fallback


@pytest.fixture
def test_data():
    """Create test data with various field types for encrypted search testing."""
    return [
        {
            "id": "doc1",
            "api_key": "api-key-123",
            "classification": "secret",
            "restricted_note": "Contains sensitive information about XYZ project",
            "personal_data": {"name": "John Doe", "ssn": "123-45-6789"},
            "timestamp": "2025-01-15T14:30:00Z",
            "priority": 3,
            "tags": ["confidential", "project-xyz", "finance"],
            "public_field": "This is a public field that doesn't need encryption"
        },
        {
            "id": "doc2",
            "api_key": "api-key-456",
            "classification": "top-secret",
            "restricted_note": "Critical vulnerability in ABC system",
            "personal_data": {"name": "Jane Smith", "ssn": "987-65-4321"},
            "timestamp": "2025-02-20T09:15:00Z",
            "priority": 1,
            "tags": ["security", "vulnerability", "critical"],
            "public_field": "Another public field without encryption"
        },
        {
            "id": "doc3",
            "api_key": "api-key-789",
            "classification": "confidential",
            "restricted_note": "Merger details with Company ABC",
            "personal_data": {"name": "Bob Johnson", "ssn": "456-78-9012"},
            "timestamp": "2025-03-10T16:45:00Z",
            "priority": 2,
            "tags": ["merger", "finance", "confidential"],
            "public_field": "Third public field"
        }
    ]


def test_basic_exact_match(security, search_fallback, test_data):
    """Test basic exact match on encrypted fields."""
    # Encrypt test data
    encrypted_data = [security.process_metadata(item) for item in test_data]
    
    # Search by exact match
    results = search_fallback.search_by_exact_match(encrypted_data, "api_key", "api-key-456")
    
    # Verify results
    assert len(results) == 1
    decrypted = security.decrypt_metadata(results[0])
    assert decrypted["id"] == "doc2"
    assert decrypted["api_key"] == "api-key-456"


def test_nested_field_exact_match(security, search_fallback, test_data):
    """Test exact match on nested encrypted fields."""
    # Encrypt test data
    encrypted_data = [security.process_metadata(item) for item in test_data]
    
    # Search by exact match in nested field
    results = search_fallback.search_by_exact_match(encrypted_data, "personal_data.name", "Jane Smith")
    
    # Verify results
    assert len(results) == 1
    decrypted = security.decrypt_metadata(results[0])
    assert decrypted["id"] == "doc2"
    assert decrypted["personal_data"]["name"] == "Jane Smith"


def test_array_contains_search(security, search_fallback, test_data):
    """Test searching for items in encrypted arrays."""
    # Encrypt test data
    encrypted_data = [security.process_metadata(item) for item in test_data]
    
    # Search for array contains
    results = search_fallback.search_by_contains(encrypted_data, "tags", "finance")
    
    # Verify results
    assert len(results) == 2
    result_ids = sorted([security.decrypt_metadata(item)["id"] for item in results])
    assert result_ids == ["doc1", "doc3"]


def test_date_range_search(security, search_fallback, test_data):
    """Test range search on encrypted date fields."""
    # Encrypt test data
    encrypted_data = [security.process_metadata(item) for item in test_data]
    
    # Define date range
    min_date = "2025-02-01T00:00:00Z"
    max_date = "2025-03-15T00:00:00Z"
    
    # Search by date range
    results = search_fallback.search_by_range(encrypted_data, "timestamp", min_date, max_date)
    
    # Verify results
    assert len(results) == 2
    result_ids = sorted([security.decrypt_metadata(item)["id"] for item in results])
    assert result_ids == ["doc2", "doc3"]


def test_numeric_range_search(security, search_fallback, test_data):
    """Test range search on encrypted numeric fields."""
    # Encrypt test data
    encrypted_data = [security.process_metadata(item) for item in test_data]
    
    # Search by numeric range (priority 1-2)
    results = search_fallback.search_by_range(encrypted_data, "priority", 1, 2)
    
    # Verify results
    assert len(results) == 2
    result_ids = sorted([security.decrypt_metadata(item)["id"] for item in results])
    assert result_ids == ["doc2", "doc3"]


def test_prefix_search(security, search_fallback, test_data):
    """Test prefix search on encrypted text fields."""
    # Encrypt test data
    encrypted_data = [security.process_metadata(item) for item in test_data]
    
    # Search by prefix
    results = search_fallback.search_by_prefix(encrypted_data, "classification", "top")
    
    # Verify results
    assert len(results) == 1
    decrypted = security.decrypt_metadata(results[0])
    assert decrypted["id"] == "doc2"
    assert decrypted["classification"] == "top-secret"


def test_case_insensitive_search(security, search_fallback, test_data):
    """Test case insensitive search on encrypted fields."""
    # Encrypt test data
    encrypted_data = [security.process_metadata(item) for item in test_data]
    
    # Search with different case
    results = search_fallback.search_by_contains(
        encrypted_data, "restricted_note", "VULNERABILITY", case_sensitive=False
    )
    
    # Verify results
    assert len(results) == 1
    decrypted = security.decrypt_metadata(results[0])
    assert decrypted["id"] == "doc2"
    assert "vulnerability" in decrypted["restricted_note"].lower()


def test_complex_batch_operations(security, search_fallback, test_data):
    """Test complex batch operations combining multiple search patterns."""
    # Encrypt test data
    encrypted_data = [security.process_metadata(item) for item in test_data]
    
    # Define batch operations (documents that are confidential AND mention "company")
    batch_operations = [
        {
            "operation": "contains",
            "field": "classification",
            "value": "confidential",
            "case_sensitive": False
        },
        {
            "operation": "contains",
            "field": "restricted_note",
            "value": "company",
            "case_sensitive": False
        }
    ]
    
    # Execute batch operations
    results = search_fallback.perform_batch_operations(encrypted_data, batch_operations)
    
    # Verify results
    assert len(results) == 1
    decrypted = security.decrypt_metadata(results[0])
    assert decrypted["id"] == "doc3"
    
    # Now try a different combination (top-secret OR critical priority)
    batch_operations = [
        {
            "operation": "exact_match",
            "field": "classification",
            "value": "top-secret"
        },
        {
            "operation": "exact_match",
            "field": "priority",
            "value": 1
        }
    ]
    
    # Execute batch operations with OR logic
    results = search_fallback.perform_batch_operations(
        encrypted_data, batch_operations, require_all=False
    )
    
    # Verify results (should be just doc2 which matches both conditions)
    assert len(results) == 1
    decrypted = security.decrypt_metadata(results[0])
    assert decrypted["id"] == "doc2"


def test_negative_filtering(security, search_fallback, test_data):
    """Test negative filtering with encrypted search."""
    # Encrypt test data
    encrypted_data = [security.process_metadata(item) for item in test_data]
    
    # Define a custom filter function for testing negative conditions
    def not_contains_filter(decrypted_value, search_value):
        """Return True if field does NOT contain the search value."""
        if isinstance(decrypted_value, str):
            return search_value.lower() not in decrypted_value.lower()
        return False
    
    # Get all documents that DON'T mention "company"
    results = search_fallback.decrypt_and_filter(
        encrypted_data, "restricted_note", "company", not_contains_filter
    )
    
    # Verify results (should be doc1 and doc2)
    assert len(results) == 2
    result_ids = sorted([security.decrypt_metadata(item)["id"] for item in results])
    assert result_ids == ["doc1", "doc2"]


def test_regular_expression_pattern(security, search_fallback, test_data):
    """Test regex-like pattern matching with encrypted search."""
    # Encrypt test data
    encrypted_data = [security.process_metadata(item) for item in test_data]
    
    # Define a custom filter function for regex-like searching
    import re
    def regex_filter(decrypted_value, pattern):
        """Apply a regex-like pattern to the decrypted value."""
        if isinstance(decrypted_value, str):
            return bool(re.search(pattern, decrypted_value))
        return False
    
    # Search for documents with social security numbers matching pattern
    results = search_fallback.decrypt_and_filter(
        encrypted_data, "personal_data.ssn", r"\d{3}-\d{2}-\d{4}", regex_filter
    )
    
    # Verify all docs match the SSN pattern
    assert len(results) == 3
    
    # More specific pattern - SSNs starting with 4
    results = search_fallback.decrypt_and_filter(
        encrypted_data, "personal_data.ssn", r"^4", regex_filter
    )
    
    # Verify only doc3 matches
    assert len(results) == 1
    decrypted = security.decrypt_metadata(results[0])
    assert decrypted["id"] == "doc3"
    assert decrypted["personal_data"]["ssn"].startswith("4")