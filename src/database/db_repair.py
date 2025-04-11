#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database repair utility for StarImageBrowse
Provides functions to check and repair corrupted databases.
"""

import os
import shutil
import logging
import sqlite3
import time
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox

logger = logging.getLogger("StarImageBrowse.database.db_repair")

def check_database_integrity(db_path):
    """Check if the database file is corrupted.
    
    Args:
        db_path (str): Path to the database file
        
    Returns:
        bool: True if database is OK, False if corrupted, None if check failed
    """
    try:
        # Open a separate connection for integrity check
        temp_conn = sqlite3.connect(db_path)
        temp_cursor = temp_conn.cursor()
        
        # Run integrity check
        temp_cursor.execute("PRAGMA integrity_check")
        result = temp_cursor.fetchone()
        
        # Close connection
        temp_conn.close()
        
        # Check result
        if result and result[0] == "ok":
            logger.info("Database integrity check passed")
            return True
        else:
            logger.error(f"Database integrity check failed: {result[0] if result else 'Unknown error'}")
            return False
    except sqlite3.Error as e:
        logger.error(f"Error checking database integrity: {e}")
        # If we can't even run the check, assume database might be corrupted
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking database integrity: {e}")
        return False

def repair_database(db_path, parent_widget=None):
    """Attempt to repair a corrupted database by creating a new one and recovering data.
    
    Args:
        db_path (str): Path to the database file
        parent_widget: Parent widget for message boxes (optional)
        
    Returns:
        bool: True if repair was successful, False otherwise
    """
    logger.warning(f"Attempting to repair corrupted database: {db_path}")
    
    # Show warning to user
    if parent_widget:
        response = QMessageBox.warning(
            parent_widget,
            "Database Corruption Detected",
            "The image database appears to be corrupted. Would you like to attempt to repair it?\n\n"
            "A backup of your current database will be created before repair.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if response != QMessageBox.StandardButton.Yes:
            logger.info("User declined database repair")
            return False
    
    # Create backup of corrupted database - use a consistent name for a single backup file
    backup_path = f"{db_path}.backup"
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"Created backup of corrupted database at {backup_path}")
        
        if parent_widget:
            QMessageBox.information(
                parent_widget,
                "Database Backup Created",
                f"A backup of your database has been created at:\n{backup_path}",
                QMessageBox.StandardButton.Ok
            )
    except Exception as e:
        logger.error(f"Failed to create backup of corrupted database: {e}")
        if parent_widget:
            QMessageBox.critical(
                parent_widget,
                "Backup Failed",
                f"Failed to create a backup of the database: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
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
            
            logger.info("Database repair completed successfully")
            
            if parent_widget:
                QMessageBox.information(
                    parent_widget,
                    "Database Repair Complete",
                    f"Database repair completed successfully.\n\n"
                    f"Recovered {recovered_items['folders']} folders and {recovered_items['images']} images.",
                    QMessageBox.StandardButton.Ok
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to replace corrupted database with repaired one: {e}")
            if parent_widget:
                QMessageBox.critical(
                    parent_widget,
                    "Repair Failed",
                    f"Failed to replace corrupted database with repaired one: {str(e)}\n\n"
                    f"The repaired database is available at: {new_db_path}",
                    QMessageBox.StandardButton.Ok
                )
            return False
            
    except Exception as e:
        logger.error(f"Failed to repair database: {e}")
        if parent_widget:
            QMessageBox.critical(
                parent_widget,
                "Repair Failed",
                f"Failed to repair database: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
        return False

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
            width INTEGER,
            height INTEGER,
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
    
    # Create index for image dimensions
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_images_dimensions ON images (width, height)
    ''')
    
    # Create Catalogs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS catalogs (
            catalog_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create Image-Catalog mapping table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS image_catalog_mapping (
            mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            catalog_id INTEGER NOT NULL,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (image_id) REFERENCES images (image_id) ON DELETE CASCADE,
            FOREIGN KEY (catalog_id) REFERENCES catalogs (catalog_id) ON DELETE CASCADE,
            UNIQUE(image_id, catalog_id)
        )
    ''')
    
    # Create indexes for the catalog tables
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_catalog_mapping_image_id ON image_catalog_mapping (image_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_catalog_mapping_catalog_id ON image_catalog_mapping (catalog_id)
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
        "images": 0,
        "catalogs": 0,
        "catalog_mappings": 0
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
            # Try to get total number of images first
            try:
                old_cursor.execute("SELECT COUNT(*) FROM images")
                total_images = old_cursor.fetchone()[0]
                logger.info(f"Found {total_images} images to recover")
            except Exception as e:
                # If count fails, we'll proceed without knowing the total
                logger.warning(f"Failed to get total image count: {e}")
                total_images = None
                
            # Determine batch size based on estimated database size
            if total_images and total_images > 100000:
                batch_size = 250
            elif total_images and total_images > 50000:
                batch_size = 500
            else:
                batch_size = 1000
                
            # Process images in batches to avoid memory issues
            logger.info(f"Recovering images using batch size of {batch_size}...")
            offset = 0
            has_more_images = True
            total_recovered = 0
            progress_interval = 5000  # Report progress every 5000 images
            next_progress_report = progress_interval
                
            # Continue fetching batches until no more images
            while has_more_images:
                try:
                    old_cursor.execute(f"SELECT * FROM images LIMIT {batch_size} OFFSET {offset}")
                    images = old_cursor.fetchall()
                    
                    if not images:
                        has_more_images = False
                        break
                        
                    # Process this batch
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
                                
                                # Get width and height if available
                                width = image[12] if len(image) > 12 else None
                                height = image[13] if len(image) > 13 else None
                                
                                # Insert into new database
                                new_cursor.execute(
                                    """INSERT INTO images 
                                       (image_id, folder_id, filename, full_path, thumbnail_path, 
                                        ai_description, user_description, width, height) 
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                    (image_id, folder_id, filename, full_path, thumbnail_path,
                                     ai_description, user_description, width, height)
                                )
                                recovered_stats["images"] += 1
                        except Exception as e:
                            logger.warning(f"Failed to recover image: {e}")
                    
                    # Update counters and commit batch
                    total_recovered += len(images)
                    if total_recovered >= next_progress_report:
                        if total_images:
                            percentage = (total_recovered / total_images) * 100
                            logger.info(f"Recovered {total_recovered}/{total_images} images ({percentage:.1f}%)...")
                        else:
                            logger.info(f"Recovered {total_recovered} images so far...")
                        next_progress_report = total_recovered + progress_interval
                    
                    offset += batch_size
                    new_conn.commit()  # Commit each batch as we go
                except Exception as e:
                    logger.warning(f"Error processing batch at offset {offset}: {e}")
                    offset += batch_size  # Skip problematic batch and continue
        except Exception as e:
            logger.warning(f"Failed to recover images: {e}")
        
        # Try to recover catalogs
        try:
            old_cursor.execute("SELECT * FROM catalogs")
            catalogs = old_cursor.fetchall()
            
            logger.info(f"Found {len(catalogs)} catalogs to recover")
            
            for catalog in catalogs:
                try:
                    # Ensure we have at least the required fields
                    if len(catalog) >= 2:
                        catalog_id = catalog[0]
                        name = catalog[1]
                        description = catalog[2] if len(catalog) > 2 else None
                        created_date = catalog[3] if len(catalog) > 3 else None
                        
                        new_cursor.execute(
                            """INSERT INTO catalogs 
                               (catalog_id, name, description, created_date) 
                               VALUES (?, ?, ?, ?)""",
                            (catalog_id, name, description, created_date)
                        )
                        recovered_stats["catalogs"] += 1
                except Exception as e:
                    logger.warning(f"Failed to recover catalog: {e}")
        except Exception as e:
            logger.warning(f"Failed to recover catalogs: {e}")
        
        # Try to recover catalog-image mappings
        try:
            old_cursor.execute("SELECT * FROM image_catalog_mapping")
            mappings = old_cursor.fetchall()
            
            logger.info(f"Found {len(mappings)} catalog-image mappings to recover")
            
            for mapping in mappings:
                try:
                    # Ensure we have at least the required fields
                    if len(mapping) >= 3:
                        mapping_id = mapping[0]
                        image_id = mapping[1]
                        catalog_id = mapping[2]
                        added_date = mapping[3] if len(mapping) > 3 else None
                        
                        new_cursor.execute(
                            """INSERT INTO image_catalog_mapping 
                               (mapping_id, image_id, catalog_id, added_date) 
                               VALUES (?, ?, ?, ?)""",
                            (mapping_id, image_id, catalog_id, added_date)
                        )
                        recovered_stats["catalog_mappings"] += 1
                except Exception as e:
                    logger.warning(f"Failed to recover catalog-image mapping: {e}")
        except Exception as e:
            logger.warning(f"Failed to recover catalog-image mappings: {e}")
        
        # Close old connection
        old_conn.close()
        
    except Exception as e:
        logger.warning(f"Failed to connect to corrupted database for recovery: {e}")
    
    # Log recovery statistics
    logger.info(f"Recovery statistics: {recovered_stats}")
    
    return recovered_stats

def check_and_repair_if_needed(db_path, parent_widget=None):
    """Check if the database is corrupted and repair it if needed.
    
    Args:
        db_path (str): Path to the database file
        parent_widget: Parent widget for message boxes (optional)
        
    Returns:
        bool: True if database was repaired, False otherwise
    """
    # Check if database exists
    if not os.path.exists(db_path):
        logger.info(f"Database file does not exist: {db_path}")
        return False
    
    # Check database integrity
    if not check_database_integrity(db_path):
        # Database is corrupted, try to repair it
        return repair_database(db_path, parent_widget)
    
    return False

def check_and_repair_database(db_path):
    """Check database integrity and repair if needed. Optimized for programmatic use in maintenance tools.
    
    Args:
        db_path (str): Path to the database file
        
    Returns:
        tuple: (repair_needed, result_message) - whether repair was needed and result description
    """
    # First check if the database exists
    if not os.path.exists(db_path):
        return False, "Database file does not exist"
    
    # Check database integrity first
    integrity_result = check_database_integrity(db_path)
    
    if integrity_result is True:
        # Database is fine, no repair needed
        logger.info("Database integrity check passed, no repair needed")
        return False, "Database integrity check passed"
        
    # Database is corrupted or check failed, attempt repair
    logger.warning("Database corruption detected, attempting repair")
    
    # Use our headless rebuild function
    rebuild_success = rebuild_database(db_path)
    
    if rebuild_success:
        return True, "Database was successfully repaired"
    else:
        return True, "Repair attempt made but some data may not have been recovered"

def rebuild_database(db_path):
    """Rebuild a corrupted database from scratch without UI interaction.
    
    This is a headless version of repair_database that doesn't require user interaction
    and is suitable for being called programmatically during error recovery.
    
    Args:
        db_path (str): Path to the database file
        
    Returns:
        bool: True if rebuild was successful, False otherwise
    """
    logger.warning(f"Rebuilding database without UI interaction: {db_path}")
    
    # Create backup of corrupted database - use a consistent name for a single backup file
    backup_path = f"{db_path}.backup"
    try:
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            logger.info(f"Created backup of corrupted database at {backup_path}")
    except Exception as e:
        logger.error(f"Failed to create backup of corrupted database: {e}")
        # Continue anyway, we'll try to rebuild
    
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
        
        # Try to recover data from corrupted database
        recovered_stats = recover_data(db_path, new_conn, new_cursor)
        
        # Commit changes and close connection
        new_conn.commit()
        new_conn.close()
        
        logger.info(f"Recovered {recovered_stats['folders']} folders and {recovered_stats['images']} images")
        
        # Replace corrupted database with new one
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
            shutil.copy2(new_db_path, db_path)
            os.remove(new_db_path)
            logger.info("Replaced corrupted database with rebuilt one")
            return True
        except Exception as e:
            logger.error(f"Failed to replace corrupted database: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to rebuild database: {e}")
        return False
