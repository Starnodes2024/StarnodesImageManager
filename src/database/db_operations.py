#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database operations for StarImageBrowse
Provides high-level database operations using the core database system.
"""

import os
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from src.database.db_core import Database, DatabaseConnection

logger = logging.getLogger("StarImageBrowse.database.db_operations")

class DatabaseOperations:
    """High-level database operations for StarImageBrowse."""
    
    def __init__(self, db_path):
        """Initialize the database operations.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self.db = Database(db_path)
        logger.info(f"Database operations initialized for: {db_path}")
        
    def add_folder(self, folder_path):
        """Add a folder to monitor for images.
        
        Args:
            folder_path (str): Path to the folder to monitor
            
        Returns:
            int: The folder_id if successful, None otherwise
        """
        conn = self.db.get_connection()
        if not conn:
            return None
            
        try:
            # Begin transaction
            if not conn.begin_transaction():
                raise Exception("Failed to begin transaction")
                
            # Check if folder already exists
            cursor = conn.execute("SELECT folder_id FROM folders WHERE path = ?", (folder_path,))
            if not cursor:
                raise Exception("Failed to check if folder exists")
                
            existing = cursor.fetchone()
            if existing:
                # Folder already exists, just return its ID
                conn.rollback()
                return existing['folder_id']
                
            # Add the folder
            cursor = conn.execute(
                "INSERT INTO folders (path, enabled, last_scan_time) VALUES (?, ?, ?)",
                (folder_path, 1, datetime.now())
            )
            if not cursor:
                raise Exception("Failed to insert folder")
                
            # Get the new folder ID
            cursor = conn.execute("SELECT last_insert_rowid()")
            if not cursor:
                raise Exception("Failed to get last insert rowid")
                
            folder_id = cursor.fetchone()[0]
            
            # Commit the transaction
            if not conn.commit():
                raise Exception("Failed to commit transaction")
                
            logger.info(f"Added folder: {folder_path} with ID: {folder_id}")
            return folder_id
            
        except Exception as e:
            logger.error(f"Error adding folder: {e}")
            conn.rollback()
            return None
            
        finally:
            conn.disconnect()
            
    def get_folders(self, enabled_only=True):
        """Get all monitored folders.
        
        Args:
            enabled_only (bool): If True, only return enabled folders
            
        Returns:
            list: List of folder dictionaries with keys: folder_id, path, enabled, last_scan_time
        """
        conn = self.db.get_connection()
        if not conn:
            return []
            
        try:
            # Build query
            query = "SELECT * FROM folders"
            if enabled_only:
                query += " WHERE enabled = 1"
                
            # Execute query
            cursor = conn.execute(query)
            if not cursor:
                raise Exception("Failed to get folders")
                
            # Convert to list of dictionaries
            folders = [dict(row) for row in cursor.fetchall()]
            
            return folders
            
        except Exception as e:
            logger.error(f"Error getting folders: {e}")
            return []
            
        finally:
            conn.disconnect()
            
    def remove_folder(self, folder_id):
        """Remove a folder from monitoring.
        
        Args:
            folder_id (int): ID of the folder to remove
            
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.db.get_connection()
        if not conn:
            return False
            
        try:
            # Begin transaction
            if not conn.begin_transaction():
                raise Exception("Failed to begin transaction")
                
            # Get images for this folder
            cursor = conn.execute("SELECT image_id FROM images WHERE folder_id = ?", (folder_id,))
            if not cursor:
                raise Exception("Failed to get images for folder")
                
            image_ids = [row['image_id'] for row in cursor.fetchall()]
            
            # Delete images
            if image_ids:
                placeholders = ','.join(['?'] * len(image_ids))
                cursor = conn.execute(f"DELETE FROM images WHERE image_id IN ({placeholders})", image_ids)
                if not cursor:
                    raise Exception("Failed to delete images")
                    
            # Delete folder
            cursor = conn.execute("DELETE FROM folders WHERE folder_id = ?", (folder_id,))
            if not cursor:
                raise Exception("Failed to delete folder")
                
            # Commit the transaction
            if not conn.commit():
                raise Exception("Failed to commit transaction")
                
            logger.info(f"Removed folder with ID: {folder_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing folder: {e}")
            conn.rollback()
            return False
            
        finally:
            conn.disconnect()
            
    def _normalize_path(self, path):
        """Normalize a file path to use consistent separators.
        
        Args:
            path (str): The path to normalize
            
        Returns:
            str: Normalized path using the OS-specific separator
        """
        if not path:
            return path
            
        # First convert to standard form with forward slashes
        normalized = os.path.normpath(path.replace('\\', '/'))
        # Then convert to os-specific path format
        return os.path.normpath(normalized)
    
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
        # Normalize paths before storing to ensure consistent format
        full_path = self._normalize_path(full_path)
        if thumbnail_path:
            thumbnail_path = self._normalize_path(thumbnail_path)
        conn = self.db.get_connection()
        if not conn:
            return None
            
        try:
            # Begin transaction
            if not conn.begin_transaction():
                raise Exception("Failed to begin transaction")
                
            # Check if image already exists
            cursor = conn.execute("SELECT image_id FROM images WHERE full_path = ?", (full_path,))
            if not cursor:
                raise Exception("Failed to check if image exists")
                
            existing = cursor.fetchone()
            if existing:
                # Image already exists, just return its ID
                conn.rollback()
                return existing['image_id']
                
            # Get file creation and modification times
            file_path = Path(full_path)
            if file_path.exists():
                creation_date = datetime.fromtimestamp(file_path.stat().st_ctime)
                last_modified_date = datetime.fromtimestamp(file_path.stat().st_mtime)
            else:
                creation_date = datetime.now()
                last_modified_date = datetime.now()
                
            # Add the image
            cursor = conn.execute(
                """INSERT INTO images (
                    folder_id, filename, full_path, file_size, file_hash,
                    creation_date, last_modified_date, thumbnail_path,
                    ai_description, last_scanned
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    folder_id, filename, full_path, file_size, file_hash,
                    creation_date, last_modified_date, thumbnail_path,
                    ai_description, datetime.now()
                )
            )
            if not cursor:
                raise Exception("Failed to insert image")
                
            # Get the new image ID
            cursor = conn.execute("SELECT last_insert_rowid()")
            if not cursor:
                raise Exception("Failed to get last insert rowid")
                
            image_id = cursor.fetchone()[0]
            
            # Commit the transaction
            if not conn.commit():
                raise Exception("Failed to commit transaction")
                
            logger.debug(f"Added image: {filename} with ID: {image_id}")
            return image_id
            
        except Exception as e:
            logger.error(f"Error adding image: {e}")
            conn.rollback()
            return None
            
        finally:
            conn.disconnect()
            
    def update_image_description(self, image_id, ai_description=None, user_description=None, retry_count=0):
        """Update the AI or user description for an image.
        
        Args:
            image_id (int): ID of the image to update
            ai_description (str, optional): AI-generated description to update
            user_description (str, optional): User-provided description to update
            retry_count (int): Number of times this operation has been retried
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Maximum number of repair attempts
        MAX_RETRIES = 1
        
        # Validate inputs
        if ai_description is None and user_description is None:
            logger.warning("No description provided for update")
            return False
            
        conn = self.db.get_connection()
        if not conn:
            return False
            
        try:
            # Begin transaction
            if not conn.begin_transaction():
                raise Exception("Failed to begin transaction")
                
            # Build update query
            updates = []
            params = []
            
            if ai_description is not None:
                updates.append("ai_description = ?")
                params.append(ai_description)
                
            if user_description is not None:
                updates.append("user_description = ?")
                params.append(user_description)
                
            # Add image_id to params
            params.append(image_id)
            
            # Execute update
            query = f"UPDATE images SET {', '.join(updates)} WHERE image_id = ?"
            cursor = conn.execute(query, params)
            if not cursor:
                raise Exception("Failed to update image description")
                
            # Check if any rows were affected
            if cursor.rowcount == 0:
                logger.warning(f"Image with ID {image_id} not found or no changes made")
                conn.rollback()
                return False
                
            # Commit the transaction
            if not conn.commit():
                raise Exception("Failed to commit transaction")
                
            logger.debug(f"Updated description for image ID: {image_id}")
            return True
            
        except sqlite3.DatabaseError as sqlite_error:
            # Handle database corruption
            error_msg = str(sqlite_error).lower()
            conn.rollback()
            
            # Check if this is a corruption error
            if "malformed" in error_msg or "corrupt" in error_msg or "disk i/o error" in error_msg:
                logger.error(f"Database corruption detected: {sqlite_error}")
                
                # Attempt repair if we haven't exceeded retry limit
                if retry_count < MAX_RETRIES:
                    logger.warning("Attempting database repair...")
                    conn.disconnect()
                    
                    # Import repair function here to avoid circular imports
                    from src.database.db_repair import repair_database
                    
                    # Try to repair the database
                    repair_success = repair_database(self.db_path)
                    
                    if repair_success:
                        logger.info("Database repair successful, retrying operation")
                        # Retry the operation with incremented retry count
                        return self.update_image_description(image_id, ai_description, user_description, retry_count + 1)
                    else:
                        logger.error("Database repair failed")
                else:
                    logger.error(f"Maximum retry attempts ({MAX_RETRIES}) reached for database repair")
            
            logger.error(f"Database error updating image description: {sqlite_error}")
            return False
        except Exception as e:
            logger.error(f"Error updating image description: {e}")
            conn.rollback()
            return False
            
        finally:
            conn.disconnect()
            
    def search_images(self, query, limit=100, offset=0):
        """Search for images based on their descriptions.
        
        Args:
            query (str): Search query to match against descriptions
            limit (int, optional): Maximum number of results to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries matching the search criteria
        """
        conn = self.db.get_connection()
        if not conn:
            return []
            
        try:
            # Use full-text search if available
            try:
                # Try FTS query first
                cursor = conn.execute(
                    """SELECT i.* FROM images i
                    JOIN image_fts f ON i.image_id = f.image_id
                    WHERE image_fts MATCH ?
                    ORDER BY i.last_modified_date DESC
                    LIMIT ? OFFSET ?""",
                    (query, limit, offset)
                )
                if cursor and cursor.fetchone():
                    # Reset cursor and fetch all results
                    cursor = conn.execute(
                        """SELECT i.* FROM images i
                        JOIN image_fts f ON i.image_id = f.image_id
                        WHERE image_fts MATCH ?
                        ORDER BY i.last_modified_date DESC
                        LIMIT ? OFFSET ?""",
                        (query, limit, offset)
                    )
                else:
                    # Fall back to LIKE query
                    search_term = f"%{query}%"
                    cursor = conn.execute(
                        """SELECT * FROM images
                        WHERE ai_description LIKE ? OR user_description LIKE ?
                        ORDER BY last_modified_date DESC
                        LIMIT ? OFFSET ?""",
                        (search_term, search_term, limit, offset)
                    )
            except sqlite3.Error:
                # Fall back to LIKE query if FTS fails
                search_term = f"%{query}%"
                cursor = conn.execute(
                    """SELECT * FROM images
                    WHERE ai_description LIKE ? OR user_description LIKE ?
                    ORDER BY last_modified_date DESC
                    LIMIT ? OFFSET ?""",
                    (search_term, search_term, limit, offset)
                )
                
            if not cursor:
                raise Exception("Failed to search images")
                
            # Convert to list of dictionaries
            images = [dict(row) for row in cursor.fetchall()]
            
            return images
            
        except Exception as e:
            logger.error(f"Error searching images: {e}")
            return []
            
        finally:
            conn.disconnect()
            
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
        conn = self.db.get_connection()
        if not conn:
            return []
            
        try:
            # Use full-text search if available and filter by folder_id
            try:
                # Try FTS query first with folder_id filter
                cursor = conn.execute(
                    """SELECT i.* FROM images i
                    JOIN image_fts f ON i.image_id = f.image_id
                    WHERE image_fts MATCH ? AND i.folder_id = ?
                    ORDER BY i.last_modified_date DESC
                    LIMIT ? OFFSET ?""",
                    (query, folder_id, limit, offset)
                )
                if cursor and cursor.fetchone():
                    # Reset cursor and fetch all results
                    cursor = conn.execute(
                        """SELECT i.* FROM images i
                        JOIN image_fts f ON i.image_id = f.image_id
                        WHERE image_fts MATCH ? AND i.folder_id = ?
                        ORDER BY i.last_modified_date DESC
                        LIMIT ? OFFSET ?""",
                        (query, folder_id, limit, offset)
                    )
                else:
                    # Fall back to LIKE query with folder_id filter
                    search_term = f"%{query}%"
                    cursor = conn.execute(
                        """SELECT * FROM images
                        WHERE (ai_description LIKE ? OR user_description LIKE ?)
                        AND folder_id = ?
                        ORDER BY last_modified_date DESC
                        LIMIT ? OFFSET ?""",
                        (search_term, search_term, folder_id, limit, offset)
                    )
            except sqlite3.Error:
                # Fall back to LIKE query if FTS fails
                search_term = f"%{query}%"
                cursor = conn.execute(
                    """SELECT * FROM images
                    WHERE (ai_description LIKE ? OR user_description LIKE ?)
                    AND folder_id = ?
                    ORDER BY last_modified_date DESC
                    LIMIT ? OFFSET ?""",
                    (search_term, search_term, folder_id, limit, offset)
                )
                
            if not cursor:
                raise Exception("Failed to search images in folder")
                
            # Convert to list of dictionaries
            images = [dict(row) for row in cursor.fetchall()]
            
            return images
            
        except Exception as e:
            logger.error(f"Error searching images in folder: {e}")
            return []
            
        finally:
            conn.disconnect()
            
    def get_images_for_folder(self, folder_id, limit=100, offset=0):
        """Get images for a specific folder.
        
        Args:
            folder_id (int): ID of the folder to get images for
            limit (int, optional): Maximum number of results to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries in the folder
        """
        conn = self.db.get_connection()
        if not conn:
            return []
            
        try:
            # Execute query
            cursor = conn.execute(
                """SELECT * FROM images
                WHERE folder_id = ?
                ORDER BY last_modified_date DESC
                LIMIT ? OFFSET ?""",
                (folder_id, limit, offset)
            )
            if not cursor:
                raise Exception("Failed to get images for folder")
                
            # Convert to list of dictionaries
            images = [dict(row) for row in cursor.fetchall()]
            
            return images
            
        except Exception as e:
            logger.error(f"Error getting images for folder: {e}")
            return []
            
        finally:
            conn.disconnect()

    def get_images_by_date_range(self, from_date, to_date, limit=1000, offset=0):
        """Get images within a specific date range.
        
        Args:
            from_date (str): Start date in 'YYYY-MM-DD HH:MM:SS' format
            to_date (str): End date in 'YYYY-MM-DD HH:MM:SS' format
            limit (int, optional): Maximum number of results to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries within the date range
        """
        conn = self.db.get_connection()
        if not conn:
            return []
            
        try:
            # Execute query checking both creation_date and last_modified_date
            # to be inclusive of both original and modified dates
            cursor = conn.execute(
                """SELECT * FROM images
                WHERE (creation_date BETWEEN ? AND ?)
                   OR (last_modified_date BETWEEN ? AND ?)
                ORDER BY last_modified_date DESC
                LIMIT ? OFFSET ?""",
                (from_date, to_date, from_date, to_date, limit, offset)
            )
            if not cursor:
                raise Exception("Failed to get images by date range")
                
            # Convert to list of dictionaries
            images = [dict(row) for row in cursor.fetchall()]
            
            return images
            
        except Exception as e:
            logger.error(f"Error getting images by date range: {e}")
            return []
            
        finally:
            conn.disconnect()
            
    def get_all_images(self, limit=1000, offset=0):
        """Get all images from all enabled folders.
        
        Args:
            limit (int, optional): Maximum number of results to return
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of image dictionaries from all enabled folders
        """
        conn = self.db.get_connection()
        if not conn:
            return []
            
        try:
            # Get all folders that are enabled
            cursor = conn.execute("SELECT folder_id FROM folders WHERE enabled = 1")
            if not cursor:
                raise Exception("Failed to get enabled folders")
                
            folders = cursor.fetchall()
            if not folders:
                return []
                
            # Extract folder IDs
            folder_ids = [f["folder_id"] for f in folders]
            
            # Create placeholders for SQL IN clause
            placeholders = ", ".join(["?" for _ in folder_ids])
            
            # Execute query to get all images from enabled folders
            query = f"""
                SELECT * FROM images
                WHERE folder_id IN ({placeholders})
                ORDER BY last_modified_date DESC
                LIMIT ? OFFSET ?
            """
            
            # Parameters: folder_ids followed by limit and offset
            params = folder_ids + [limit, offset]
            
            cursor = conn.execute(query, params)
            if not cursor:
                raise Exception("Failed to get images from all folders")
                
            # Convert to list of dictionaries
            images = [dict(row) for row in cursor.fetchall()]
            
            return images
            
        except Exception as e:
            logger.error(f"Error getting all images: {e}")
            return []
            
        finally:
            conn.disconnect()
            
    def get_image_count(self):
        """Get the total number of images in the database.
        
        Returns:
            int: Total number of images
        """
        conn = self.db.get_connection()
        if not conn:
            return 0
            
        try:
            # Execute query to count all images
            cursor = conn.execute("SELECT COUNT(*) as count FROM images")
            if not cursor:
                raise Exception("Failed to count images")
                
            result = cursor.fetchone()
            if not result:
                return 0
                
            return result['count']
            
        except Exception as e:
            logger.error(f"Error counting images: {e}")
            return 0
            
        finally:
            conn.disconnect()
            
    def get_image_by_id(self, image_id):
        """Get an image by its ID.
        
        Args:
            image_id (int): ID of the image to get
            
        Returns:
            dict: Image data or None if not found
        """
        conn = self.db.get_connection()
        if not conn:
            return None
            
        try:
            # Execute query
            cursor = conn.execute("SELECT * FROM images WHERE image_id = ?", (image_id,))
            if not cursor:
                raise Exception("Failed to get image by ID")
                
            # Get the image
            image = cursor.fetchone()
            if not image:
                return None
                
            return dict(image)
            
        except Exception as e:
            logger.error(f"Error getting image by ID: {e}")
            return None
            
        finally:
            conn.disconnect()
            
    def delete_image(self, image_id):
        """Delete an image from the database.
        
        Args:
            image_id (int): ID of the image to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.db.get_connection()
        if not conn:
            return False
            
        try:
            # Begin transaction
            if not conn.begin_transaction():
                raise Exception("Failed to begin transaction")
                
            # Delete the image
            cursor = conn.execute("DELETE FROM images WHERE image_id = ?", (image_id,))
            if not cursor:
                raise Exception("Failed to delete image")
                
            # Check if any rows were affected
            if cursor.rowcount == 0:
                logger.warning(f"Image with ID {image_id} not found")
                conn.rollback()
                return False
                
            # Commit the transaction
            if not conn.commit():
                raise Exception("Failed to commit transaction")
                
            logger.info(f"Deleted image with ID: {image_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting image: {e}")
            conn.rollback()
            return False
            
        finally:
            conn.disconnect()
            
    def update_image_path(self, image_id, new_filename, new_full_path):
        """Update the filename and path for an image.
        
        Args:
            image_id (int): ID of the image to update
            new_filename (str): New filename for the image
            new_full_path (str): New full path for the image
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Normalize the new path before storing
        new_full_path = self._normalize_path(new_full_path)
        logger.debug(f"Updating image path with normalized path: {new_full_path}")
        conn = self.db.get_connection()
        if not conn:
            return False
            
        try:
            # Begin transaction
            if not conn.begin_transaction():
                raise Exception("Failed to begin transaction")
                
            # Update the image
            cursor = conn.execute(
                "UPDATE images SET filename = ?, full_path = ? WHERE image_id = ?",
                (new_filename, new_full_path, image_id)
            )
            if not cursor:
                raise Exception("Failed to update image path")
                
            # Check if any rows were affected
            if cursor.rowcount == 0:
                logger.warning(f"Image with ID {image_id} not found")
                conn.rollback()
                return False
                
            # Commit the transaction
            if not conn.commit():
                raise Exception("Failed to commit transaction")
                
            logger.info(f"Updated path for image ID: {image_id} to {new_full_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating image path: {e}")
            conn.rollback()
            return False
            
        finally:
            conn.disconnect()
    
    def update_folder_scan_time(self, folder_id):
        """Update the last scan time for a folder.
        
        Args:
            folder_id (int): ID of the folder to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.db.get_connection()
        if not conn:
            return False
            
        try:
            # Begin transaction
            if not conn.begin_transaction():
                raise Exception("Failed to begin transaction")
                
            # Update the folder
            cursor = conn.execute(
                "UPDATE folders SET last_scan_time = ? WHERE folder_id = ?",
                (datetime.now(), folder_id)
            )
            if not cursor:
                raise Exception("Failed to update folder scan time")
                
            # Check if any rows were affected
            if cursor.rowcount == 0:
                logger.warning(f"Folder with ID {folder_id} not found")
                conn.rollback()
                return False
                
            # Commit the transaction
            if not conn.commit():
                raise Exception("Failed to commit transaction")
                
            logger.debug(f"Updated scan time for folder ID: {folder_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating folder scan time: {e}")
            conn.rollback()
            return False
            
        finally:
            conn.disconnect()
            
    def optimize_database(self):
        """Optimize the database for better performance.
        
        Returns:
            bool: True if optimization was successful, False otherwise
        """
        return self.db.optimize()
        
    def vacuum_database(self):
        """Run VACUUM on the database to reclaim unused space.
        
        Returns:
            bool: True if vacuum was successful, False otherwise
        """
        return self.db.vacuum()
        
    def analyze_database(self):
        """Run ANALYZE on the database to update statistics.
        
        Returns:
            bool: True if analyze was successful, False otherwise
        """
        return self.db.analyze()
        
    def check_database_integrity(self):
        """Check the integrity of the database.
        
        Returns:
            bool: True if the database is intact, False otherwise
        """
        return self.db.integrity_check()
