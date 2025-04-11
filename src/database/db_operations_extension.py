#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database operations extensions for StarImageBrowse
Adds additional database capabilities for pagination and all images view
"""

import logging

logger = logging.getLogger("StarImageBrowse.database.db_operations_extension")

def add_get_all_images_method(db_ops):
    """Add get_all_images method to database operations
    
    Args:
        db_ops: The database operations instance to extend
    """
    def get_all_images(self, limit=None, offset=0):
        """Get all images from the database with pagination
        
        Args:
            limit (int, optional): Maximum number of images to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries
        """
        conn = self.db.get_connection()
        if not conn:
            logger.error("Failed to get database connection")
            return []
            
        try:
            # Build query with pagination
            query = "SELECT * FROM images ORDER BY last_modified_date DESC"
            params = []
            
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
                
                if offset > 0:
                    query += " OFFSET ?"
                    params.append(offset)
            
            # Execute query
            cursor = conn.execute(query, params)
            images = []
            
            for row in cursor:
                image = {
                    'image_id': row['image_id'],
                    'folder_id': row['folder_id'],
                    'filename': row['filename'],
                    'full_path': row['full_path'],
                    'thumbnail_path': row['thumbnail_path'],
                    'last_modified_date': row['last_modified_date'],
                    'user_description': row['user_description'],
                    'ai_description': row['ai_description'],
                    'width': row['width'],
                    'height': row['height']
                }
                images.append(image)
                
            return images
        
        except Exception as e:
            logger.error(f"Error getting all images: {e}")
            return []
    
    # Add method to the object
    import types
    db_ops.get_all_images = types.MethodType(get_all_images, db_ops)

def add_get_all_images_count_method(db_ops):
    """Add get_all_images_count method to database operations
    
    Args:
        db_ops: The database operations instance to extend
    """
    def get_all_images_count(self):
        """Get total count of all images in the database
        
        Returns:
            int: Total number of images
        """
        conn = self.db.get_connection()
        if not conn:
            logger.error("Failed to get database connection")
            return 0
            
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM images")
            count = cursor.fetchone()[0]
            return count
        
        except Exception as e:
            logger.error(f"Error counting all images: {e}")
            return 0
    
    # Add method to the object
    import types
    db_ops.get_all_images_count = types.MethodType(get_all_images_count, db_ops)

def extend_db_operations(db_manager):
    """Extend database operations with additional methods
    
    Args:
        db_manager: The database manager instance to extend
    """
    # Add methods to db_ops
    add_get_all_images_method(db_manager.db_ops)
    add_get_all_images_count_method(db_manager.db_ops)
    
    # Also make them available on the db_manager directly
    db_manager.get_all_images = db_manager.db_ops.get_all_images
    db_manager.get_all_images_count = db_manager.db_ops.get_all_images_count
