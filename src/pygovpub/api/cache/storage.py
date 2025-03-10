"""
Storage backends for API response caching.

This module provides storage implementations for the caching system,
including in-memory storage and interfaces for persistent storage options.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generic, Optional, Set, TypeVar, List, Tuple

T = TypeVar('T')  # Type for cached value


@dataclass
class CacheMetadata:
    """Metadata for a cached item."""
    
    created_at: float = field(default_factory=time.time)
    """Timestamp when the item was created."""
    
    expires_at: Optional[float] = None
    """Timestamp when the item expires."""
    
    accessed_at: float = field(default_factory=time.time)
    """Timestamp when the item was last accessed."""
    
    access_count: int = 0
    """Number of times the item has been accessed."""
    
    etag: Optional[str] = None
    """ETag from the source, if available."""
    
    size_bytes: Optional[int] = None
    """Size of the cached item in bytes."""
    
    tags: Set[str] = field(default_factory=set)
    """Tags for categorization and selective invalidation."""
    
    def is_expired(self) -> bool:
        """Check if the cache entry is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def update_access(self) -> None:
        """Update access metadata."""
        self.accessed_at = time.time()
        self.access_count += 1


@dataclass
class CacheItem(Generic[T]):
    """A cached item with its metadata."""
    
    key: str
    """The cache key."""
    
    value: T
    """The cached value."""
    
    metadata: CacheMetadata = field(default_factory=CacheMetadata)
    """Metadata about the cached item."""


class CacheStorage(ABC, Generic[T]):
    """Abstract base class for cache storage backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[CacheItem[T]]:
        """Get an item from the cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: T, ttl: Optional[int] = None,
            metadata: Optional[Dict[str, Any]] = None) -> None:
        """Set an item in the cache."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete an item from the cache."""
        pass
    
    @abstractmethod
    def has(self, key: str) -> bool:
        """Check if an item exists in the cache."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all items from the cache."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache."""
        pass
    
    @abstractmethod
    def invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate items by tags."""
        pass
    
    @abstractmethod
    def get_keys_by_pattern(self, pattern: str) -> List[str]:
        """Get keys matching a pattern."""
        pass


class MemoryStorage(CacheStorage[T]):
    """In-memory storage implementation."""
    
    def __init__(self, max_items: int = 1000):
        """Initialize in-memory storage.
        
        Args:
            max_items: Maximum number of items to store.
        """
        self._store: Dict[str, CacheItem[T]] = {}
        self._max_items = max_items
        self._hits = 0
        self._misses = 0
        self._created_at = time.time()
    
    def get(self, key: str) -> Optional[CacheItem[T]]:
        """Get an item from the cache."""
        if key not in self._store:
            self._misses += 1
            return None
        
        cache_item = self._store[key]
        
        # Check if expired
        if cache_item.metadata.is_expired():
            self.delete(key)
            self._misses += 1
            return None
        
        # Update access metadata
        cache_item.metadata.update_access()
        self._hits += 1
        
        return cache_item
    
    def set(self, key: str, value: T, ttl: Optional[int] = None,
            metadata: Optional[Dict[str, Any]] = None) -> None:
        """Set an item in the cache."""
        # Enforce maximum item limit with LRU eviction
        if len(self._store) >= self._max_items and key not in self._store:
            # Find least recently used item
            lru_key = min(
                self._store.items(),
                key=lambda item: item[1].metadata.accessed_at
            )[0]
            # Remove it
            self.delete(lru_key)
        
        # Create metadata
        meta = CacheMetadata()
        
        # Set expiration if TTL provided
        if ttl is not None:
            meta.expires_at = time.time() + ttl
        
        # Add additional metadata
        if metadata:
            if 'etag' in metadata:
                meta.etag = metadata['etag']
            if 'size_bytes' in metadata:
                meta.size_bytes = metadata['size_bytes']
            if 'tags' in metadata:
                meta.tags = set(metadata['tags'])
        
        # Create and store the cache item
        self._store[key] = CacheItem(key=key, value=value, metadata=meta)
    
    def delete(self, key: str) -> bool:
        """Delete an item from the cache."""
        if key in self._store:
            del self._store[key]
            return True
        return False
    
    def has(self, key: str) -> bool:
        """Check if an item exists in the cache."""
        if key not in self._store:
            return False
        
        # Check if expired
        if self._store[key].metadata.is_expired():
            self.delete(key)
            return False
        
        return True
    
    def clear(self) -> None:
        """Clear all items from the cache."""
        self._store.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache."""
        current_time = time.time()
        expired_count = sum(1 for item in self._store.values() 
                           if item.metadata.is_expired())
        
        # Calculate sizes
        total_size = 0
        if self._store:
            for item in self._store.values():
                if item.metadata.size_bytes:
                    total_size += item.metadata.size_bytes
        
        # Count by tags
        tag_counts: Dict[str, int] = {}
        for item in self._store.values():
            for tag in item.metadata.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        return {
            "item_count": len(self._store),
            "max_items": self._max_items,
            "expired_count": expired_count,
            "hit_count": self._hits,
            "miss_count": self._misses,
            "hit_ratio": (self._hits / (self._hits + self._misses)) 
                         if (self._hits + self._misses) > 0 else 0,
            "uptime": current_time - self._created_at,
            "total_size_bytes": total_size,
            "tag_counts": tag_counts,
        }
    
    def invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate items by tags."""
        if not tags:
            return 0
        
        tag_set = set(tags)
        keys_to_delete = [
            key for key, item in self._store.items()
            if item.metadata.tags & tag_set
        ]
        
        for key in keys_to_delete:
            self.delete(key)
        
        return len(keys_to_delete)
    
    def get_keys_by_pattern(self, pattern: str) -> List[str]:
        """Get keys matching a pattern.
        
        Note: This simple implementation only supports wildcard (*)
        at the end of the pattern.
        """
        if not pattern:
            return list(self._store.keys())
        
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return [key for key in self._store.keys() if key.startswith(prefix)]
        else:
            return [key for key in self._store.keys() if key == pattern]
    
    def cleanup(self) -> int:
        """Remove expired items."""
        keys_to_delete = [
            key for key, item in self._store.items()
            if item.metadata.is_expired()
        ]
        
        for key in keys_to_delete:
            self.delete(key)
        
        return len(keys_to_delete)