#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database indexing optimization for StarImageBrowse
Enhances query performance through strategic index creation.
"""

import logging
from .db_core import DatabaseConnection

logger = logging.getLogger("StarImageBrowse.database.db_indexing")

class DatabaseIndexOptimizer:
    """Optimizes database indexes for better query performance."""
    
    def __init__(self, db_path):
        """Initialize the database index optimizer.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        
    def create_optimized_indexes(self):
        """Create optimized indexes for the database.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Creating optimized indexes...")
        conn = DatabaseConnection(self.db_path)
        
        try:
            if not conn.connect():
                raise Exception("Failed to connect to database")
                
            # Begin transaction
            if not conn.begin_transaction():
                raise Exception("Failed to begin transaction")
                
            # Create composite indexes for common query patterns
            logger.info("Creating composite indexes for common query patterns...")
            operations = [
                # Folder-based queries with date filtering
                "CREATE INDEX IF NOT EXISTS idx_images_folder_date ON images(folder_id, last_modified_date)",
                
                # Optimize search and sort operations
                "CREATE INDEX IF NOT EXISTS idx_images_search ON images(ai_description, user_description)",
                
                # Optimize filtering for images without descriptions
                "CREATE INDEX IF NOT EXISTS idx_images_no_desc ON images(folder_id) WHERE ai_description IS NULL OR ai_description = ''",
                
                # Optimize path-based lookups
                "CREATE INDEX IF NOT EXISTS idx_images_path ON images(full_path)",
                
                # Optimize thumbnail fetching
                "CREATE INDEX IF NOT EXISTS idx_images_thumbnail ON images(thumbnail_path)",
                
                # Optimize for the virtual FTS table if it exists
                "CREATE INDEX IF NOT EXISTS idx_images_image_id ON images(image_id)"
            ]
            
            # Execute each index creation statement
            for operation in operations:
                try:
                    conn.execute(operation)
                    logger.debug(f"Executed: {operation}")
                except Exception as e:
                    logger.warning(f"Error executing {operation}: {e}")
            
            # Commit the transaction
            if not conn.commit():
                raise Exception("Failed to commit transaction")
                
            logger.info("Optimized indexes created successfully")
            
            # Analyze the database to update statistics
            conn.execute("ANALYZE")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating optimized indexes: {e}")
            conn.rollback()
            return False
            
        finally:
            conn.disconnect()
            
    def check_index_usage(self):
        """Check the usage of indexes in the database.
        
        Returns:
            dict: Index usage statistics
        """
        logger.info("Checking index usage...")
        conn = DatabaseConnection(self.db_path)
        
        try:
            if not conn.connect():
                raise Exception("Failed to connect to database")
                
            # Get list of indexes
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            if not cursor:
                raise Exception("Failed to get index list")
                
            indexes = [row['name'] for row in cursor.fetchall()]
            
            # Get index usage statistics
            stats = {"indexes": []}
            for index in indexes:
                stats["indexes"].append({
                    "name": index,
                    "table": index.split("_")[1] if "_" in index else "unknown"
                })
                
            return stats
            
        except Exception as e:
            logger.error(f"Error checking index usage: {e}")
            return {"error": str(e)}
            
        finally:
            conn.disconnect()
