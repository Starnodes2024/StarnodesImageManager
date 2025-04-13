#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Thumbnail generator for StarImageBrowse
Handles the creation and management of image thumbnails.
"""

import os
import sys
import logging
import hashlib
from pathlib import Path
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger("StarImageBrowse.image_processing")

class ThumbnailGenerator:
    """Generates and manages image thumbnails."""
    
    def __init__(self, thumbnail_dir, size=(200, 200)):
        """Initialize the thumbnail generator.
        
        Args:
            thumbnail_dir (str): Directory to store thumbnails
            size (tuple): Thumbnail size (width, height)
        """
        self.thumbnail_dir = thumbnail_dir
        self.size = size
        
        # Log information about the thumbnail directory
        logger.info(f"Thumbnail generator initialized with directory: {thumbnail_dir} and size: {size}")
        
        # Check if we're in portable mode and adapt paths if needed
        if getattr(sys, 'frozen', False):
            # We're running in portable mode
            logger.info("Running in portable mode - checking thumbnail directories")
            
            # Check if the provided path exists
            if os.path.exists(thumbnail_dir):
                logger.info(f"Using provided thumbnail directory: {thumbnail_dir}")
            else:
                # Try to find the correct portable path
                exe_dir = os.path.dirname(sys.executable)
                possible_dirs = [
                    os.path.join(exe_dir, "data", "thumbnails"),
                    os.path.join(exe_dir, "thumbnails")
                ]
                
                for possible_dir in possible_dirs:
                    if os.path.exists(possible_dir):
                        logger.info(f"Found alternative thumbnail directory: {possible_dir}")
                        self.thumbnail_dir = possible_dir
                        break
        
        # Ensure the thumbnail directory exists
        os.makedirs(self.thumbnail_dir, exist_ok=True)
        logger.info(f"Created/verified thumbnail directory: {self.thumbnail_dir}")
    
    def get_thumbnail_path(self, image_path):
        """Get the relative path for a thumbnail based on the original image path.
        
        Args:
            image_path (str): Path to the original image
            
        Returns:
            str: Relative path where the thumbnail should be stored (just the filename)
        """
        # Create a unique filename for the thumbnail
        image_hash = hashlib.md5(image_path.encode()).hexdigest()
        image_ext = os.path.splitext(image_path)[1].lower()
        
        # Always use .jpg for thumbnails to save space
        thumbnail_filename = f"{image_hash}.jpg"
        
        # Return just the filename as a relative path
        return thumbnail_filename
        
    def get_absolute_thumbnail_path(self, image_path):
        """Get the absolute path for a thumbnail based on the original image path.
        
        Args:
            image_path (str): Path to the original image or thumbnail filename
            
        Returns:
            str: Absolute path where the thumbnail is stored
        """
        # Log the input path for debugging
        logger.debug(f"Getting absolute path for thumbnail: {image_path}")
        
        # Check if this is already an absolute path to a thumbnail file
        if os.path.isabs(image_path) and os.path.exists(image_path) and image_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            logger.debug(f"Using provided absolute path directly: {image_path}")
            return image_path
            
        if os.path.dirname(image_path):
            # This is a full image path, get the thumbnail filename first
            thumbnail_filename = self.get_thumbnail_path(image_path)
            logger.debug(f"Generated thumbnail filename from image path: {thumbnail_filename}")
        else:
            # This is already just a filename
            thumbnail_filename = image_path
            logger.debug(f"Using provided filename: {thumbnail_filename}")
        
        # First try the standard thumbnail directory
        thumbnail_path = os.path.join(self.thumbnail_dir, thumbnail_filename)
        logger.debug(f"Constructed absolute thumbnail path: {thumbnail_path}")
        
        # Check if the file exists at the constructed path
        if os.path.exists(thumbnail_path):
            logger.debug(f"Thumbnail exists at: {thumbnail_path}")
            return thumbnail_path
        
        # If running in portable mode, try an alternative path structure
        if getattr(sys, 'frozen', False):
            # Check if there's a 'thumbnails' directory in the executable directory
            exe_dir = os.path.dirname(sys.executable)
            alt_thumbnails_dir = os.path.join(exe_dir, "thumbnails")
            if os.path.exists(alt_thumbnails_dir):
                alt_path = os.path.join(alt_thumbnails_dir, thumbnail_filename)
                if os.path.exists(alt_path):
                    logger.debug(f"Found thumbnail in alternative location: {alt_path}")
                    return alt_path
            
            # Another possibility: thumbnails directly in data folder
            data_thumbnails_dir = os.path.join(exe_dir, "data", "thumbnails")
            if os.path.exists(data_thumbnails_dir):
                data_path = os.path.join(data_thumbnails_dir, thumbnail_filename)
                if os.path.exists(data_path):
                    logger.debug(f"Found thumbnail in data directory: {data_path}")
                    return data_path
        
        # Return the standard path even if it doesn't exist yet
        # It will be used when generating the thumbnail
        return thumbnail_path
    
    def generate_thumbnail(self, image_path, force=False, target_format=None):
        """Generate a thumbnail for the given image.
        
        Args:
            image_path (str): Path to the original image
            force (bool): If True, regenerate thumbnail even if it exists
            target_format (str, optional): Target format for the thumbnail ('JPEG', 'PNG', 'WebP')
            
        Returns:
            str: Path to the generated thumbnail, or None if generation failed
        """
        if not os.path.exists(image_path):
            logger.warning(f"Image not found: {image_path}")
            return None
        
        # Check file size
        try:
            file_size = os.path.getsize(image_path)
            if file_size == 0:
                logger.warning(f"Empty file (0 bytes): {image_path}")
                return None
            elif file_size > 100 * 1024 * 1024:  # 100MB
                logger.warning(f"File too large ({file_size / (1024*1024):.1f} MB): {image_path}")
                # We'll still try to process it, but log the warning
        except OSError as e:
            logger.error(f"Error getting file size for {image_path}: {e}")
            return None
        
        # Get the relative path for storage in the database
        thumbnail_path = self.get_thumbnail_path(image_path)
        
        # CRITICAL FIX: If we're running as frozen executable, force using the portable directory
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Get the executable directory
            exe_dir = os.path.dirname(sys.executable)
            portable_thumbnails_dir = os.path.join(exe_dir, "data", "thumbnails")
            
            # Ensure portable directory exists
            os.makedirs(portable_thumbnails_dir, exist_ok=True)
            
            # If our current directory is the PyInstaller temp dir, override it
            if sys._MEIPASS in self.thumbnail_dir:
                logger.warning(f"FIXING: Redirecting from PyInstaller temp path: {self.thumbnail_dir}")
                logger.warning(f"FIXING: Using portable path instead: {portable_thumbnails_dir}")
                # Update the instance variable to use our portable directory
                self.thumbnail_dir = portable_thumbnails_dir
                
        # Get the absolute path for file operations
        absolute_thumbnail_path = os.path.join(self.thumbnail_dir, thumbnail_path)
        
        # Log the path we're using
        logger.debug(f"Generating thumbnail at: {absolute_thumbnail_path}")
        
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(absolute_thumbnail_path), exist_ok=True)
        
        # Check if thumbnail already exists
        if os.path.exists(absolute_thumbnail_path) and not force:
            # Check if the original image is newer than the thumbnail
            if os.path.getmtime(image_path) <= os.path.getmtime(absolute_thumbnail_path):
                logger.debug(f"Thumbnail already exists and is up to date: {absolute_thumbnail_path}")
                return thumbnail_path
        
        try:
            # Open the image
            with Image.open(image_path) as img:
                # Log image format and mode for debugging
                logger.debug(f"Processing image: {image_path}, format: {img.format}, mode: {img.mode}, size: {img.size}")
                
                # Handle different image modes
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    # Create a white background for images with transparency
                    logger.debug(f"Converting transparent image to RGB: {image_path}")
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    
                    # Paste the image on the background if it has alpha
                    try:
                        if img.mode == 'RGBA':
                            background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
                        elif img.mode == 'LA':
                            background.paste(img, mask=img.split()[1])  # 1 is the alpha channel
                        elif img.mode == 'P' and 'transparency' in img.info:
                            background.paste(img, mask=img.convert('RGBA').split()[3])
                        img = background
                    except Exception as e:
                        logger.warning(f"Error handling transparency in {image_path}: {e}")
                        # Fall back to simple conversion
                        img = img.convert('RGB')
                elif img.mode != 'RGB':
                    logger.debug(f"Converting image from {img.mode} to RGB: {image_path}")
                    img = img.convert('RGB')
                
                # Create a proportional thumbnail
                try:
                    img.thumbnail(self.size, Image.Resampling.LANCZOS)
                except Exception as e:
                    logger.warning(f"Error using LANCZOS resampling for {image_path}: {e}")
                    # Fall back to simpler resampling method
                    try:
                        img.thumbnail(self.size, Image.Resampling.NEAREST)
                    except Exception as e2:
                        logger.error(f"Error creating thumbnail with fallback method: {e2}")
                        return None
                
                # Save the thumbnail in the specified format
                try:
                    # Use target_format if specified, otherwise default to JPEG
                    output_format = target_format or "JPEG"
                    
                    if output_format.upper() == "WEBP":
                        img.save(absolute_thumbnail_path, "WEBP", quality=85, lossless=False)
                    elif output_format.upper() == "PNG":
                        img.save(absolute_thumbnail_path, "PNG", compress_level=6, optimize=True)
                    else:  # Default to JPEG
                        img.save(absolute_thumbnail_path, "JPEG", quality=85, optimize=True)
                    logger.debug(f"Generated thumbnail: {absolute_thumbnail_path}")
                    return thumbnail_path
                except Exception as e:
                    logger.error(f"Error saving thumbnail for {image_path}: {e}")
                    # Try with lower quality if optimization fails
                    try:
                        img.save(absolute_thumbnail_path, "JPEG", quality=70, optimize=False)
                        logger.debug(f"Generated thumbnail with reduced quality: {absolute_thumbnail_path}")
                        return thumbnail_path
                    except Exception as e2:
                        logger.error(f"Error saving thumbnail with reduced quality: {e2}")
                        return None
                
        except UnidentifiedImageError as e:
            logger.error(f"Unidentified image format for {image_path}: {e}")
            return None
        except OSError as e:
            logger.error(f"OS error generating thumbnail for {image_path}: {e}")
            return None
        except ValueError as e:
            logger.error(f"Value error generating thumbnail for {image_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating thumbnail for {image_path}: {str(e)}")
            return None
    
    def delete_thumbnail(self, thumbnail_path):
        """Delete a thumbnail.
        
        Args:
            thumbnail_path (str): Path to the thumbnail to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not thumbnail_path or not os.path.exists(thumbnail_path):
            return False
        
        try:
            os.remove(thumbnail_path)
            logger.debug(f"Deleted thumbnail: {thumbnail_path}")
            return True
        except OSError as e:
            logger.error(f"Error deleting thumbnail {thumbnail_path}: {e}")
            return False
    
    def cleanup_orphaned_thumbnails(self, valid_thumbnail_paths):
        """Clean up orphaned thumbnails that don't correspond to any image in the database.
        
        Args:
            valid_thumbnail_paths (list): List of valid thumbnail paths from the database
            
        Returns:
            int: Number of thumbnails deleted
        """
        count = 0
        
        try:
            # Get all thumbnails in the directory
            for filename in os.listdir(self.thumbnail_dir):
                thumbnail_path = os.path.join(self.thumbnail_dir, filename)
                
                # Skip directories
                if os.path.isdir(thumbnail_path):
                    continue
                
                # Check if this thumbnail is in the valid list
                if thumbnail_path not in valid_thumbnail_paths:
                    # Delete orphaned thumbnail
                    if os.path.exists(thumbnail_path):
                        os.remove(thumbnail_path)
                        count += 1
                        logger.debug(f"Deleted orphaned thumbnail: {thumbnail_path}")
            
            logger.info(f"Cleaned up {count} orphaned thumbnails")
            return count
            
        except OSError as e:
            logger.error(f"Error cleaning up orphaned thumbnails: {e}")
            return count
