"""
Cache manager for API responses.

This module provides the main cache management interface for caching
API responses, tracking rate limits, and managing cache lifecycle.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, TypeVar, Union, Tuple, Generic, cast

from pygovpub.auth.models import ApiSource
from pygovpub.config import get_config_manager, FeatureFlag
from .storage import CacheStorage, CacheItem, MemoryStorage

T = TypeVar('T')  # Type for cached value


class CacheStatus(Enum):
    """Status of a cache operation."""
    
    HIT = auto()
    """Cache hit - item was found in cache."""
    
    MISS = auto()
    """Cache miss - item was not found in cache."""
    
    EXPIRED = auto()
    """Cache hit but item was expired."""
    
    ERROR = auto()
    """Error during cache operation."""
    
    DISABLED = auto()
    """Cache is disabled."""


@dataclass
class CacheResult(Generic[T]):
    """Result of a cache operation."""
    
    status: CacheStatus
    """Status of the cache operation."""
    
    key: str
    """Cache key that was accessed."""
    
    value: Optional[T] = None
    """The cached value, if available."""
    
    ttl: Optional[int] = None
    """Time-to-live for the cached item."""
    
    etag: Optional[str] = None
    """ETag for the cached item."""
    
    metadata: Optional[Dict[str, Any]] = None
    """Additional metadata for the cached item."""


class CacheManager:
    """Manager for API response caching."""
    
    def __init__(self, storage: Optional[CacheStorage] = None, enabled: bool = True):
        """Initialize the cache manager.
        
        Args:
            storage: Storage backend to use (defaults to MemoryStorage)
            enabled: Whether the cache is enabled
        """
        self._config = get_config_manager()
        
        # Override with passed enabled parameter
        self._enabled = enabled
        
        # If no storage provided, use config to determine
        if storage is None:
            # Use in-memory storage with config-based TTL
            cache_ttl = self._config.get_option("cache_ttl") or 3600
            self._storage = MemoryStorage[Any](max_items=1000)
        else:
            self._storage = storage
    
    @property
    def enabled(self) -> bool:
        """Whether the cache is enabled."""
        # Check both instance setting and config setting
        return (self._enabled and 
                self._config.get_feature_flag(FeatureFlag.CACHE_ENABLED))
    
    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set whether the cache is enabled."""
        self._enabled = value
    
    def generate_key(self, source: ApiSource, path: str, 
                   params: Optional[Dict[str, Any]] = None) -> str:
        """Generate a cache key for an API request.
        
        Args:
            source: API source (congress or govinfo)
            path: API path
            params: Query parameters
            
        Returns:
            Cache key string
        """
        # Start with API source and path
        key_parts = [source.value, path]
        
        # Add sorted parameters if present
        if params:
            # Sort params for consistent keys regardless of order
            sorted_params = sorted(params.items())
            
            # Convert to strings and filter out None values
            param_strs = [
                f"{k}={v}" for k, v in sorted_params 
                if v is not None
            ]
            
            # Add to key parts
            key_parts.extend(param_strs)
        
        # Join with colons
        key_base = ":".join(key_parts)
        
        # Use hash to ensure reasonable key length
        key_hash = hashlib.md5(key_base.encode()).hexdigest()
        
        # Final key format: source:hash
        return f"{source.value}:{key_hash}"
    
    def get(self, key: str) -> CacheResult:
        """Get an item from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cache result with status and value if found
        """
        if not self.enabled:
            return CacheResult(status=CacheStatus.DISABLED, key=key)
        
        try:
            cache_item = self._storage.get(key)
            
            if cache_item is None:
                return CacheResult(status=CacheStatus.MISS, key=key)
            
            # Extract metadata
            metadata = {}
            if cache_item.metadata.etag:
                metadata['etag'] = cache_item.metadata.etag
            if cache_item.metadata.size_bytes:
                metadata['size_bytes'] = cache_item.metadata.size_bytes
            if cache_item.metadata.tags:
                metadata['tags'] = list(cache_item.metadata.tags)
            
            # Calculate remaining TTL
            ttl = None
            if cache_item.metadata.expires_at:
                ttl = int(cache_item.metadata.expires_at - time.time())
                if ttl < 0:
                    ttl = 0
            
            return CacheResult(
                status=CacheStatus.HIT,
                key=key,
                value=cache_item.value,
                ttl=ttl,
                etag=cache_item.metadata.etag,
                metadata=metadata
            )
        except Exception:
            return CacheResult(status=CacheStatus.ERROR, key=key)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None,
           tags: Optional[List[str]] = None, etag: Optional[str] = None) -> bool:
        """Set an item in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
            tags: List of tags for categorization
            etag: ETag for the resource
            
        Returns:
            Success status
        """
        if not self.enabled:
            return False
        
        try:
            # Use default TTL from config if not specified
            if ttl is None:
                ttl = self._config.get_option("cache_ttl") or 3600
            
            # Prepare metadata
            metadata: Dict[str, Any] = {}
            if etag:
                metadata['etag'] = etag
            
            # Estimate size if possible
            try:
                if isinstance(value, (dict, list)):
                    # For dictionaries and lists, use JSON size
                    size = len(json.dumps(value).encode())
                elif isinstance(value, str):
                    # For strings, use encoded string length
                    size = len(value.encode())
                elif isinstance(value, bytes):
                    # For bytes, use length
                    size = len(value)
                else:
                    # For other types, don't set size
                    size = None
                
                if size is not None:
                    metadata['size_bytes'] = size
            except Exception:
                # If size calculation fails, just continue without it
                pass
            
            # Add tags
            if tags:
                metadata['tags'] = tags
            
            # Set in storage
            self._storage.set(key, value, ttl=ttl, metadata=metadata)
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        """Delete an item from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Success status
        """
        if not self.enabled:
            return False
        
        return self._storage.delete(key)
    
    def has(self, key: str) -> bool:
        """Check if an item exists in the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Whether the item exists and is not expired
        """
        if not self.enabled:
            return False
        
        return self._storage.has(key)
    
    def clear(self) -> bool:
        """Clear all items from the cache.
        
        Returns:
            Success status
        """
        if not self.enabled:
            return False
        
        try:
            self._storage.clear()
            return True
        except Exception:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache.
        
        Returns:
            Dictionary of cache statistics
        """
        if not self.enabled:
            return {"status": "disabled"}
        
        try:
            stats = self._storage.get_stats()
            stats["status"] = "enabled"
            return stats
        except Exception:
            return {"status": "error"}
    
    def invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate items by tags.
        
        Args:
            tags: List of tags to match
            
        Returns:
            Number of items invalidated
        """
        if not self.enabled or not tags:
            return 0
        
        return self._storage.invalidate_by_tags(tags)
    
    def invalidate_by_source(self, source: ApiSource) -> int:
        """Invalidate all items for a specific API source.
        
        Args:
            source: API source to invalidate
            
        Returns:
            Number of items invalidated
        """
        if not self.enabled:
            return 0
        
        # Get keys matching source prefix
        keys = self._storage.get_keys_by_pattern(f"{source.value}:*")
        
        # Delete each key
        count = 0
        for key in keys:
            if self._storage.delete(key):
                count += 1
        
        return count
    
    def get_cached_response(self, source: ApiSource, path: str,
                         params: Optional[Dict[str, Any]] = None) -> CacheResult:
        """Get a cached API response.
        
        Args:
            source: API source
            path: API path
            params: Query parameters
            
        Returns:
            Cache result with status and value if found
        """
        key = self.generate_key(source, path, params)
        return self.get(key)
    
    def cache_response(self, source: ApiSource, path: str,
                     params: Optional[Dict[str, Any]] = None,
                     response: Any = None, ttl: Optional[int] = None,
                     etag: Optional[str] = None) -> bool:
        """Cache an API response.
        
        Args:
            source: API source
            path: API path
            params: Query parameters
            response: Response data to cache
            ttl: Time-to-live in seconds
            etag: ETag for the resource
            
        Returns:
            Success status
        """
        key = self.generate_key(source, path, params)
        
        # Generate appropriate tags
        tags = [source.value]
        
        # Add path components as tags
        path_parts = path.strip('/').split('/')
        for i in range(len(path_parts)):
            # Add progressive path components
            path_tag = '/'.join(path_parts[:i+1])
            if path_tag:
                tags.append(path_tag)
        
        return self.set(key, response, ttl=ttl, tags=tags, etag=etag)