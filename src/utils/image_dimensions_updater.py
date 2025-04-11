#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Image dimensions updater for StarImageBrowse
Extracts image dimensions from files and updates the database.
"""

import os
import logging
from PIL import Image
from pathlib import Path
from datetime import datetime

# Import the database upgrade function
from src.database.db_upgrade import upgrade_database_schema

logger = logging.getLogger("StarImageBrowse.utils.image_dimensions_updater")

class ImageDimensionsUpdater:
    """Updates image dimensions in the database based on actual image files."""
    
    def __init__(self, db_manager, enhanced_search):
        """Initialize the image dimensions updater.
        
        Args:
            db_manager: Database manager instance
            enhanced_search: Enhanced search instance for updating dimensions
        """
        self.db_manager = db_manager
        self.enhanced_search = enhanced_search
        
        # Ensure database has the required columns
        self._ensure_database_schema()
        
    def _ensure_database_schema(self):
        """Ensure the database has the required width and height columns."""
        try:
            # Get the database path from the db_manager
            db_path = self.db_manager.db_ops.db.db_path
            
            # Call the upgrade function
            success, message = upgrade_database_schema(db_path)
            if success:
                logger.info(f"Database schema check: {message}")
            else:
                logger.error(f"Failed to upgrade database schema: {message}")
                
        except Exception as e:
            logger.error(f"Error ensuring database schema: {e}")
    
    def update_all_images(self, progress_callback=None):
        """Update dimensions for all images in the database.
        
        Args:
            progress_callback (callable, optional): Callback for progress updates (current, total)
            
        Returns:
            dict: Results with updated_count, failed_count, and total_count
        """
        results = {
            'updated_count': 0,
            'failed_count': 0,
            'total_count': 0,
            'not_found_count': 0
        }
        
        # Get all images from the database
        images = self.db_manager.get_all_images()
        total_images = len(images)
        results['total_count'] = total_images
        
        logger.info(f"Starting dimension update for {total_images} images")
        
        # Process in batches for better performance
        batch_size = 100
        batch_updates = []
        
        for i, image in enumerate(images):
            try:
                # Check if the image file exists
                full_path = image.get('full_path')
                if not full_path or not os.path.exists(full_path):
                    logger.warning(f"Image file not found: {full_path}")
                    results['not_found_count'] += 1
                    continue
                
                # Get dimensions with PIL
                with Image.open(full_path) as img:
                    width, height = img.size
                
                # Add to batch updates
                batch_updates.append((image['image_id'], width, height))
                
                # Update progress
                if progress_callback and i % 10 == 0:
                    progress_callback(i + 1, total_images)
                
                # Process batch if we've reached batch size or on last item
                if len(batch_updates) >= batch_size or i == total_images - 1:
                    updated_count = self.enhanced_search.batch_update_image_dimensions(batch_updates)
                    results['updated_count'] += updated_count
                    results['failed_count'] += len(batch_updates) - updated_count
                    batch_updates = []
                    
            except Exception as e:
                logger.error(f"Error updating dimensions for image {image.get('image_id')}: {e}")
                results['failed_count'] += 1
        
        # Final progress update
        if progress_callback:
            progress_callback(total_images, total_images)
            
        logger.info(f"Finished dimension update: {results['updated_count']} updated, " 
                    f"{results['failed_count']} failed, {results['not_found_count']} not found")
        
        return results
        
    def update_single_folder(self, folder_id, progress_callback=None):
        """Update dimensions for images in a specific folder.
        
        Args:
            folder_id (int): ID of the folder to update
            progress_callback (callable, optional): Callback for progress updates (current, total)
            
        Returns:
            dict: Results with updated_count, failed_count, and total_count
        """
        results = {
            'updated_count': 0,
            'failed_count': 0,
            'total_count': 0,
            'not_found_count': 0
        }
        
        # Get images from the specified folder
        images = self.db_manager.get_images_for_folder(folder_id)
        total_images = len(images)
        results['total_count'] = total_images
        
        logger.info(f"Starting dimension update for {total_images} images in folder {folder_id}")
        
        # Process in batches for better performance
        batch_size = 100
        batch_updates = []
        
        for i, image in enumerate(images):
            try:
                # Check if the image file exists
                full_path = image.get('full_path')
                if not full_path or not os.path.exists(full_path):
                    logger.warning(f"Image file not found: {full_path}")
                    results['not_found_count'] += 1
                    continue
                
                # Get dimensions with PIL
                with Image.open(full_path) as img:
                    width, height = img.size
                
                # Add to batch updates
                batch_updates.append((image['image_id'], width, height))
                
                # Update progress
                if progress_callback and i % 10 == 0:
                    progress_callback(i + 1, total_images)
                
                # Process batch if we've reached batch size or on last item
                if len(batch_updates) >= batch_size or i == total_images - 1:
                    updated_count = self.enhanced_search.batch_update_image_dimensions(batch_updates)
                    results['updated_count'] += updated_count
                    results['failed_count'] += len(batch_updates) - updated_count
                    batch_updates = []
                    
            except Exception as e:
                logger.error(f"Error updating dimensions for image {image.get('image_id')}: {e}")
                results['failed_count'] += 1
        
        # Final progress update
        if progress_callback:
            progress_callback(total_images, total_images)
            
        logger.info(f"Finished dimension update for folder {folder_id}: {results['updated_count']} updated, " 
                    f"{results['failed_count']} failed, {results['not_found_count']} not found")
        
        return results
        
    def update_for_new_image(self, image_id, full_path):
        """Update dimensions for a single new image.
        
        Args:
            image_id (int): ID of the image to update
            full_path (str): Full path to the image file
            
        Returns:
            tuple: (width, height) if successful, (None, None) otherwise
        """
        try:
            if not os.path.exists(full_path):
                logger.warning(f"Image file not found: {full_path}")
                return None, None
                
            # Get dimensions with PIL
            with Image.open(full_path) as img:
                width, height = img.size
                
            # Update the database
            if self.enhanced_search.update_image_dimensions(image_id, width, height):
                logger.debug(f"Updated dimensions for image {image_id}: {width}×{height}")
                return width, height
            else:
                logger.warning(f"Failed to update dimensions for image {image_id}")
                return None, None
                
        except Exception as e:
            logger.error(f"Error updating dimensions for image {image_id}: {e}")
            return None, None
