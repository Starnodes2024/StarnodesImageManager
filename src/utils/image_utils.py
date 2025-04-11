#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Image utility functions for StarImageBrowse.
Provides functions for working with image files.
"""

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger("StarImageBrowse.utils.image_utils")

def is_supported_image(file_path):
    """Check if a file is a supported image format.
    
    Args:
        file_path (str): Path to the file to check
        
    Returns:
        bool: True if the file is a supported image format, False otherwise
    """
    if not os.path.isfile(file_path):
        return False
        
    # Get file extension in lowercase
    ext = Path(file_path).suffix.lower()
    
    # List of supported image formats
    supported_formats = [
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp'
    ]
    
    return ext in supported_formats

def get_image_dimensions(file_path):
    """Get the dimensions of an image.
    
    Args:
        file_path (str): Path to the image file
        
    Returns:
        tuple: (width, height) or None if not an image or error occurs
    """
    try:
        from PIL import Image
        
        if not is_supported_image(file_path):
            return None
            
        with Image.open(file_path) as img:
            return img.size
    except Exception as e:
        logger.error(f"Error getting image dimensions for {file_path}: {e}")
        return None

def format_dimension_string(dimensions):
    """Format image dimensions as a string.
    
    Args:
        dimensions (tuple): (width, height) tuple
        
    Returns:
        str: Formatted dimensions string (e.g., "1024x768")
    """
    if not dimensions or len(dimensions) != 2:
        return "Unknown"
        
    width, height = dimensions
    return f"{width}x{height}"

def extract_comfyui_workflow(image_path, output_json_path=None):
    """Extract ComfyUI workflow data from an image and save it as a JSON file.
    
    Args:
        image_path (str): Path to the image file
        output_json_path (str, optional): Path to save the JSON file. If None, uses image_path + "_workflow.json"
        
    Returns:
        tuple: (success, message, output_path) where:
            success (bool): True if workflow was extracted successfully
            message (str): Success or error message
            output_path (str): Path to the saved JSON file or None if failed
    """
    try:
        from PIL import Image
        
        # Open the image
        img = Image.open(image_path)
        
        # Check if workflow data exists
        if "workflow" in img.info:
            workflow_data = img.info["workflow"]
            
            # If no output path specified, use image path as base
            if output_json_path is None:
                output_json_path = os.path.splitext(image_path)[0] + "_workflow.json"
            
            # Save workflow as JSON file
            with open(output_json_path, "w") as f:
                f.write(workflow_data)
            
            logger.info(f"ComfyUI workflow extracted to {output_json_path}")
            return True, "Workflow extracted successfully", output_json_path
        else:
            logger.info(f"No ComfyUI workflow data found in image: {image_path}")
            return False, "No workflow data found in image", None
    except Exception as e:
        error_msg = f"Error extracting workflow from {image_path}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, None



