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
    
    def add_image(self, folder_id, filename, full_path, file_size, file_hash=None, thumbnail_path=None, ai_description=None):
        """Add an image to the database.
        
        Args:
            folder_id (int): ID of the folder containing the image
            filename (str): Name of the image file
            full_path (str): Full path to the image file
            file_size (int): Size of the image file in bytes
            file_hash (str, optional): Hash of the image file for deduplication
            thumbnail_path (str, optional): Path to the thumbnail image
            ai_description (str, optional): AI-generated description of the image
            
        Returns:
            int: The image_id if successful, None otherwise
        """
        return self.db_ops.add_image(folder_id, filename, full_path, file_size, file_hash, thumbnail_path, ai_description)
    
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
