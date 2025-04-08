#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Memory-optimized image processor for StarImageBrowse.
Provides efficient image processing operations using memory pooling.
"""

import os
import time
import logging
import threading
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, QByteArray, QBuffer, QIODevice
from typing import Dict, List, Tuple, Optional, Union, Any, Callable

from .memory_pool import MemoryPool, ImageBuffer

logger = logging.getLogger("StarImageBrowse.memory.image_processor_pool")

class ImageProcessorPool:
    """Image processor that uses memory pooling for efficient operations."""
    
    def __init__(self, config_manager=None):
        """Initialize the image processor pool.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.memory_pool = MemoryPool(config_manager)
        self.image_buffer = ImageBuffer(self.memory_pool)
        self.lock = threading.RLock()
        
        # Track current operations for resource management
        self.active_operations = {}
        
        # Initialize default processing parameters
        self.thumbnail_size = (200, 200)
        self.jpeg_quality = 85
        
        # Load configuration if available
        if config_manager:
            self.thumbnail_size = (
                config_manager.get("thumbnails", "size", 200),
                config_manager.get("thumbnails", "size", 200)
            )
            self.jpeg_quality = config_manager.get("thumbnails", "quality", 85)
        
        logger.info(f"Image processor pool initialized with thumbnail size {self.thumbnail_size}")
    
    def load_image(self, file_path: str) -> Tuple[Image.Image, Dict]:
        """Load an image file with memory pooling.
        
        Args:
            file_path (str): Path to the image file
            
        Returns:
            tuple: (PIL.Image, metadata_dict)
        """
        try:
            # Open image with PIL
            with Image.open(file_path) as img:
                # Get metadata before processing
                metadata = self._extract_metadata(img, file_path)
                
                # Convert to RGB/RGBA if needed
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGBA')
                
                # Get a pooled buffer for the image
                buffer_id, buffer, release_fn = self.image_buffer.get_buffer_for_pil_image(img)
                
                # Copy image data into the buffer
                np.copyto(buffer, np.array(img))
                
                # Create a new PIL image from the buffer
                pooled_img = Image.fromarray(buffer)
                
                # Register cleanup function
                operation_id = f"load_{os.path.basename(file_path)}_{time.time()}"
                self.active_operations[operation_id] = {
                    "buffer_id": buffer_id,
                    "release_fn": release_fn,
                    "start_time": time.time()
                }
                
                return pooled_img, metadata
        
        except Exception as e:
            logger.error(f"Error loading image {file_path}: {e}")
            # Fall back to standard loading if pooled loading fails
            try:
                img = Image.open(file_path)
                metadata = self._extract_metadata(img, file_path)
                return img, metadata
            except Exception as e2:
                logger.error(f"Fallback loading also failed for {file_path}: {e2}")
                raise
    
    def _extract_metadata(self, img: Image.Image, file_path: str) -> Dict:
        """Extract metadata from the image.
        
        Args:
            img (PIL.Image): Image to extract metadata from
            file_path (str): Path to the image file
            
        Returns:
            dict: Metadata dictionary
        """
        metadata = {
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "format": img.format,
            "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0
        }
        
        # Extract EXIF data if available
        try:
            exif = img.getexif()
            if exif:
                # Get common EXIF tags
                for tag_id in (271, 272, 274, 305, 306, 36867, 36868):  # Common EXIF tags
                    if tag_id in exif:
                        metadata[f"exif_{tag_id}"] = str(exif[tag_id])
        except Exception as e:
            logger.debug(f"Error extracting EXIF from {file_path}: {e}")
        
        return metadata
    
    def create_thumbnail(self, image: Union[Image.Image, str], size: Optional[Tuple[int, int]] = None) -> QPixmap:
        """Create a thumbnail from an image with memory pooling.
        
        Args:
            image (PIL.Image or str): Image or path to image file
            size (tuple, optional): Thumbnail size (width, height)
            
        Returns:
            QPixmap: Thumbnail pixmap
        """
        try:
            # Use default size if not specified
            if size is None:
                size = self.thumbnail_size
            
            # Load the image if a path was provided
            if isinstance(image, str):
                img, _ = self.load_image(image)
            else:
                img = image
            
            # Create a unique operation ID
            operation_id = f"thumbnail_{id(image)}_{time.time()}"
            
            # Calculate size while preserving aspect ratio
            img_ratio = img.width / img.height
            target_ratio = size[0] / size[1]
            
            if img_ratio > target_ratio:
                # Image is wider than thumbnail
                thumb_width = size[0]
                thumb_height = int(thumb_width / img_ratio)
            else:
                # Image is taller than thumbnail
                thumb_height = size[1]
                thumb_width = int(thumb_height * img_ratio)
            
            # Get a buffer for the thumbnail
            buffer_id, buffer, release_fn = self.image_buffer.get_buffer_for_image(
                thumb_width, thumb_height, 4 if img.mode == 'RGBA' else 3
            )
            
            # Store the operation
            self.active_operations[operation_id] = {
                "buffer_id": buffer_id,
                "release_fn": release_fn,
                "start_time": time.time()
            }
            
            # Resize the image into our buffer
            thumbnail = img.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
            np.copyto(buffer, np.array(thumbnail))
            
            # Convert numpy array to QPixmap
            if buffer.shape[2] == 3:
                # RGB format
                qimg = QImage(
                    buffer.tobytes(),
                    thumb_width, thumb_height,
                    thumb_width * 3,
                    QImage.Format.Format_RGB888
                )
            else:
                # RGBA format
                qimg = QImage(
                    buffer.tobytes(),
                    thumb_width, thumb_height,
                    thumb_width * 4,
                    QImage.Format.Format_RGBA8888
                )
            
            # Convert to QPixmap
            pixmap = QPixmap.fromImage(qimg)
            
            # Release the buffer
            self._cleanup_operation(operation_id)
            
            return pixmap
        
        except Exception as e:
            logger.error(f"Error creating thumbnail: {e}")
            # Fall back to standard thumbnail creation
            try:
                if isinstance(image, str):
                    img = Image.open(image)
                else:
                    img = image
                
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                if img.mode == "RGBA":
                    format = QImage.Format.Format_RGBA8888
                else:
                    format = QImage.Format.Format_RGB888
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                
                # Convert to QPixmap
                img_data = img.tobytes("raw", img.mode)
                qimg = QImage(
                    img_data, img.width, img.height, 
                    img.width * (4 if img.mode == "RGBA" else 3),
                    format
                )
                return QPixmap.fromImage(qimg)
            except Exception as e2:
                logger.error(f"Fallback thumbnail creation also failed: {e2}")
                # Return an empty pixmap
                return QPixmap()
    
    def batch_create_thumbnails(self, image_paths: List[str], size: Optional[Tuple[int, int]] = None) -> Dict[str, QPixmap]:
        """Create thumbnails for multiple images using memory pooling.
        
        Args:
            image_paths (list): List of image file paths
            size (tuple, optional): Thumbnail size (width, height)
            
        Returns:
            dict: Dictionary mapping image paths to thumbnails
        """
        results = {}
        operation_id = f"batch_thumbnails_{time.time()}"
        
        try:
            # Use default size if not specified
            if size is None:
                size = self.thumbnail_size
            
            # Process each image
            for path in image_paths:
                try:
                    pixmap = self.create_thumbnail(path, size)
                    results[path] = pixmap
                except Exception as e:
                    logger.error(f"Error creating thumbnail for {path}: {e}")
                    results[path] = QPixmap()
            
            return results
        
        finally:
            # Clean up any lingering operations
            self._cleanup_operation(operation_id)
    
    def process_image(self, image: Union[Image.Image, str], operations: List[Dict]) -> Image.Image:
        """Process an image with a series of operations using memory pooling.
        
        Args:
            image (PIL.Image or str): Image or path to image file
            operations (list): List of operation dictionaries
                Each operation dict should have:
                - 'type': Operation type (resize, crop, rotate, etc.)
                - Additional parameters specific to the operation
            
        Returns:
            PIL.Image: Processed image
        """
        try:
            # Load the image if a path was provided
            if isinstance(image, str):
                img, _ = self.load_image(image)
            else:
                img = image
            
            # Create a unique operation ID
            operation_id = f"process_{id(image)}_{time.time()}"
            
            # Get a buffer for the image
            buffer_id, buffer, release_fn = self.image_buffer.get_buffer_for_pil_image(img)
            
            # Copy image data to buffer
            np.copyto(buffer, np.array(img))
            
            # Create PIL image from buffer
            processed_img = Image.fromarray(buffer)
            
            # Store the operation
            self.active_operations[operation_id] = {
                "buffer_id": buffer_id,
                "release_fn": release_fn,
                "start_time": time.time()
            }
            
            # Apply each operation
            for op in operations:
                op_type = op.get('type', '').lower()
                
                if op_type == 'resize':
                    width = op.get('width', processed_img.width)
                    height = op.get('height', processed_img.height)
                    method = op.get('method', 'lanczos')
                    
                    # Map method name to PIL resampling filter
                    resampling = {
                        'nearest': Image.Resampling.NEAREST,
                        'bilinear': Image.Resampling.BILINEAR,
                        'bicubic': Image.Resampling.BICUBIC,
                        'lanczos': Image.Resampling.LANCZOS
                    }.get(method, Image.Resampling.LANCZOS)
                    
                    processed_img = processed_img.resize((width, height), resampling)
                
                elif op_type == 'crop':
                    left = op.get('left', 0)
                    top = op.get('top', 0)
                    right = op.get('right', processed_img.width)
                    bottom = op.get('bottom', processed_img.height)
                    processed_img = processed_img.crop((left, top, right, bottom))
                
                elif op_type == 'rotate':
                    angle = op.get('angle', 0)
                    expand = op.get('expand', False)
                    processed_img = processed_img.rotate(angle, expand=expand)
                
                elif op_type == 'flip':
                    horizontal = op.get('horizontal', False)
                    vertical = op.get('vertical', False)
                    
                    if horizontal:
                        processed_img = ImageOps.mirror(processed_img)
                    if vertical:
                        processed_img = ImageOps.flip(processed_img)
                
                elif op_type == 'adjust':
                    brightness = op.get('brightness', 1.0)
                    contrast = op.get('contrast', 1.0)
                    saturation = op.get('saturation', 1.0)
                    
                    if brightness != 1.0:
                        processed_img = ImageEnhance.Brightness(processed_img).enhance(brightness)
                    if contrast != 1.0:
                        processed_img = ImageEnhance.Contrast(processed_img).enhance(contrast)
                    if saturation != 1.0:
                        processed_img = ImageEnhance.Color(processed_img).enhance(saturation)
                
                elif op_type == 'filter':
                    filter_type = op.get('filter', 'blur')
                    
                    if filter_type == 'blur':
                        radius = op.get('radius', 2)
                        processed_img = processed_img.filter(ImageFilter.GaussianBlur(radius))
                    elif filter_type == 'sharpen':
                        processed_img = processed_img.filter(ImageFilter.SHARPEN)
                    elif filter_type == 'edge_enhance':
                        processed_img = processed_img.filter(ImageFilter.EDGE_ENHANCE)
            
            # Return the processed image
            return processed_img
        
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            # Return the original image
            if isinstance(image, str):
                return Image.open(image)
            else:
                return image
        
        finally:
            # Clean up operation
            self._cleanup_operation(operation_id)
    
    def batch_process_images(self, image_paths: List[str], operations: List[Dict]) -> Dict[str, Image.Image]:
        """Process multiple images with the same operations using memory pooling.
        
        Args:
            image_paths (list): List of image file paths
            operations (list): List of operation dictionaries
                Each operation dict should have:
                - 'type': Operation type (resize, crop, rotate, etc.)
                - Additional parameters specific to the operation
            
        Returns:
            dict: Dictionary mapping image paths to processed images
        """
        results = {}
        operation_id = f"batch_process_{time.time()}"
        
        try:
            # Process each image
            for path in image_paths:
                try:
                    processed = self.process_image(path, operations)
                    results[path] = processed
                except Exception as e:
                    logger.error(f"Error processing image {path}: {e}")
                    # Add original image to results on error
                    try:
                        results[path] = Image.open(path)
                    except:
                        # If we can't even open the image, add None
                        results[path] = None
            
            return results
        
        finally:
            # Clean up any lingering operations
            self._cleanup_operation(operation_id)
    
    def save_image(self, image: Image.Image, output_path: str, format: Optional[str] = None, quality: Optional[int] = None) -> bool:
        """Save an image to a file with optimized memory usage.
        
        Args:
            image (PIL.Image): Image to save
            output_path (str): Path to save the image to
            format (str, optional): Format to save as (jpg, png, etc.)
            quality (int, optional): JPEG quality (1-100)
            
        Returns:
            bool: True if successful
        """
        try:
            # Use format from path if not specified
            if format is None:
                format = os.path.splitext(output_path)[1].strip('.').upper()
                if not format:
                    format = 'JPEG'
            
            # Use default quality if not specified
            if quality is None and format.upper() in ('JPEG', 'JPG'):
                quality = self.jpeg_quality
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # Save the image
            image.save(output_path, format=format, quality=quality)
            return True
        
        except Exception as e:
            logger.error(f"Error saving image to {output_path}: {e}")
            return False
    
    def _cleanup_operation(self, operation_id):
        """Clean up resources for a completed operation.
        
        Args:
            operation_id (str): ID of the operation to clean up
        """
        with self.lock:
            if operation_id in self.active_operations:
                try:
                    # Get operation info
                    info = self.active_operations.pop(operation_id)
                    
                    # Release the buffer
                    if "release_fn" in info:
                        info["release_fn"]()
                    
                except Exception as e:
                    logger.error(f"Error cleaning up operation {operation_id}: {e}")
    
    def cleanup_old_operations(self, max_age_seconds=300):
        """Clean up operations older than the specified age.
        
        Args:
            max_age_seconds (int): Maximum age in seconds
            
        Returns:
            int: Number of operations cleaned up
        """
        with self.lock:
            now = time.time()
            to_cleanup = []
            
            # Find old operations
            for op_id, info in self.active_operations.items():
                if now - info.get("start_time", 0) > max_age_seconds:
                    to_cleanup.append(op_id)
            
            # Clean up each operation
            for op_id in to_cleanup:
                self._cleanup_operation(op_id)
            
            return len(to_cleanup)
    
    def get_memory_stats(self):
        """Get memory usage statistics.
        
        Returns:
            dict: Memory statistics
        """
        with self.lock:
            stats = self.memory_pool.get_stats()
            stats["active_operations"] = len(self.active_operations)
            stats["active_buffers"] = self.image_buffer.get_active_buffer_count()
            return stats
