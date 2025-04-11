#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database repair utility for StarImageBrowse

This script will repair a corrupted SQLite database by:
1. Creating a backup of the current database
2. Creating a new database with the correct schema
3. Attempting to recover data from the corrupted database
4. Replacing the corrupted database with the repaired one

Run this script directly to repair the database.
"""

import os
import sys
import shutil
import sqlite3
import logging
import time
from datetime import datetime
from pathlib import Path

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Setup logging
log_dir = os.path.join(current_dir, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"repair_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DatabaseRepair")

def create_schema(conn, cursor):
    """Create the database schema.
    
    Args:
        conn: Database connection
        cursor: Database cursor
    """
    # Create folders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            folder_id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            enabled INTEGER DEFAULT 1,
            last_scan_time TIMESTAMP
        )
    ''')
    
    # Create images table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            image_id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_id INTEGER,
            filename TEXT NOT NULL,
            full_path TEXT UNIQUE NOT NULL,
            file_size INTEGER,
            file_hash TEXT,
            creation_date TIMESTAMP,
            last_modified_date TIMESTAMP,
            thumbnail_path TEXT,
            ai_description TEXT,
            user_description TEXT,
            last_scanned TIMESTAMP,
            FOREIGN KEY (folder_id) REFERENCES folders (folder_id)
        )
    ''')
    
    # Create index on full_path for faster lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_images_full_path ON images (full_path)
    ''')
    
    # Create index for searching descriptions
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_images_ai_description ON images (ai_description)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_images_user_description ON images (user_description)
    ''')
    
    conn.commit()

def recover_data(old_db_path, new_conn, new_cursor):
    """Try to recover data from a corrupted database.
    
    Args:
        old_db_path (str): Path to the corrupted database
        new_conn: Connection to the new database
        new_cursor: Cursor for the new database
        
    Returns:
        dict: Statistics about recovered items
    """
    recovered_stats = {
        "folders": 0,
        "images": 0
    }
    
    try:
        # Try to connect to old database in read-only mode with recovery mode
        uri = f"file:{old_db_path}?mode=ro"
        old_conn = sqlite3.connect(uri, uri=True)
        old_cursor = old_conn.cursor()
        
        # Try to recover folders
        try:
            old_cursor.execute("SELECT * FROM folders")
            folders = old_cursor.fetchall()
            
            for folder in folders:
                try:
                    # Ensure we have at least the required fields
                    if len(folder) >= 2:
                        folder_id = folder[0]
                        path = folder[1]
                        enabled = folder[2] if len(folder) > 2 else 1
                        
                        new_cursor.execute(
                            "INSERT INTO folders (folder_id, path, enabled) VALUES (?, ?, ?)",
                            (folder_id, path, enabled)
                        )
                        recovered_stats["folders"] += 1
                except Exception as e:
                    logger.warning(f"Failed to recover folder: {e}")
        except Exception as e:
            logger.warning(f"Failed to recover folders: {e}")
        
        # Try to recover images
        try:
            # Try to get all images, but limit to 10000 to avoid memory issues
            old_cursor.execute("SELECT * FROM images LIMIT 10000")
            images = old_cursor.fetchall()
            
            for image in images:
                try:
                    # Ensure we have at least the required fields
                    if len(image) >= 4:
                        # Extract the fields we need
                        image_id = image[0]
                        folder_id = image[1]
                        filename = image[2]
                        full_path = image[3]
                        
                        # Get optional fields with defaults
                        thumbnail_path = image[8] if len(image) > 8 else None
                        ai_description = image[9] if len(image) > 9 else None
                        user_description = image[10] if len(image) > 10 else None
                        
                        # Insert into new database
                        new_cursor.execute(
                            """INSERT INTO images 
                               (image_id, folder_id, filename, full_path, thumbnail_path, 
                                ai_description, user_description) 
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (image_id, folder_id, filename, full_path, thumbnail_path,
                             ai_description, user_description)
                        )
                        recovered_stats["images"] += 1
                except Exception as e:
                    logger.warning(f"Failed to recover image: {e}")
        except Exception as e:
            logger.warning(f"Failed to recover images: {e}")
        
        # Close old connection
        old_conn.close()
        
    except Exception as e:
        logger.warning(f"Failed to connect to corrupted database for recovery: {e}")
    
    return recovered_stats

def repair_database(db_path):
    """Attempt to repair a corrupted database by creating a new one and recovering data.
    
    Args:
        db_path (str): Path to the database file
        
    Returns:
        bool: True if repair was successful, False otherwise
    """
    logger.info(f"Starting database repair for: {db_path}")
    
    # Create backup of corrupted database
    backup_path = f"{db_path}.backup_{int(time.time())}"
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Created backup of corrupted database at {backup_path}")
    except Exception as e:
        logger.error(f"Failed to create backup of corrupted database: {e}")
        return False
    
    # Create a new database file
    new_db_path = f"{db_path}.new"
    if os.path.exists(new_db_path):
        try:
            os.remove(new_db_path)
        except Exception as e:
            logger.error(f"Failed to remove existing new database file: {e}")
            return False
    
    try:
        # Create new database with schema
        new_conn = sqlite3.connect(new_db_path)
        new_cursor = new_conn.cursor()
        
        # Create schema in new database
        create_schema(new_conn, new_cursor)
        
        # Try to recover data from old database
        recovered_items = recover_data(db_path, new_conn, new_cursor)
        
        # Commit changes and close new database
        new_conn.commit()
        new_conn.close()
        
        # Replace old database with new one
        try:
            os.remove(db_path)
            shutil.move(new_db_path, db_path)
            
            logger.info(f"Database repair completed successfully")
            logger.info(f"Recovered {recovered_items['folders']} folders and {recovered_items['images']} images")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to replace corrupted database with repaired one: {e}")
            logger.info(f"The repaired database is available at: {new_db_path}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to repair database: {e}")
        return False

def main():
    """Main function to repair the database."""
    from src.config.config_manager import ConfigManager
    
    # Load configuration
    config_manager = ConfigManager()
    
    # Get database path
    db_path = config_manager.get("database", "path")
    if not os.path.isabs(db_path):
        db_path = os.path.join(current_dir, db_path)
    
    logger.info(f"Database path: {db_path}")
    
    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database file does not exist: {db_path}")
        print(f"ERROR: Database file does not exist: {db_path}")
        return False
    
    # Repair database
    success = repair_database(db_path)
    
    if success:
        logger.info("Database repair completed successfully")
        print("Database repair completed successfully")
        return True
    else:
        logger.error("Failed to repair database")
        print("Failed to repair database. Check the logs for details.")
        return False

if __name__ == "__main__":
    main()
