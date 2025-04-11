#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utility script to update missing metadata for existing images.
Updates format, last_modified, and other metadata fields in the database.
"""

import os
import sys
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from PIL import Image, UnidentifiedImageError

# Add the project root to the path so we can import project modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.database.db_manager import DatabaseManager
from src.config.config_manager import ConfigManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("StarImageBrowse.update_metadata")

def update_image_metadata(db_path, progress_callback=None):
    """
    Update metadata for all images in the database.
    
    Args:
        db_path (str): Path to the database
        progress_callback (callable, optional): Callback for progress updates (current, total)
        
    Returns:
        dict: Statistics about the update process
    """
    logger.info(f"Updating metadata for images in database: {db_path}")
    
    stats = {
        "total": 0,
        "format_updated": 0,
        "date_updated": 0,
        "failed": 0,
        "columns_added": False
    }
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if the required columns exist, add them if they don't
        logger.info("Checking if required columns exist...")
        cursor.execute("PRAGMA table_info(images)")
        columns = {row[1] for row in cursor.fetchall()}
        
        # Add format column if it doesn't exist
        if "format" not in columns:
            logger.info("Adding format column to images table")
            cursor.execute("ALTER TABLE images ADD COLUMN format TEXT")
            stats["columns_added"] = True
        
        # Add date_added column if it doesn't exist
        if "date_added" not in columns:
            logger.info("Adding date_added column to images table")
            # First add the column without a default value
            cursor.execute("ALTER TABLE images ADD COLUMN date_added TIMESTAMP")
            # Then update all existing records with current timestamp
            cursor.execute("UPDATE images SET date_added = CURRENT_TIMESTAMP WHERE date_added IS NULL")
            stats["columns_added"] = True
        
        # Commit these schema changes before proceeding
        conn.commit()
        
        # Get all images - use a more efficient query that only fetches what we need
        cursor.execute("SELECT image_id, full_path, format, date_added, last_modified_date FROM images")
        images = cursor.fetchall()
        
        total_images = len(images)
        stats["total"] = total_images
        logger.info(f"Found {stats['total']} images in database")
        
        # Process in batches for better performance
        batch_size = 100
        batch_count = 0
        batch_updates = []
        
        # Update progress at regular intervals
        progress_interval = max(1, min(1000, total_images // 100))  # Report progress at most 100 times
        
        # Process each image
        for i, image in enumerate(images):
            try:
                image_id = image["image_id"]
                full_path = image["full_path"]
                current_format = image["format"]
                date_added = image["date_added"]
                last_modified = image["last_modified_date"]
                
                # Skip processing if this image already has all metadata
                if current_format and date_added and last_modified:
                    continue
                
                # Check if file exists
                if not os.path.exists(full_path):
                    logger.debug(f"Image file not found: {full_path}")
                    continue
                
                update_data = {"id": image_id}
                updates_needed = False
                
                # Update format if missing
                if not current_format:
                    try:
                        with Image.open(full_path) as img:
                            image_format = img.format
                            if image_format:
                                update_data["format"] = image_format
                                updates_needed = True
                                stats["format_updated"] += 1
                    except Exception as e:
                        logger.debug(f"Error getting format for {full_path}: {e}")
                
                # Update dates if missing
                if not date_added:
                    try:
                        ctime = os.path.getctime(full_path)
                        update_data["date_added"] = datetime.fromtimestamp(ctime)
                        updates_needed = True
                        stats["date_updated"] += 1
                    except Exception:
                        # Fall back to current time
                        update_data["date_added"] = datetime.now()
                        updates_needed = True
                        stats["date_updated"] += 1
                
                if not last_modified:
                    try:
                        mtime = os.path.getmtime(full_path)
                        update_data["last_modified"] = datetime.fromtimestamp(mtime)
                        updates_needed = True
                        stats["date_updated"] += 1
                    except Exception:
                        # Fall back to current time
                        update_data["last_modified"] = datetime.now()
                        updates_needed = True
                        stats["date_updated"] += 1
                
                # Add to batch if updates are needed
                if updates_needed:
                    batch_updates.append(update_data)
                    batch_count += 1
                
                # Process batch if we've reached batch size
                if len(batch_updates) >= batch_size:
                    _execute_batch_update(cursor, batch_updates)
                    batch_updates = []
                    # Commit every 1000 images to avoid transaction getting too large
                    if batch_count % 1000 == 0:
                        logger.debug(f"Committing changes after {batch_count} updates")
                        conn.commit()
                
                # Update progress
                if progress_callback and i % progress_interval == 0:
                    progress_callback(i + 1, total_images)
                    
            except Exception as e:
                logger.error(f"Error updating metadata for image {image.get('image_id')}: {e}")
                stats["failed"] += 1
        
        # Process any remaining images in the batch
        if batch_updates:
            _execute_batch_update(cursor, batch_updates)
        
        # Final progress update
        if progress_callback:
            progress_callback(total_images, total_images)
        
        # Commit final changes
        conn.commit()
        logger.info(f"Updated format for {stats['format_updated']} images")
        logger.info(f"Updated dates for {stats['date_updated']} images")
        logger.info(f"Failed to update {stats['failed']} images")
    
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
        stats["failed"] = stats["total"]
        raise
    
    finally:
        if 'conn' in locals() and conn:
            conn.close()
    
    return stats


def _execute_batch_update(cursor, batch_updates):
    """
    Execute batch updates for multiple images.
    
    Args:
        cursor: Database cursor
        batch_updates: List of dicts with update data
    """
    for update in batch_updates:
        image_id = update["id"]
        set_clauses = []
        params = []
        
        # Build SQL update for this image
        if "format" in update:
            set_clauses.append("format = ?")
            params.append(update["format"])
        
        if "date_added" in update:
            set_clauses.append("date_added = ?")
            params.append(update["date_added"])
        
        if "last_modified" in update:
            set_clauses.append("last_modified_date = ?")
            params.append(update["last_modified"])
        
        if set_clauses:
            # Execute the update
            params.append(image_id)  # Add image_id for WHERE clause
            update_query = f"UPDATE images SET {', '.join(set_clauses)} WHERE image_id = ?"
            cursor.execute(update_query, params)

def main():
    """Main function to run the metadata update."""
    try:
        # Load configuration
        config_manager = ConfigManager()
        db_path = config_manager.get_database_path()
        
        if not db_path or not os.path.exists(db_path):
            logger.error(f"Database file not found: {db_path}")
            return False
        
        # Update metadata
        stats = update_image_metadata(db_path)
        
        # Report results
        print("\nMetadata Update Results:")
        print(f"Total images processed: {stats['total']}")
        print(f"Format information updated: {stats['format_updated']}")
        print(f"Date information updated: {stats['date_updated']}")
        print(f"Failed updates: {stats['failed']}")
        
        if stats["failed"] == 0:
            print("\nMetadata update completed successfully!")
            return True
        else:
            print(f"\nMetadata update completed with {stats['failed']} failures.")
            return False
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
