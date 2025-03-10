"""
Tests for the API cache storage classes.
"""

import time
import pytest
from typing import Dict, Any

from pygovpub.api.cache.storage import CacheMetadata, CacheItem, MemoryStorage


def test_cache_metadata_initialization():
    """Test CacheMetadata initialization and defaults."""
    # Create metadata with defaults
    meta = CacheMetadata()
    
    # Verify default values
    assert meta.created_at > 0
    assert meta.expires_at is None
    assert meta.accessed_at > 0
    assert meta.access_count == 0
    assert meta.etag is None
    assert meta.size_bytes is None
    assert meta.tags == set()
    assert not meta.is_expired()


def test_cache_metadata_expiration_check():
    """Test expiration checking for cache metadata."""
    # Create metadata with expiration in the past
    meta_expired = CacheMetadata(expires_at=time.time() - 10)
    assert meta_expired.is_expired()
    
    # Create metadata with expiration in the future
    meta_valid = CacheMetadata(expires_at=time.time() + 10)
    assert not meta_valid.is_expired()
    
    # Create metadata with no expiration
    meta_no_expiry = CacheMetadata(expires_at=None)
    assert not meta_no_expiry.is_expired()


def test_cache_metadata_update_access():
    """Test updating access metadata."""
    meta = CacheMetadata()
    original_accessed_at = meta.accessed_at
    original_access_count = meta.access_count
    
    # Wait briefly to ensure time changes
    time.sleep(0.001)
    
    # Update access metadata
    meta.update_access()
    
    # Verify updates
    assert meta.accessed_at > original_accessed_at
    assert meta.access_count == original_access_count + 1


def test_cache_item_initialization():
    """Test CacheItem initialization."""
    # Create item with minimal parameters
    item = CacheItem(key="test_key", value={"data": "test"})
    
    # Verify values
    assert item.key == "test_key"
    assert item.value == {"data": "test"}
    assert isinstance(item.metadata, CacheMetadata)
    
    # Create item with custom metadata
    meta = CacheMetadata(etag="test-etag", tags={"tag1", "tag2"})
    item_with_meta = CacheItem(key="key2", value="value2", metadata=meta)
    
    # Verify custom metadata
    assert item_with_meta.metadata.etag == "test-etag"
    assert item_with_meta.metadata.tags == {"tag1", "tag2"}


def test_memory_storage_initialization():
    """Test MemoryStorage initialization."""
    # Create storage with default max_items
    storage = MemoryStorage[Dict[str, Any]]()
    assert storage._max_items == 1000
    
    # Create storage with custom max_items
    storage_custom = MemoryStorage[str](max_items=100)
    assert storage_custom._max_items == 100


def test_memory_storage_get_set():
    """Test basic get and set operations."""
    storage = MemoryStorage[Dict[str, Any]]()
    
    # Set new item
    storage.set("key1", {"data": "value1"})
    
    # Get item
    item = storage.get("key1")
    assert item is not None
    assert item.key == "key1"
    assert item.value == {"data": "value1"}
    
    # Get non-existent item
    assert storage.get("nonexistent") is None


def test_memory_storage_with_ttl():
    """Test storage with time-to-live."""
    storage = MemoryStorage[str]()
    
    # Set item with short TTL
    storage.set("short_ttl", "will expire soon", ttl=0.1)
    
    # Set item with longer TTL
    storage.set("long_ttl", "will last longer", ttl=10)
    
    # Verify both exist initially
    assert storage.has("short_ttl")
    assert storage.has("long_ttl")
    
    # Wait for short TTL to expire
    time.sleep(0.2)
    
    # Verify short TTL has expired but long TTL still exists
    assert not storage.has("short_ttl")
    assert storage.has("long_ttl")
    
    # Verify get also respects expiration
    assert storage.get("short_ttl") is None
    assert storage.get("long_ttl") is not None


def test_memory_storage_metadata():
    """Test storage with metadata."""
    storage = MemoryStorage[str]()
    
    # Set with metadata
    storage.set(
        "key1", 
        "value1",
        metadata={
            "etag": "etag1",
            "size_bytes": 100,
            "tags": ["tag1", "tag2"]
        }
    )
    
    # Get and verify metadata
    item = storage.get("key1")
    assert item is not None
    assert item.metadata.etag == "etag1"
    assert item.metadata.size_bytes == 100
    assert item.metadata.tags == {"tag1", "tag2"}


def test_memory_storage_delete():
    """Test delete operation."""
    storage = MemoryStorage[str]()
    
    # Set items
    storage.set("key1", "value1")
    storage.set("key2", "value2")
    
    # Verify items exist
    assert storage.has("key1")
    assert storage.has("key2")
    
    # Delete one item
    result = storage.delete("key1")
    assert result is True
    
    # Verify item was deleted
    assert not storage.has("key1")
    assert storage.has("key2")
    
    # Delete non-existent item
    result = storage.delete("nonexistent")
    assert result is False


def test_memory_storage_clear():
    """Test clear operation."""
    storage = MemoryStorage[str]()
    
    # Set multiple items
    storage.set("key1", "value1")
    storage.set("key2", "value2")
    
    # Verify items exist
    assert storage.has("key1")
    assert storage.has("key2")
    
    # Clear storage
    storage.clear()
    
    # Verify all items removed
    assert not storage.has("key1")
    assert not storage.has("key2")


def test_memory_storage_max_items():
    """Test maximum items limit."""
    # Create storage with small max_items
    storage = MemoryStorage[int](max_items=3)
    
    # Set up to max_items
    storage.set("key1", 1)
    storage.set("key2", 2)
    storage.set("key3", 3)
    
    # Verify all items exist
    assert storage.has("key1")
    assert storage.has("key2")
    assert storage.has("key3")
    
    # Access key1 to make it most recently used
    storage.get("key1")
    
    # Add new item, should evict least recently used (key2 or key3)
    storage.set("key4", 4)
    
    # Verify one of the older items was evicted (but not key1)
    assert storage.has("key1")
    assert storage.has("key4")
    assert len([key for key in ["key2", "key3"] if storage.has(key)]) == 1


def test_memory_storage_stats():
    """Test statistics reporting."""
    storage = MemoryStorage[str]()
    
    # Check initial stats
    stats = storage.get_stats()
    assert stats["item_count"] == 0
    assert stats["hit_count"] == 0
    assert stats["miss_count"] == 0
    
    # Add items
    storage.set("key1", "value1", metadata={"tags": ["tag1"]})
    storage.set("key2", "value2", metadata={"tags": ["tag2", "common"]})
    storage.set("key3", "value3", metadata={"tags": ["tag3", "common"]})
    
    # Perform hits and misses
    storage.get("key1")  # hit
    storage.get("key2")  # hit
    storage.get("nonexistent")  # miss
    
    # Check updated stats
    stats = storage.get_stats()
    assert stats["item_count"] == 3
    assert stats["hit_count"] == 2
    assert stats["miss_count"] == 1
    assert stats["hit_ratio"] == 2/3
    assert "tag_counts" in stats
    assert stats["tag_counts"]["common"] == 2


def test_memory_storage_invalidate_by_tags():
    """Test invalidation by tags."""
    storage = MemoryStorage[str]()
    
    # Add items with tags
    storage.set("key1", "value1", metadata={"tags": ["tag1"]})
    storage.set("key2", "value2", metadata={"tags": ["tag2", "common"]})
    storage.set("key3", "value3", metadata={"tags": ["tag3", "common"]})
    
    # Invalidate by common tag
    count = storage.invalidate_by_tags(["common"])
    assert count == 2
    
    # Verify only untagged item remains
    assert storage.has("key1")
    assert not storage.has("key2")
    assert not storage.has("key3")


def test_memory_storage_pattern_matching():
    """Test key pattern matching."""
    storage = MemoryStorage[str]()
    
    # Add items with different prefixes
    storage.set("prefix1:key1", "value1")
    storage.set("prefix1:key2", "value2")
    storage.set("prefix2:key1", "value3")
    
    # Match by exact pattern
    keys = storage.get_keys_by_pattern("prefix1:key1")
    assert len(keys) == 1
    assert "prefix1:key1" in keys
    
    # Match by prefix pattern
    keys = storage.get_keys_by_pattern("prefix1:*")
    assert len(keys) == 2
    assert "prefix1:key1" in keys
    assert "prefix1:key2" in keys
    
    # Match by another prefix
    keys = storage.get_keys_by_pattern("prefix2:*")
    assert len(keys) == 1
    assert "prefix2:key1" in keys
    
    # Match all keys
    keys = storage.get_keys_by_pattern("")
    assert len(keys) == 3


def test_memory_storage_cleanup():
    """Test cleanup of expired items."""
    storage = MemoryStorage[str]()
    
    # Add items with different expiration times
    storage.set("expire_soon", "value1", ttl=0.1)
    storage.set("expire_later", "value2", ttl=10)
    storage.set("no_expiry", "value3")
    
    # Initially all items exist
    assert len(storage._store) == 3
    
    # Wait for first item to expire
    time.sleep(0.2)
    
    # Run cleanup
    count = storage.cleanup()
    assert count == 1
    
    # Verify expired item was removed
    assert len(storage._store) == 2
    assert not storage.has("expire_soon")
    assert storage.has("expire_later")
    assert storage.has("no_expiry")