#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database optimizer for StarImageBrowse
Provides optimizations for large image collections.
"""

import os
import logging
import sqlite3
import time
import shutil
from pathlib import Path

logger = logging.getLogger("StarImageBrowse.database.db_optimizer")

class DatabaseOptimizer:
    """Optimizer for the SQLite database to improve performance with large image collections."""
    
    def __init__(self, db_manager):
        """Initialize the database optimizer.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
    
    def optimize_database(self):
        """Perform various optimizations on the database for better performance.
        
        Returns:
            bool: True if optimization was successful, False otherwise
        """
        logger.info("Starting database optimization...")
        start_time = time.time()
        
        # Create a backup before optimization
        backup_path = f"{self.db_manager.db_path}.backup_optimize"
        try:
            shutil.copy2(self.db_manager.db_path, backup_path)
            logger.info(f"Created backup before optimization at {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup before optimization: {e}")
            return False
        
        # Use a safer approach by creating a new optimized copy
        return self._create_optimized_copy(backup_path, start_time)
    
    def _create_optimized_copy(self, source_db_path, start_time):
        """Create an optimized copy of the database and replace the original.
        
        This is a safer approach than modifying the database in-place.
        
        Args:
            source_db_path (str): Path to the source database to optimize
            start_time (float): Time when optimization started (for elapsed time calculation)
            
        Returns:
            bool: True if optimization was successful, False otherwise
        """
        # Create a new database file
        new_db_path = f"{self.db_manager.db_path}.new_optimized"
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
            self._create_schema(new_conn, new_cursor)
            
            # Copy data from old database
            if not self._copy_data(source_db_path, new_conn, new_cursor):
                logger.error("Failed to copy data to new database")
                new_conn.close()
                return False
            
            # Create indexes and optimize the new database
            self._create_performance_indexes_on_conn(new_conn, new_cursor)
            
            # Set safe performance pragmas
            self._set_safe_performance_pragmas_on_conn(new_conn, new_cursor)
            
            # Run ANALYZE to update statistics
            new_cursor.execute("ANALYZE")
            
            # Close connection
            new_conn.close()
            
            # Verify new database
            if not self._verify_database(new_db_path):
                logger.error("New database verification failed")
                return False
            
            # Replace old database with new one
            try:
                # Close any existing connections to the database
                self.db_manager.disconnect()
                
                # Windows-friendly approach: Instead of replacing the file directly, use SQLite's backup API
                # This bypasses Windows file locking issues
                try:
                    # Create a new in-memory database
                    temp_conn = sqlite3.connect(":memory:")
                    # Load the optimized database into memory
                    optimized_conn = sqlite3.connect(new_db_path)
                    optimized_conn.backup(temp_conn)
                    optimized_conn.close()
                    
                    # Now we need to connect to the original database and restore from our in-memory copy
                    # This approach works around Windows file locking
                    orig_conn = sqlite3.connect(self.db_manager.db_path)
                    temp_conn.backup(orig_conn)
                    
                    # Close all connections
                    temp_conn.close()
                    orig_conn.close()
                    
                    # Remove the temporary optimized file
                    try:
                        os.remove(new_db_path)
                    except:
                        pass  # Non-critical if we can't remove it
                    
                    logger.info(f"Successfully replaced original database with optimized version using backup API")
                except Exception as backup_error:
                    logger.error(f"Backup API approach failed: {backup_error}")
                    logger.info("Falling back to file replacement method...")
                    
                    # Try traditional file replacement as fallback
                    # Create a backup of the original first
                    backup_path = f"{self.db_manager.db_path}.backup"
                    try:
                        shutil.copy2(self.db_manager.db_path, backup_path)
                        os.replace(new_db_path, self.db_manager.db_path)
                        logger.info(f"Successfully replaced original database with optimized version using file replacement")
                    except Exception as replace_error:
                        logger.error(f"File replacement fallback also failed: {replace_error}")
                        # Restore from backup if we have one and the replacement failed
                        if os.path.exists(backup_path):
                            try:
                                os.replace(backup_path, self.db_manager.db_path)
                                logger.info("Restored original database from backup")
                            except:
                                logger.error("Could not restore from backup")
                        raise replace_error
                
                elapsed_time = time.time() - start_time
                logger.info(f"Database optimization completed in {elapsed_time:.2f} seconds")
                return True
            except Exception as e:
                logger.error(f"Failed to replace original database: {e}")
                logger.info(f"Optimized database is available at: {new_db_path}")
                return False
            
        except Exception as e:
            logger.error(f"Error creating optimized database: {e}")
            return False
    
    def _create_performance_indexes(self):
        """Create additional indexes to improve query performance."""
        try:
            # Connect to the database if not already connected
            was_connected = self.db_manager.conn is not None
            if not was_connected:
                if not self.db_manager.connect():
                    logger.error("Failed to connect to database for creating indexes")
                    return False
            
            # Create indexes
            self._create_performance_indexes_on_conn(self.db_manager.conn, self.db_manager.cursor)
            
            # Disconnect if we connected in this method
            if not was_connected:
                self.db_manager.disconnect()
                
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error creating performance indexes: {e}")
            if self.db_manager.conn:
                self.db_manager.conn.rollback()
            return False
    
    def _create_performance_indexes_on_conn(self, conn, cursor):
        """Create additional indexes to improve query performance on a specific connection."""
        try:
            # Index for folder_id to speed up folder-based queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_images_folder_id ON images (folder_id)
            ''')
            
            # Index for last_modified_date to speed up sorting
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_images_last_modified ON images (last_modified_date DESC)
            ''')
            
            # Compound index for search queries with sorting
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_images_search_modified ON images (ai_description, last_modified_date DESC)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_images_search_modified_user ON images (user_description, last_modified_date DESC)
            ''')
            
            conn.commit()
            logger.info("Performance indexes created successfully")
            
        except sqlite3.Error as e:
            logger.error(f"Error creating performance indexes: {e}")
            conn.rollback()
            raise
    
    def _enable_wal_mode(self):
        """Enable Write-Ahead Logging (WAL) mode for better performance."""
        try:
            self.db_manager.cursor.execute("PRAGMA journal_mode=WAL")
            result = self.db_manager.cursor.fetchone()
            if result and result[0] == "wal":
                logger.info("WAL mode enabled successfully")
            else:
                logger.warning(f"Failed to enable WAL mode, got: {result[0] if result else 'None'}")
        except sqlite3.Error as e:
            logger.error(f"Error enabling WAL mode: {e}")
            raise
    
    def _set_performance_pragmas(self):
        """Set various PRAGMA settings for better performance."""
        try:
            # Set synchronous mode to NORMAL for better performance
            self.db_manager.cursor.execute("PRAGMA synchronous=NORMAL")
            
            # Set journal mode to WAL for better performance
            self.db_manager.cursor.execute("PRAGMA journal_mode=WAL")
            
            # Set temp store to MEMORY for better performance
            self.db_manager.cursor.execute("PRAGMA temp_store=MEMORY")
            
            # Set cache size to 10000 pages (about 40MB)
            self.db_manager.cursor.execute("PRAGMA cache_size=10000")
            
            # Set page size to 4096 bytes
            self.db_manager.cursor.execute("PRAGMA page_size=4096")
            
            logger.info("Performance PRAGMAs set successfully")
            
        except sqlite3.Error as e:
            logger.error(f"Error setting performance PRAGMAs: {e}")
            raise
    
    def analyze_database_stats(self):
        """Analyze database statistics and return information about the database.
        
        Returns:
            dict: Dictionary with database statistics
        """
        try:
            if not self.db_manager.connect():
                logger.error("Failed to connect to database for analysis")
                return {
                    "total_images": 0,
                    "total_folders": 0,
                    "database_size_mb": 0,
                    "error": "Failed to connect to database"
                }
            
            # Get total number of images
            self.db_manager.cursor.execute("SELECT COUNT(*) FROM images")
            total_images = self.db_manager.cursor.fetchone()[0]
            
            # Get total number of folders
            self.db_manager.cursor.execute("SELECT COUNT(*) FROM folders")
            total_folders = self.db_manager.cursor.fetchone()[0]
            
            # Get database file size
            try:
                database_size_bytes = os.path.getsize(self.db_manager.db_path)
                database_size_mb = database_size_bytes / (1024 * 1024)
            except Exception as e:
                logger.error(f"Error getting database file size: {e}")
                database_size_mb = 0
            
            # Get additional statistics
            stats = {
                "total_images": total_images,
                "total_folders": total_folders,
                "database_size_mb": database_size_mb
            }
            
            # Get images with descriptions
            self.db_manager.cursor.execute("SELECT COUNT(*) FROM images WHERE ai_description IS NOT NULL AND ai_description != ''")
            stats["images_with_ai_descriptions"] = self.db_manager.cursor.fetchone()[0]
            
            self.db_manager.cursor.execute("SELECT COUNT(*) FROM images WHERE user_description IS NOT NULL AND user_description != ''")
            stats["images_with_user_descriptions"] = self.db_manager.cursor.fetchone()[0]
            
            return stats
            
        except sqlite3.Error as e:
            logger.error(f"Error analyzing database statistics: {e}")
            return {
                "total_images": 0,
                "total_folders": 0,
                "database_size_mb": 0,
                "error": str(e)
            }
        finally:
            self.db_manager.disconnect()
    
    def optimize_query_performance(self):
        """Optimize database for query performance.
        
        Returns:
            bool: True if optimization was successful, False otherwise
        """
        try:
            if not self.db_manager.connect():
                logger.error("Failed to connect to database for query optimization")
                return False
            
            # Create additional indexes
            self._create_performance_indexes()
            
            # Set performance pragmas
            self._set_safe_performance_pragmas()
            
            # Run ANALYZE to update statistics
            self.db_manager.cursor.execute("ANALYZE")
            
            # Create virtual tables for full-text search
            self.create_virtual_tables()
            
            # Commit changes
            self.db_manager.conn.commit()
            
            logger.info("Query optimization completed successfully")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error optimizing query performance: {e}")
            if self.db_manager.conn:
                self.db_manager.conn.rollback()
            return False
        finally:
            self.db_manager.disconnect()
    
    def create_virtual_tables(self):
        """Create virtual tables for full-text search capabilities.
        
        Returns:
            bool: True if creation was successful, False otherwise
        """
        try:
            # Connect to the database if not already connected
            was_connected = self.db_manager.conn is not None
            if not was_connected:
                if not self.db_manager.connect():
                    logger.error("Failed to connect to database for creating virtual tables")
                    return False
            
            # Create virtual table for full-text search on descriptions
            self.db_manager.cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS image_fts USING fts5(
                    image_id UNINDEXED,
                    ai_description,
                    user_description,
                    content='images',
                    content_rowid='image_id'
                )
            ''')
            
            # Check if the FTS table needs to be populated
            self.db_manager.cursor.execute("SELECT COUNT(*) FROM image_fts")
            fts_count = self.db_manager.cursor.fetchone()[0]
            
            self.db_manager.cursor.execute("SELECT COUNT(*) FROM images")
            images_count = self.db_manager.cursor.fetchone()[0]
            
            # Populate FTS table if needed
            if fts_count < images_count:
                logger.info("Populating full-text search table...")
                self.db_manager.cursor.execute('''
                    INSERT INTO image_fts(image_id, ai_description, user_description)
                    SELECT image_id, ai_description, user_description FROM images
                    WHERE image_id NOT IN (SELECT image_id FROM image_fts)
                ''')
            
            # Create triggers to keep FTS table in sync
            self._create_fts_triggers()
            
            self.db_manager.conn.commit()
            logger.info("Virtual tables created successfully")
            
            # Disconnect if we connected in this method
            if not was_connected:
                self.db_manager.disconnect()
                
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error creating virtual tables: {e}")
            if self.db_manager.conn:
                self.db_manager.conn.rollback()
            return False
    
    def _set_safe_performance_pragmas(self):
        """Set only essential and safe PRAGMA settings for better performance."""
        try:
            # Connect to the database if not already connected
            was_connected = self.db_manager.conn is not None
            if not was_connected:
                if not self.db_manager.connect():
                    logger.error("Failed to connect to database for setting PRAGMAs")
                    return False
            
            # Set PRAGMAs
            self._set_safe_performance_pragmas_on_conn(self.db_manager.conn, self.db_manager.cursor)
            
            # Disconnect if we connected in this method
            if not was_connected:
                self.db_manager.disconnect()
                
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error setting safe performance PRAGMAs: {e}")
            return False
    
    def _set_safe_performance_pragmas_on_conn(self, conn, cursor):
        """Set only essential and safe PRAGMA settings for better performance on a specific connection."""
        try:
            # Set synchronous mode to NORMAL for better performance with good reliability
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # Set journal mode to DELETE for better compatibility
            cursor.execute("PRAGMA journal_mode=DELETE")
            
            # Set temp store to MEMORY for better performance
            cursor.execute("PRAGMA temp_store=MEMORY")
            
            # Set cache size to 5000 pages (about 20MB) - more conservative
            cursor.execute("PRAGMA cache_size=5000")
            
            logger.info("Safe performance PRAGMAs set successfully")
            
        except sqlite3.Error as e:
            logger.error(f"Error setting safe performance PRAGMAs: {e}")
            raise
    
    def _create_fts_triggers(self):
        """Create triggers to keep FTS table in sync with the images table."""
        # Trigger for INSERT
        self.db_manager.cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS images_ai_insert AFTER INSERT ON images BEGIN
                INSERT INTO image_fts(image_id, ai_description, user_description)
                VALUES (new.image_id, new.ai_description, new.user_description);
            END
        ''')
        
        # Trigger for UPDATE
        self.db_manager.cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS images_ai_update AFTER UPDATE ON images BEGIN
                UPDATE image_fts SET 
                    ai_description = new.ai_description,
                    user_description = new.user_description
                WHERE image_id = new.image_id;
            END
        ''')
        
        # Trigger for DELETE
        self.db_manager.cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS images_ai_delete AFTER DELETE ON images BEGIN
                DELETE FROM image_fts WHERE image_id = old.image_id;
            END
        ''')
        
        logger.info("FTS triggers created successfully")
    
    def _create_schema(self, conn, cursor):
        """Create the database schema in a new database.
        
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
                format TEXT,
                date_added TIMESTAMP,
                FOREIGN KEY (folder_id) REFERENCES folders (folder_id)
            )
        ''')
        
        # Create catalogs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS catalogs (
                catalog_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_date TIMESTAMP
            )
        ''')
        
        # Create image_catalog_mapping table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS image_catalog_mapping (
                mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER,
                catalog_id INTEGER,
                added_date TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images (image_id),
                FOREIGN KEY (catalog_id) REFERENCES catalogs (catalog_id)
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
        
        # Create indexes for catalog mappings
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_catalog_mapping_image_id ON image_catalog_mapping (image_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_catalog_mapping_catalog_id ON image_catalog_mapping (catalog_id)
        ''')
        
        conn.commit()
        logger.info("Database schema created successfully")
    
    def _copy_data(self, source_db_path, dest_conn, dest_cursor):
        """Copy data from source database to destination database.
        
        Args:
            source_db_path (str): Path to the source database
            dest_conn: Destination database connection
            dest_cursor: Destination database cursor
            
        Returns:
            bool: True if data was copied successfully, False otherwise
        """
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
                
            # Get total number of images to copy
            source_cursor.execute("SELECT COUNT(*) FROM images")
            total_images = source_cursor.fetchone()[0]
            logger.info(f"Total images to copy: {total_images}")
            
            # Determine optimal batch size based on total images
            # Smaller batch for very large databases to prevent memory issues
            if total_images > 100000:
                batch_size = 250
            elif total_images > 50000:
                batch_size = 500
            else:
                batch_size = 1000
                
            # Copy images in batches to avoid memory issues
            logger.info(f"Copying images using batch size of {batch_size}...")
            offset = 0
            total_copied = 0
            progress_interval = min(10000, max(1000, total_images // 10))  # Report progress at reasonable intervals
            next_progress_report = progress_interval
            
            while True:
                source_cursor.execute(f"SELECT * FROM images LIMIT {batch_size} OFFSET {offset}")
                images = source_cursor.fetchall()
                
                if not images:
                    break
                    
                for image in images:
                    image_dict = dict(image)
                    
                    # Check if additional columns exist in the source database
                    width = image_dict.get('width')
                    height = image_dict.get('height')
                    format_value = image_dict.get('format')
                    date_added = image_dict.get('date_added')
                    
                    dest_cursor.execute(
                        """INSERT INTO images (
                            image_id, folder_id, filename, full_path, file_size, file_hash,
                            creation_date, last_modified_date, thumbnail_path,
                            ai_description, user_description, last_scanned,
                            width, height, format, date_added
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                            image_dict['last_scanned'],
                            width,
                            height,
                            format_value,
                            date_added
                        )
                    )
                
                total_copied += len(images)
                
                # Report progress at intervals, or for every batch in small databases
                if total_copied >= next_progress_report or total_images < 1000:
                    percentage = (total_copied / total_images) * 100 if total_images > 0 else 100
                    logger.info(f"Copied {total_copied}/{total_images} images ({percentage:.1f}%)...")
                    next_progress_report = total_copied + progress_interval
                
                offset += batch_size
                dest_conn.commit()  # Commit each batch
            
            # Copy catalogs
            try:
                logger.info("Copying catalogs...")
                source_cursor.execute("SELECT * FROM catalogs")
                catalogs = source_cursor.fetchall()
                
                for catalog in catalogs:
                    catalog_dict = dict(catalog)
                    dest_cursor.execute(
                        "INSERT INTO catalogs (catalog_id, name, description, created_date) VALUES (?, ?, ?, ?)",
                        (
                            catalog_dict['catalog_id'],
                            catalog_dict['name'],
                            catalog_dict['description'],
                            catalog_dict['created_date']
                        )
                    )
                logger.info(f"Copied {len(catalogs)} catalogs")
                
                # Copy image_catalog_mapping
                logger.info("Copying catalog mappings...")
                source_cursor.execute("SELECT * FROM image_catalog_mapping")
                mappings = source_cursor.fetchall()
                
                for mapping in mappings:
                    mapping_dict = dict(mapping)
                    dest_cursor.execute(
                        "INSERT INTO image_catalog_mapping (mapping_id, image_id, catalog_id, added_date) VALUES (?, ?, ?, ?)",
                        (
                            mapping_dict['mapping_id'],
                            mapping_dict['image_id'],
                            mapping_dict['catalog_id'],
                            mapping_dict['added_date']
                        )
                    )
                logger.info(f"Copied {len(mappings)} catalog mappings")
            except sqlite3.Error as e:
                # Do not fail if catalog tables don't exist in source, they might be new
                logger.warning(f"Could not copy catalog data: {e} - this might be expected if upgrading from an older version")
            
            dest_conn.commit()
            
            # Close source connection
            source_conn.close()
            
            # Verify all images were copied
            if total_copied < total_images:
                logger.warning(f"Not all images were copied! Expected {total_images}, but copied {total_copied}.")
            else:
                logger.info(f"Successfully copied all {total_copied} images and {len(folders)} folders")
                
            return True
        except sqlite3.Error as e:
            logger.error(f"Error copying data: {e}")
            return False
    
    def _verify_database(self, db_path):
        """Verify the database integrity and functionality.
        
        Args:
            db_path (str): Path to the database to verify
            
        Returns:
            bool: True if database is valid, False otherwise
        """
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
