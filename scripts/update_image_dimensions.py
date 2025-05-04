#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Update Image Dimensions Script

This script updates the width and height columns in the database
by reading the dimensions from the source image files.
"""

import os
import sys
import json
import logging
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from PIL import Image, UnidentifiedImageError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("StarImageBrowse.scripts.update_image_dimensions")

def get_image_dimensions(image_path):
    """Get the width and height of an image.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        tuple: (width, height) or (None, None) if the image cannot be read
    """
    try:
        with Image.open(image_path) as img:
            return img.width, img.height
    except (UnidentifiedImageError, FileNotFoundError, PermissionError, OSError) as e:
        logger.warning(f"Error reading image {image_path}: {e}")
        return None, None

def update_dimensions_in_db(db_path, batch_size=100, max_images=None):
    """Update image dimensions in the database.
    
    Args:
        db_path (str): Path to the SQLite database file
        batch_size (int): Number of images to process in each batch
        max_images (int, optional): Maximum number of images to process
        
    Returns:
        tuple: (success_count, failed_count, skipped_count)
    """
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return 0, 0, 0
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if width and height columns exist
        cursor.execute("PRAGMA table_info(images)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if "width" not in columns or "height" not in columns:
            logger.error("Width and height columns do not exist in the images table")
            return 0, 0, 0
        
        # Get images that need dimension updates
        query = """
            SELECT image_id, full_path 
            FROM images 
            WHERE (width IS NULL OR height IS NULL) 
            AND full_path IS NOT NULL
        """
        
        if max_images:
            query += f" LIMIT {max_images}"
            
        cursor.execute(query)
        images = cursor.fetchall()
        
        if not images:
            logger.info("No images found that need dimension updates")
            return 0, 0, 0
            
        logger.info(f"Found {len(images)} images that need dimension updates")
        
        # Process images in batches
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for i in range(0, len(images), batch_size):
            batch = images[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} of {(len(images) + batch_size - 1) // batch_size}")
            
            for image in batch:
                image_id = image['image_id']
                full_path = image['full_path']
                
                if not os.path.exists(full_path):
                    logger.warning(f"Image not found: {full_path}")
                    skipped_count += 1
                    continue
                
                width, height = get_image_dimensions(full_path)
                
                if width is None or height is None:
                    failed_count += 1
                    continue
                
                try:
                    cursor.execute(
                        "UPDATE images SET width = ?, height = ? WHERE image_id = ?",
                        (width, height, image_id)
                    )
                    success_count += 1
                    if success_count % 100 == 0:
                        logger.info(f"Updated {success_count} images so far")
                except sqlite3.Error as e:
                    logger.error(f"Error updating image {image_id}: {e}")
                    failed_count += 1
            
            # Commit after each batch
            conn.commit()
            
        logger.info(f"Completed dimension updates: {success_count} successful, {failed_count} failed, {skipped_count} skipped")
        return success_count, failed_count, skipped_count
        
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return 0, 0, 0
    finally:
        if conn:
            conn.close()

def get_db_path_from_settings():
    """Get the database path from settings.json.
    
    Returns:
        str: Database path from settings.json or None if not found
    """
    try:
        # Find settings.json in the app directory (two levels up from the scripts directory)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.dirname(os.path.dirname(script_dir))
        settings_path = os.path.join(app_dir, "settings.json")
        
        if not os.path.exists(settings_path):
            logger.error(f"Settings file not found: {settings_path}")
            return None
            
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            
        # Get database path from settings
        db_path = settings.get("database_path")
        if not db_path:
            logger.error("Database path not found in settings.json")
            return None
            
        # Make sure the path is absolute
        if not os.path.isabs(db_path):
            db_path = os.path.join(app_dir, db_path)
            
        return db_path
        
    except Exception as e:
        logger.error(f"Error reading settings.json: {e}")
        return None

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Update image dimensions in the database")
    parser.add_argument("--db_path", type=str, help="Path to the SQLite database file (overrides settings.json)")
    parser.add_argument("--max_images", type=int, help="Maximum number of images to process")
    args = parser.parse_args()
    
    # Use fixed batch size of 100 as requested
    batch_size = 100
    
    # Get database path from command line or settings.json
    db_path = args.db_path
    
    if not db_path:
        # Try to get database path from settings.json
        db_path = get_db_path_from_settings()
        
        if not db_path:
            # Ask for database path if not found in settings
            db_path = input("Enter the path to the SQLite database file: ")
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return
    
    start_time = datetime.now()
    logger.info(f"Starting dimension update at {start_time}")
    
    success, failed, skipped = update_dimensions_in_db(
        db_path, 
        batch_size=batch_size,  # Use fixed batch size of 100
        max_images=args.max_images
    )
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info(f"Dimension update completed in {duration}")
    logger.info(f"Summary: {success} updated, {failed} failed, {skipped} skipped")

if __name__ == "__main__":
    main()
