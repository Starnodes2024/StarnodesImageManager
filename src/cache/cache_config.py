#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cache configuration for StarImageBrowse.
Defines default settings and provides utility functions for cache configuration.
"""

import os
import logging
import psutil

logger = logging.getLogger("StarImageBrowse.cache.cache_config")

# Default cache settings
DEFAULT_CACHE_CONFIG = {
    # Memory caches
    "l1_size": 1000,           # Number of items in L1 (fast) cache
    "l1_ttl": 300,             # L1 cache TTL in seconds (5 minutes)
    "l2_size": 5000,           # Number of items in L2 (medium) cache
    "l2_ttl": 1800,            # L2 cache TTL in seconds (30 minutes)
    
    # Disk cache
    "disk_size": 10000,        # Number of items in disk cache
    "disk_ttl": 86400,         # Disk cache TTL in seconds (1 day)
    
    # Thumbnail-specific settings
    "thumbnail_memory_limit": 200,  # Number of thumbnails to keep in memory
    
    # Image settings
    "image_memory_limit": 20,   # Number of full images to keep in memory
    
    # Advanced settings
    "prefetch_enabled": True,   # Whether to prefetch items
    "prefetch_distance": 10,    # Number of items to prefetch
    "memory_pressure_limit": 75 # % of memory usage to trigger cache reduction
}

def get_optimal_cache_sizes():
    """Calculate optimal cache sizes based on system resources.
    
    Returns:
        dict: Optimized cache settings
    """
    try:
        # Get system memory information
        mem = psutil.virtual_memory()
        total_mem_gb = mem.total / (1024 ** 3)  # Convert to GB
        
        # Scale cache sizes based on available memory
        config = DEFAULT_CACHE_CONFIG.copy()
        
        # For systems with less than 4GB RAM
        if total_mem_gb < 4:
            config["l1_size"] = 500
            config["l2_size"] = 2000
            config["thumbnail_memory_limit"] = 100
            config["image_memory_limit"] = 10
            
        # For systems with 4-8GB RAM (use defaults)
        
        # For systems with more than 8GB RAM
        elif total_mem_gb > 8:
            config["l1_size"] = 2000
            config["l2_size"] = 10000
            config["thumbnail_memory_limit"] = 500
            config["image_memory_limit"] = 50
            
        # For systems with more than 16GB RAM
        if total_mem_gb > 16:
            config["l1_size"] = 4000
            config["l2_size"] = 20000
            config["thumbnail_memory_limit"] = 1000
            config["image_memory_limit"] = 100
            
        logger.info(f"Optimized cache settings for system with {total_mem_gb:.1f}GB RAM")
        return config
        
    except Exception as e:
        logger.error(f"Error calculating optimal cache sizes: {e}")
        return DEFAULT_CACHE_CONFIG

def apply_cache_config(config_manager):
    """Apply cache configuration to the config manager.
    
    Args:
        config_manager: Configuration manager instance
        
    Returns:
        bool: True if successful
    """
    try:
        # Get optimal settings
        optimal_settings = get_optimal_cache_sizes()
        
        # Apply settings if not already set
        for key, value in optimal_settings.items():
            if not config_manager.has("cache", key):
                config_manager.set("cache", key, value)
                
        logger.info("Applied cache configuration")
        return True
        
    except Exception as e:
        logger.error(f"Error applying cache configuration: {e}")
        return False

def memory_pressure_check():
    """Check if the system is under memory pressure.
    
    Returns:
        bool: True if under pressure
    """
    try:
        mem = psutil.virtual_memory()
        percent_used = mem.percent
        
        # Consider memory pressure if usage is above the threshold
        threshold = DEFAULT_CACHE_CONFIG["memory_pressure_limit"]
        if percent_used > threshold:
            logger.warning(f"System under memory pressure: {percent_used}% used (threshold: {threshold}%)")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error checking memory pressure: {e}")
        return False
