#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Lazy thumbnail loader for StarImageBrowse
Provides optimized thumbnail loading for better performance with large image collections.
"""

import os
import logging
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot, QThreadPool, QTimer
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger("StarImageBrowse.ui.lazy_thumbnail_loader")

class ThumbnailLoadSignals(QObject):
    """Signals for thumbnail loading."""
    finished = pyqtSignal(int, QPixmap)  # image_id, pixmap
    error = pyqtSignal(int, str)  # image_id, error message

class ThumbnailLoadTask(QRunnable):
    """Task for loading a thumbnail in a background thread."""
    
    def __init__(self, image_id, thumbnail_path, max_size=(200, 200)):
        """Initialize the thumbnail load task.
        
        Args:
            image_id (int): ID of the image
            thumbnail_path (str): Path to the thumbnail image
            max_size (tuple): Maximum size (width, height) for the thumbnail
        """
        super().__init__()
        self.image_id = image_id
        self.thumbnail_path = thumbnail_path
        self.max_size = max_size
        self.signals = ThumbnailLoadSignals()
        
    @pyqtSlot()
    def run(self):
        """Run the thumbnail loading task."""
        try:
            if not self.thumbnail_path or not os.path.exists(self.thumbnail_path):
                self.signals.error.emit(self.image_id, "Thumbnail file not found")
                return
            
            # Load the image
            pixmap = QPixmap(self.thumbnail_path)
            if pixmap.isNull():
                self.signals.error.emit(self.image_id, "Failed to load thumbnail")
                return
            
            # Scale if needed using a simpler method that doesn't rely on Qt enums
            max_width, max_height = self.max_size
            if pixmap.width() > max_width or pixmap.height() > max_height:
                # Calculate the scaling factor to maintain aspect ratio
                width_ratio = max_width / pixmap.width()
                height_ratio = max_height / pixmap.height()
                scale_ratio = min(width_ratio, height_ratio)
                
                # Calculate new dimensions
                new_width = int(pixmap.width() * scale_ratio)
                new_height = int(pixmap.height() * scale_ratio)
                
                # Scale the pixmap
                pixmap = pixmap.scaled(new_width, new_height)
            
            # Emit the loaded pixmap
            self.signals.finished.emit(self.image_id, pixmap)
            
        except Exception as e:
            logger.error(f"Error loading thumbnail {self.image_id}: {str(e)}")
            self.signals.error.emit(self.image_id, str(e))

class LazyThumbnailLoader(QObject):
    """Manager for lazy loading thumbnails."""
    
    def __init__(self, max_concurrent=4, parent=None):
        """Initialize the lazy thumbnail loader.
        
        Args:
            max_concurrent (int): Maximum number of concurrent loading tasks
            parent (QObject, optional): Parent object
        """
        super().__init__(parent)
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(max_concurrent)
        self.pending_tasks = {}  # image_id -> (thumbnail_path, callback)
        self.active_tasks = set()  # Set of image_ids currently being loaded
        self.load_timer = QTimer(self)
        self.load_timer.timeout.connect(self.process_pending_tasks)
        self.load_timer.start(50)  # Check for pending tasks every 50ms
        
        # Cache of loaded thumbnails
        self.cache = {}  # image_id -> QPixmap
        self.cache_size_limit = 100  # Maximum number of thumbnails to cache
        
        logger.info(f"LazyThumbnailLoader initialized with max_concurrent={max_concurrent}")
    
    def queue_thumbnail(self, image_id, thumbnail_path, callback):
        """Queue a thumbnail for loading.
        
        Args:
            image_id (int): ID of the image
            thumbnail_path (str): Path to the thumbnail image
            callback (callable): Function to call with the loaded pixmap
        """
        # Check if already in cache
        if image_id in self.cache:
            QTimer.singleShot(0, lambda: callback(self.cache[image_id]))
            return
        
        # Add to pending tasks
        self.pending_tasks[image_id] = (thumbnail_path, callback)
    
    def process_pending_tasks(self):
        """Process pending thumbnail loading tasks."""
        # If no pending tasks or at max concurrent tasks, do nothing
        if not self.pending_tasks or len(self.active_tasks) >= self.threadpool.maxThreadCount():
            return
        
        # Get the next pending task
        image_id, (thumbnail_path, callback) = next(iter(self.pending_tasks.items()))
        del self.pending_tasks[image_id]
        self.active_tasks.add(image_id)
        
        # Create and start the task
        task = ThumbnailLoadTask(image_id, thumbnail_path)
        task.signals.finished.connect(lambda img_id, pixmap: self.on_thumbnail_loaded(img_id, pixmap, callback))
        task.signals.error.connect(lambda img_id, error: self.on_thumbnail_error(img_id, error, callback))
        self.threadpool.start(task)
    
    def on_thumbnail_loaded(self, image_id, pixmap, callback):
        """Handle a successfully loaded thumbnail.
        
        Args:
            image_id (int): ID of the image
            pixmap (QPixmap): Loaded thumbnail pixmap
            callback (callable): Function to call with the loaded pixmap
        """
        # Remove from active tasks
        self.active_tasks.discard(image_id)
        
        # Add to cache
        self.cache[image_id] = pixmap
        self.manage_cache()
        
        # Call the callback
        callback(pixmap)
    
    def on_thumbnail_error(self, image_id, error, callback):
        """Handle an error loading a thumbnail.
        
        Args:
            image_id (int): ID of the image
            error (str): Error message
            callback (callable): Function to call with None
        """
        # Remove from active tasks
        self.active_tasks.discard(image_id)
        
        # Log the error
        logger.warning(f"Failed to load thumbnail {image_id}: {error}")
        
        # Call the callback with None
        callback(None)
    
    def manage_cache(self):
        """Manage the thumbnail cache size."""
        if len(self.cache) > self.cache_size_limit:
            # Remove oldest items (first items in the dictionary)
            excess = len(self.cache) - self.cache_size_limit
            for _ in range(excess):
                self.cache.pop(next(iter(self.cache.keys())))
    
    def clear_cache(self):
        """Clear the thumbnail cache."""
        self.cache.clear()
    
    def cancel_pending(self, image_id=None):
        """Cancel pending thumbnail loading tasks.
        
        Args:
            image_id (int, optional): ID of the image to cancel, or None to cancel all
        """
        if image_id is not None:
            if image_id in self.pending_tasks:
                del self.pending_tasks[image_id]
        else:
            self.pending_tasks.clear()
