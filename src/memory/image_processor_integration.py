#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integration utilities for the memory pool image processor.
Allows seamless integration with existing image processing code.
"""

import logging
import os
from typing import Dict, List, Tuple, Optional, Union, Any

from src.config.config_manager import ConfigManager
from src.memory.memory_utils import get_image_processor, is_memory_pool_enabled
from src.image_processing.optimized_thumbnail_generator import OptimizedThumbnailGenerator

logger = logging.getLogger("StarImageBrowse.memory.image_processor_integration")

_thumbnail_generator = None

def get_thumbnail_generator(thumbnail_dir: str, size: Tuple[int, int] = (200, 200), config_manager=None) -> OptimizedThumbnailGenerator:
    """Get an optimized thumbnail generator instance.
    
    Args:
        thumbnail_dir (str): Directory to store thumbnails
        size (tuple): Thumbnail size (width, height)
        config_manager: Configuration manager instance
        
    Returns:
        OptimizedThumbnailGenerator: Thumbnail generator instance
    """
    global _thumbnail_generator
    
    if _thumbnail_generator is None:
        # Create a new thumbnail generator
        _thumbnail_generator = OptimizedThumbnailGenerator(thumbnail_dir, size, config_manager)
        logger.debug("Created optimized thumbnail generator")
    
    return _thumbnail_generator

def process_image_for_ai(image_path: str) -> Optional[str]:
    """Process an image for AI analysis with memory pooling if enabled.
    
    This function loads and potentially resizes an image for AI analysis,
    using memory pooling for optimal performance if it's enabled.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        str or None: Path to the processed image
    """
    if not os.path.exists(image_path):
        logger.error(f"Image file not found: {image_path}")
        return None
    
    try:
        # Get image processor
        if is_memory_pool_enabled():
            # Use memory pooled image processor
            image_processor = get_image_processor()
            
            # Load the image with memory pooling
            img, _ = image_processor.load_image(image_path)
            
            # Process for AI analysis (resize if needed, convert formats, etc.)
            max_dimension = 1024  # Maximum dimension for AI processing
            
            if img.width > max_dimension or img.height > max_dimension:
                # Resize while maintaining aspect ratio
                img = image_processor.process_image(img, [
                    {
                        'type': 'resize',
                        'width': max_dimension if img.width > img.height else int(max_dimension * img.width / img.height),
                        'height': max_dimension if img.height > img.width else int(max_dimension * img.height / img.width),
                        'method': 'lanczos'
                    }
                ])
            
            # Create a temporary file for the processed image
            temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            basename = os.path.basename(image_path)
            processed_path = os.path.join(temp_dir, f"ai_ready_{basename}")
            
            # Save the processed image
            image_processor.save_image(img, processed_path)
            
            return processed_path
            
        else:
            # Use standard PIL processing
            from PIL import Image
            
            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                
                # Resize if needed
                max_dimension = 1024  # Maximum dimension for AI processing
                
                if img.width > max_dimension or img.height > max_dimension:
                    # Calculate new dimensions
                    if img.width > img.height:
                        new_width = max_dimension
                        new_height = int(max_dimension * img.height / img.width)
                    else:
                        new_height = max_dimension
                        new_width = int(max_dimension * img.width / img.height)
                    
                    # Resize the image
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Create a temporary file for the processed image
                temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "temp")
                os.makedirs(temp_dir, exist_ok=True)
                
                basename = os.path.basename(image_path)
                processed_path = os.path.join(temp_dir, f"ai_ready_{basename}")
                
                # Save the processed image
                img.save(processed_path)
                
                return processed_path
            
    except Exception as e:
        logger.error(f"Error processing image for AI: {e}")
        return None

def batch_process_images_for_ai(image_paths: List[str]) -> Dict[str, str]:
    """Process multiple images for AI analysis with memory pooling.
    
    Args:
        image_paths (list): List of paths to image files
        
    Returns:
        dict: Dictionary mapping original paths to processed paths
    """
    results = {}
    
    if is_memory_pool_enabled():
        # Use memory pooled image processor for batch processing
        image_processor = get_image_processor()
        
        # Prepare temporary directory
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Define the operations
        operations = [
            {
                'type': 'resize',
                'width': 1024,
                'height': 1024,
                'method': 'lanczos'
            }
        ]
        
        # Process images in batch
        processed_images = image_processor.batch_process_images(image_paths, operations)
        
        # Save processed images
        for original_path, processed_img in processed_images.items():
            if processed_img:
                basename = os.path.basename(original_path)
                processed_path = os.path.join(temp_dir, f"ai_ready_{basename}")
                
                # Save the processed image
                if image_processor.save_image(processed_img, processed_path):
                    results[original_path] = processed_path
                else:
                    results[original_path] = None
            else:
                results[original_path] = None
    else:
        # Process individually with standard PIL
        for path in image_paths:
            processed_path = process_image_for_ai(path)
            results[path] = processed_path
    
    return results
