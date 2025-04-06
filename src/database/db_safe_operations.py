#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Safe database operations for StarImageBrowse
This module provides functions for safely performing database operations
with proper error handling and recovery.
"""

import os
import sqlite3
import logging
import shutil
import time
from pathlib import Path

logger = logging.getLogger("StarImageBrowse.database.db_safe_operations")

def safe_update_description(db_path, image_id, ai_description=None, user_description=None):
    """Safely update an image description using a dedicated connection.
    
    This function creates a new connection for each update operation to prevent
    corruption issues. It also handles errors and performs retries if needed.
    
    Args:
        db_path (str): Path to the database file
        image_id (int): ID of the image to update
        ai_description (str, optional): AI-generated description to update
        user_description (str, optional): User-provided description to update
        
    Returns:
        bool: True if successful, False otherwise
    """
    max_retries = 3
    retry_count = 0
    
    while retry_count <= max_retries:
        conn = None
        try:
            # Create a new connection for this operation
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Build the update query
            updates = []
            params = []
            
            if ai_description is not None:
                updates.append("ai_description = ?")
                params.append(ai_description)
            
            if user_description is not None:
                updates.append("user_description = ?")
                params.append(user_description)
            
            if not updates:
                logger.warning("No description provided for update")
                return False
            
            # Use a transaction with immediate mode for better reliability
            cursor.execute("BEGIN IMMEDIATE TRANSACTION")
            
            # Update the image description
            query = f"UPDATE images SET {', '.join(updates)} WHERE image_id = ?"
            params.append(image_id)
            
            cursor.execute(query, params)
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.debug(f"Updated description for image ID: {image_id}")
                return True
            else:
                logger.warning(f"Image with ID {image_id} not found or no changes made")
                return False
                
        except sqlite3.Error as e:
            logger.error(f"Error updating image description (attempt {retry_count + 1}/{max_retries + 1}): {e}")
            
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            
            # Check if this is a corruption error
            if "database disk image is malformed" in str(e) or "database is locked" in str(e):
                # Try to repair the database
                if repair_database(db_path):
                    logger.info("Database repaired, retrying update operation")
                    retry_count += 1
                    continue
                else:
                    logger.error("Database repair failed")
                    return False
            
            # For other errors, just retry
            if retry_count < max_retries:
                retry_count += 1
                time.sleep(0.5)  # Wait a bit before retrying
                continue
            else:
                return False
                
        finally:
            # Always close the connection
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    return False

def repair_database(db_path):
    """Repair a corrupted database.
    
    This function performs a comprehensive database repair process including:
    1. Creating a backup of the current database
    2. Attempting SQLite's built-in integrity checks and recovery
    3. Trying to rebuild the database with VACUUM
    4. Creating a new database and recovering data if needed
    5. Restoring from backup as last resort
    
    Args:
        db_path (str): Path to the database file
        
    Returns:
        bool: True if repair was successful, False otherwise
    """
    logger.info(f"Attempting to repair database: {db_path}")
    
    # Create a backup of the current database - use a consistent name for a single backup file
    backup_path = f"{db_path}.backup"
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Created backup at {backup_path}")
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        # Continue anyway, we'll try to repair
    
    try:
        # Try to recover the database using SQLite's recovery mechanisms
        # Use the "?immutable=1" flag to open the database in read-only mode for the integrity check
        uri = f"file:{db_path}?immutable=1"
        try:
            recover_conn = sqlite3.connect(uri, uri=True)
            recover_cursor = recover_conn.cursor()
            
            # Run integrity check
            recover_cursor.execute("PRAGMA integrity_check")
            result = recover_cursor.fetchone()
            
            if result and result[0] == "ok":
                logger.info("Database integrity check passed")
                recover_conn.close()
                return True
                
            recover_conn.close()
        except sqlite3.Error as e:
            logger.warning(f"Initial integrity check failed: {e}")
        
        # Try using a temporary file for repair
        temp_db_path = f"{db_path}.temp"
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except:
                pass
        
        # Try to copy and rebuild with VACUUM
        try:
            logger.info("Attempting repair with database copy and VACUUM")
            shutil.copy2(db_path, temp_db_path)
            
            # Open the temporary database and try to repair it
            temp_conn = sqlite3.connect(temp_db_path)
            temp_cursor = temp_conn.cursor()
            
            # Set pragmas for recovery
            temp_cursor.execute("PRAGMA journal_mode = DELETE")
            temp_cursor.execute("PRAGMA synchronous = OFF")
            
            # Run VACUUM to rebuild the database
            logger.info("Running VACUUM to rebuild the database")
            temp_cursor.execute("VACUUM")
            temp_conn.commit()
            
            # Run integrity check 
            temp_cursor.execute("PRAGMA integrity_check")
            result = temp_cursor.fetchone()
            
            if result and result[0] == "ok":
                logger.info("Temporary database repaired successfully with VACUUM")
                temp_conn.close()
                
                # Replace the original database with the repaired one
                os.remove(db_path)
                shutil.copy2(temp_db_path, db_path)
                os.remove(temp_db_path)
                
                logger.info("Replaced original database with repaired version")
                return True
                
            temp_conn.close()
        except Exception as e:
            logger.warning(f"VACUUM repair attempt failed: {e}")
        
        # If we get here, try more drastic measures - create a new database and recover data
        logger.info("Attempting to create new database and recover data")
        
        # Import the database repair module here to avoid circular imports
        from src.database.db_repair import rebuild_database
        if rebuild_database(db_path):
            logger.info("Successfully rebuilt database with recovered data")
            return True
        
        # If that failed too, try to restore from backup
        logger.info("Attempting to restore from backup")
        
        # Remove the corrupted database
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
                logger.info("Removed corrupted database")
        except Exception as e:
            logger.error(f"Failed to remove corrupted database: {e}")
            return False
            
        # Copy the backup to the original location
        try:
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, db_path)
                logger.info("Restored database from backup")
                return True
            else:
                logger.error("Backup file not available for restore")
                return False
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error in database repair process: {e}")
        return False
