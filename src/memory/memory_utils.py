#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utility functions for memory management in StarImageBrowse.
Provides easy access to memory pool and monitoring features.
"""

import gc
import logging
import threading
import time
import psutil
from typing import Dict, Optional, Callable, Any

from .memory_pool import MemoryPool
from .image_processor_pool import ImageProcessorPool

logger = logging.getLogger("StarImageBrowse.memory.memory_utils")

# Global instances
_memory_pool = None
_image_processor = None
_config_manager = None
_memory_monitor_thread = None
_monitor_running = False

def initialize_memory_management(config_manager=None):
    """Initialize the memory management system.
    
    Args:
        config_manager: Configuration manager instance
    """
    global _memory_pool, _image_processor, _config_manager
    
    _config_manager = config_manager
    
    # Create the memory pool if it doesn't exist
    if _memory_pool is None:
        _memory_pool = MemoryPool(config_manager)
        logger.info("Memory pool initialized")
    
    # Create the image processor if it doesn't exist
    if _image_processor is None:
        _image_processor = ImageProcessorPool(config_manager)
        logger.info("Image processor pool initialized")
    
    # Start memory monitoring if enabled
    if config_manager and config_manager.get("memory", "debug_memory_usage", False):
        start_memory_monitoring()


def get_memory_pool():
    """Get the global memory pool instance.
    
    Returns:
        MemoryPool: Global memory pool instance
    """
    global _memory_pool, _config_manager
    
    if _memory_pool is None:
        _memory_pool = MemoryPool(_config_manager)
        logger.info("Memory pool created on first use")
    
    return _memory_pool


def get_image_processor():
    """Get the global image processor instance.
    
    Returns:
        ImageProcessorPool: Global image processor instance
    """
    global _image_processor, _config_manager
    
    if _image_processor is None:
        _image_processor = ImageProcessorPool(_config_manager)
        logger.info("Image processor created on first use")
    
    return _image_processor


def is_memory_pool_enabled():
    """Check if memory pooling is enabled.
    
    Returns:
        bool: True if memory pooling is enabled
    """
    global _config_manager
    
    if _config_manager:
        return _config_manager.get("memory", "enable_memory_pool", True)
    
    return True


def get_system_memory_info():
    """Get system memory information.
    
    Returns:
        dict: Memory information dictionary
    """
    try:
        mem_info = psutil.virtual_memory()
        return {
            "total_gb": mem_info.total / (1024**3),
            "available_gb": mem_info.available / (1024**3),
            "used_gb": mem_info.used / (1024**3),
            "percent_used": mem_info.percent
        }
    except Exception as e:
        logger.error(f"Error getting system memory info: {e}")
        return {
            "total_gb": 0,
            "available_gb": 0,
            "used_gb": 0,
            "percent_used": 0
        }


def force_garbage_collection():
    """Force garbage collection to free memory."""
    try:
        # Run garbage collection
        collected = gc.collect()
        logger.debug(f"Garbage collection: {collected} objects collected")
        return collected
    except Exception as e:
        logger.error(f"Error during garbage collection: {e}")
        return 0


def cleanup_memory_pools():
    """Clean up all memory pools."""
    global _memory_pool, _image_processor
    
    try:
        if _memory_pool:
            _memory_pool.clear()
            logger.info("Memory pool cleared")
        
        if _image_processor:
            _image_processor.cleanup_old_operations()
            logger.info("Image processor operations cleaned up")
        
        # Force garbage collection
        force_garbage_collection()
        
    except Exception as e:
        logger.error(f"Error cleaning up memory pools: {e}")


def _memory_monitor_task():
    """Background task for monitoring memory usage."""
    global _monitor_running
    
    cleanup_interval = 60  # Default to 60 seconds
    log_interval = 300     # Log memory stats every 5 minutes by default
    
    # Get configuration if available
    if _config_manager:
        cleanup_interval = _config_manager.get("memory", "cleanup_interval", 60)
        log_interval = cleanup_interval * 5  # Log every 5 cleanup cycles by default
    
    last_cleanup = time.time()
    last_log = time.time()
    
    while _monitor_running:
        try:
            now = time.time()
            
            # Clean up old operations periodically
            if now - last_cleanup >= cleanup_interval:
                if _image_processor:
                    cleaned = _image_processor.cleanup_old_operations()
                    if cleaned > 0:
                        logger.debug(f"Cleaned up {cleaned} image operations")
                
                last_cleanup = now
            
            # Log memory usage periodically
            if now - last_log >= log_interval:
                if _memory_pool:
                    stats = _memory_pool.get_stats()
                    logger.info(f"Memory pool stats: {stats}")
                
                sys_mem = get_system_memory_info()
                logger.info(f"System memory: {sys_mem['percent_used']}% used, "
                           f"{sys_mem['available_gb']:.1f} GB available")
                
                last_log = now
            
            # Sleep for a while
            time.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            logger.error(f"Error in memory monitor task: {e}")
            time.sleep(30)  # Longer sleep on error


def start_memory_monitoring():
    """Start memory usage monitoring in a background thread."""
    global _memory_monitor_thread, _monitor_running
    
    if _memory_monitor_thread is not None and _memory_monitor_thread.is_alive():
        logger.debug("Memory monitoring already running")
        return
    
    _monitor_running = True
    _memory_monitor_thread = threading.Thread(
        target=_memory_monitor_task,
        name="MemoryMonitor"
    )
    _memory_monitor_thread.daemon = True
    _memory_monitor_thread.start()
    
    logger.info("Memory monitoring started")


def stop_memory_monitoring():
    """Stop memory usage monitoring."""
    global _memory_monitor_thread, _monitor_running
    
    _monitor_running = False
    
    if _memory_monitor_thread and _memory_monitor_thread.is_alive():
        # Allow thread to exit gracefully
        _memory_monitor_thread.join(1.0)
        logger.info("Memory monitoring stopped")


def get_memory_stats():
    """Get current memory usage statistics.
    
    Returns:
        dict: Memory statistics dictionary
    """
    stats = {}
    
    # Get system memory info
    sys_mem = get_system_memory_info()
    stats.update({
        "system_" + k: v for k, v in sys_mem.items()
    })
    
    # Get memory pool stats if available
    if _memory_pool:
        pool_stats = _memory_pool.get_stats()
        stats.update({
            "pool_" + k: v for k, v in pool_stats.items()
        })
    
    # Get image processor stats if available
    if _image_processor:
        proc_stats = _image_processor.get_memory_stats()
        stats.update({
            "proc_" + k: v for k, v in proc_stats.items()
        })
    
    return stats
