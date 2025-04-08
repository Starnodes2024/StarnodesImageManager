#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Memory pool for image processing operations in StarImageBrowse.
Provides optimized memory management to reduce fragmentation and improve performance.
"""

import gc
import time
import threading
import logging
import numpy as np
from PIL import Image
from typing import Dict, List, Tuple, Optional, Union, Any, Callable
import psutil

logger = logging.getLogger("StarImageBrowse.memory.memory_pool")

class MemoryChunk:
    """Represents a reusable chunk of memory for image processing."""
    
    def __init__(self, buffer_size: int, buffer_type: str = "numpy"):
        """Initialize a memory chunk.
        
        Args:
            buffer_size (int): Size of memory buffer in bytes
            buffer_type (str): Type of buffer to create ('numpy' or 'bytearray')
        """
        self.size = buffer_size
        self.type = buffer_type
        self.creation_time = time.time()
        self.last_used = self.creation_time
        self.use_count = 0
        self.in_use = False
        self._buffer = None
        self._allocate_buffer()
    
    def _allocate_buffer(self):
        """Allocate the underlying memory buffer."""
        try:
            if self.type == "numpy":
                # Create a numpy array (common for image processing)
                buffer_size = max(1, self.size // 4)  # Convert bytes to float32 elements
                self._buffer = np.zeros(buffer_size, dtype=np.float32)
            else:
                # Create a bytearray (more general purpose)
                self._buffer = bytearray(self.size)
                
            logger.debug(f"Allocated {self.type} buffer of size {self.size} bytes")
        except MemoryError as e:
            logger.error(f"Memory allocation failed for {self.size} bytes: {e}")
            # Create a smaller buffer to avoid complete failure
            if self.size > 1024 * 1024:  # If over 1MB, try with 1MB
                self.size = 1024 * 1024
                self._allocate_buffer()
            else:
                raise
    
    def acquire(self):
        """Mark the chunk as in-use.
        
        Returns:
            The underlying buffer
        """
        self.in_use = True
        self.last_used = time.time()
        self.use_count += 1
        return self._buffer
    
    def release(self):
        """Release the chunk back to the pool."""
        self.in_use = False
        self.last_used = time.time()
    
    def resize(self, new_size: int):
        """Resize the memory chunk.
        
        Args:
            new_size (int): New size in bytes
            
        Returns:
            bool: True if resize was successful
        """
        if self.in_use:
            logger.warning("Cannot resize memory chunk while in use")
            return False
            
        try:
            self.size = new_size
            self._buffer = None
            self._allocate_buffer()
            return True
        except Exception as e:
            logger.error(f"Error resizing memory chunk: {e}")
            return False
    
    def clear(self):
        """Clear the buffer contents without deallocating."""
        if not self.in_use:
            try:
                if self.type == "numpy":
                    self._buffer.fill(0)
                else:
                    for i in range(len(self._buffer)):
                        self._buffer[i] = 0
            except Exception as e:
                logger.error(f"Error clearing memory chunk: {e}")
    
    def __del__(self):
        """Clean up resources on deletion."""
        self._buffer = None


class MemoryPool:
    """Pool of reusable memory chunks for image processing operations."""
    
    def __init__(self, config_manager=None):
        """Initialize the memory pool.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.chunks = []  # List of all memory chunks
        self.size_pools = {}  # Dictionary of chunks by size category
        self.lock = threading.RLock()
        self.total_allocated = 0
        self.max_pool_size = 100 * 1024 * 1024  # 100MB default
        
        # Load configuration
        if config_manager:
            self.max_pool_size = self.config_manager.get(
                "memory", "max_pool_size", 100 * 1024 * 1024
            )
        
        # Get system memory info to adjust pool size
        try:
            mem_info = psutil.virtual_memory()
            system_total = mem_info.total
            
            # Adjust pool size based on system memory (max 5% of total memory)
            max_possible = int(system_total * 0.05)
            self.max_pool_size = min(self.max_pool_size, max_possible)
            
            logger.info(f"Memory pool initialized with max size of {self.max_pool_size / (1024*1024):.1f} MB")
        except Exception as e:
            logger.error(f"Error getting system memory info: {e}")
    
    def _get_size_key(self, size: int) -> str:
        """Get a size category key for the requested size.
        
        Args:
            size (int): Size in bytes
            
        Returns:
            str: Size category key
        """
        # Use discrete size categories to improve reuse chances
        if size <= 1024:  # 1KB
            return "tiny"
        elif size <= 10 * 1024:  # 10KB
            return "small"
        elif size <= 100 * 1024:  # 100KB
            return "medium"
        elif size <= 1024 * 1024:  # 1MB
            return "large"
        elif size <= 10 * 1024 * 1024:  # 10MB
            return "xl"
        else:
            return "xxl"
    
    def _find_available_chunk(self, size_key: str, min_size: int) -> Optional[MemoryChunk]:
        """Find an available chunk of the appropriate size.
        
        Args:
            size_key (str): Size category key
            min_size (int): Minimum size in bytes
            
        Returns:
            MemoryChunk or None: Available chunk or None if not found
        """
        if size_key not in self.size_pools:
            return None
            
        for chunk in self.size_pools[size_key]:
            if not chunk.in_use and chunk.size >= min_size:
                return chunk
                
        return None
    
    def get_buffer(self, size: int, buffer_type: str = "numpy") -> Tuple[Any, Callable]:
        """Get a buffer from the pool of at least the specified size.
        
        Args:
            size (int): Size of the buffer in bytes
            buffer_type (str): Type of buffer ('numpy' or 'bytearray')
            
        Returns:
            tuple: (buffer, release_function)
        """
        with self.lock:
            size_key = self._get_size_key(size)
            
            # Try to find an existing chunk
            chunk = self._find_available_chunk(size_key, size)
            
            # Create a new chunk if needed
            if chunk is None:
                # Check if we need to clean up first
                if self.total_allocated + size > self.max_pool_size:
                    self._cleanup()
                
                # Create new chunk
                chunk = MemoryChunk(size, buffer_type)
                self.chunks.append(chunk)
                
                # Add to size pool
                if size_key not in self.size_pools:
                    self.size_pools[size_key] = []
                self.size_pools[size_key].append(chunk)
                
                self.total_allocated += chunk.size
            
            # Get the buffer and return with a release function
            buffer = chunk.acquire()
            release_fn = lambda c=chunk: c.release()
            
            return buffer, release_fn
    
    def _cleanup(self):
        """Clean up unused memory chunks to reduce memory usage."""
        with self.lock:
            # Sort chunks by last used time (oldest first)
            unused_chunks = [c for c in self.chunks if not c.in_use]
            unused_chunks.sort(key=lambda c: c.last_used)
            
            # Calculate how much memory to free
            target_reduction = max(
                self.total_allocated * 0.2,  # 20% of total
                self.total_allocated + self.max_pool_size * 0.1  # 10% over max
            )
            
            freed = 0
            removed_chunks = []
            
            # Remove oldest chunks until we've freed enough memory
            for chunk in unused_chunks:
                if freed >= target_reduction:
                    break
                    
                removed_chunks.append(chunk)
                freed += chunk.size
            
            # Actually remove the chunks
            for chunk in removed_chunks:
                self.chunks.remove(chunk)
                size_key = self._get_size_key(chunk.size)
                if size_key in self.size_pools and chunk in self.size_pools[size_key]:
                    self.size_pools[size_key].remove(chunk)
                
                self.total_allocated -= chunk.size
            
            # Explicitly run garbage collection to reclaim memory
            if removed_chunks:
                logger.info(f"Cleaned up {len(removed_chunks)} chunks, freed {freed / (1024*1024):.1f} MB")
                gc.collect()
    
    def clear(self):
        """Clear all memory chunks and free memory."""
        with self.lock:
            # Only remove chunks that aren't in use
            chunks_to_remove = [c for c in self.chunks if not c.in_use]
            
            for chunk in chunks_to_remove:
                self.chunks.remove(chunk)
                size_key = self._get_size_key(chunk.size)
                if size_key in self.size_pools and chunk in self.size_pools[size_key]:
                    self.size_pools[size_key].remove(chunk)
                
                self.total_allocated -= chunk.size
            
            # Explicitly run garbage collection
            gc.collect()
            
            logger.info(f"Cleared {len(chunks_to_remove)} unused memory chunks")
            
            # Report on chunks still in use
            in_use = [c for c in self.chunks if c.in_use]
            if in_use:
                logger.warning(f"{len(in_use)} memory chunks still in use, cannot free")
    
    def get_stats(self):
        """Get statistics about the memory pool.
        
        Returns:
            dict: Memory pool statistics
        """
        with self.lock:
            used_chunks = [c for c in self.chunks if c.in_use]
            unused_chunks = [c for c in self.chunks if not c.in_use]
            
            used_memory = sum(c.size for c in used_chunks)
            unused_memory = sum(c.size for c in unused_chunks)
            
            return {
                "total_chunks": len(self.chunks),
                "used_chunks": len(used_chunks),
                "unused_chunks": len(unused_chunks),
                "total_allocated_mb": self.total_allocated / (1024 * 1024),
                "used_memory_mb": used_memory / (1024 * 1024),
                "unused_memory_mb": unused_memory / (1024 * 1024),
                "max_pool_size_mb": self.max_pool_size / (1024 * 1024)
            }


class ImageBuffer:
    """Helper class for managing image processing buffers."""
    
    def __init__(self, memory_pool):
        """Initialize the image buffer.
        
        Args:
            memory_pool (MemoryPool): Memory pool instance
        """
        self.memory_pool = memory_pool
        self.active_buffers = {}  # Dictionary of active buffers
        self.lock = threading.RLock()
    
    def get_buffer_for_image(self, width, height, channels=4):
        """Get a buffer suitable for processing an image of the given dimensions.
        
        Args:
            width (int): Image width in pixels
            height (int): Image height in pixels
            channels (int): Number of channels (1=L, 3=RGB, 4=RGBA)
            
        Returns:
            tuple: (buffer_id, numpy_array, release_function)
        """
        with self.lock:
            # Calculate required buffer size
            buffer_size = width * height * channels * 4  # 4 bytes per float32
            
            # Get buffer from pool
            buffer, release_fn = self.memory_pool.get_buffer(buffer_size, "numpy")
            
            # Generate a unique buffer ID
            buffer_id = f"img_{time.time()}_{id(buffer)}"
            
            # Store in active buffers
            self.active_buffers[buffer_id] = {
                "buffer": buffer,
                "release_fn": release_fn,
                "size": buffer_size,
                "shape": (height, width, channels)
            }
            
            # Create a properly shaped view of the buffer
            # Note: we use the raw buffer to create a view with the right shape
            # This avoids copying the data and makes efficient use of the pooled memory
            shape_size = width * height * channels
            if len(buffer) >= shape_size:
                shaped_array = buffer[:shape_size].reshape((height, width, channels))
            else:
                # If the buffer is too small, resize it (this should not happen normally)
                logger.warning(f"Buffer too small for image: {len(buffer)} < {shape_size}")
                buffer.resize((height, width, channels))
                shaped_array = buffer
            
            # Create a custom release function that releases both the view and the buffer
            def combined_release():
                with self.lock:
                    if buffer_id in self.active_buffers:
                        info = self.active_buffers.pop(buffer_id)
                        info["release_fn"]()
            
            return buffer_id, shaped_array, combined_release
    
    def get_buffer_for_pil_image(self, image):
        """Get a buffer suitable for processing a PIL image.
        
        Args:
            image (PIL.Image): PIL Image
            
        Returns:
            tuple: (buffer_id, numpy_array, release_function)
        """
        width, height = image.size
        mode = image.mode
        
        if mode == "L":
            channels = 1
        elif mode == "RGB":
            channels = 3
        elif mode == "RGBA":
            channels = 4
        else:
            # Convert to RGBA for other modes
            image = image.convert("RGBA")
            channels = 4
        
        return self.get_buffer_for_image(width, height, channels)
    
    def release_all(self):
        """Release all active buffers."""
        with self.lock:
            for buffer_id, info in list(self.active_buffers.items()):
                info["release_fn"]()
            self.active_buffers.clear()
            
    def get_active_buffer_count(self):
        """Get the number of active buffers.
        
        Returns:
            int: Number of active buffers
        """
        with self.lock:
            return len(self.active_buffers)
