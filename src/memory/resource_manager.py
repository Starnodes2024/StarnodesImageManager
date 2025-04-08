#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Resource management for StarImageBrowse
Provides advanced resource cleanup and memory monitoring.
"""

import os
import gc
import logging
import psutil
import threading
import time
import weakref
from typing import Dict, List, Callable, Any, Optional, Set

logger = logging.getLogger("StarImageBrowse.memory.resource_manager")

class ResourceManager:
    """Manages application resources and handles cleanup."""
    
    def __init__(self, config_manager=None):
        """Initialize the resource manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        
        # Default configuration
        self.gc_threshold = 80  # Percent memory usage threshold to trigger GC
        self.monitor_interval = 10  # Seconds between monitoring checks
        self.aggressive_cleanup = False  # Whether to use aggressive cleanup
        self.monitoring_enabled = True  # Whether to enable memory monitoring
        
        # Callbacks for resource cleanup
        self.cleanup_callbacks = []
        
        # Tracked resources
        self.tracked_resources = weakref.WeakValueDictionary()
        self.tracked_resource_ids = set()
        
        # Memory usage statistics
        self.peak_memory_usage = 0
        self.current_memory_usage = 0
        self.last_gc_time = 0
        
        # Load configuration if provided
        if config_manager:
            self.gc_threshold = config_manager.get("memory", "gc_threshold", 80)
            self.monitor_interval = config_manager.get("memory", "monitor_interval", 10)
            self.aggressive_cleanup = config_manager.get("memory", "aggressive_cleanup", False)
            self.monitoring_enabled = config_manager.get("memory", "monitoring_enabled", True)
        
        # Start monitoring thread if enabled
        self.monitor_thread = None
        self.stop_monitoring = threading.Event()
        if self.monitoring_enabled:
            self.start_monitoring()
        
        logger.info(f"Resource manager initialized with gc_threshold={self.gc_threshold}%, "
                   f"monitor_interval={self.monitor_interval}s, aggressive_cleanup={self.aggressive_cleanup}")
    
    def register_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called during resource cleanup.
        
        Args:
            callback: Function to call during cleanup
        """
        if callback not in self.cleanup_callbacks:
            self.cleanup_callbacks.append(callback)
            logger.debug(f"Registered cleanup callback: {callback.__qualname__ if hasattr(callback, '__qualname__') else str(callback)}")
    
    def unregister_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """Unregister a cleanup callback.
        
        Args:
            callback: Function to remove from cleanup callbacks
        """
        if callback in self.cleanup_callbacks:
            self.cleanup_callbacks.remove(callback)
            logger.debug(f"Unregistered cleanup callback: {callback.__qualname__ if hasattr(callback, '__qualname__') else str(callback)}")
    
    def track_resource(self, resource_id: str, resource: Any) -> None:
        """Track a resource for cleanup.
        
        Args:
            resource_id: Unique identifier for the resource
            resource: Resource object to track
        """
        # Add to weak dictionary
        self.tracked_resources[resource_id] = resource
        self.tracked_resource_ids.add(resource_id)
        logger.debug(f"Tracking resource: {resource_id}")
    
    def untrack_resource(self, resource_id: str) -> None:
        """Stop tracking a resource.
        
        Args:
            resource_id: Unique identifier for the resource
        """
        if resource_id in self.tracked_resources:
            del self.tracked_resources[resource_id]
        if resource_id in self.tracked_resource_ids:
            self.tracked_resource_ids.remove(resource_id)
        logger.debug(f"Untracked resource: {resource_id}")
    
    def get_tracked_resource(self, resource_id: str) -> Optional[Any]:
        """Get a tracked resource by ID.
        
        Args:
            resource_id: Unique identifier for the resource
            
        Returns:
            Resource object or None if not found or already garbage collected
        """
        return self.tracked_resources.get(resource_id)
    
    def cleanup_tracked_resources(self) -> None:
        """Clean up tracked resources."""
        # Find resource IDs that exist in tracked_resource_ids but not in tracked_resources
        # (these are resources that have been garbage collected)
        to_remove = set()
        for resource_id in self.tracked_resource_ids:
            if resource_id not in self.tracked_resources:
                to_remove.add(resource_id)
        
        # Remove these IDs
        self.tracked_resource_ids -= to_remove
        
        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} tracked resources that were garbage collected")
    
    def start_monitoring(self) -> None:
        """Start the memory monitoring thread."""
        if self.monitor_thread is not None and self.monitor_thread.is_alive():
            logger.warning("Memory monitoring thread is already running")
            return
        
        self.stop_monitoring.clear()
        self.monitor_thread = threading.Thread(
            target=self._memory_monitor_thread,
            daemon=True,
            name="MemoryMonitorThread"
        )
        self.monitor_thread.start()
        logger.info("Started memory monitoring thread")
    
    def stop_monitoring(self) -> None:
        """Stop the memory monitoring thread."""
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            logger.warning("Memory monitoring thread is not running")
            return
        
        self.stop_monitoring.set()
        self.monitor_thread.join(timeout=2.0)
        if self.monitor_thread.is_alive():
            logger.warning("Memory monitoring thread did not stop cleanly")
        else:
            logger.info("Stopped memory monitoring thread")
        
        self.monitor_thread = None
    
    def _memory_monitor_thread(self) -> None:
        """Memory monitoring thread function."""
        logger.debug("Memory monitoring thread started")
        
        while not self.stop_monitoring.is_set():
            try:
                # Get current memory usage
                mem_info = psutil.Process().memory_info()
                current_usage = mem_info.rss / (1024 * 1024)  # MB
                current_percent = psutil.virtual_memory().percent
                
                self.current_memory_usage = current_usage
                self.peak_memory_usage = max(self.peak_memory_usage, current_usage)
                
                logger.debug(f"Memory usage: {current_usage:.2f} MB, {current_percent:.1f}%, peak: {self.peak_memory_usage:.2f} MB")
                
                # Check if we need to trigger cleanup
                if current_percent > self.gc_threshold:
                    # Only trigger if we haven't triggered recently
                    if time.time() - self.last_gc_time > 60:  # At most once per minute
                        logger.warning(f"Memory usage ({current_percent:.1f}%) exceeds threshold ({self.gc_threshold}%), triggering cleanup")
                        self.trigger_cleanup(force_aggressive=current_percent > 90)
                        self.last_gc_time = time.time()
                
                # Sleep for the monitoring interval
                for _ in range(int(self.monitor_interval * 10)):
                    if self.stop_monitoring.is_set():
                        break
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in memory monitor thread: {e}")
                time.sleep(5)  # Wait a bit longer if there was an error
        
        logger.debug("Memory monitoring thread stopped")
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics.
        
        Returns:
            dict: Memory usage statistics
        """
        try:
            mem_info = psutil.Process().memory_info()
            virtual_mem = psutil.virtual_memory()
            
            return {
                'rss_mb': mem_info.rss / (1024 * 1024),  # MB
                'vms_mb': mem_info.vms / (1024 * 1024),  # MB
                'percent': virtual_mem.percent,
                'peak_mb': self.peak_memory_usage,
                'system_total_mb': virtual_mem.total / (1024 * 1024),
                'system_available_mb': virtual_mem.available / (1024 * 1024)
            }
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {
                'rss_mb': 0,
                'vms_mb': 0,
                'percent': 0,
                'peak_mb': self.peak_memory_usage,
                'system_total_mb': 0,
                'system_available_mb': 0
            }
    
    def trigger_cleanup(self, force_aggressive: bool = False) -> None:
        """Trigger resource cleanup.
        
        Args:
            force_aggressive: Whether to force aggressive cleanup regardless of settings
        """
        logger.info("Triggering resource cleanup")
        start_time = time.time()
        
        # Call cleanup callbacks
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in cleanup callback {callback.__qualname__ if hasattr(callback, '__qualname__') else str(callback)}: {e}")
        
        # Clean up tracked resources
        self.cleanup_tracked_resources()
        
        # Run garbage collection
        gc.collect()
        
        # Aggressive cleanup if enabled or forced
        if self.aggressive_cleanup or force_aggressive:
            logger.info("Performing aggressive cleanup")
            
            # Run garbage collection multiple times with different generations
            for i in range(3):
                gc.collect(i)
            
            # Get list of garbage collector objects and look for large objects
            gc_objects = gc.get_objects()
            large_objects = [obj for obj in gc_objects if hasattr(obj, '__sizeof__') and obj.__sizeof__() > 1024 * 1024]
            logger.debug(f"Found {len(large_objects)} large objects (>1MB) in memory")
            
            # Force clear large lists and dictionaries
            for obj in large_objects:
                try:
                    if isinstance(obj, (list, dict)) and not isinstance(obj, (tuple, frozenset)):
                        obj.clear()
                except Exception:
                    pass
            
            # Run garbage collection again
            gc.collect()
        
        # Log memory usage after cleanup
        elapsed = time.time() - start_time
        mem_usage = self.get_memory_usage()
        logger.info(f"Resource cleanup completed in {elapsed:.2f}s, "
                   f"memory usage: {mem_usage['rss_mb']:.2f} MB, {mem_usage['percent']:.1f}%")
    
    def register_finalizer(self, obj: Any, callback: Callable[[], None]) -> None:
        """Register a finalizer for an object.
        
        Args:
            obj: Object to register finalizer for
            callback: Function to call when the object is garbage collected
        """
        try:
            weakref.finalize(obj, callback)
            logger.debug(f"Registered finalizer for object of type {type(obj).__name__}")
        except Exception as e:
            logger.error(f"Error registering finalizer: {e}")
    
    def register_large_object(self, obj_id: str, obj: Any, size_hint: Optional[int] = None) -> None:
        """Register a large object for memory tracking.
        
        Args:
            obj_id: Identifier for the object
            obj: The object itself
            size_hint: Optional hint about the object's size in bytes
        """
        try:
            size = size_hint or (obj.__sizeof__() if hasattr(obj, '__sizeof__') else 0)
            logger.debug(f"Registering large object {obj_id} of type {type(obj).__name__}, size ~{size/(1024*1024):.2f} MB")
            self.track_resource(obj_id, obj)
            
            # Register a callback to be called when the object is garbage collected
            def cleanup_callback():
                logger.debug(f"Large object {obj_id} of type {type(obj).__name__} was garbage collected")
                self.untrack_resource(obj_id)
            
            self.register_finalizer(obj, cleanup_callback)
            
        except Exception as e:
            logger.error(f"Error registering large object: {e}")
    
    def cleanup(self) -> None:
        """Perform cleanup when the resource manager is shutting down."""
        logger.info("Resource manager shutting down, cleaning up resources")
        
        # Stop the monitoring thread
        self.stop_monitoring.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        
        # Trigger cleanup one last time
        self.trigger_cleanup(force_aggressive=True)
        
        # Clear callbacks and tracked resources
        self.cleanup_callbacks = []
        self.tracked_resources.clear()
        self.tracked_resource_ids.clear()
        
        logger.info("Resource manager cleanup complete")
    
    def __del__(self):
        """Clean up resources when the object is deleted."""
        self.cleanup()


class BatchOperationContext:
    """Context manager for batch operations with memory monitoring."""
    
    def __init__(self, resource_manager: ResourceManager, operation_name: str, estimated_size_mb: float = 0):
        """Initialize the batch operation context.
        
        Args:
            resource_manager: Resource manager instance
            operation_name: Name of the batch operation
            estimated_size_mb: Estimated memory size of the operation in MB
        """
        self.resource_manager = resource_manager
        self.operation_name = operation_name
        self.estimated_size_mb = estimated_size_mb
        self.start_time = 0
        self.start_memory = {}
        
    def __enter__(self):
        """Start the batch operation context."""
        self.start_time = time.time()
        self.start_memory = self.resource_manager.get_memory_usage()
        
        logger.info(f"Starting batch operation: {self.operation_name}, "
                   f"estimated memory: {self.estimated_size_mb:.2f} MB")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End the batch operation context."""
        elapsed = time.time() - self.start_time
        end_memory = self.resource_manager.get_memory_usage()
        
        memory_diff = end_memory['rss_mb'] - self.start_memory['rss_mb']
        
        if exc_type is not None:
            logger.error(f"Batch operation {self.operation_name} failed with error: {exc_val}")
        
        logger.info(f"Completed batch operation: {self.operation_name}, "
                   f"elapsed time: {elapsed:.2f}s, memory change: {memory_diff:.2f} MB")
        
        # If memory usage increased significantly, trigger cleanup
        if memory_diff > 100:  # More than 100MB increase
            logger.info(f"Significant memory increase detected ({memory_diff:.2f} MB), triggering cleanup")
            self.resource_manager.trigger_cleanup()
        
        # Don't suppress exceptions
        return False
