"""
Tests for the API cache manager.
"""

import json
import time
from unittest.mock import patch, MagicMock
import pytest
from typing import Dict, Any, Optional

from pygovpub.api.cache.manager import CacheManager, CacheStatus, CacheResult
from pygovpub.api.cache.storage import MemoryStorage
from pygovpub.auth.models import ApiSource


class TrackedMemoryStorage(MemoryStorage[Any]):
    """Test storage implementation to track operations."""
    
    def __init__(self, max_items: int = 1000):
        super().__init__(max_items)
        self.operations = []
    
    def get(self, key):
        self.operations.append(('get', key))
        return super().get(key)
    
    def set(self, key, value, ttl=None, metadata=None):
        self.operations.append(('set', key, value))
        return super().set(key, value, ttl, metadata)
    
    def delete(self, key):
        self.operations.append(('delete', key))
        return super().delete(key)
    
    def clear(self):
        self.operations.append(('clear',))
        return super().clear()


@pytest.fixture
def tracked_storage_factory():
    """Fixture that provides a function to create TrackedMemoryStorage instances."""
    def _create_storage(max_items: int = 1000):
        return TrackedMemoryStorage(max_items)
    return _create_storage


@pytest.fixture
def tracked_storage(tracked_storage_factory):
    """Fixture that provides a TrackedMemoryStorage instance with default settings."""
    return tracked_storage_factory()


def test_cache_manager_initialization(tracked_storage):
    """Test CacheManager initialization."""
    # Create with defaults
    manager = CacheManager()
    assert manager.enabled
    
    # Create with custom storage and disabled
    manager_custom = CacheManager(storage=tracked_storage, enabled=False)
    assert not manager_custom.enabled


def test_cache_manager_enable_disable():
    """Test enabling and disabling the cache."""
    manager = CacheManager()
    
    # Default is enabled
    assert manager.enabled
    
    # Disable
    manager.enabled = False
    assert not manager.enabled
    
    # Re-enable
    manager.enabled = True
    assert manager.enabled


def test_cache_manager_config_flag():
    """Test cache manager respects config settings."""
    # Create manager with direct config setting
    manager = CacheManager(enabled=True)
    assert manager.enabled
    
    # Override to disable
    manager.enabled = False
    assert not manager.enabled


def test_cache_key_generation():
    """Test cache key generation."""
    manager = CacheManager()
    
    # Simple key
    key1 = manager.generate_key(ApiSource.CONGRESS, "/bills/117/hr1")
    assert key1.startswith("congress:")
    
    # Key with parameters
    key2 = manager.generate_key(
        ApiSource.GOVINFO, 
        "/packages/BILLS-117hr1enr",
        {"format": "pdf"}
    )
    assert key2.startswith("govinfo:")
    
    # Key with same path but different parameters
    key3 = manager.generate_key(
        ApiSource.GOVINFO, 
        "/packages/BILLS-117hr1enr",
        {"format": "xml"}
    )
    
    # Keys should be different
    assert key2 != key3
    
    # Parameter order shouldn't matter
    key4 = manager.generate_key(
        ApiSource.CONGRESS, 
        "/members",
        {"limit": 10, "offset": 0}
    )
    key5 = manager.generate_key(
        ApiSource.CONGRESS, 
        "/members",
        {"offset": 0, "limit": 10}
    )
    assert key4 == key5
    
    # None parameters should be excluded
    key6 = manager.generate_key(
        ApiSource.CONGRESS, 
        "/members",
        {"limit": 10, "offset": None}
    )
    key7 = manager.generate_key(
        ApiSource.CONGRESS, 
        "/members",
        {"limit": 10}
    )
    assert key6 == key7


def test_cache_get_miss():
    """Test cache miss."""
    manager = CacheManager()
    result = manager.get("nonexistent")
    
    assert result.status == CacheStatus.MISS
    assert result.key == "nonexistent"
    assert result.value is None


def test_cache_set_get():
    """Test setting and retrieving from cache."""
    manager = CacheManager()
    
    # Set value
    success = manager.set("test_key", {"data": "test"}, ttl=60)
    assert success
    
    # Get value
    result = manager.get("test_key")
    assert result.status == CacheStatus.HIT
    assert result.key == "test_key"
    assert result.value == {"data": "test"}
    assert result.ttl is not None
    assert result.ttl <= 60


def test_cache_with_metadata():
    """Test cache with metadata."""
    manager = CacheManager()
    
    # Set with tags and etag
    success = manager.set(
        "test_key", 
        "test_value",
        ttl=60,
        tags=["tag1", "tag2"],
        etag="etag123"
    )
    assert success
    
    # Get with metadata
    result = manager.get("test_key")
    assert result.status == CacheStatus.HIT
    assert result.etag == "etag123"
    assert result.metadata is not None
    assert "tags" in result.metadata
    assert set(result.metadata["tags"]) == {"tag1", "tag2"}


def test_cache_expiration():
    """Test cache expiration."""
    manager = CacheManager()
    
    # Set with short TTL
    manager.set("short_ttl", "will expire", ttl=0.1)
    
    # Verify exists initially
    result = manager.get("short_ttl")
    assert result.status == CacheStatus.HIT
    
    # Wait for expiration
    time.sleep(0.2)
    
    # Verify expired
    result = manager.get("short_ttl")
    assert result.status == CacheStatus.MISS


def test_cache_delete():
    """Test cache deletion."""
    manager = CacheManager()
    
    # Set value
    manager.set("test_key", "test_value")
    
    # Verify exists
    assert manager.has("test_key")
    
    # Delete
    result = manager.delete("test_key")
    assert result
    
    # Verify deleted
    assert not manager.has("test_key")
    
    # Delete non-existent
    result = manager.delete("nonexistent")
    assert not result


def test_cache_clear():
    """Test cache clearing."""
    manager = CacheManager()
    
    # Set multiple values
    manager.set("key1", "value1")
    manager.set("key2", "value2")
    
    # Verify exist
    assert manager.has("key1")
    assert manager.has("key2")
    
    # Clear
    result = manager.clear()
    assert result
    
    # Verify cleared
    assert not manager.has("key1")
    assert not manager.has("key2")


def test_cache_stats():
    """Test cache statistics."""
    manager = CacheManager()
    
    # Check initial stats
    stats = manager.get_stats()
    assert stats["status"] == "enabled"
    assert stats["item_count"] == 0
    
    # Add items
    manager.set("key1", "value1")
    manager.set("key2", "value2")
    
    # Perform operations
    manager.get("key1")
    manager.get("nonexistent")
    
    # Check updated stats
    stats = manager.get_stats()
    assert stats["item_count"] == 2
    assert stats["hit_count"] == 1
    assert stats["miss_count"] == 1


def test_cache_disabled_operations():
    """Test operations with cache disabled."""
    manager = CacheManager(enabled=False)
    
    # Attempt operations
    set_result = manager.set("key", "value")
    assert not set_result
    
    get_result = manager.get("key")
    assert get_result.status == CacheStatus.DISABLED
    
    delete_result = manager.delete("key")
    assert not delete_result
    
    has_result = manager.has("key")
    assert not has_result
    
    clear_result = manager.clear()
    assert not clear_result
    
    stats = manager.get_stats()
    assert stats["status"] == "disabled"


def test_invalidate_by_tags():
    """Test tag-based invalidation."""
    manager = CacheManager()
    
    # Set items with tags
    manager.set("key1", "value1", tags=["tag1"])
    manager.set("key2", "value2", tags=["tag2", "common"])
    manager.set("key3", "value3", tags=["tag3", "common"])
    
    # Verify all exist
    assert manager.has("key1")
    assert manager.has("key2")
    assert manager.has("key3")
    
    # Invalidate by common tag
    count = manager.invalidate_by_tags(["common"])
    assert count == 2
    
    # Verify invalidated items are gone
    assert manager.has("key1")
    assert not manager.has("key2")
    assert not manager.has("key3")


def test_invalidate_by_source():
    """Test source-based invalidation."""
    manager = CacheManager()
    
    # Create keys that start with source prefixes
    manager.set("congress:key1", "value1")
    manager.set("congress:key2", "value2")
    manager.set("govinfo:key1", "value3")
    
    # Verify all exist
    assert manager.has("congress:key1")
    assert manager.has("congress:key2")
    assert manager.has("govinfo:key1")
    
    # Invalidate congress source
    count = manager.invalidate_by_source(ApiSource.CONGRESS)
    assert count == 2
    
    # Verify congress items are gone, govinfo remains
    assert not manager.has("congress:key1")
    assert not manager.has("congress:key2")
    assert manager.has("govinfo:key1")


def test_cache_response_functions():
    """Test API response caching functions."""
    manager = CacheManager()
    
    # Cache a response
    success = manager.cache_response(
        ApiSource.CONGRESS,
        "/bills/117/hr1",
        params={"format": "json"},
        response={"title": "Test Bill"},
        ttl=60,
        etag="etag123"
    )
    assert success
    
    # Get cached response
    result = manager.get_cached_response(
        ApiSource.CONGRESS,
        "/bills/117/hr1",
        params={"format": "json"}
    )
    assert result.status == CacheStatus.HIT
    assert result.value == {"title": "Test Bill"}
    assert result.etag == "etag123"
    
    # Get non-existent response
    result = manager.get_cached_response(
        ApiSource.CONGRESS,
        "/bills/117/hr2",
        params={"format": "json"}
    )
    assert result.status == CacheStatus.MISS


def test_size_calculation():
    """Test size calculation for different types."""
    manager = CacheManager()
    
    # Test with different value types
    manager.set("dict_key", {"data": "test", "nested": {"value": 123}})
    manager.set("string_key", "Hello, world!")
    manager.set("bytes_key", b"Binary data")
    manager.set("int_key", 12345)
    
    # Get stats
    stats = manager.get_stats()
    assert stats["total_size_bytes"] > 0  # Should have calculated size for dict, string, and bytes