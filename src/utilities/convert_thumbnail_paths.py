#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utility to convert absolute thumbnail paths to relative paths in the database.
This makes the application more portable and better for backup/restore operations.
"""

import os
import sys
import logging
import sqlite3
from pathlib import Path

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(parent_dir)
sys.path.insert(0, project_root)

# Import database related modules
from src.database.db_manager import DatabaseManager
from src.database.db_connection import DatabaseConnection

# Set up logging
logger = logging.getLogger("STARNODESImageManager.utilities.convert_thumbnail_paths")

def get_default_db_path():
    """Get the default database path."""
    from src.config.config_manager import ConfigManager
    
    config_manager = ConfigManager()
    db_path = config_manager.get("database", "path")
    
    if not os.path.isabs(db_path):
        db_path = os.path.join(project_root, db_path)
    
    return db_path

def get_thumbnails_dir():
    """Get the thumbnails directory from configuration or fall back to default."""
    try:
        from src.config.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        # Get the configured thumbnails path
        thumbnails_path = config_manager.get("thumbnails", "path")
        
        if thumbnails_path:
            # Ensure it's an absolute path
            if not os.path.isabs(thumbnails_path):
                if getattr(sys, 'frozen', False):
                    # When running as executable, base path is executable location
                    exe_dir = os.path.dirname(sys.executable)
                    thumbnails_path = os.path.join(exe_dir, thumbnails_path)
                else:
                    # In script mode, resolve relative to project root
                    thumbnails_path = os.path.join(project_root, thumbnails_path)
            
            # Create the directory if it doesn't exist
            os.makedirs(thumbnails_path, exist_ok=True)
            logger.info(f"Using configured thumbnails directory: {thumbnails_path}")
            return thumbnails_path
    except Exception as e:
        logger.warning(f"Error getting thumbnails directory from config: {e}")
    
    # Fallback to default location
    default_path = os.path.join(project_root, "data", "thumbnails")
    os.makedirs(default_path, exist_ok=True)
    logger.info(f"Using default thumbnails directory: {default_path}")
    return default_path

def convert_to_relative_paths(db_path=None, dry_run=False, db_manager=None, progress_callback=None):
    """Convert absolute thumbnail paths to relative paths in the database.
    
    Args:
        db_path (str): Path to the database file. If None, use the default.
        dry_run (bool): If True, only show what would be changed but don't update the database.
        db_manager: Optional database manager instance to use instead of creating a new connection.
        progress_callback: Optional callback for progress updates (not used to avoid PyQt signal issues).
        
    Returns:
        tuple: (success count, unchanged count, error count)
    """
    # First check if we're running as executable
    is_frozen = getattr(sys, 'frozen', False)
    if is_frozen:
        logger.info("Running in executable mode, will ensure proper thumbnail paths")
    if db_path is None:
        db_path = get_default_db_path()
    
    thumbnails_dir = get_thumbnails_dir()
    logger.info(f"Thumbnails directory: {thumbnails_dir}")
    
    # Use the provided db_manager or create a new connection
    conn = None
    using_external_connection = False
    
    try:
        if db_manager is not None:
            # Use the existing database manager
            logger.debug("Using provided database manager")
            using_external_connection = True
            
            # Get all images with absolute thumbnail paths through db_manager
            images = db_manager.execute_query(
                "SELECT image_id, thumbnail_path FROM images WHERE thumbnail_path IS NOT NULL"
            )
        else:
            # Create a new connection if no db_manager provided
            logger.debug(f"Creating new database connection to {db_path}")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all images with absolute thumbnail paths
            cursor.execute("SELECT image_id, thumbnail_path FROM images WHERE thumbnail_path IS NOT NULL")
            images = cursor.fetchall()
        
        success_count = 0
        unchanged_count = 0
        error_count = 0
        
        for image in images:
            image_id = image['image_id']
            thumbnail_path = image['thumbnail_path']
            
            # Skip if already relative (no directory path)
            if thumbnail_path and not os.path.dirname(thumbnail_path):
                unchanged_count += 1
                continue
            
            # Skip if not an absolute path
            if not thumbnail_path or not os.path.isabs(thumbnail_path):
                unchanged_count += 1
                continue
            
            try:
                # Check if it's within the thumbnails directory
                try:
                    thumbnail_rel_path = os.path.relpath(thumbnail_path, thumbnails_dir)
                    if thumbnail_rel_path.startswith(".."):
                        # Path is outside of thumbnails directory, extract filename only
                        thumbnail_rel_path = os.path.basename(thumbnail_path)
                except ValueError:
                    # This can happen with different drives on Windows
                    # Just use the filename in this case
                    thumbnail_rel_path = os.path.basename(thumbnail_path)
                    
                # When running as an executable, always store just the filename for maximum portability
                if getattr(sys, 'frozen', False):
                    thumbnail_rel_path = os.path.basename(thumbnail_path)
                
                # Update database if not dry run
                if not dry_run:
                    if using_external_connection:
                        # Use the db_manager to update
                        db_manager.execute_query(
                            "UPDATE images SET thumbnail_path = ? WHERE image_id = ?",
                            (thumbnail_rel_path, image_id)
                        )
                    else:
                        # Use our own connection
                        cursor.execute(
                            "UPDATE images SET thumbnail_path = ? WHERE image_id = ?",
                            (thumbnail_rel_path, image_id)
                        )
                
                logger.info(f"Image {image_id}: {thumbnail_path} -> {thumbnail_rel_path}")
                success_count += 1
            except Exception as e:
                logger.error(f"Error processing image {image_id}: {e}")
                error_count += 1
        
        # Commit changes if not dry run and using our own connection
        if not dry_run and success_count > 0 and not using_external_connection and conn:
            conn.commit()
            logger.info(f"Committed {success_count} changes to the database")
        
        # When using external connection, it manages its own commits
        if using_external_connection and success_count > 0:
            logger.info(f"Updated {success_count} records using external database connection")
        
        return (success_count, unchanged_count, error_count)
    
    except Exception as e:
        logger.error(f"Database error: {e}")
        return (0, 0, 1)
    
    finally:
        # Only close the connection if we created it ourselves
        if conn and not using_external_connection:
            conn.close()

def setup_logging():
    """Set up logging configuration."""
    # Use the standardized data/logs directory instead of a separate logs directory
    log_dir = os.path.join(project_root, "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    logger.setLevel(logging.INFO)
    
    # File handler
    log_file = os.path.join(log_dir, "convert_thumbnails.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger.addHandler(console_handler)

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert absolute thumbnail paths to relative in the database")
    parser.add_argument("--db-path", help="Path to the database file (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Do not modify the database, just show what would change")
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging()
    
    logger.info("Starting thumbnail path conversion utility")
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made to the database")
    
    # Run the conversion
    success, unchanged, errors = convert_to_relative_paths(args.db_path, args.dry_run)
    
    logger.info(f"Conversion complete: {success} paths converted, {unchanged} unchanged, {errors} errors")
    
    if not args.dry_run and success > 0:
        logger.info("Database updated successfully")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
