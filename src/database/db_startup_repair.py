#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database startup repair for StarImageBrowse
This module ensures the database is in a good state at application startup.
"""

import os
import logging
import sqlite3
import shutil
import time
from pathlib import Path

logger = logging.getLogger("StarImageBrowse.database.db_startup_repair")

def ensure_database_integrity(db_path):
    """
    Ensure the database is in a good state at application startup.
    This function is called before any database operations are performed.
    
    Args:
        db_path (str): Path to the database file
        
    Returns:
        bool: True if database is now in a good state, False otherwise
    """
    logger.info(f"Checking database integrity at startup: {db_path}")
    
    # Check if database exists
    if not os.path.exists(db_path):
        logger.info("Database does not exist, will be created when needed")
        return True
    
    # Create backup of current database - use a consistent name for a single backup file
    backup_path = f"{db_path}.backup"
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Created backup at {backup_path}")
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        # Continue anyway, we'll try to repair
    
    # Try to open the database and check integrity
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Run integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        
        if result and result[0] == "ok":
            logger.info("Database integrity check passed")
            conn.close()
            return True
        else:
            logger.warning(f"Database integrity check failed: {result[0] if result else 'Unknown error'}")
            conn.close()
            
            # Database is corrupted, rebuild it
            return rebuild_database(db_path, backup_path)
            
    except sqlite3.Error as e:
        logger.error(f"Error checking database integrity: {e}")
        # Database is likely corrupted, rebuild it
        return rebuild_database(db_path, backup_path)

def rebuild_database(db_path, backup_path):
    """
    Rebuild the database from scratch or from a backup.
    
    Args:
        db_path (str): Path to the database file
        backup_path (str): Path to the backup file
        
    Returns:
        bool: True if rebuild was successful, False otherwise
    """
    logger.info("Rebuilding database from scratch")
    
    try:
        # Remove the corrupted database
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info("Removed corrupted database")
        
        # Create a new database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create the schema
        create_schema(conn, cursor)
        
        # Try to recover data from backup
        try:
            recover_data(backup_path, conn, cursor)
        except Exception as e:
            logger.warning(f"Could not recover data from backup: {e}")
            # Continue with empty database
        
        # Set optimal performance settings
        set_performance_settings(conn, cursor)
        
        # Close connection
        conn.close()
        
        logger.info("Database rebuilt successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error rebuilding database: {e}")
        return False

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
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_images_search_modified_user ON images (user_description, last_modified_date DESC)
    ''')
    
    # Create virtual table for full-text search
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
    logger.info("Database schema created successfully")

def recover_data(backup_path, conn, cursor):
    """Try to recover data from a backup database."""
    if not os.path.exists(backup_path):
        logger.warning(f"Backup file not found: {backup_path}")
        return
    
    logger.info(f"Attempting to recover data from backup: {backup_path}")
    
    try:
        # Connect to backup database
        backup_conn = sqlite3.connect(backup_path)
        backup_conn.row_factory = sqlite3.Row
        backup_cursor = backup_conn.cursor()
        
        # Recover folders
        try:
            backup_cursor.execute("SELECT * FROM folders")
            folders = backup_cursor.fetchall()
            
            for folder in folders:
                folder_dict = dict(folder)
                cursor.execute(
                    "INSERT INTO folders (folder_id, path, enabled, last_scan_time) VALUES (?, ?, ?, ?)",
                    (
                        folder_dict['folder_id'],
                        folder_dict['path'],
                        folder_dict['enabled'],
                        folder_dict['last_scan_time']
                    )
                )
            
            logger.info(f"Recovered {len(folders)} folders")
        except Exception as e:
            logger.warning(f"Error recovering folders: {e}")
        
        # Recover images in batches
        try:
            batch_size = 500
            offset = 0
            total_recovered = 0
            
            while True:
                backup_cursor.execute(f"SELECT * FROM images LIMIT {batch_size} OFFSET {offset}")
                images = backup_cursor.fetchall()
                
                if not images:
                    break
                
                for image in images:
                    image_dict = dict(image)
                    try:
                        cursor.execute(
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
                        total_recovered += 1
                    except sqlite3.Error as e:
                        # Skip this image if there's an error
                        logger.warning(f"Error recovering image {image_dict.get('image_id')}: {e}")
                
                offset += batch_size
                conn.commit()  # Commit each batch
            
            logger.info(f"Recovered {total_recovered} images")
            
            # Populate FTS table
            cursor.execute('''
                INSERT INTO image_fts(image_id, ai_description, user_description)
                SELECT image_id, ai_description, user_description FROM images
                WHERE image_id NOT IN (SELECT image_id FROM image_fts)
            ''')
            
        except Exception as e:
            logger.warning(f"Error recovering images: {e}")
        
        backup_conn.close()
        conn.commit()
        
    except Exception as e:
        logger.error(f"Error recovering data from backup: {e}")
        raise

def set_performance_settings(conn, cursor):
    """Set optimal performance settings for the database."""
    try:
        # Set synchronous mode to NORMAL for better performance with good reliability
        cursor.execute("PRAGMA synchronous=NORMAL")
        
        # Set journal mode to DELETE for better compatibility
        cursor.execute("PRAGMA journal_mode=DELETE")
        
        # Set temp store to MEMORY for better performance
        cursor.execute("PRAGMA temp_store=MEMORY")
        
        # Set cache size to 5000 pages (about 20MB) - conservative but effective
        cursor.execute("PRAGMA cache_size=5000")
        
        # Run ANALYZE to update statistics
        cursor.execute("ANALYZE")
        
        conn.commit()
        logger.info("Performance settings applied successfully")
        
    except sqlite3.Error as e:
        logger.error(f"Error setting performance settings: {e}")
        raise
