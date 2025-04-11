#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced search functionality for StarImageBrowse
Provides comprehensive search queries supporting multiple criteria and scopes.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Union, Optional, Tuple

logger = logging.getLogger("StarImageBrowse.database.enhanced_search")

class EnhancedSearch:
    """Provides enhanced search functionality with multiple criteria and scopes."""
    
    def __init__(self, db_operations):
        """Initialize the enhanced search.
        
        Args:
            db_operations: Database operations instance for executing queries
        """
        self.db_ops = db_operations
        
    def reset_connection(self):
        """Reset the database connection for the enhanced search.
        
        This is useful after database repair or when switching to a different database.
        """
        if hasattr(self.db_ops, 'db') and self.db_ops.db:
            try:
                # Close existing connections if any
                if hasattr(self.db_ops.db, 'disconnect') and callable(self.db_ops.db.disconnect):
                    self.db_ops.db.disconnect()
                    
                # Re-establish the connection
                if hasattr(self.db_ops.db, 'connect') and callable(self.db_ops.db.connect):
                    self.db_ops.db.connect()
                    logger.info("Enhanced search database connection reset successful")
            except Exception as e:
                logger.error(f"Error resetting enhanced search database connection: {e}")
        
    def search(self, params, folder_id=None, catalog_id=None, limit=1000000, offset=0):
        """Execute a search with multiple criteria.
        
        Args:
            params (dict): Search parameters dictionary with the following keys:
                scope (str): 'folder', 'catalog', or 'all'
                text_enabled (bool): Whether text search is enabled
                text_query (str): Search query text
                date_enabled (bool): Whether date search is enabled
                date_from (datetime): Start date for range
                date_to (datetime): End date for range
                dimensions_enabled (bool): Whether dimension search is enabled
                min_width (int): Minimum image width
                max_width (int): Maximum image width
                min_height (int): Minimum image height
                max_height (int): Maximum image height
                dimension_preset (int): Preset index (0=custom, 5=square, 6=portrait, 7=landscape)
            folder_id (int, optional): ID of the folder to search in (if scope is 'folder')
            catalog_id (int, optional): ID of the catalog to search in (if scope is 'catalog')
            limit (int, optional): Maximum number of results to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries matching the search criteria
        """
        # Initialize connection
        conn = self.db_ops.db.get_connection()
        if not conn:
            logger.error("Failed to get database connection for search")
            return []
            
        try:
            # Build the query
            query_parts = []
            query_params = []
            
            # Base query - depends on scope
            scope = params.get('scope', 'folder')
            
            if scope == 'folder' and folder_id is not None:
                base_query = "SELECT * FROM images WHERE folder_id = ?"
                query_params.append(folder_id)
            elif scope == 'catalog' and catalog_id is not None:
                base_query = """
                    SELECT i.* FROM images i
                    JOIN image_catalog_mapping m ON i.image_id = m.image_id
                    WHERE m.catalog_id = ?
                """
                query_params.append(catalog_id)
            else:
                base_query = "SELECT * FROM images WHERE 1=1"
            
            # Add criteria based on enabled options
            # 1. Text search
            if params.get('text_enabled', False) and params.get('text_query'):
                query_text = params['text_query'].strip()
                if query_text:
                    try:
                        # Always use basic LIKE search - more reliable and simpler
                        logger.info(f"Searching for: '{query_text}' using basic LIKE search")
                        like_pattern = f"%{query_text}%"
                        query_parts.append("(ai_description LIKE ? OR user_description LIKE ? OR filename LIKE ?)")
                        query_params.extend([like_pattern, like_pattern, like_pattern])
                    except Exception as e:
                        # Fallback to basic LIKE search on error
                        logger.warning(f"Error using FTS: {e}, using fallback LIKE search")
                        like_pattern = f"%{query_text}%"
                        query_parts.append("(ai_description LIKE ? OR user_description LIKE ? OR filename LIKE ?)")
                        query_params.extend([like_pattern, like_pattern, like_pattern])
            
            # 2. Date range
            if params.get('date_enabled', False):
                date_from = params.get('date_from')
                date_to = params.get('date_to')
                
                if date_from and date_to:
                    # Convert to datetime objects if they're not already
                    if not isinstance(date_from, datetime):
                        date_from = datetime.combine(date_from, datetime.min.time())
                    if not isinstance(date_to, datetime):
                        date_to = datetime.combine(date_to, datetime.max.time())
                    
                    query_parts.append("last_modified_date BETWEEN ? AND ?")
                    query_params.append(date_from)
                    query_params.append(date_to)
            
            # 3. Image dimensions
            if params.get('dimensions_enabled', False):
                dimension_preset = params.get('dimension_preset', 0)
                
                if dimension_preset == 5:  # Square
                    query_parts.append("width = height AND width IS NOT NULL AND height IS NOT NULL")
                elif dimension_preset == 6:  # Portrait
                    query_parts.append("height > width AND width IS NOT NULL AND height IS NOT NULL")
                elif dimension_preset == 7:  # Landscape
                    query_parts.append("width > height AND width IS NOT NULL AND height IS NOT NULL")
                else:  # Custom or specific resolution
                    min_width = params.get('min_width')
                    max_width = params.get('max_width')
                    min_height = params.get('min_height')
                    max_height = params.get('max_height')
                    
                    # Add a condition to filter only images that have dimensions stored
                    query_parts.append("(width IS NOT NULL AND height IS NOT NULL)")
                    
                    # Apply dimension filters only if they're useful values
                    if min_width is not None and min_width > 0:
                        query_parts.append("width >= ?")
                        query_params.append(min_width)
                    
                    if max_width is not None and max_width < 10000:
                        query_parts.append("width <= ?")
                        query_params.append(max_width)
                    
                    if min_height is not None and min_height > 0:
                        query_parts.append("height >= ?")
                        query_params.append(min_height)
                    
                    if max_height is not None and max_height < 10000:
                        query_parts.append("height <= ?")
                        query_params.append(max_height)
            
            # Combine all parts of the query
            final_query = base_query
            if query_parts:
                final_query += " AND " + " AND ".join(query_parts)
            
            # Add order by clause
            final_query += " ORDER BY last_modified_date DESC LIMIT ? OFFSET ?"
            query_params.append(limit)
            query_params.append(offset)
            
            # Execute the query
            logger.debug(f"Executing search query: {final_query} with params: {query_params}")
            cursor = conn.execute(final_query, tuple(query_params))
            if not cursor:
                logger.error("Failed to execute search query")
                return []
            
            # Convert to list of dictionaries
            results = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Found {len(results)} images matching search criteria")
            
            return results
            
        except Exception as e:
            logger.error(f"Error performing enhanced search: {e}")
            return []
            
        finally:
            conn.disconnect()
    
    def update_image_dimensions(self, image_id, width, height):
        """Update the width and height of an image.
        
        Args:
            image_id (int): ID of the image to update
            width (int): Width of the image in pixels
            height (int): Height of the image in pixels
            
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.db_ops.db.get_connection()
        if not conn:
            return False
            
        try:
            # Begin transaction
            if not conn.begin_transaction():
                raise Exception("Failed to begin transaction")
                
            # Update the image dimensions
            cursor = conn.execute(
                "UPDATE images SET width = ?, height = ? WHERE image_id = ?",
                (width, height, image_id)
            )
            if not cursor:
                raise Exception("Failed to update image dimensions")
                
            # Check if any rows were affected
            if cursor.rowcount == 0:
                logger.warning(f"No image found with ID {image_id} to update dimensions")
                conn.rollback()
                return False
                
            # Commit the transaction
            if not conn.commit():
                raise Exception("Failed to commit transaction")
                
            logger.debug(f"Updated dimensions for image {image_id}: {width}×{height}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating image dimensions: {e}")
            conn.rollback()
            return False
            
        finally:
            conn.disconnect()
    
    def batch_update_image_dimensions(self, image_dimensions):
        """Update dimensions for multiple images with resilient error handling.
        
        This method processes each image individually to avoid losing all updates when one fails.
        
        Args:
            image_dimensions (list): List of tuples (image_id, width, height)
            
        Returns:
            int: Number of images successfully updated
        """
        if not image_dimensions:
            return 0
            
        # Track statistics
        success_count = 0
        failure_count = 0
        total_count = len(image_dimensions)
        batch_size = 50  # Process in smaller batches
        
        # Disconnect and reconnect to ensure fresh connection
        try:
            self.reset_connection()
        except Exception as e:
            logger.warning(f"Connection reset failed but continuing: {e}")
        
        # Process images in small batches to limit transaction size
        for i in range(0, total_count, batch_size):
            batch = image_dimensions[i:i + batch_size]
            
            # Get a fresh connection for each batch
            conn = self.db_ops.db.get_connection()
            if not conn:
                logger.error("Failed to get database connection for batch update")
                continue
                
            try:
                # Begin transaction for this batch
                conn.begin_transaction()
                
                # Update each image in the batch
                for image_id, width, height in batch:
                    try:
                        cursor = conn.execute(
                            "UPDATE images SET width = ?, height = ? WHERE image_id = ?",
                            (width, height, image_id)
                        )
                        if cursor and cursor.rowcount > 0:
                            success_count += 1
                    except Exception as item_error:
                        # Log the error but continue with other images
                        logger.debug(f"Error updating dimensions for image {image_id}: {item_error}")
                        failure_count += 1
                        continue
                
                # Commit this batch
                conn.commit()
                logger.debug(f"Batch {i//batch_size + 1}: Updated {len(batch) - failure_count} images")
                
            except Exception as batch_error:
                # Log batch error and rollback
                logger.error(f"Error processing batch {i//batch_size + 1}: {batch_error}")
                conn.rollback()
                failure_count += len(batch)
            finally:
                # Always disconnect after each batch
                conn.disconnect()
                
            # Short log message every 500 images
            if (i + batch_size) % 500 == 0 or (i + batch_size) >= total_count:
                logger.info(f"Progress: {success_count} updated, {failure_count} failed out of {total_count}")
        
        logger.info(f"Completed dimension updates: {success_count} successful, {failure_count} failed")
        return success_count
    
    def get_statistics(self):
        """Get statistics about the image collection.
        
        Returns:
            dict: Statistics including dimension ranges, counts, etc.
        """
        conn = self.db_ops.db.get_connection()
        if not conn:
            return {}
            
        try:
            stats = {}
            
            # Total images
            cursor = conn.execute("SELECT COUNT(*) FROM images")
            if cursor:
                stats['total_images'] = cursor.fetchone()[0]
                
            # Images with dimensions
            cursor = conn.execute("SELECT COUNT(*) FROM images WHERE width IS NOT NULL AND height IS NOT NULL")
            if cursor:
                stats['images_with_dimensions'] = cursor.fetchone()[0]
                
            # Min/max dimensions
            cursor = conn.execute("""
                SELECT 
                    MIN(width) as min_width, 
                    MAX(width) as max_width,
                    MIN(height) as min_height,
                    MAX(height) as max_height
                FROM images
                WHERE width IS NOT NULL AND height IS NOT NULL
            """)
            if cursor:
                row = cursor.fetchone()
                if row:
                    stats['min_width'] = row[0] or 0
                    stats['max_width'] = row[1] or 0
                    stats['min_height'] = row[2] or 0
                    stats['max_height'] = row[3] or 0
                    
            # Count by aspect ratio
            cursor = conn.execute("""
                SELECT 
                    COUNT(CASE WHEN width = height THEN 1 END) as square_count,
                    COUNT(CASE WHEN width > height THEN 1 END) as landscape_count,
                    COUNT(CASE WHEN height > width THEN 1 END) as portrait_count
                FROM images
                WHERE width IS NOT NULL AND height IS NOT NULL
            """)
            if cursor:
                row = cursor.fetchone()
                if row:
                    stats['square_images'] = row[0] or 0
                    stats['landscape_images'] = row[1] or 0
                    stats['portrait_images'] = row[2] or 0
                    
            return stats
            
        except Exception as e:
            logger.error(f"Error getting image statistics: {e}")
            return {}
            
        finally:
            conn.disconnect()
