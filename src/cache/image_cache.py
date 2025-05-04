#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Image caching subsystem for StarImageBrowse.
Optimizes thumbnail and image loading through multi-level caching.
"""

import os
import io
import time
import logging
import threading
from PIL import Image
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import QByteArray, QBuffer, QIODevice

from .cache_manager import CacheManager

logger = logging.getLogger("StarImageBrowse.cache.image_cache")

class ImageCacheItem:
    """Container for cached image data with metadata."""
    
    def __init__(self, image_id, pixmap=None, pil_image=None, path=None, metadata=None):
        """Initialize image cache item.
        
        Args:
            image_id (int): Database ID of the image
            pixmap (QPixmap, optional): Qt pixmap for UI display
            pil_image (PIL.Image, optional): PIL image for processing
            path (str, optional): Path to the original image
            metadata (dict, optional): Additional image metadata
        """
        self.image_id = image_id
        self.pixmap = pixmap
        self.pil_image = pil_image
        self.path = path
        self.metadata = metadata or {}
        self.last_accessed = time.time()
        self.access_count = 0
    
    def access(self):
        """Update access time and count."""
        self.last_accessed = time.time()
        self.access_count += 1
        return self
    
    def serialize(self):
        """Convert to serializable form for disk caching.
        
        Returns:
            dict: Serializable representation
        """
        # We don't serialize QPixmap objects to avoid pickling errors
        # Only store metadata and path information
        
        # Convert PIL image to bytes if present
        pil_data = None
        if self.pil_image is not None:
            try:
                img_io = io.BytesIO()
                self.pil_image.save(img_io, format='PNG')
                pil_data = img_io.getvalue()
            except Exception as e:
                logger.error(f"Error serializing PIL image: {e}")
                pil_data = None
        
        return {
            'image_id': self.image_id,
            'pixmap_data': None,  # Don't store pixmap data
            'pil_data': pil_data,
            'path': self.path,
            'metadata': self.metadata,
            'last_accessed': self.last_accessed,
            'access_count': self.access_count
        }
    
    @classmethod
    def deserialize(cls, data):
        """Create instance from serialized data.
        
        Args:
            data (dict): Serialized data
            
        Returns:
            ImageCacheItem: Reconstructed instance
        """
        # Reconstruct QPixmap if present
        pixmap = None
        if data.get('pixmap_data'):
            pixmap = QPixmap()
            pixmap.loadFromData(data['pixmap_data'])
        
        # Reconstruct PIL image if present
        pil_image = None
        if data.get('pil_data'):
            pil_image = Image.open(io.BytesIO(data['pil_data']))
        
        item = cls(
            image_id=data['image_id'],
            pixmap=pixmap,
            pil_image=pil_image,
            path=data['path'],
            metadata=data['metadata']
        )
        
        item.last_accessed = data['last_accessed']
        item.access_count = data['access_count']
        
        return item


class ImageCache:
    """Specialized image caching system using the multi-level cache framework."""
    
    def __init__(self, config_manager=None):
        """Initialize image cache.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.cache_manager = CacheManager(config_manager)
        self.memory_limit = 100  # Default number of images to keep in memory
        self.lock = threading.RLock()
        
        # Configure cache sizes from config if available
        if config_manager:
            self.memory_limit = config_manager.get("cache", "thumbnail_memory_limit", 100)
        
        # Memory-only cache for pixmaps (not serialized to disk)
        self.pixmap_cache = {}  # {image_id: QPixmap}
        self.pixmap_lru = []    # LRU list of image_ids
        
        logger.info(f"Initialized image cache with memory limit of {self.memory_limit}")
    
    def get_thumbnail(self, image_id):
        """Get a thumbnail pixmap from cache.
        
        Args:
            image_id (int): Database ID of the image
            
        Returns:
            QPixmap or None if not found
        """
        # First check the fast memory-only cache
        with self.lock:
            if image_id in self.pixmap_cache:
                pixmap = self.pixmap_cache[image_id]
                # Update LRU order
                if image_id in self.pixmap_lru:
                    self.pixmap_lru.remove(image_id)
                self.pixmap_lru.append(image_id)
                return pixmap
        
        # Try the multi-level cache
        key = f"thumbnail:{image_id}"
        cache_item = self.cache_manager.get(key)
        
        if cache_item:
            # Found in cache, extract pixmap
            if cache_item.pixmap and not cache_item.pixmap.isNull():
                # Add to memory-only cache
                self._add_to_pixmap_cache(image_id, cache_item.pixmap)
                return cache_item.pixmap
        
        return None
    
    def set_thumbnail(self, image_id, pixmap, path=None, metadata=None):
        """Cache a thumbnail pixmap.
        
        Args:
            image_id (int): Database ID of the image
            pixmap (QPixmap): Thumbnail pixmap to cache
            path (str, optional): Path to the original image
            metadata (dict, optional): Additional image metadata
            
        Returns:
            bool: True if cached successfully
        """
        if pixmap is None or pixmap.isNull():
            return False
        
        # Add to memory-only cache (this is safe and doesn't use pickle)
        self._add_to_pixmap_cache(image_id, pixmap)
        
        # Only store metadata in the disk cache, not the actual pixmap
        # to avoid pickling errors
        cache_item = ImageCacheItem(
            image_id=image_id,
            pixmap=None,  # Don't store pixmap in the serialized item
            path=path,
            metadata=metadata
        )
        
        # Add metadata to multi-level cache
        key = f"thumbnail:{image_id}"
        try:
            return self.cache_manager.put(key, cache_item)
        except Exception as e:
            logger.error(f"Error caching thumbnail metadata: {e}")
            return False
    
    def get_image(self, image_id):
        """Get a full image from cache.
        
        Args:
            image_id (int): Database ID of the image
            
        Returns:
            PIL.Image or None if not found
        """
        key = f"image:{image_id}"
        cache_item = self.cache_manager.get(key)
        
        if cache_item and cache_item.pil_image:
            return cache_item.pil_image
        
        return None
    
    def set_image(self, image_id, image, path=None, metadata=None):
        """Cache a full image.
        
        Args:
            image_id (int): Database ID of the image
            image (PIL.Image): Image to cache
            path (str, optional): Path to the original image
            metadata (dict, optional): Additional image metadata
            
        Returns:
            bool: True if cached successfully
        """
        if image is None:
            return False
        
        # Create cache item
        cache_item = ImageCacheItem(
            image_id=image_id,
            pil_image=image,
            path=path,
            metadata=metadata
        )
        
        # Add to multi-level cache
        key = f"image:{image_id}"
        return self.cache_manager.put(key, cache_item)
    
    def remove(self, image_id):
        """Remove an image from all caches.
        
        Args:
            image_id (int): Database ID of the image
            
        Returns:
            bool: True if removed from at least one cache
        """
        success = False
        
        # Remove from memory-only cache
        with self.lock:
            if image_id in self.pixmap_cache:
                del self.pixmap_cache[image_id]
                if image_id in self.pixmap_lru:
                    self.pixmap_lru.remove(image_id)
                success = True
        
        # Remove from multi-level cache
        thumbnail_key = f"thumbnail:{image_id}"
        image_key = f"image:{image_id}"
        
        if self.cache_manager.remove(thumbnail_key):
            success = True
        
        if self.cache_manager.remove(image_key):
            success = True
        
        return success
    
    def clear(self):
        """Clear all image caches."""
        # Clear memory-only cache
        with self.lock:
            self.pixmap_cache.clear()
            self.pixmap_lru.clear()
        
        # Clear only the thumbnail and image prefixes
        for cache_level in self.cache_manager.caches.values():
            # Since we don't have a good way to selectively clear by prefix in the current
            # implementation, we'll just clear everything in each cache level
            cache_level.clear()
        
        logger.info("Cleared all image caches")
    
    def _add_to_pixmap_cache(self, image_id, pixmap):
        """Add a pixmap to the memory-only cache.
        
        Args:
            image_id (int): Database ID of the image
            pixmap (QPixmap): Thumbnail pixmap to cache
        """
        with self.lock:
            # Add to cache
            self.pixmap_cache[image_id] = pixmap
            
            # Add to LRU list
            if image_id in self.pixmap_lru:
                self.pixmap_lru.remove(image_id)
            self.pixmap_lru.append(image_id)
            
            # Enforce memory limit
            while len(self.pixmap_lru) > self.memory_limit:
                # Remove oldest pixmap
                oldest_id = self.pixmap_lru.pop(0)
                if oldest_id in self.pixmap_cache:
                    del self.pixmap_cache[oldest_id]
