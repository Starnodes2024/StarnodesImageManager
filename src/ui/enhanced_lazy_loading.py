#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced lazy loading for StarImageBrowse
Provides optimized image loading with viewport-aware prioritization and prefetching.
"""

import os
import logging
import time
import uuid
from collections import OrderedDict
from PyQt6.QtCore import (
    QObject, QRunnable, pyqtSignal, QThreadPool, QTimer, 
    QRect, QPoint, QSize, Qt
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QScrollArea, QWidget

from .lazy_thumbnail_loader import LazyThumbnailLoader
from src.memory.memory_utils import get_image_processor, is_memory_pool_enabled
from src.memory.image_processor_integration import process_image_for_ai, batch_process_images_for_ai
from src.processing.task_manager import get_task_manager
from src.processing.batch_operations import get_batch_operations

logger = logging.getLogger("StarImageBrowse.ui.enhanced_lazy_loading")

class EnhancedLazyLoading(QObject):
    """Enhanced lazy loading system with viewport awareness and prefetching."""
    
    def __init__(self, scroll_area, thumbnail_container, max_concurrent=6, config_manager=None):
        """Initialize the enhanced lazy loading system.
        
        Args:
            scroll_area (QScrollArea): The scroll area containing thumbnails
            thumbnail_container (QWidget): The container widget for thumbnails
            max_concurrent (int): Maximum number of concurrent loading tasks
            config_manager: Configuration manager instance
        """
        super().__init__()
        
        self.scroll_area = scroll_area
        self.thumbnail_container = thumbnail_container
        self.config_manager = config_manager
        self.loader = LazyThumbnailLoader(max_concurrent=max_concurrent, config_manager=config_manager)
        
        # Initialize performance optimizations
        self.initialize_optimizations()
        
        # Viewport tracking
        self.viewport_rect = QRect()
        self.prefetch_margin = 300  # Pixels to extend beyond visible area for prefetching
        
        # Thumbnail tracking
        self.thumbnails = {}  # widget -> (image_id, thumbnail_path)
        self.loading_queue = OrderedDict()  # OrderedDict to maintain priority
        
        # Performance tracking
        self.last_load_time = {}  # image_id -> last load time
        self.load_durations = {}  # image_id -> load duration
        self.avg_load_time = 0.1  # Initial estimate: 100ms per thumbnail
        self.batch_mode = False   # Whether we're in batch loading mode
        self.batch_size = 20      # Number of images to process in a batch
        
        # Timer for periodic viewport check
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_viewport)
        self.check_timer.start(250)  # Check viewport 4 times per second
        
        # Last scroll position to detect scrolling
        self.last_scroll_position = 0
        self.scrolling = False
        self.scroll_stabilize_timer = QTimer(self)
        self.scroll_stabilize_timer.setSingleShot(True)
        self.scroll_stabilize_timer.timeout.connect(self.on_scroll_stabilized)
        
        # Memory optimization timer
        self.memory_optimize_timer = QTimer(self)
        self.memory_optimize_timer.timeout.connect(self.optimize_memory)
        self.memory_optimize_timer.start(10000)  # Check every 10 seconds
        
        # Batch processing timers
        self.batch_timer = QTimer(self)
        self.batch_timer.timeout.connect(self.process_batch_queue)
        self.batch_timer.setSingleShot(True)
        
        # Connect to scroll area's scrollbar
        if scroll_area.verticalScrollBar():
            scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)
        
        logger.info("Enhanced lazy loading initialized with advanced optimizations")
        
    def initialize_optimizations(self):
        """Initialize performance optimizations."""
        # Check if memory pooling is enabled
        self.use_memory_pool = False
        try:
            self.use_memory_pool = is_memory_pool_enabled()
            if self.use_memory_pool:
                self.image_processor = get_image_processor()
                logger.info("Using memory pool for enhanced lazy loading")
        except Exception as e:
            logger.warning(f"Could not initialize memory pool: {e}")
            
        # Check if parallel processing is enabled
        self.use_parallel_processing = False
        try:
            if self.config_manager:
                self.use_parallel_processing = self.config_manager.get("processing", "enable_parallel", True)
            
            if self.use_parallel_processing:
                self.task_manager = get_task_manager(self.config_manager)
                self.batch_operations = get_batch_operations(self.config_manager)
                logger.info("Using parallel processing for enhanced lazy loading")
        except Exception as e:
            logger.warning(f"Could not initialize parallel processing: {e}")
    
    def register_thumbnail(self, widget, image_id, thumbnail_path):
        """Register a thumbnail widget for lazy loading.
        
        Args:
            widget (QWidget): The thumbnail widget
            image_id (int): ID of the image
            thumbnail_path (str): Path to the thumbnail image
        """
        self.thumbnails[widget] = (image_id, thumbnail_path)
        
        # If visible, add to loading queue with high priority
        if self.is_widget_visible(widget):
            self.add_to_loading_queue(widget, high_priority=True)
    
    def unregister_thumbnail(self, widget):
        """Unregister a thumbnail widget.
        
        Args:
            widget (QWidget): The thumbnail widget to unregister
        """
        if widget in self.thumbnails:
            del self.thumbnails[widget]
    
    def clear_thumbnails(self):
        """Clear all registered thumbnails."""
        self.thumbnails.clear()
        self.loading_queue.clear()
        self.loader.cancel_pending()
        self.loader.clear_cache()
    
    def check_viewport(self):
        """Check the current viewport and prioritize loading of visible thumbnails."""
        if not self.thumbnails:
            return
            
        # Get current viewport rectangle
        viewport_rect = self.scroll_area.viewport().rect()
        viewport_rect_global = QRect(
            self.scroll_area.viewport().mapToGlobal(QPoint(0, 0)),
            viewport_rect.size()
        )
        
        # Extend viewport for prefetching
        prefetch_rect = viewport_rect.adjusted(
            -self.prefetch_margin, -self.prefetch_margin,
            self.prefetch_margin, self.prefetch_margin
        )
        
        # Only update loading queue if we're not actively scrolling
        if not self.scrolling:
            self.loading_queue.clear()
            
            # First, add visible widgets with high priority
            for widget in self.thumbnails:
                if self.is_widget_visible(widget, viewport_rect_global):
                    self.add_to_loading_queue(widget, high_priority=True)
            
            # Then, add widgets in the prefetch area with normal priority
            for widget in self.thumbnails:
                widget_rect_global = QRect(
                    widget.mapToGlobal(QPoint(0, 0)),
                    widget.size()
                )
                
                if not self.is_widget_visible(widget, viewport_rect_global) and \
                   prefetch_rect.intersects(self.scroll_area.viewport().mapFromGlobal(widget_rect_global.topLeft()).x()):
                    self.add_to_loading_queue(widget, high_priority=False)
        
        # Process any pending tasks
        self.process_loading_queue()
    
    def is_widget_visible(self, widget, viewport_rect_global=None):
        """Check if a widget is visible in the viewport.
        
        Args:
            widget (QWidget): The widget to check
            viewport_rect_global (QRect, optional): The global viewport rectangle
            
        Returns:
            bool: True if the widget is visible, False otherwise
        """
        if not viewport_rect_global:
            viewport_rect = self.scroll_area.viewport().rect()
            viewport_rect_global = QRect(
                self.scroll_area.viewport().mapToGlobal(QPoint(0, 0)),
                viewport_rect.size()
            )
        
        widget_rect_global = QRect(
            widget.mapToGlobal(QPoint(0, 0)),
            widget.size()
        )
        
        return viewport_rect_global.intersects(widget_rect_global)
    
    def add_to_loading_queue(self, widget, high_priority=False):
        """Add a widget to the loading queue.
        
        Args:
            widget (QWidget): The widget to add
            high_priority (bool): Whether this is a high-priority widget
        """
        if widget not in self.thumbnails:
            return
            
        image_id, thumbnail_path = self.thumbnails[widget]
        
        # Skip if already loaded
        if hasattr(widget, 'thumbnail_loaded') and widget.thumbnail_loaded:
            return
            
        # Add to loading queue, prioritizing visible widgets
        if high_priority:
            # Add to front of queue
            new_queue = OrderedDict()
            new_queue[widget] = (image_id, thumbnail_path)
            
            # Add existing items after
            for w, data in self.loading_queue.items():
                if w != widget:  # Avoid duplicates
                    new_queue[w] = data
                    
            self.loading_queue = new_queue
        else:
            # Add to end of queue if not already in queue
            if widget not in self.loading_queue:
                self.loading_queue[widget] = (image_id, thumbnail_path)
    
    def process_loading_queue(self):
        """Process the next items in the loading queue."""
        if not self.loading_queue:
            return
            
        # Check if we should use batch processing
        visible_count = sum(1 for widget in self.loading_queue if self.is_widget_visible(widget))
        
        # If we have many visible thumbnails to load, use batch processing
        if self.use_parallel_processing and visible_count >= self.batch_size and not self.batch_mode:
            self.start_batch_loading()
            return
            
        # Process up to max_concurrent items using standard method
        for _ in range(min(self.loader.threadpool.maxThreadCount(), len(self.loading_queue))):
            if not self.loading_queue:
                break
                
            # Get the next widget to load
            widget, (image_id, thumbnail_path) = next(iter(self.loading_queue.items()))
            
            # Skip if already loading this image
            if hasattr(widget, 'loading') and widget.loading:
                # Remove from queue and continue
                self.loading_queue.pop(widget, None)
                continue
                
            # Mark as loading
            widget.loading = True
            
            # Record start time for performance tracking
            start_time = time.time()
            self.last_load_time[image_id] = start_time
            
            # Create callback
            def create_callback(w, img_id, start_t):
                def callback(pixmap):
                    if pixmap:
                        if hasattr(w, 'set_thumbnail'):
                            w.set_thumbnail(pixmap)
                        elif hasattr(w, 'thumbnail_label'):
                            w.thumbnail_label.setPixmap(pixmap)
                    else:
                        if hasattr(w, 'set_thumbnail'):
                            # Create error pixmap
                            error_pixmap = QPixmap(200, 200)
                            error_pixmap.fill(Qt.GlobalColor.lightGray)
                            w.set_thumbnail(error_pixmap)
                        elif hasattr(w, 'thumbnail_label'):
                            # Create error pixmap
                            error_pixmap = QPixmap(200, 200)
                            error_pixmap.fill(Qt.GlobalColor.lightGray)
                            w.thumbnail_label.setPixmap(error_pixmap)
                    
                    # Mark as loaded
                    w.thumbnail_loaded = True
                    w.loading = False
                    
                    # Track load duration for performance optimization
                    end_time = time.time()
                    duration = end_time - start_t
                    self.load_durations[img_id] = duration
                    
                    # Update average load time
                    if len(self.load_durations) > 0:
                        self.avg_load_time = sum(self.load_durations.values()) / len(self.load_durations)
                    
                return callback
            
            # Use memory pool if enabled
            if self.use_memory_pool and hasattr(self, 'image_processor'):
                # Use memory pooled image loading
                try:
                    pixmap = self.image_processor.create_thumbnail(thumbnail_path)
                    create_callback(widget, image_id, start_time)(pixmap)
                except Exception as e:
                    logger.error(f"Error loading thumbnail with memory pool: {e}")
                    # Fall back to standard loading
                    self.loader.queue_thumbnail(image_id, thumbnail_path, 
                                              create_callback(widget, image_id, start_time))
            else:
                # Use standard lazy loading
                self.loader.queue_thumbnail(image_id, thumbnail_path, 
                                          create_callback(widget, image_id, start_time))
            
            # Remove from queue
            self.loading_queue.pop(widget, None)
    
    def start_batch_loading(self):
        """Start batch loading of thumbnails using parallel processing."""
        if not self.use_parallel_processing or self.batch_mode:
            return
            
        self.batch_mode = True
        logger.info(f"Starting batch loading of thumbnails with {len(self.loading_queue)} in queue")
        
        # Prepare batch of visible images
        batch_images = []
        batch_widgets = {}
        
        # First prioritize visible thumbnails
        for widget, (image_id, thumbnail_path) in list(self.loading_queue.items())[:self.batch_size]:
            # Skip if already loading
            if hasattr(widget, 'loading') and widget.loading:
                continue
                
            # Mark as loading
            widget.loading = True
            
            # Add to batch
            batch_images.append({
                'id': image_id,
                'path': thumbnail_path
            })
            
            # Track widget for callback
            batch_widgets[image_id] = widget
            
            # Remove from queue
            self.loading_queue.pop(widget, None)
            
            # Stop if batch size reached
            if len(batch_images) >= self.batch_size:
                break
        
        if not batch_images:
            self.batch_mode = False
            return
        
        try:
            # Define batch completion callback
            def on_batch_complete(results):
                self.batch_mode = False
                
                # Process results
                for task_id, result in results.get('results', {}).items():
                    if not result:
                        continue
                        
                    image_id = result.get('image_id')
                    thumbnail = result.get('thumbnail')
                    
                    if image_id and thumbnail and image_id in batch_widgets:
                        widget = batch_widgets[image_id]
                        
                        # Set thumbnail
                        if hasattr(widget, 'set_thumbnail'):
                            widget.set_thumbnail(thumbnail)
                        elif hasattr(widget, 'thumbnail_label'):
                            widget.thumbnail_label.setPixmap(thumbnail)
                            
                        # Mark as loaded
                        widget.thumbnail_loaded = True
                        widget.loading = False
                
                # Process any remaining items in the queue
                QTimer.singleShot(100, self.process_loading_queue)
            
            # Execute batch operation
            if self.use_parallel_processing and hasattr(self, 'batch_operations'):
                # Use the parallel processing batch operations
                self.batch_operations.process_thumbnails(
                    batch_images, show_progress=False, on_complete=on_batch_complete
                )
            else:
                # Fall back to standard processing
                self.batch_mode = False
                self.process_loading_queue()
                
        except Exception as e:
            logger.error(f"Error starting batch thumbnail loading: {e}")
            self.batch_mode = False
            
            # Return items to queue and continue with standard processing
            for image_id, widget in batch_widgets.items():
                # Find the corresponding thumbnail path
                for w, (img_id, thumb_path) in self.thumbnails.items():
                    if img_id == image_id:
                        self.loading_queue[widget] = (image_id, thumb_path)
                        widget.loading = False
                        break
            
            # Continue with standard processing
            self.process_loading_queue()
    
    def process_batch_queue(self):
        """Process the batch queue periodically."""
        if self.batch_mode:
            return
            
        # Check if there are enough items to justify batch processing
        if len(self.loading_queue) >= self.batch_size:
            self.start_batch_loading()
        else:
            # Process using standard method
            self.process_loading_queue()
    
    def on_scroll_changed(self, value):
        """Handle scroll position changes.
        
        Args:
            value (int): New scroll position
        """
        # Detect if we're scrolling
        self.scrolling = True
        
        # Restart timer when scrolling stops
        self.scroll_stabilize_timer.stop()
        self.scroll_stabilize_timer.start(150)  # Wait 150ms after scrolling stops
        
        # Update last scroll position
        self.last_scroll_position = value
    
    def on_scroll_stabilized(self):
        """Handle scroll stabilization (when scrolling stops)."""
        self.scrolling = False
        
        # Force queue rebuild and load visible thumbnails
        self.check_viewport()
    
    def optimize_memory(self):
        """Optimize memory usage by clearing cache of off-screen thumbnails."""
        # Skip if we're in batch mode
        if self.batch_mode:
            return
            
        # Track how many thumbnails were cleared
        cleared_count = 0
        
        # Calculate extended viewport for keeping thumbnails
        viewport_rect = self.scroll_area.viewport().rect()
        extended_rect = viewport_rect.adjusted(
            -self.prefetch_margin*2, -self.prefetch_margin*2,
            self.prefetch_margin*2, self.prefetch_margin*2
        )
        
        # Get the total number of thumbnails and loaded thumbnails
        total_thumbnails = len(self.thumbnails)
        loaded_thumbnails = sum(1 for widget in self.thumbnails 
                              if hasattr(widget, 'thumbnail_loaded') and widget.thumbnail_loaded)
        
        # Skip if we have few loaded thumbnails
        if loaded_thumbnails < 50:  # Only optimize if we have many loaded thumbnails
            return
            
        # Clear cache of items far from viewport
        for widget, (image_id, _) in list(self.thumbnails.items()):
            # If widget is far from viewport, clear its pixmap
            if hasattr(widget, 'thumbnail_loaded') and widget.thumbnail_loaded:
                widget_pos = widget.mapTo(self.scroll_area.viewport(), QPoint(0, 0))
                
                # Check if widget is very far from viewport (outside extended rect)
                if not extended_rect.contains(widget_pos):
                    # Clear pixmap to free memory
                    if hasattr(widget, 'thumbnail_label'):
                        widget.thumbnail_label.clear()
                        widget.thumbnail_loaded = False
                        cleared_count += 1
        
        # Clean up performance tracking data to avoid memory leaks
        if len(self.load_durations) > 1000:
            # Keep only the most recent 100 entries
            excess = len(self.load_durations) - 100
            for key in list(self.load_durations.keys())[:excess]:
                self.load_durations.pop(key, None)
        
        if len(self.last_load_time) > 1000:
            # Keep only the most recent 100 entries
            excess = len(self.last_load_time) - 100
            for key in list(self.last_load_time.keys())[:excess]:
                self.last_load_time.pop(key, None)
        
        # Clear the loader's cache periodically
        self.loader.clear_cache()
        
        # Use memory pool cleanup if available
        if cleared_count > 0 and self.use_memory_pool and hasattr(self, 'image_processor'):
            try:
                # Trigger memory pool cleanup
                self.image_processor.cleanup_old_operations()
                logger.debug(f"Memory optimization: cleared {cleared_count} thumbnails, memory pool cleaned up")
            except Exception as e:
                logger.warning(f"Error cleaning up memory pool: {e}")
        elif cleared_count > 0:
            logger.debug(f"Memory optimization: cleared {cleared_count} thumbnails")
