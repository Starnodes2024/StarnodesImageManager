#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database manager for StarImageBrowse
Handles database initialization, connections, and queries.
This is a compatibility layer that uses the new database system.
"""

import os
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from src.database.db_operations import DatabaseOperations

logger = logging.getLogger("StarImageBrowse.database")

class DatabaseManager:
    """Manages database operations for the image browser application."""
    
    def __init__(self, db_path):
        """Initialize the database manager.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = None  # For backwards compatibility
        self.cursor = None  # For backwards compatibility
        
        # Create the new database operations object
        self.db_ops = DatabaseOperations(db_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        logger.info(f"Database path: {db_path}")
    
    def connect(self):
        """Establish a connection to the database.
        
        This method is kept for backwards compatibility.
        """
        # The new system doesn't maintain persistent connections
        # but we'll simulate it for backwards compatibility
        try:
            # Create a temporary connection for backwards compatibility
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            self.cursor = self.conn.cursor()
            
            logger.debug("Database connection established (compatibility mode)")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            return False
    
    def disconnect(self):
        """Close the database connection.
        
        This method is kept for backwards compatibility.
        """
        if self.conn:
            try:
                self.conn.close()
                logger.debug("Database connection closed (compatibility mode)")
            except sqlite3.Error as e:
                logger.error(f"Error closing database connection: {e}")
            finally:
                self.conn = None
                self.cursor = None
    
    def initialize_database(self):
        """Initialize the database schema if it doesn't exist.
        
        This method is kept for backwards compatibility.
        The new system initializes the database automatically.
        """
        # The new system initializes the database automatically
        # when the DatabaseOperations object is created
        logger.info("Database initialized (compatibility mode)")
        return True
    
    def add_folder(self, folder_path):
        """Add a folder to monitor for images.
        
        Args:
            folder_path (str): Path to the folder to monitor
            
        Returns:
            int: The folder_id if successful, None otherwise
        """
        return self.db_ops.add_folder(folder_path)
    
    def get_folders(self, enabled_only=True):
        """Get all monitored folders.
        
        Args:
            enabled_only (bool): If True, only return enabled folders
            
        Returns:
            list: List of folder dictionaries with keys: folder_id, path, enabled, last_scan_time
        """
        return self.db_ops.get_folders(enabled_only)
    
    def remove_folder(self, folder_id):
        """Remove a folder from monitoring.
        
        Args:
            folder_id (int): ID of the folder to remove
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.db_ops.remove_folder(folder_id)
    
    def add_image(self, folder_id, filename, full_path, file_size, file_hash=None, thumbnail_path=None, ai_description=None, image_format=None):
        """Add an image to the database.
        
        Args:
            folder_id (int): ID of the folder containing the image
            filename (str): Name of the image file
            full_path (str): Full path to the image file
            file_size (int): Size of the image file in bytes
            file_hash (str, optional): Hash of the image file for deduplication
            thumbnail_path (str, optional): Path to the thumbnail image
            ai_description (str, optional): AI-generated description of the image
            image_format (str, optional): Format of the image (JPEG, PNG, etc.)
            
        Returns:
            int: The image_id if successful, None otherwise
        """
        return self.db_ops.add_image(folder_id, filename, full_path, file_size, file_hash, thumbnail_path, ai_description, image_format)
    
    def update_image_description(self, image_id, ai_description=None, user_description=None, retry_count=0):
        """Update the AI or user description for an image.
        
        Args:
            image_id (int): ID of the image to update
            ai_description (str, optional): AI-generated description to update
            user_description (str, optional): User-provided description to update
            retry_count (int, optional): Number of retries attempted (internal use)
            
        Returns:
            bool: True if successful, False otherwise
        """
        # The retry_count parameter is kept for backwards compatibility
        # but is not used in the new system as it handles retries internally
        return self.db_ops.update_image_description(image_id, ai_description, user_description)
    
    def search_images(self, query, limit=100, offset=0):
        """Search for images based on their descriptions.
        
        Args:
            query (str): Search query to match against descriptions
            limit (int, optional): Maximum number of results to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries matching the search criteria
        """
        return self.db_ops.search_images(query, limit, offset)
    
    def search_images_in_folder(self, folder_id, query, limit=100, offset=0):
        """Search for images based on their descriptions within a specific folder.
        
        Args:
            folder_id (int): ID of the folder to search within
            query (str): Search query to match against descriptions
            limit (int, optional): Maximum number of results to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries matching the search criteria in the specified folder
        """
        return self.db_ops.search_images_in_folder(folder_id, query, limit, offset)
    
    def get_images_by_date_range(self, from_date, to_date, limit=1000000, offset=0):
        """Get images within a specific date range.
        
        Args:
            from_date (str): Start date in 'YYYY-MM-DD HH:MM:SS' format
            to_date (str): End date in 'YYYY-MM-DD HH:MM:SS' format
            limit (int, optional): Maximum number of results to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries within the date range
        """
        return self.db_ops.get_images_by_date_range(from_date, to_date, limit, offset)
    
    def get_all_images(self, limit=10000000, offset=0):
        """Get all images from all enabled folders.
        
        Args:
            limit (int, optional): Maximum number of results to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries from all enabled folders
        """
        return self.db_ops.get_all_images(limit, offset)
    
    def get_image_count(self):
        """Get the total number of images in the database.
        
        Returns:
            int: Total number of images
        """
        return self.db_ops.get_image_count()
        
    def get_image_count_for_folder(self, folder_id):
        """Get the number of images in a specific folder.
        
        Args:
            folder_id (int): ID of the folder to count images for
            
        Returns:
            int: Number of images in the folder
        """
        return self.db_ops.get_image_count_for_folder(folder_id)
        
    def get_folder_by_id(self, folder_id):
        """Get a folder by its ID.
        
        Args:
            folder_id (int): ID of the folder to get
            
        Returns:
            dict: Folder data or None if not found
        """
        return self.db_ops.get_folder_by_id(folder_id)
        
    def get_image_count_for_catalog(self, catalog_id):
        """Get the number of images in a specific catalog.
        
        Args:
            catalog_id (int): ID of the catalog to count images for
            
        Returns:
            int: Number of images in the catalog
        """
        return self.db_ops.get_image_count_for_catalog(catalog_id)
    
    def get_images_for_folder(self, folder_id, limit=100, offset=0):
        """Get images for a specific folder.
        
        Args:
            folder_id (int): ID of the folder to get images for
            limit (int, optional): Maximum number of results to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries in the folder
        """
        return self.db_ops.get_images_for_folder(folder_id, limit, offset)
    
    def optimize_for_large_collections(self):
        """Optimize the database for large image collections.
        
        This method applies various optimizations to improve performance
        when dealing with large numbers of images.
        
        Returns:
            bool: True if optimization was successful, False otherwise
        """
        return self.db_ops.optimize_database()
    
    def get_image_by_id(self, image_id):
        """Get an image by its ID.
        
        Args:
            image_id (int): ID of the image to get
            
        Returns:
            dict: Image data or None if not found
        """
        return self.db_ops.get_image_by_id(image_id)
    
    def delete_image(self, image_id):
        """Delete an image from the database.
        
        Args:
            image_id (int): ID of the image to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.db_ops.delete_image(image_id)
    
    def update_folder_scan_time(self, folder_id):
        """Update the last scan time for a folder.
        
        Args:
            folder_id (int): ID of the folder to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.db_ops.update_folder_scan_time(folder_id)
    
    def _create_performance_indexes(self):
        """Create additional indexes to improve query performance.
        
        This method is kept for backwards compatibility.
        The new system creates indexes automatically.
        """
        # The new system creates indexes automatically
        logger.info("Performance indexes created (compatibility mode)")
        return True
    
    def _set_performance_pragmas(self):
        """Set safe PRAGMA settings for better performance.
        
        This method is kept for backwards compatibility.
        The new system sets performance pragmas automatically.
        """
        # The new system sets performance pragmas automatically
        logger.info("Performance PRAGMAs set (compatibility mode)")
        return True
    
    def _check_and_repair_if_needed(self):
        """Check if the database is corrupted and repair it if needed.
        
        This method is kept for backwards compatibility.
        The new system checks and repairs the database automatically.
        """
        # The new system checks and repairs the database automatically
        result = self.db_ops.check_database_integrity()
        if result:
            logger.debug("Database integrity check passed (compatibility mode)")
        else:
            logger.warning("Database integrity check failed (compatibility mode)")
        return result
    
    def _create_virtual_tables(self):
        """Create virtual tables for full-text search capabilities.
        
        This method is kept for backwards compatibility.
        The new system creates virtual tables automatically.
        """
        # The new system creates virtual tables automatically
        logger.info("Virtual tables created (compatibility mode)")
        return True
        
    def update_image_path(self, image_id, new_filename, new_full_path):
        """Update the filename and path for an image.
        
        Args:
            image_id (int): ID of the image to update
            new_filename (str): New filename for the image
            new_full_path (str): New full path for the image
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.db_ops.update_image_path(image_id, new_filename, new_full_path)
    
    def get_image_description(self, image_id):
        """Get the AI description for an image.
        
        Args:
            image_id (int): ID of the image to get description for
            
        Returns:
            str: AI description or None if not found
        """
        image = self.get_image_by_id(image_id)
        if image and 'ai_description' in image:
            return image['ai_description']
        return None
        
    # Catalog operations (new feature)
    
    def create_catalog(self, name, description=""):
        """Create a new catalog.
        
        Args:
            name (str): Name of the catalog
            description (str, optional): Description of the catalog
            
        Returns:
            int: The catalog_id if successful, None otherwise
        """
        return self.db_ops.create_catalog(name, description)
    
    def get_catalogs(self):
        """Get all catalogs.
        
        Returns:
            list: List of catalog dictionaries with keys: catalog_id, name, description, created_date
        """
        return self.db_ops.get_catalogs()
    
    def add_image_to_catalog(self, image_id, catalog_id):
        """Add an image to a catalog.
        
        Args:
            image_id (int): ID of the image to add
            catalog_id (int): ID of the catalog to add the image to
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.db_ops.add_image_to_catalog(image_id, catalog_id)
    
    def remove_image_from_catalog(self, image_id, catalog_id):
        """Remove an image from a catalog.
        
        Args:
            image_id (int): ID of the image to remove
            catalog_id (int): ID of the catalog to remove the image from
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.db_ops.remove_image_from_catalog(image_id, catalog_id)
    
    def get_images_for_catalog(self, catalog_id, limit=1000000, offset=0):
        """Get images for a specific catalog.
        
        Args:
            catalog_id (int): ID of the catalog to get images for
            limit (int, optional): Maximum number of results to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries in the catalog
        """
        return self.db_ops.get_images_for_catalog(catalog_id, limit, offset)
    
    def get_catalog_by_id(self, catalog_id):
        """Get a catalog by its ID.
        
        Args:
            catalog_id (int): ID of the catalog to get
            
        Returns:
            dict: Catalog data or None if not found
        """
        return self.db_ops.get_catalog_by_id(catalog_id)
    
    def delete_catalog(self, catalog_id):
        """Delete a catalog.
        
        Args:
            catalog_id (int): ID of the catalog to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.db_ops.delete_catalog(catalog_id)
    
    def get_catalogs_for_image(self, image_id):
        """Get all catalogs that an image belongs to.
        
        Args:
            image_id (int): ID of the image
            
        Returns:
            list: List of catalog dictionaries for the image
        """
        return self.db_ops.get_catalogs_for_image(image_id)
