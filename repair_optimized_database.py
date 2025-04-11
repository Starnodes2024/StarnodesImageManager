#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Repair optimized database for StarImageBrowse

This script fixes issues with the optimized database that prevent updating descriptions.
It creates a new properly optimized database that maintains full functionality.
"""

import os
import sys
import shutil
import logging
import sqlite3
import time
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("StarImageBrowse.database.repair_optimized")

def get_database_path():
    """Get the path to the database file."""
    # Default database path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_db_path = os.path.join(base_dir, "data", "star_image_browse.db")
    
    if os.path.exists(default_db_path):
        return default_db_path
    else:
        logger.error(f"Database not found at {default_db_path}")
        return None

def backup_database(db_path):
    """Create a backup of the database."""
    backup_path = f"{db_path}.backup_before_repair_{int(time.time())}"
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Created backup at {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return None

def create_schema(conn, cursor):
    """Create the database schema."""
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
    
    # Create performance indexes
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_images_folder_id ON images (folder_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_images_last_modified ON images (last_modified_date DESC)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_images_search_modified ON images (ai_description, last_modified_date DESC)
    ''')
    
    conn.commit()
    logger.info("Database schema created successfully")

def create_virtual_tables(conn, cursor):
    """Create virtual tables for full-text search."""
    try:
        # Create virtual table for full-text search on descriptions
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS image_fts USING fts5(
                image_id UNINDEXED,
                ai_description,
                user_description,
                content='images',
                content_rowid='image_id'
            )
        ''')
        
        # Create triggers to keep FTS table in sync with the images table
        # Trigger for INSERT
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS images_ai_insert AFTER INSERT ON images BEGIN
                INSERT INTO image_fts(image_id, ai_description, user_description)
                VALUES (new.image_id, new.ai_description, new.user_description);
            END
        ''')
        
        # Trigger for UPDATE
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS images_ai_update AFTER UPDATE ON images BEGIN
                UPDATE image_fts SET 
                    ai_description = new.ai_description,
                    user_description = new.user_description
                WHERE image_id = new.image_id;
            END
        ''')
        
        # Trigger for DELETE
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS images_ai_delete AFTER DELETE ON images BEGIN
                DELETE FROM image_fts WHERE image_id = old.image_id;
            END
        ''')
        
        conn.commit()
        logger.info("Virtual tables created successfully")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error creating virtual tables: {e}")
        conn.rollback()
        return False

def set_safe_performance_pragmas(conn, cursor):
    """Set safe performance PRAGMA settings."""
    try:
        # Set synchronous mode to NORMAL for better performance with reliability
        cursor.execute("PRAGMA synchronous=NORMAL")
        
        # Set journal mode to DELETE for better compatibility
        cursor.execute("PRAGMA journal_mode=DELETE")
        
        # Set temp store to MEMORY for better performance
        cursor.execute("PRAGMA temp_store=MEMORY")
        
        # Set cache size to 5000 pages (about 20MB)
        cursor.execute("PRAGMA cache_size=5000")
        
        # Run ANALYZE to update statistics
        cursor.execute("ANALYZE")
        
        logger.info("Safe performance PRAGMAs set successfully")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error setting performance PRAGMAs: {e}")
        return False

def copy_data(source_db_path, dest_conn, dest_cursor):
    """Copy data from source database to destination database."""
    try:
        # Connect to source database
        source_conn = sqlite3.connect(source_db_path)
        source_conn.row_factory = sqlite3.Row
        source_cursor = source_conn.cursor()
        
        # Copy folders
        logger.info("Copying folders...")
        source_cursor.execute("SELECT * FROM folders")
        folders = source_cursor.fetchall()
        
        for folder in folders:
            folder_dict = dict(folder)
            dest_cursor.execute(
                "INSERT INTO folders (folder_id, path, enabled, last_scan_time) VALUES (?, ?, ?, ?)",
                (
                    folder_dict['folder_id'],
                    folder_dict['path'],
                    folder_dict['enabled'],
                    folder_dict['last_scan_time']
                )
            )
        
        # Copy images in batches to avoid memory issues
        logger.info("Copying images...")
        batch_size = 500
        offset = 0
        total_copied = 0
        
        while True:
            source_cursor.execute(f"SELECT * FROM images LIMIT {batch_size} OFFSET {offset}")
            images = source_cursor.fetchall()
            
            if not images:
                break
                
            for image in images:
                image_dict = dict(image)
                dest_cursor.execute(
                    """INSERT INTO images (
                        image_id, folder_id, filename, full_path, file_size, file_hash,
                        creation_date, last_modified_date, thumbnail_path,
                        ai_description, user_description, last_scanned
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        image_dict['image_id'],
                        image_dict['folder_id'],
                        image_dict['filename'],
                        image_dict['full_path'],
                        image_dict['file_size'],
                        image_dict['file_hash'],
                        image_dict['creation_date'],
                        image_dict['last_modified_date'],
                        image_dict['thumbnail_path'],
                        image_dict['ai_description'],
                        image_dict['user_description'],
                        image_dict['last_scanned']
                    )
                )
            
            total_copied += len(images)
            logger.info(f"Copied {total_copied} images so far...")
            offset += batch_size
            dest_conn.commit()  # Commit each batch
        
        # Populate FTS table
        logger.info("Populating full-text search table...")
        dest_cursor.execute('''
            INSERT INTO image_fts(image_id, ai_description, user_description)
            SELECT image_id, ai_description, user_description FROM images
        ''')
        
        dest_conn.commit()
        source_conn.close()
        
        logger.info(f"Successfully copied {total_copied} images and {len(folders)} folders")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error copying data: {e}")
        return False

def verify_database(db_path):
    """Verify the database integrity."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Run integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        
        if result and result[0] == "ok":
            logger.info("Database integrity check passed")
            
            # Test updating a description
            cursor.execute("SELECT image_id FROM images LIMIT 1")
            result = cursor.fetchone()
            
            if result:
                image_id = result[0]
                test_desc = f"Test description {time.time()}"
                
                cursor.execute(
                    "UPDATE images SET ai_description = ? WHERE image_id = ?",
                    (test_desc, image_id)
                )
                conn.commit()
                
                # Verify update
                cursor.execute("SELECT ai_description FROM images WHERE image_id = ?", (image_id,))
                updated = cursor.fetchone()
                
                if updated and updated[0] == test_desc:
                    logger.info("Database update test passed")
                    conn.close()
                    return True
                else:
                    logger.error("Database update test failed")
            else:
                logger.warning("No images found to test update")
                conn.close()
                return True  # Empty database is still valid
        else:
            logger.error(f"Database integrity check failed: {result[0] if result else 'Unknown error'}")
        
        conn.close()
        return False
    except sqlite3.Error as e:
        logger.error(f"Error verifying database: {e}")
        return False

def repair_optimized_database():
    """Repair the optimized database."""
    # Get database path
    db_path = get_database_path()
    if not db_path:
        logger.error("Database path not found")
        return False
    
    # Create backup
    backup_path = backup_database(db_path)
    if not backup_path:
        logger.error("Failed to create backup, aborting repair")
        return False
    
    # Create new database file
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
        
        # Copy data from old database
        if not copy_data(db_path, new_conn, new_cursor):
            logger.error("Failed to copy data to new database")
            new_conn.close()
            return False
        
        # Create virtual tables
        if not create_virtual_tables(new_conn, new_cursor):
            logger.warning("Failed to create virtual tables, continuing anyway")
        
        # Set safe performance pragmas
        if not set_safe_performance_pragmas(new_conn, new_cursor):
            logger.warning("Failed to set performance pragmas, continuing anyway")
        
        # Close connection
        new_conn.close()
        
        # Verify new database
        if not verify_database(new_db_path):
            logger.error("New database verification failed")
            return False
        
        # Replace old database with new one
        try:
            os.replace(new_db_path, db_path)
            logger.info(f"Successfully replaced old database with repaired version")
            return True
        except Exception as e:
            logger.error(f"Failed to replace old database: {e}")
            logger.info(f"Repaired database is available at: {new_db_path}")
            return False
        
    except Exception as e:
        logger.error(f"Error repairing database: {e}")
        return False

if __name__ == "__main__":
    print("StarImageBrowse Database Repair Utility")
    print("======================================")
    print("This utility will repair the optimized database to fix issues with updating descriptions.")
    print("A backup of your current database will be created before any changes are made.")
    
    proceed = input("Do you want to proceed? (y/n): ").lower().strip()
    if proceed == 'y':
        if repair_optimized_database():
            print("\nDatabase repair completed successfully!")
            print("You can now restart StarImageBrowse and the database should work correctly.")
        else:
            print("\nDatabase repair failed. Please check the error messages above.")
    else:
        print("Operation cancelled.")
