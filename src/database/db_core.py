#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Core database functionality for StarImageBrowse
Provides a robust and optimized database system for handling large image collections.
"""

import os
import sqlite3
import logging
import shutil
import time
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("StarImageBrowse.database.db_core")

class DatabaseConnection:
    """A single database connection with transaction management."""
    
    def __init__(self, db_path):
        """Initialize a database connection.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.in_transaction = False
        
    def connect(self):
        """Establish a connection to the database."""
        if self.conn is not None:
            return True
            
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            self.cursor = self.conn.cursor()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            return False
            
    def disconnect(self):
        """Close the database connection."""
        if self.conn is not None:
            try:
                if self.in_transaction:
                    self.conn.rollback()
                    self.in_transaction = False
                self.conn.close()
            except sqlite3.Error as e:
                logger.error(f"Error disconnecting from database: {e}")
            finally:
                self.conn = None
                self.cursor = None
                
    def begin_transaction(self):
        """Begin a transaction."""
        if self.conn is None:
            if not self.connect():
                return False
                
        try:
            self.cursor.execute("BEGIN IMMEDIATE TRANSACTION")
            self.in_transaction = True
            return True
        except sqlite3.Error as e:
            logger.error(f"Error beginning transaction: {e}")
            return False
            
    def commit(self):
        """Commit the current transaction."""
        if self.conn is None or not self.in_transaction:
            return False
            
        try:
            self.conn.commit()
            self.in_transaction = False
            return True
        except sqlite3.Error as e:
            logger.error(f"Error committing transaction: {e}")
            return False
            
    def rollback(self):
        """Rollback the current transaction."""
        if self.conn is None or not self.in_transaction:
            return False
            
        try:
            self.conn.rollback()
            self.in_transaction = False
            return True
        except sqlite3.Error as e:
            logger.error(f"Error rolling back transaction: {e}")
            return False
            
    def execute(self, query, params=None):
        """Execute a SQL query.
        
        Args:
            query (str): SQL query to execute
            params (tuple, optional): Parameters for the query
            
        Returns:
            cursor: Database cursor for fetching results
        """
        if self.conn is None:
            if not self.connect():
                return None
                
        try:
            if params is None:
                self.cursor.execute(query)
            else:
                self.cursor.execute(query, params)
            return self.cursor
        except sqlite3.Error as e:
            error_msg = str(e).lower()
            
            # Check if this is a corruption error
            if "malformed" in error_msg or "corrupt" in error_msg or "disk i/o error" in error_msg:
                logger.error(f"Database corruption detected during query execution: {e}")
                # Let the caller handle the corruption error
                raise sqlite3.DatabaseError(f"Database corruption detected: {e}")
            else:
                logger.error(f"Error executing query: {e}")
            return None
            
    def execute_many(self, query, params_list):
        """Execute a SQL query with multiple parameter sets.
        
        Args:
            query (str): SQL query to execute
            params_list (list): List of parameter tuples
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self.conn is None:
            if not self.connect():
                return False
                
        try:
            self.cursor.executemany(query, params_list)
            return True
        except sqlite3.Error as e:
            logger.error(f"Error executing query with multiple parameters: {e}")
            return False

class Database:
    """Core database functionality for StarImageBrowse."""
    
    def __init__(self, db_path):
        """Initialize the database.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize the database if it doesn't exist
        self._initialize_if_needed()
        
        logger.info(f"Database initialized at: {db_path}")
        
    def _initialize_if_needed(self):
        """Initialize the database if it doesn't exist."""
        if not os.path.exists(self.db_path):
            logger.info(f"Creating new database at {self.db_path}")
            conn = DatabaseConnection(self.db_path)
            try:
                if not conn.connect():
                    raise Exception("Failed to connect to database")
                
                # Create the database schema
                self._create_schema(conn)
                logger.info("Database schema created successfully")
                
                # Set optimal performance settings
                self._set_performance_settings(conn)
                logger.info("Performance settings applied")
            finally:
                conn.disconnect()
        else:
            # Check and repair the database if needed
            self._check_and_repair()
            
    def _check_and_repair(self):
        """Check if the database is corrupted and repair it if needed."""
        logger.info(f"Checking database integrity: {self.db_path}")
        
        # Create backup of current database
        backup_path = f"{self.db_path}.backup"
        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Created backup at {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            # Continue anyway, we'll try to repair
        
        # Try to open the database and check integrity
        conn = DatabaseConnection(self.db_path)
        try:
            if not conn.connect():
                raise Exception("Failed to connect to database")
            
            # Run integrity check
            cursor = conn.execute("PRAGMA integrity_check")
            if not cursor:
                raise Exception("Failed to run integrity check")
                
            result = cursor.fetchone()
            
            if result and result[0] == "ok":
                logger.info("Database integrity check passed")
                conn.disconnect()
                return True
            else:
                logger.warning(f"Database integrity check failed: {result[0] if result else 'Unknown error'}")
                conn.disconnect()
                
                # Database is corrupted, rebuild it
                return self._rebuild_database(backup_path)
                
        except sqlite3.Error as e:
            logger.error(f"Error checking database integrity: {e}")
            conn.disconnect()
            
            # Database is likely corrupted, rebuild it
            return self._rebuild_database(backup_path)
            
    def _rebuild_database(self, backup_path):
        """Rebuild the database from scratch or from a backup.
        
        Args:
            backup_path (str): Path to the backup file
            
        Returns:
            bool: True if rebuild was successful, False otherwise
        """
        logger.info("Rebuilding database from scratch")
        
        try:
            # Remove the corrupted database
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
                logger.info("Removed corrupted database")
            
            # Create a new database
            conn = DatabaseConnection(self.db_path)
            if not conn.connect():
                raise Exception("Failed to connect to new database")
            
            # Create the schema
            self._create_schema(conn)
            
            # Try to recover data from backup
            try:
                self._recover_data(backup_path, conn)
            except Exception as e:
                logger.warning(f"Could not recover data from backup: {e}")
                # Continue with empty database
            
            # Set optimal performance settings
            self._set_performance_settings(conn)
            
            # Close connection
            conn.disconnect()
            
            logger.info("Database rebuilt successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error rebuilding database: {e}")
            return False
            
    def _create_schema(self, conn):
        """Create the database schema.
        
        Args:
            conn (DatabaseConnection): Database connection
        """
        # Create folders table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS folders (
                folder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                enabled INTEGER DEFAULT 1,
                last_scan_time TIMESTAMP
            )
        ''')
        
        # Create images table
        conn.execute('''
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
                format TEXT,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (folder_id) REFERENCES folders (folder_id)
            )
        ''')
        
        # Create index on full_path for faster lookups
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_full_path ON images (full_path)
        ''')
        
        # Create index for searching descriptions
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_ai_description ON images (ai_description)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_user_description ON images (user_description)
        ''')
        
        # Create performance indexes
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_folder_id ON images (folder_id)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_last_modified ON images (last_modified_date DESC)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_search_modified ON images (ai_description, last_modified_date DESC)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_search_modified_user ON images (user_description, last_modified_date DESC)
        ''')
        
        # Create Catalogs table (new feature)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS catalogs (
                catalog_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create Image-Catalog mapping table (new feature)
        conn.execute('''
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
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_catalog_mapping_image_id ON image_catalog_mapping (image_id)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_catalog_mapping_catalog_id ON image_catalog_mapping (catalog_id)
        ''')
        
        # Create virtual table for full-text search
        conn.execute('''
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
        conn.execute('''
            CREATE TRIGGER IF NOT EXISTS images_ai_insert AFTER INSERT ON images BEGIN
                INSERT INTO image_fts(image_id, ai_description, user_description)
                VALUES (new.image_id, new.ai_description, new.user_description);
            END
        ''')
        
        # Trigger for UPDATE
        conn.execute('''
            CREATE TRIGGER IF NOT EXISTS images_ai_update AFTER UPDATE ON images BEGIN
                UPDATE image_fts SET 
                    ai_description = new.ai_description,
                    user_description = new.user_description
                WHERE image_id = new.image_id;
            END
        ''')
        
        # Trigger for DELETE
        conn.execute('''
            CREATE TRIGGER IF NOT EXISTS images_ai_delete AFTER DELETE ON images BEGIN
                DELETE FROM image_fts WHERE image_id = old.image_id;
            END
        ''')
        
        # Commit the changes
        conn.commit()
        
    def _recover_data(self, backup_path, conn):
        """Try to recover data from a backup database.
        
        Args:
            backup_path (str): Path to the backup database
            conn (DatabaseConnection): Database connection
        """
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
                    conn.execute(
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
                            conn.execute(
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
                conn.execute('''
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
            
    def _set_performance_settings(self, conn):
        """Set optimal performance settings for the database.
        
        Args:
            conn (DatabaseConnection): Database connection
        """
        try:
            # Set synchronous mode to NORMAL for better performance with good reliability
            conn.execute("PRAGMA synchronous=NORMAL")
            
            # Set journal mode to DELETE for better compatibility
            conn.execute("PRAGMA journal_mode=DELETE")
            
            # Set temp store to MEMORY for better performance
            conn.execute("PRAGMA temp_store=MEMORY")
            
            # Set cache size to 5000 pages (about 20MB) - conservative but effective
            conn.execute("PRAGMA cache_size=5000")
            
            # Run ANALYZE to update statistics
            conn.execute("ANALYZE")
            
            conn.commit()
            
        except sqlite3.Error as e:
            logger.error(f"Error setting performance settings: {e}")
            raise
            
    def get_connection(self):
        """Get a new database connection.
        
        Returns:
            DatabaseConnection: A new database connection
        """
        conn = DatabaseConnection(self.db_path)
        if conn.connect():
            return conn
        return None
        
    def close_all_connections(self):
        """Force close all database connections.
        
        This is used before database repair operations to ensure all connections
        are properly closed so the database file can be replaced.
        
        Returns:
            bool: True if successful
        """
        logger.info("Forcing close of all database connections...")
        
        try:
            # Create a temporary connection to release locks
            temp_conn = None
            try:
                # Connect with a short timeout to avoid hanging
                temp_conn = sqlite3.connect(self.db_path, timeout=1)
                temp_conn.close()
            except Exception as e:
                logger.warning(f"Could not create temporary connection: {e}")
            finally:
                if temp_conn:
                    try:
                        temp_conn.close()
                    except:
                        pass
            
            # Force Python's garbage collector to run
            import gc
            gc.collect()
            
            # On Windows, we need to wait a bit for file locks to be released
            if os.name == 'nt':
                time.sleep(0.5)
                
            logger.info("All database connections should be closed")
            return True
            
        except Exception as e:
            logger.error(f"Error closing all database connections: {e}")
            return False
        
    def optimize(self):
        """Optimize the database for better performance.
        
        Returns:
            bool: True if optimization was successful, False otherwise
        """
        logger.info("Optimizing database...")
        
        # Create a new optimized database
        optimized_db_path = f"{self.db_path}.optimized"
        
        try:
            # Remove any existing optimized database
            if os.path.exists(optimized_db_path):
                os.remove(optimized_db_path)
                
            # Create a new connection to the current database
            source_conn = DatabaseConnection(self.db_path)
            if not source_conn.connect():
                raise Exception("Failed to connect to source database")
                
            # Create a new connection to the optimized database
            optimized_conn = DatabaseConnection(optimized_db_path)
            if not optimized_conn.connect():
                raise Exception("Failed to connect to optimized database")
                
            # Create the schema in the optimized database
            self._create_schema(optimized_conn)
            
            # Set optimal performance settings
            self._set_performance_settings(optimized_conn)
            
            # Copy data from the source database to the optimized database
            
            # Copy folders
            cursor = source_conn.execute("SELECT * FROM folders")
            if not cursor:
                raise Exception("Failed to select folders from source database")
                
            folders = cursor.fetchall()
            for folder in folders:
                folder_dict = dict(folder)
                optimized_conn.execute(
                    "INSERT INTO folders (folder_id, path, enabled, last_scan_time) VALUES (?, ?, ?, ?)",
                    (
                        folder_dict['folder_id'],
                        folder_dict['path'],
                        folder_dict['enabled'],
                        folder_dict['last_scan_time']
                    )
                )
                
            # Copy images in batches
            batch_size = 500
            offset = 0
            total_copied = 0
            
            while True:
                cursor = source_conn.execute(f"SELECT * FROM images LIMIT {batch_size} OFFSET {offset}")
                if not cursor:
                    raise Exception("Failed to select images from source database")
                    
                images = cursor.fetchall()
                if not images:
                    break
                
                for image in images:
                    image_dict = dict(image)
                    optimized_conn.execute(
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
                    total_copied += 1
                
                offset += batch_size
                optimized_conn.commit()  # Commit each batch
                
            # Close connections
            source_conn.disconnect()
            optimized_conn.disconnect()
            
            # Create a backup of the current database
            backup_path = f"{self.db_path}.backup"
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Created backup at {backup_path}")
            
            # Replace the current database with the optimized one
            os.remove(self.db_path)
            shutil.copy2(optimized_db_path, self.db_path)
            os.remove(optimized_db_path)
            
            logger.info(f"Database optimization complete. Copied {total_copied} images.")
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            return False
            
    def vacuum(self):
        """Run VACUUM on the database to reclaim unused space.
        
        Returns:
            bool: True if vacuum was successful, False otherwise
        """
        logger.info("Running VACUUM on database...")
        
        conn = DatabaseConnection(self.db_path)
        try:
            if not conn.connect():
                raise Exception("Failed to connect to database")
                
            conn.execute("VACUUM")
            conn.commit()
            
            logger.info("VACUUM completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error running VACUUM: {e}")
            return False
            
        finally:
            conn.disconnect()
            
    def analyze(self):
        """Run ANALYZE on the database to update statistics.
        
        Returns:
            bool: True if analyze was successful, False otherwise
        """
        logger.info("Running ANALYZE on database...")
        
        conn = DatabaseConnection(self.db_path)
        try:
            if not conn.connect():
                raise Exception("Failed to connect to database")
                
            conn.execute("ANALYZE")
            conn.commit()
            
            logger.info("ANALYZE completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error running ANALYZE: {e}")
            return False
            
        finally:
            conn.disconnect()
            
    def integrity_check(self):
        """Run integrity check on the database.
        
        Returns:
            bool: True if the database is intact, False otherwise
        """
        logger.info("Running integrity check on database...")
        
        conn = DatabaseConnection(self.db_path)
        try:
            if not conn.connect():
                raise Exception("Failed to connect to database")
                
            cursor = conn.execute("PRAGMA integrity_check")
            if not cursor:
                raise Exception("Failed to run integrity check")
                
            result = cursor.fetchone()
            
            if result and result[0] == "ok":
                logger.info("Database integrity check passed")
                return True
            else:
                logger.warning(f"Database integrity check failed: {result[0] if result else 'Unknown error'}")
                return False
                
        except Exception as e:
            logger.error(f"Error running integrity check: {e}")
            return False
            
        finally:
            conn.disconnect()
