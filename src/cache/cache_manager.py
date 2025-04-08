#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Multi-level cache manager for StarImageBrowse application.
Implements a coordinated caching system with different cache levels.
"""

import os
import time
import pickle
import logging
import hashlib
import threading
from functools import lru_cache
from collections import OrderedDict, defaultdict
from typing import Any, Dict, List, Tuple, Callable, Optional, Union

logger = logging.getLogger("StarImageBrowse.cache.cache_manager")

class CacheStats:
    """Track cache performance statistics."""
    
    def __init__(self):
        """Initialize cache statistics."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.size = 0
        self.last_reset = time.time()
        self.lock = threading.Lock()
    
    def record_hit(self):
        """Record a cache hit."""
        with self.lock:
            self.hits += 1
    
    def record_miss(self):
        """Record a cache miss."""
        with self.lock:
            self.misses += 1
    
    def record_eviction(self):
        """Record a cache eviction."""
        with self.lock:
            self.evictions += 1
    
    def update_size(self, size):
        """Update current cache size."""
        with self.lock:
            self.size = size
    
    def hit_rate(self):
        """Calculate cache hit rate."""
        with self.lock:
            total = self.hits + self.misses
            return self.hits / total if total > 0 else 0
    
    def get_stats(self):
        """Get cache statistics as dictionary."""
        with self.lock:
            return {
                "hits": self.hits,
                "misses": self.misses, 
                "evictions": self.evictions,
                "size": self.size,
                "hit_rate": self.hit_rate(),
                "age_seconds": time.time() - self.last_reset
            }
    
    def reset(self):
        """Reset statistics."""
        with self.lock:
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.last_reset = time.time()


class CacheLevel:
    """Base class for a cache level."""
    
    def __init__(self, name, max_size, ttl=None):
        """Initialize cache level.
        
        Args:
            name (str): Name of this cache level
            max_size (int): Maximum number of items to store
            ttl (int, optional): Time-to-live in seconds for cache entries
        """
        self.name = name
        self.max_size = max_size
        self.ttl = ttl
        self.stats = CacheStats()
        self._lock = threading.RLock()
    
    def get(self, key):
        """Get an item from the cache."""
        raise NotImplementedError("Subclasses must implement get()")
    
    def put(self, key, value):
        """Put an item in the cache."""
        raise NotImplementedError("Subclasses must implement put()")
    
    def contains(self, key):
        """Check if key exists in cache."""
        raise NotImplementedError("Subclasses must implement contains()")
    
    def remove(self, key):
        """Remove an item from the cache."""
        raise NotImplementedError("Subclasses must implement remove()")
    
    def clear(self):
        """Clear all items from the cache."""
        raise NotImplementedError("Subclasses must implement clear()")
    
    def get_stats(self):
        """Get statistics for this cache level."""
        return self.stats.get_stats()


class MemoryCache(CacheLevel):
    """Fast in-memory cache optimized for speed."""
    
    def __init__(self, name, max_size=100, ttl=None):
        """Initialize memory cache.
        
        Args:
            name (str): Name of this cache level
            max_size (int): Maximum number of items to store
            ttl (int, optional): Time-to-live in seconds for cache entries
        """
        super().__init__(name, max_size, ttl)
        self._cache = OrderedDict()  # {key: (value, timestamp)}
    
    def get(self, key):
        """Get an item from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Value or None if not found/expired
        """
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                
                # Check TTL if set
                if self.ttl is not None and time.time() - timestamp > self.ttl:
                    # Expired
                    self._cache.pop(key)
                    self.stats.record_miss()
                    return None
                
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self.stats.record_hit()
                return value
            
            self.stats.record_miss()
            return None
    
    def put(self, key, value):
        """Put an item in the cache.
        
        Args:
            key: Cache key
            value: Value to store
            
        Returns:
            True if added, False if error
        """
        try:
            with self._lock:
                # Check if we need to evict
                if len(self._cache) >= self.max_size and key not in self._cache:
                    # Remove oldest item (first in OrderedDict)
                    self._cache.popitem(last=False)
                    self.stats.record_eviction()
                
                # Add/update item
                self._cache[key] = (value, time.time())
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                
                # Update size stat
                self.stats.update_size(len(self._cache))
                return True
        except Exception as e:
            logger.error(f"Error adding item to memory cache: {e}")
            return False
    
    def contains(self, key):
        """Check if key exists in cache (and is not expired).
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if in cache and not expired
        """
        with self._lock:
            if key in self._cache:
                if self.ttl is not None:
                    _, timestamp = self._cache[key]
                    if time.time() - timestamp > self.ttl:
                        # Expired
                        self._cache.pop(key)
                        return False
                return True
            return False
    
    def remove(self, key):
        """Remove an item from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if removed, False if not found
        """
        with self._lock:
            if key in self._cache:
                self._cache.pop(key)
                self.stats.update_size(len(self._cache))
                return True
            return False
    
    def clear(self):
        """Clear all items from the cache."""
        with self._lock:
            self._cache.clear()
            self.stats.update_size(0)


class DiskCache(CacheLevel):
    """Persistent disk-based cache for larger objects."""
    
    def __init__(self, name, directory, max_size=1000, ttl=None):
        """Initialize disk cache.
        
        Args:
            name (str): Name of this cache level
            directory (str): Directory to store cache files
            max_size (int): Maximum number of items to store
            ttl (int, optional): Time-to-live in seconds for cache entries
        """
        super().__init__(name, max_size, ttl)
        self.directory = directory
        self._metadata = {}  # {key: timestamp}
        self._ensure_directory()
        self._load_metadata()
    
    def _ensure_directory(self):
        """Ensure cache directory exists."""
        os.makedirs(self.directory, exist_ok=True)
    
    def _get_path(self, key):
        """Get file path for a key.
        
        Args:
            key: Cache key
            
        Returns:
            str: File path
        """
        # Convert key to a safe filename using a hash
        hash_obj = hashlib.md5(str(key).encode('utf-8'))
        filename = hash_obj.hexdigest()
        return os.path.join(self.directory, filename)
    
    def _load_metadata(self):
        """Load metadata for existing cache files."""
        try:
            meta_path = os.path.join(self.directory, "metadata.pkl")
            if os.path.exists(meta_path):
                with open(meta_path, 'rb') as f:
                    self._metadata = pickle.load(f)
            
            # Validate metadata against actual files
            actual_files = set(f for f in os.listdir(self.directory) 
                               if os.path.isfile(os.path.join(self.directory, f)) and f != "metadata.pkl")
            meta_files = set(self._get_path(k).split(os.path.sep)[-1] for k in self._metadata.keys())
            
            # Remove metadata for files that no longer exist
            for key in list(self._metadata.keys()):
                if self._get_path(key).split(os.path.sep)[-1] not in actual_files:
                    del self._metadata[key]
            
            # Add metadata for files that exist but aren't in metadata
            for filename in actual_files:
                if filename not in meta_files and filename != "metadata.pkl":
                    # Use file mtime as timestamp
                    path = os.path.join(self.directory, filename)
                    mtime = os.path.getmtime(path)
                    # We don't know the original key, so use filename as the key
                    self._metadata[filename] = mtime
            
            # Update size stat
            self.stats.update_size(len(self._metadata))
            
        except Exception as e:
            logger.error(f"Error loading disk cache metadata: {e}")
            self._metadata = {}
    
    def _save_metadata(self):
        """Save metadata to disk."""
        try:
            meta_path = os.path.join(self.directory, "metadata.pkl")
            with open(meta_path, 'wb') as f:
                pickle.dump(self._metadata, f)
        except Exception as e:
            logger.error(f"Error saving disk cache metadata: {e}")
    
    def get(self, key):
        """Get an item from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Value or None if not found/expired
        """
        with self._lock:
            if key in self._metadata:
                timestamp = self._metadata[key]
                
                # Check TTL if set
                if self.ttl is not None and time.time() - timestamp > self.ttl:
                    # Expired
                    self.remove(key)
                    self.stats.record_miss()
                    return None
                
                try:
                    path = self._get_path(key)
                    if not os.path.exists(path):
                        # File doesn't exist, remove from metadata
                        del self._metadata[key]
                        self._save_metadata()
                        self.stats.record_miss()
                        return None
                    
                    with open(path, 'rb') as f:
                        value = pickle.load(f)
                    
                    # Update timestamp
                    self._metadata[key] = time.time()
                    self._save_metadata()
                    
                    self.stats.record_hit()
                    return value
                    
                except Exception as e:
                    logger.error(f"Error retrieving item from disk cache: {e}")
                    self.stats.record_miss()
                    return None
            
            self.stats.record_miss()
            return None
    
    def put(self, key, value):
        """Put an item in the cache.
        
        Args:
            key: Cache key
            value: Value to store
            
        Returns:
            bool: True if added, False if error
        """
        try:
            with self._lock:
                # Check if we need to evict
                if len(self._metadata) >= self.max_size and key not in self._metadata:
                    # Find oldest item
                    oldest_key = min(self._metadata.items(), key=lambda x: x[1])[0]
                    self.remove(oldest_key)
                    self.stats.record_eviction()
                
                # Save to disk
                path = self._get_path(key)
                with open(path, 'wb') as f:
                    pickle.dump(value, f)
                
                # Update metadata
                self._metadata[key] = time.time()
                self._save_metadata()
                
                # Update size stat
                self.stats.update_size(len(self._metadata))
                return True
                
        except Exception as e:
            logger.error(f"Error adding item to disk cache: {e}")
            return False
    
    def contains(self, key):
        """Check if key exists in cache (and is not expired).
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if in cache and not expired
        """
        with self._lock:
            if key in self._metadata:
                if self.ttl is not None:
                    timestamp = self._metadata[key]
                    if time.time() - timestamp > self.ttl:
                        # Expired
                        self.remove(key)
                        return False
                
                # Verify file exists
                path = self._get_path(key)
                if not os.path.exists(path):
                    # File doesn't exist, remove from metadata
                    del self._metadata[key]
                    self._save_metadata()
                    return False
                    
                return True
            return False
    
    def remove(self, key):
        """Remove an item from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if removed, False if not found
        """
        with self._lock:
            if key in self._metadata:
                # Remove file
                path = self._get_path(key)
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    logger.error(f"Error removing file from disk cache: {e}")
                
                # Remove from metadata
                del self._metadata[key]
                self._save_metadata()
                
                # Update size stat
                self.stats.update_size(len(self._metadata))
                return True
            return False
    
    def clear(self):
        """Clear all items from the cache."""
        with self._lock:
            # Remove all files
            for key in list(self._metadata.keys()):
                self.remove(key)
            
            # Clear metadata
            self._metadata.clear()
            self._save_metadata()
            
            # Update size stat
            self.stats.update_size(0)


class CacheManager:
    """Multi-level cache manager that coordinates different cache levels."""
    
    def __init__(self, config_manager=None):
        """Initialize cache manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.caches = {}  # {cache_name: cache_level}
        self.default_cache = None
        self.lock = threading.RLock()
        
        # Initialize default caches if config manager provided
        if config_manager:
            self._init_default_caches()
    
    def _init_default_caches(self):
        """Initialize default caches based on configuration."""
        try:
            # Get app directory
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cache_dir = os.path.join(app_dir, "cache")
            os.makedirs(cache_dir, exist_ok=True)
            
            # Memory cache levels
            self.add_cache(MemoryCache(
                name="L1", 
                max_size=self.config_manager.get("cache", "l1_size", 1000),
                ttl=self.config_manager.get("cache", "l1_ttl", 300)  # 5 minutes
            ))
            
            self.add_cache(MemoryCache(
                name="L2", 
                max_size=self.config_manager.get("cache", "l2_size", 5000),
                ttl=self.config_manager.get("cache", "l2_ttl", 1800)  # 30 minutes
            ))
            
            # Disk cache
            disk_cache_dir = os.path.join(cache_dir, "disk_cache")
            self.add_cache(DiskCache(
                name="Disk", 
                directory=disk_cache_dir,
                max_size=self.config_manager.get("cache", "disk_size", 10000),
                ttl=self.config_manager.get("cache", "disk_ttl", 86400)  # 1 day
            ))
            
            # Set default cache to L1
            self.default_cache = "L1"
            
            logger.info("Initialized default cache levels")
            
        except Exception as e:
            logger.error(f"Error initializing default caches: {e}")
    
    def add_cache(self, cache):
        """Add a cache level to the manager.
        
        Args:
            cache (CacheLevel): Cache level to add
            
        Returns:
            bool: True if added successfully
        """
        with self.lock:
            if cache.name in self.caches:
                logger.warning(f"Cache '{cache.name}' already exists, replacing")
            
            self.caches[cache.name] = cache
            
            # If this is the first cache, set it as default
            if self.default_cache is None:
                self.default_cache = cache.name
                
            return True
    
    def get_cache(self, name=None):
        """Get a specific cache level.
        
        Args:
            name (str, optional): Name of cache to get. If None, returns default.
            
        Returns:
            CacheLevel or None if not found
        """
        with self.lock:
            if name is None:
                name = self.default_cache
                
            return self.caches.get(name)
    
    def get(self, key, cache_names=None):
        """Get an item from the cache hierarchy.
        
        Args:
            key: Cache key
            cache_names (list, optional): List of cache names to search, in order.
                                         If None, searches all caches.
            
        Returns:
            Value or None if not found in any cache
        """
        with self.lock:
            # Determine which caches to search
            if cache_names is None:
                # Start with fastest (typically memory) caches
                search_caches = list(self.caches.keys())
            else:
                # Use specified caches
                search_caches = [name for name in cache_names if name in self.caches]
            
            # Try each cache
            value = None
            found_in = None
            
            for cache_name in search_caches:
                cache = self.caches[cache_name]
                value = cache.get(key)
                
                if value is not None:
                    found_in = cache_name
                    break
            
            # If found in a lower level cache, add to higher level caches
            if found_in is not None and search_caches.index(found_in) > 0:
                # Propagate to higher level caches
                for cache_name in search_caches[:search_caches.index(found_in)]:
                    self.caches[cache_name].put(key, value)
            
            return value
    
    def put(self, key, value, cache_names=None):
        """Put an item in the cache hierarchy.
        
        Args:
            key: Cache key
            value: Value to store
            cache_names (list, optional): List of cache names to store in.
                                         If None, stores in all caches.
            
        Returns:
            bool: True if stored in at least one cache
        """
        with self.lock:
            # Determine which caches to store in
            if cache_names is None:
                # Store in all caches
                store_caches = list(self.caches.keys())
            else:
                # Use specified caches
                store_caches = [name for name in cache_names if name in self.caches]
            
            # Store in each cache
            success = False
            for cache_name in store_caches:
                cache = self.caches[cache_name]
                if cache.put(key, value):
                    success = True
            
            return success
    
    def remove(self, key, cache_names=None):
        """Remove an item from the cache hierarchy.
        
        Args:
            key: Cache key
            cache_names (list, optional): List of cache names to remove from.
                                         If None, removes from all caches.
            
        Returns:
            bool: True if removed from at least one cache
        """
        with self.lock:
            # Determine which caches to remove from
            if cache_names is None:
                # Remove from all caches
                remove_caches = list(self.caches.keys())
            else:
                # Use specified caches
                remove_caches = [name for name in cache_names if name in self.caches]
            
            # Remove from each cache
            success = False
            for cache_name in remove_caches:
                cache = self.caches[cache_name]
                if cache.remove(key):
                    success = True
            
            return success
    
    def clear(self, cache_names=None):
        """Clear caches.
        
        Args:
            cache_names (list, optional): List of cache names to clear.
                                         If None, clears all caches.
        """
        with self.lock:
            # Determine which caches to clear
            if cache_names is None:
                # Clear all caches
                clear_caches = list(self.caches.keys())
            else:
                # Use specified caches
                clear_caches = [name for name in cache_names if name in self.caches]
            
            # Clear each cache
            for cache_name in clear_caches:
                cache = self.caches[cache_name]
                cache.clear()
    
    def get_stats(self):
        """Get statistics for all caches.
        
        Returns:
            dict: Dictionary of cache statistics
        """
        with self.lock:
            return {name: cache.get_stats() for name, cache in self.caches.items()}


# Decorator for caching function results
def cached(func=None, *, key_fn=None, cache_names=None, manager=None):
    """Decorator for caching function results.
    
    Args:
        func (callable, optional): Function to decorate
        key_fn (callable, optional): Function to generate cache key from args/kwargs
        cache_names (list, optional): List of cache names to use
        manager (CacheManager, optional): Cache manager to use
        
    Returns:
        callable: Decorated function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get/create cache manager
            nonlocal manager
            if manager is None:
                from src.config.config_manager import ConfigManager
                config = ConfigManager()
                manager = CacheManager(config)
            
            # Generate cache key
            if key_fn is not None:
                key = key_fn(*args, **kwargs)
            else:
                # Default key generation
                arg_str = str(args) + str(sorted(kwargs.items()))
                key = f"{func.__module__}.{func.__name__}:{hashlib.md5(arg_str.encode()).hexdigest()}"
            
            # Try to get from cache
            result = manager.get(key, cache_names)
            if result is not None:
                return result
            
            # Not in cache, call function
            result = func(*args, **kwargs)
            
            # Store in cache
            manager.put(key, result, cache_names)
            
            return result
        
        return wrapper
    
    # Handle both @cached and @cached() syntax
    if func is None:
        return decorator
    return decorator(func)
