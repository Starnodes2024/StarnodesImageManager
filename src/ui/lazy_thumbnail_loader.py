#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Lazy thumbnail loader for StarImageBrowse
Provides optimized thumbnail loading for better performance with large image collections.
"""

import os
import sys
import logging
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot, QThreadPool, QTimer
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QApplication

# Import the new caching system
from src.cache.image_cache import ImageCache

logger = logging.getLogger("StarImageBrowse.ui.lazy_thumbnail_loader")

class ThumbnailLoadSignals(QObject):
    """Signals for thumbnail loading."""
    finished = pyqtSignal(int, QPixmap)  # image_id, pixmap
    error = pyqtSignal(int, str)  # image_id, error message

class ThumbnailLoadTask(QRunnable):
    """Task for loading a thumbnail in a background thread."""
    
    def __init__(self, image_id, thumbnail_path, max_size=(200, 200), thumbnails_dir=None):
        """Initialize the thumbnail load task.
        
        Args:
            image_id (int): ID of the image
            thumbnail_path (str): Path to the thumbnail image (can be relative or absolute)
            max_size (tuple): Maximum size (width, height) for the thumbnail
            thumbnails_dir (str, optional): Directory where thumbnails are stored
        """
        super().__init__()
        self.image_id = image_id
        self.thumbnail_path = thumbnail_path
        self.max_size = max_size
        self.thumbnails_dir = thumbnails_dir
        self.signals = ThumbnailLoadSignals()
        
    @pyqtSlot()
    def run(self):
        """Run the thumbnail loading task."""
        try:
            # PORTABLE FIX: First check if we're running as an executable
            if getattr(sys, 'frozen', False):
                # Get the filename from the path
                thumbnail_filename = os.path.basename(self.thumbnail_path)
                
                # Construct the path to the portable thumbnails directory
                exe_dir = os.path.dirname(sys.executable)
                portable_thumbnails_dir = os.path.join(exe_dir, "data", "thumbnails")
                portable_path = os.path.join(portable_thumbnails_dir, thumbnail_filename)
                
                # Check if the thumbnail exists in the portable directory first
                if os.path.exists(portable_path):
                    logger.debug(f"Using portable thumbnail path: {portable_path}")
                    actual_path = portable_path
                # If not, continue with normal path resolution
                else:
                    # Handle relative paths by prepending the thumbnails directory
                    actual_path = self.thumbnail_path
                    if self.thumbnails_dir and not os.path.isabs(self.thumbnail_path):
                        actual_path = os.path.join(self.thumbnails_dir, self.thumbnail_path)
                    logger.debug(f"Portable path not found, using: {actual_path}")
            else:
                # DEV MODE: Use the exact same /data/thumbnails structure as portable mode
                # Get the filename from the path
                thumbnail_filename = os.path.basename(self.thumbnail_path)
                
                # First, check if the thumbnail is in the consistent data/thumbnails directory
                app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                dev_thumbnails_dir = os.path.join(app_dir, "data", "thumbnails")
                dev_path = os.path.join(dev_thumbnails_dir, thumbnail_filename)
                
                # Check if the thumbnail exists in the dev directory first 
                if os.path.exists(dev_path):
                    logger.debug(f"Using dev mode data/thumbnails path: {dev_path}")
                    actual_path = dev_path
                else:
                    # Fall back to the regular path resolution
                    actual_path = self.thumbnail_path
                    if self.thumbnails_dir and not os.path.isabs(self.thumbnail_path):
                        actual_path = os.path.join(self.thumbnails_dir, self.thumbnail_path)
                    logger.debug(f"Dev mode data/thumbnails path not found, falling back to: {actual_path}")
                
            # Log path information for debugging
            logger.debug(f"Loading thumbnail: ID={self.image_id}, Path={self.thumbnail_path}, Actual path={actual_path}")
            
            if not actual_path or not os.path.exists(actual_path):
                logger.warning(f"Thumbnail file not found: {actual_path} (original: {self.thumbnail_path})")
                self.signals.error.emit(self.image_id, "Thumbnail file not found")
                return
            
            # Load the image using a method that doesn't cause UI flickering
            # Use QImage first and then convert to QPixmap to prevent UI flicker
            img = QImage(actual_path)
            if img.isNull():
                self.signals.error.emit(self.image_id, "Failed to load thumbnail")
                return
            
            # Scale if needed using a simpler method that doesn't rely on Qt enums
            max_width, max_height = self.max_size
            if img.width() > max_width or img.height() > max_height:
                # Calculate the scaling factor to maintain aspect ratio
                width_ratio = max_width / img.width()
                height_ratio = max_height / img.height()
                scale_ratio = min(width_ratio, height_ratio)
                
                # Calculate new dimensions
                new_width = int(img.width() * scale_ratio)
                new_height = int(img.height() * scale_ratio)
                
                # Scale the image
                img = img.scaled(new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            # Convert to QPixmap only at the end
            pixmap = QPixmap.fromImage(img)
            
            # Emit the loaded pixmap
            self.signals.finished.emit(self.image_id, pixmap)
            
        except Exception as e:
            logger.error(f"Error loading thumbnail {self.image_id}: {str(e)}")
            self.signals.error.emit(self.image_id, str(e))

class LazyThumbnailLoader(QObject):
    """Manager for lazy loading thumbnails.
    
    Uses a multi-level caching system for efficient thumbnail access with 
    optimization for both memory and disk storage.
    """
    
    def __init__(self, max_concurrent=4, parent=None, config_manager=None, thumbnails_dir=None):
        """Initialize the lazy thumbnail loader.
        
        Args:
            max_concurrent (int): Maximum number of concurrent loading tasks
            parent (QObject, optional): Parent object
            config_manager: Configuration manager instance
        """
        super().__init__(parent)
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(max_concurrent)
        self.pending_tasks = {}  # image_id -> (thumbnail_path, callback)
        self.active_tasks = set()  # Set of image_ids currently being loaded
        self.load_timer = QTimer(self)
        self.load_timer.timeout.connect(self.process_pending_tasks)
        self.load_timer.start(50)  # Check for pending tasks every 50ms
        
        # CRITICAL FIX: Always use portable directory when running as executable to avoid temp directories
        if getattr(sys, 'frozen', False):
            # We're running as a PyInstaller executable
            # FORCE using the portable thumbnails directory regardless of other settings
            exe_dir = os.path.dirname(sys.executable)
            portable_thumbnails_dir = os.path.join(exe_dir, "data", "thumbnails")
            
            # Ensure the directory exists
            os.makedirs(portable_thumbnails_dir, exist_ok=True)
            
            self.thumbnails_dir = portable_thumbnails_dir
            logger.info(f"[PORTABLE MODE] Forcing use of portable thumbnails directory: {self.thumbnails_dir}")
        else:
            # For development mode, use the provided directory or get from config
            self.thumbnails_dir = thumbnails_dir
            # If no directory provided, try to get the default from config
            if self.thumbnails_dir is None and config_manager:
                thumb_path = config_manager.get("thumbnails", "path")
                if thumb_path:
                    self.thumbnails_dir = thumb_path
                    logger.info(f"Using configured thumbnails directory from config: {self.thumbnails_dir}")
                else:
                    # In script mode, use a path relative to the script
                    app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    self.thumbnails_dir = os.path.join(app_dir, "data", "thumbnails")
                    logger.info(f"Using script-relative thumbnails directory: {self.thumbnails_dir}")
        
        # Initialize the multi-level image cache
        self.image_cache = ImageCache(config_manager)
        
        # Cache parameters
        self.cache_size_limit = 100  # Maximum number of thumbnails in memory
        if config_manager:
            self.cache_size_limit = config_manager.get("cache", "thumbnail_memory_limit", 100)
        
        logger.info(f"LazyThumbnailLoader initialized with max_concurrent={max_concurrent} and cache_size_limit={self.cache_size_limit}")
    
    def queue_thumbnail(self, image_id, thumbnail_path, callback):
        """Queue a thumbnail for loading.
        
        Args:
            image_id (int): ID of the image
            thumbnail_path (str): Path to the thumbnail image
            callback (callable): Function to call with the loaded pixmap
        """
        # First check the multi-level cache
        pixmap = self.image_cache.get_thumbnail(image_id)
        if pixmap and not pixmap.isNull():
            # Found in cache, return immediately via callback
            QTimer.singleShot(0, lambda: callback(pixmap))
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
        task = ThumbnailLoadTask(image_id, thumbnail_path, thumbnails_dir=self.thumbnails_dir)
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
        
        # Add to multi-level cache
        if pixmap and not pixmap.isNull():
            self.image_cache.set_thumbnail(image_id, pixmap)
        
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
    
    def clear_cache(self):
        """Clear the thumbnail cache."""
        # Clear the multi-level image cache
        self.image_cache.clear()
    
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
