#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Optimized thumbnail generator for StarImageBrowse
Uses memory pooling for efficient thumbnail generation.
"""

import os
import time
import logging
from PIL import Image, UnidentifiedImageError
from PyQt6.QtGui import QPixmap
from typing import Dict, Tuple, Optional, List, Union

from src.memory.memory_pool import MemoryPool
from src.memory.image_processor_pool import ImageProcessorPool

logger = logging.getLogger("StarImageBrowse.image_processing.optimized_thumbnail_generator")

class OptimizedThumbnailGenerator:
    """Generates thumbnails with optimized memory usage using memory pooling."""
    
    def __init__(self, thumbnail_dir: str, size: Tuple[int, int] = (200, 200), config_manager=None):
        """Initialize the optimized thumbnail generator.
        
        Args:
            thumbnail_dir (str): Directory to store thumbnails
            size (tuple): Thumbnail size (width, height)
            config_manager: Configuration manager instance
        """
        self.thumbnail_dir = thumbnail_dir
        self.size = size
        self.config_manager = config_manager
        
        # Create thumbnail directory if it doesn't exist
        os.makedirs(self.thumbnail_dir, exist_ok=True)
        
        # Initialize image processor pool
        self.image_processor = ImageProcessorPool(config_manager)
        
        # Load configuration
        self.quality = 85
        if config_manager:
            self.quality = config_manager.get("thumbnails", "quality", 85)
            self.enable_memory_pool = config_manager.get("memory", "enable_memory_pool", True)
        else:
            self.enable_memory_pool = True
        
        logger.info(f"Optimized thumbnail generator initialized with size={size}, quality={self.quality}")
    
    def get_thumbnail_path(self, image_path: str) -> str:
        """Get the path where a thumbnail should be stored.
        
        Args:
            image_path (str): Path to the original image
            
        Returns:
            str: Path where the thumbnail should be stored
        """
        # Create a filename based on the original filename
        # We use the absolute path to ensure uniqueness
        abs_path = os.path.abspath(image_path)
        base_name = os.path.splitext(os.path.basename(abs_path))[0]
        return os.path.join(self.thumbnail_dir, f"{base_name}_thumb.jpg")
    
    def thumbnail_exists(self, image_path: str) -> bool:
        """Check if a thumbnail already exists for the image.
        
        Args:
            image_path (str): Path to the original image
            
        Returns:
            bool: True if the thumbnail exists
        """
        thumb_path = self.get_thumbnail_path(image_path)
        return os.path.exists(thumb_path)
    
    def generate_thumbnail(self, image_path: str, force: bool = False) -> Optional[str]:
        """Generate a thumbnail for an image.
        
        Args:
            image_path (str): Path to the original image
            force (bool): If True, regenerate the thumbnail even if it exists
            
        Returns:
            str or None: Path to the thumbnail or None if generation failed
        """
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return None
        
        thumb_path = self.get_thumbnail_path(image_path)
        
        # Check if thumbnail already exists
        if not force and os.path.exists(thumb_path):
            return thumb_path
        
        try:
            # Use memory pooling if enabled
            if self.enable_memory_pool:
                # Use the image processor pool to create the thumbnail
                # Generate the thumbnail
                thumbnail = self.image_processor.process_image(image_path, [
                    {
                        'type': 'resize',
                        'width': self.size[0],
                        'height': self.size[1],
                        'method': 'lanczos'
                    }
                ])
                
                # Save the thumbnail
                self.image_processor.save_image(thumbnail, thumb_path, format='JPEG', quality=self.quality)
            else:
                # Fall back to standard PIL thumbnail generation
                with Image.open(image_path) as img:
                    # Convert to RGB if needed
                    if img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGB')
                    
                    # Create a copy to avoid modifying the original
                    thumb = img.copy()
                    thumb.thumbnail(self.size, Image.Resampling.LANCZOS)
                    
                    # Save thumbnail
                    thumb.save(thumb_path, 'JPEG', quality=self.quality)
            
            return thumb_path
            
        except Exception as e:
            logger.error(f"Error generating thumbnail for {image_path}: {e}")
            return None
    
    def batch_generate_thumbnails(self, image_paths: List[str], force: bool = False) -> Dict[str, str]:
        """Generate thumbnails for multiple images in batch mode.
        
        Args:
            image_paths (list): List of paths to original images
            force (bool): If True, regenerate thumbnails even if they exist
            
        Returns:
            dict: Dictionary mapping original paths to thumbnail paths
        """
        results = {}
        paths_to_process = []
        
        # First, check which thumbnails need to be generated
        for path in image_paths:
            thumb_path = self.get_thumbnail_path(path)
            
            if not force and os.path.exists(thumb_path):
                # Thumbnail already exists
                results[path] = thumb_path
            elif os.path.exists(path):
                # Need to generate this thumbnail
                paths_to_process.append(path)
            else:
                # Original image doesn't exist
                logger.error(f"Image file not found: {path}")
                results[path] = None
        
        # Generate thumbnails for images that need processing
        if paths_to_process:
            try:
                if self.enable_memory_pool:
                    # Use memory pooling for batch processing
                    for path in paths_to_process:
                        thumb_path = self.get_thumbnail_path(path)
                        
                        # Use the image processor to create and save the thumbnail
                        thumbnail = self.image_processor.process_image(path, [
                            {
                                'type': 'resize',
                                'width': self.size[0],
                                'height': self.size[1],
                                'method': 'lanczos'
                            }
                        ])
                        
                        if thumbnail:
                            self.image_processor.save_image(thumbnail, thumb_path, format='JPEG', quality=self.quality)
                            results[path] = thumb_path
                        else:
                            results[path] = None
                else:
                    # Standard batch processing without memory pooling
                    for path in paths_to_process:
                        results[path] = self.generate_thumbnail(path, force=force)
            
            except Exception as e:
                logger.error(f"Error in batch thumbnail generation: {e}")
                # Fill in missing results
                for path in paths_to_process:
                    if path not in results:
                        results[path] = None
        
        return results
    
    def load_thumbnail_pixmap(self, image_path: str) -> Optional[QPixmap]:
        """Load a thumbnail as a QPixmap.
        
        Args:
            image_path (str): Path to the original image
            
        Returns:
            QPixmap or None: Thumbnail pixmap or None if loading failed
        """
        # Generate the thumbnail if it doesn't exist
        thumb_path = self.generate_thumbnail(image_path)
        
        if not thumb_path or not os.path.exists(thumb_path):
            logger.error(f"Thumbnail not found for {image_path}")
            return None
        
        try:
            # Use memory pooling to load the thumbnail if enabled
            if self.enable_memory_pool:
                return self.image_processor.create_thumbnail(thumb_path, self.size)
            else:
                # Standard pixmap loading
                return QPixmap(thumb_path)
                
        except Exception as e:
            logger.error(f"Error loading thumbnail pixmap for {image_path}: {e}")
            return None
    
    def batch_load_thumbnail_pixmaps(self, image_paths: List[str]) -> Dict[str, QPixmap]:
        """Load multiple thumbnails as QPixmaps in batch mode.
        
        Args:
            image_paths (list): List of paths to original images
            
        Returns:
            dict: Dictionary mapping original paths to thumbnail pixmaps
        """
        results = {}
        
        # First, generate any missing thumbnails
        thumbnail_paths = self.batch_generate_thumbnails(image_paths)
        
        # Then load the pixmaps
        if self.enable_memory_pool:
            # Use memory pooling for batch loading
            paths_to_load = [thumbnail_paths[path] for path in image_paths if path in thumbnail_paths and thumbnail_paths[path]]
            
            # Load thumbnails in batch
            if paths_to_load:
                pixmaps = self.image_processor.batch_create_thumbnails(paths_to_load, self.size)
                
                # Map back to original paths
                for original_path, thumb_path in thumbnail_paths.items():
                    if thumb_path in pixmaps:
                        results[original_path] = pixmaps[thumb_path]
                    else:
                        results[original_path] = None
        else:
            # Standard loading without memory pooling
            for path in image_paths:
                if path in thumbnail_paths and thumbnail_paths[path]:
                    try:
                        results[path] = QPixmap(thumbnail_paths[path])
                    except Exception as e:
                        logger.error(f"Error loading thumbnail pixmap for {path}: {e}")
                        results[path] = None
                else:
                    results[path] = None
        
        return results
    
    def cleanup(self):
        """Clean up resources."""
        # Clean up the image processor pool
        if hasattr(self, 'image_processor'):
            self.image_processor.cleanup_old_operations()
    
    def __del__(self):
        """Clean up resources when the object is deleted."""
        self.cleanup()
