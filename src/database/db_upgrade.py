#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database upgrade functionality for StarImageBrowse
Handles updates to the database schema for feature additions.
"""

import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger("StarImageBrowse.database.db_upgrade")

def upgrade_database_schema(db_path):
    """Upgrade the database schema to the latest version.
    
    This function will add any missing tables and columns to the database.
    
    Args:
        db_path (str): Path to the database file
        
    Returns:
        tuple: (success, message) - Where success is a boolean and message is a descriptive string
    """
    if not os.path.exists(db_path):
        return False, f"Database file not found: {db_path}"
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get the list of existing tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Existing tables: {existing_tables}")
        
        # Track the number of modifications made
        changes_made = 0
        
        # Check for catalogs table
        if "catalogs" not in existing_tables:
            logger.info("Adding catalogs table to database")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS catalogs (
                    catalog_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            changes_made += 1
            
        # Check for image_catalog_mapping table
        if "image_catalog_mapping" not in existing_tables:
            logger.info("Adding image_catalog_mapping table to database")
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
            changes_made += 1
            
        # Create indexes for the catalog tables
        if "image_catalog_mapping" in existing_tables or changes_made > 0:
            logger.info("Adding indexes for catalog tables")
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_catalog_mapping_image_id ON image_catalog_mapping (image_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_catalog_mapping_catalog_id ON image_catalog_mapping (catalog_id)
            ''')

        # Check if images table has width and height columns
        cursor.execute("PRAGMA table_info(images)")
        columns = {row[1] for row in cursor.fetchall()}
        
        # Add width and height columns if they don't exist
        if "width" not in columns:
            logger.info("Adding width column to images table")
            cursor.execute("ALTER TABLE images ADD COLUMN width INTEGER")
            changes_made += 1
            
        if "height" not in columns:
            logger.info("Adding height column to images table")
            cursor.execute("ALTER TABLE images ADD COLUMN height INTEGER")
            changes_made += 1
            
        # Add format column if it doesn't exist
        if "format" not in columns:
            logger.info("Adding format column to images table")
            cursor.execute("ALTER TABLE images ADD COLUMN format TEXT")
            changes_made += 1
        
        # Add date_added column if it doesn't exist
        if "date_added" not in columns:
            logger.info("Adding date_added column to images table")
            # First add the column without a default value
            cursor.execute("ALTER TABLE images ADD COLUMN date_added TIMESTAMP")
            # Then update all existing records with current timestamp
            cursor.execute("UPDATE images SET date_added = CURRENT_TIMESTAMP WHERE date_added IS NULL")
            changes_made += 1

        # Create index for image dimensions if needed
        if "width" not in columns or "height" not in columns:
            logger.info("Adding index for image dimensions")
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_images_dimensions ON images (width, height)
            ''')
            
        # Create index for dates if needed
        if "date_added" not in columns:
            logger.info("Adding index for date_added")
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_images_date_added ON images (date_added DESC)
            ''')
            
        # Check for image_fts table for full-text search
        if "image_fts" not in existing_tables:
            logger.info("Adding full-text search virtual table")
            try:
                # Create the FTS5 virtual table
                cursor.execute('''
                    CREATE VIRTUAL TABLE IF NOT EXISTS image_fts USING fts5(
                        image_id,
                        ai_description,
                        user_description,
                        filename,
                        content=''  
                    )
                ''')
                
                # Create triggers to keep FTS table in sync with the images table
                cursor.execute('''
                    CREATE TRIGGER IF NOT EXISTS images_ai_insert AFTER INSERT ON images BEGIN
                        INSERT INTO image_fts(image_id, ai_description, user_description, filename) 
                        VALUES (new.image_id, new.ai_description, new.user_description, new.filename);
                    END
                ''')
                
                cursor.execute('''
                    CREATE TRIGGER IF NOT EXISTS images_ai_update AFTER UPDATE ON images BEGIN
                        DELETE FROM image_fts WHERE image_id = old.image_id;
                        INSERT INTO image_fts(image_id, ai_description, user_description, filename) 
                        VALUES (new.image_id, new.ai_description, new.user_description, new.filename);
                    END
                ''')
                
                cursor.execute('''
                    CREATE TRIGGER IF NOT EXISTS images_ai_delete AFTER DELETE ON images BEGIN
                        DELETE FROM image_fts WHERE image_id = old.image_id;
                    END
                ''')
                
                # Populate the FTS table with existing data
                try:
                    # First check how many images exist
                    image_count = cursor.execute("SELECT COUNT(*) FROM images").fetchone()[0]
                    if image_count > 0:
                        logger.info(f"Populating FTS table with {image_count} existing images")
                        
                        # Use a transaction for better performance
                        cursor.execute("BEGIN TRANSACTION")
                        
                        # Clear any existing data in FTS table to avoid duplicates
                        cursor.execute("DELETE FROM image_fts")
                        
                        # Insert all image data in one go
                        cursor.execute('''
                            INSERT INTO image_fts(image_id, ai_description, user_description, filename)
                            SELECT image_id, ai_description, user_description, filename FROM images
                        ''')
                        
                        # Commit the transaction
                        cursor.execute("COMMIT")
                        logger.info("FTS table successfully populated")
                    else:
                        logger.info("No images to populate in FTS table")
                except sqlite3.Error as e:
                    # Roll back if there's an error
                    cursor.execute("ROLLBACK")
                    logger.error(f"Error populating FTS table: {e}")
                    # We'll continue anyway - the triggers will populate it going forward
                
                changes_made += 1
                logger.info("Full-text search table created and populated")
                
            except sqlite3.Error as e:
                logger.error(f"Error creating FTS table: {e}")
                # Continue anyway - this is not critical
            
        conn.commit()
        
        if changes_made > 0:
            return True, f"Successfully upgraded database schema with {changes_made} changes"
        else:
            return True, "Database schema is already up-to-date"
            
    except sqlite3.Error as e:
        logger.error(f"Error upgrading database: {e}")
        if conn:
            conn.rollback()
        return False, f"Failed to upgrade database: {str(e)}"
    finally:
        if conn:
            conn.close()
