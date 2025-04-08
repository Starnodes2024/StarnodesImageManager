#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database sharding for StarImageBrowse
Implements database sharding for handling very large image collections.
"""

import os
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import shutil

from src.database.db_core import Database, DatabaseConnection
from src.database.db_indexing import DatabaseIndexOptimizer

logger = logging.getLogger("StarImageBrowse.database.db_sharding")

class ShardingStrategy:
    """Base class for database sharding strategies."""
    
    def get_shard_for_folder(self, folder_id):
        """Get the shard for a specific folder.
        
        Args:
            folder_id (int): Folder ID
            
        Returns:
            str: Shard identifier
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def get_shard_for_image(self, image_data):
        """Get the shard for a specific image.
        
        Args:
            image_data (dict): Image data
            
        Returns:
            str: Shard identifier
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def get_all_shards(self):
        """Get all possible shards.
        
        Returns:
            list: List of all shard identifiers
        """
        raise NotImplementedError("Subclasses must implement this method")


class FolderBasedSharding(ShardingStrategy):
    """Shards the database based on folder IDs."""
    
    def __init__(self, max_folders_per_shard=10):
        """Initialize folder-based sharding.
        
        Args:
            max_folders_per_shard (int): Maximum number of folders per shard
        """
        self.max_folders_per_shard = max_folders_per_shard
        
    def get_shard_for_folder(self, folder_id):
        """Get the shard for a specific folder.
        
        Args:
            folder_id (int): Folder ID
            
        Returns:
            str: Shard identifier (e.g., 'shard_0', 'shard_1', etc.)
        """
        shard_id = folder_id // self.max_folders_per_shard
        return f"shard_{shard_id}"
    
    def get_shard_for_image(self, image_data):
        """Get the shard for a specific image.
        
        Args:
            image_data (dict): Image data
            
        Returns:
            str: Shard identifier
        """
        return self.get_shard_for_folder(image_data['folder_id'])
    
    def get_all_shards(self):
        """Get all possible shards.
        
        Returns:
            list: List of all shard identifiers
        """
        # This will be populated by the ShardManager based on existing shards
        return []


class DateBasedSharding(ShardingStrategy):
    """Shards the database based on date ranges."""
    
    def __init__(self, interval_months=6):
        """Initialize date-based sharding.
        
        Args:
            interval_months (int): Number of months per shard
        """
        self.interval_months = interval_months
        
    def _date_to_shard(self, date):
        """Convert a date to a shard identifier.
        
        Args:
            date (datetime): Date
            
        Returns:
            str: Shard identifier (e.g., 'shard_2025_01')
        """
        year = date.year
        # Integer division to get the period (e.g., Jan-Jun = 0, Jul-Dec = 1)
        period = (date.month - 1) // self.interval_months
        return f"shard_{year}_{period}"
    
    def get_shard_for_folder(self, folder_id):
        """Get the shard for a specific folder.
        
        Args:
            folder_id (int): Folder ID
            
        Returns:
            str: Default shard identifier (fallback)
        """
        # Folders aren't date-based, so return a default shard
        return "shard_default"
    
    def get_shard_for_image(self, image_data):
        """Get the shard for a specific image.
        
        Args:
            image_data (dict): Image data
            
        Returns:
            str: Shard identifier
        """
        if 'last_modified_date' in image_data and image_data['last_modified_date']:
            try:
                if isinstance(image_data['last_modified_date'], str):
                    date = datetime.strptime(image_data['last_modified_date'], '%Y-%m-%d %H:%M:%S')
                else:
                    date = image_data['last_modified_date']
                return self._date_to_shard(date)
            except (ValueError, TypeError):
                logger.warning(f"Invalid date format: {image_data['last_modified_date']}")
        
        # Fallback to current date
        return self._date_to_shard(datetime.now())
    
    def get_all_shards(self):
        """Get all possible shards for a reasonable time range.
        
        Returns:
            list: List of all shard identifiers
        """
        shards = []
        # Generate shards for the last 5 years and next 1 year
        current_date = datetime.now()
        start_date = current_date - timedelta(days=5*365)
        end_date = current_date + timedelta(days=365)
        
        current = start_date
        while current <= end_date:
            shards.append(self._date_to_shard(current))
            # Add interval_months to move to the next period
            month = current.month + self.interval_months
            year = current.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            current = current.replace(year=year, month=month)
        
        return sorted(list(set(shards)))  # Remove duplicates and sort


class ShardManager:
    """Manages database shards for large image collections."""
    
    def __init__(self, base_db_path, sharding_strategy=None, enable_sharding=False):
        """Initialize the shard manager.
        
        Args:
            base_db_path (str): Base path for the database
            sharding_strategy (ShardingStrategy, optional): Sharding strategy instance
            enable_sharding (bool): Whether to enable sharding
        """
        self.base_db_path = base_db_path
        self.base_dir = os.path.dirname(base_db_path)
        self.base_name = os.path.basename(base_db_path)
        self.enable_sharding = enable_sharding
        
        # Default to folder-based sharding if none provided
        self.sharding_strategy = sharding_strategy or FolderBasedSharding()
        
        # Cache of database instances for each shard
        self.db_cache = {}
        
        # Cache of folder to shard mapping
        self.folder_shard_map = {}
        
        logger.info(f"Shard manager initialized with base DB: {base_db_path}, sharding enabled: {enable_sharding}")
        
        # Initialize the shards directory if sharding is enabled
        if self.enable_sharding:
            self._initialize_shards_directory()
            self._load_folder_shard_mapping()
    
    def _initialize_shards_directory(self):
        """Initialize the directory structure for shards."""
        shards_dir = os.path.join(self.base_dir, "shards")
        os.makedirs(shards_dir, exist_ok=True)
        logger.info(f"Initialized shards directory: {shards_dir}")
    
    def _get_shard_path(self, shard_id):
        """Get the path for a specific shard.
        
        Args:
            shard_id (str): Shard identifier
            
        Returns:
            str: Path to the shard database file
        """
        return os.path.join(self.base_dir, "shards", f"{shard_id}.db")
    
    def _load_folder_shard_mapping(self):
        """Load the mapping of folders to shards from the main database."""
        if not self.enable_sharding:
            return
            
        # Use the main database to get folders
        main_db = Database(self.base_db_path)
        conn = main_db.get_connection()
        
        try:
            if not conn.connect():
                logger.error("Failed to connect to main database")
                return
                
            cursor = conn.execute("SELECT folder_id, shard_id FROM folder_shard_mapping")
            if not cursor:
                logger.warning("Failed to load folder shard mapping or table doesn't exist")
                # Table might not exist yet, create it
                self._create_folder_shard_mapping_table(conn)
                return
                
            # Load the mapping
            for row in cursor.fetchall():
                self.folder_shard_map[row['folder_id']] = row['shard_id']
                
            logger.info(f"Loaded {len(self.folder_shard_map)} folder shard mappings")
            
        except Exception as e:
            logger.error(f"Error loading folder shard mapping: {e}")
            # Table might not exist yet, create it
            self._create_folder_shard_mapping_table(conn)
            
        finally:
            conn.disconnect()
    
    def _create_folder_shard_mapping_table(self, conn):
        """Create the folder shard mapping table in the main database.
        
        Args:
            conn (DatabaseConnection): Database connection
        """
        try:
            # Begin transaction
            if not conn.begin_transaction():
                logger.error("Failed to begin transaction")
                return
                
            # Create the mapping table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS folder_shard_mapping (
                    folder_id INTEGER PRIMARY KEY,
                    shard_id TEXT NOT NULL
                )
            """)
            
            # Commit transaction
            if not conn.commit():
                logger.error("Failed to commit transaction")
                return
                
            logger.info("Created folder shard mapping table")
            
        except Exception as e:
            logger.error(f"Error creating folder shard mapping table: {e}")
            conn.rollback()
    
    def _update_folder_shard_mapping(self, folder_id, shard_id):
        """Update the folder to shard mapping in the main database.
        
        Args:
            folder_id (int): Folder ID
            shard_id (str): Shard identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enable_sharding:
            return True
            
        # Update local cache
        self.folder_shard_map[folder_id] = shard_id
        
        # Update database
        main_db = Database(self.base_db_path)
        conn = main_db.get_connection()
        
        try:
            if not conn.connect():
                logger.error("Failed to connect to main database")
                return False
                
            # Begin transaction
            if not conn.begin_transaction():
                logger.error("Failed to begin transaction")
                return False
                
            # Update or insert the mapping
            conn.execute("""
                INSERT OR REPLACE INTO folder_shard_mapping (folder_id, shard_id)
                VALUES (?, ?)
            """, (folder_id, shard_id))
            
            # Commit transaction
            if not conn.commit():
                logger.error("Failed to commit transaction")
                return False
                
            logger.debug(f"Updated folder shard mapping: folder={folder_id}, shard={shard_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating folder shard mapping: {e}")
            conn.rollback()
            return False
            
        finally:
            conn.disconnect()
    
    def get_db_for_folder(self, folder_id):
        """Get the database instance for a specific folder.
        
        Args:
            folder_id (int): Folder ID
            
        Returns:
            Database: Database instance
        """
        if not self.enable_sharding:
            # Return the main database if sharding is disabled
            return Database(self.base_db_path)
            
        # Check if we have a shard mapping for this folder
        shard_id = self.folder_shard_map.get(folder_id)
        
        if not shard_id:
            # Assign a shard for this folder
            shard_id = self.sharding_strategy.get_shard_for_folder(folder_id)
            # Update the mapping
            self._update_folder_shard_mapping(folder_id, shard_id)
        
        return self.get_db_for_shard(shard_id)
    
    def get_db_for_shard(self, shard_id):
        """Get the database instance for a specific shard.
        
        Args:
            shard_id (str): Shard identifier
            
        Returns:
            Database: Database instance
        """
        if not self.enable_sharding:
            # Return the main database if sharding is disabled
            return Database(self.base_db_path)
            
        # Check if we have this shard in the cache
        if shard_id in self.db_cache:
            return self.db_cache[shard_id]
            
        # Create the shard database path
        shard_path = self._get_shard_path(shard_id)
        
        # Create the shard database if it doesn't exist
        if not os.path.exists(shard_path):
            self._initialize_shard(shard_id, shard_path)
            
        # Create and cache the database instance
        db = Database(shard_path)
        self.db_cache[shard_id] = db
        
        return db
    
    def _initialize_shard(self, shard_id, shard_path):
        """Initialize a new shard database.
        
        Args:
            shard_id (str): Shard identifier
            shard_path (str): Path to the shard database file
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Initializing new shard: {shard_id} at {shard_path}")
        
        try:
            # Create the shard directory if it doesn't exist
            os.makedirs(os.path.dirname(shard_path), exist_ok=True)
            
            # If main database exists, copy schema from it
            if os.path.exists(self.base_db_path):
                # Create a new empty database
                conn = sqlite3.connect(shard_path)
                conn.close()
                
                # Create a new database instance
                db = Database(shard_path)
                # It will initialize automatically
                
                # Create optimized indexes
                index_optimizer = DatabaseIndexOptimizer(shard_path)
                index_optimizer.create_optimized_indexes()
                
                logger.info(f"Shard {shard_id} initialized successfully")
                return True
            else:
                logger.error(f"Main database {self.base_db_path} does not exist")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing shard {shard_id}: {e}")
            return False
    
    def get_dbs_for_query(self, query_type, **kwargs):
        """Get the database instances needed for a specific query.
        
        Args:
            query_type (str): Type of query (e.g., 'folder', 'search', 'date_range')
            **kwargs: Additional arguments for the query
            
        Returns:
            list: List of Database instances
        """
        if not self.enable_sharding:
            # Return the main database if sharding is disabled
            return [Database(self.base_db_path)]
            
        if query_type == 'folder':
            folder_id = kwargs.get('folder_id')
            if folder_id is not None:
                return [self.get_db_for_folder(folder_id)]
            else:
                logger.error("Folder ID is required for folder query")
                return []
                
        elif query_type == 'image':
            image_id = kwargs.get('image_id')
            if image_id is not None:
                # We need to query all shards for this image
                return self.get_all_shard_dbs()
            else:
                logger.error("Image ID is required for image query")
                return []
                
        elif query_type == 'search' or query_type == 'all_images':
            # For search queries or getting all images, query all shards
            return self.get_all_shard_dbs()
            
        elif query_type == 'date_range':
            # For date range queries, we can be more selective with date-based sharding
            if isinstance(self.sharding_strategy, DateBasedSharding):
                from_date = kwargs.get('from_date')
                to_date = kwargs.get('to_date')
                
                if from_date and to_date:
                    # Convert string dates to datetime objects if needed
                    if isinstance(from_date, str):
                        from_date = datetime.strptime(from_date, '%Y-%m-%d %H:%M:%S')
                    if isinstance(to_date, str):
                        to_date = datetime.strptime(to_date, '%Y-%m-%d %H:%M:%S')
                        
                    # Get all possible shards within this date range
                    shards = []
                    current = from_date
                    while current <= to_date:
                        shard_id = self.sharding_strategy._date_to_shard(current)
                        if shard_id not in shards:
                            shards.append(shard_id)
                        
                        # Move to next month
                        month = current.month + 1
                        year = current.year + (month - 1) // 12
                        month = ((month - 1) % 12) + 1
                        current = current.replace(year=year, month=month, day=1)
                    
                    # Get the database instances
                    return [self.get_db_for_shard(shard_id) for shard_id in shards]
                else:
                    logger.error("From and to dates are required for date range query")
                    return []
            else:
                # If not using date-based sharding, query all shards
                return self.get_all_shard_dbs()
                
        else:
            logger.warning(f"Unknown query type: {query_type}")
            # Default to all shards
            return self.get_all_shard_dbs()
    
    def get_all_shard_dbs(self):
        """Get database instances for all existing shards.
        
        Returns:
            list: List of Database instances
        """
        if not self.enable_sharding:
            # Return the main database if sharding is disabled
            return [Database(self.base_db_path)]
            
        # First, check the shards directory
        shards_dir = os.path.join(self.base_dir, "shards")
        
        if not os.path.exists(shards_dir):
            # If shards directory doesn't exist yet, return main database
            return [Database(self.base_db_path)]
            
        # Find all .db files in the shards directory
        shard_files = [f for f in os.listdir(shards_dir) if f.endswith('.db')]
        
        if not shard_files:
            # If no shard files yet, return main database
            return [Database(self.base_db_path)]
            
        # Get database instances for each shard
        dbs = []
        for shard_file in shard_files:
            shard_id = os.path.splitext(shard_file)[0]
            dbs.append(self.get_db_for_shard(shard_id))
            
        return dbs
    
    def migrate_to_sharding(self):
        """Migrate the database from a single file to sharded structure.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enable_sharding:
            logger.warning("Sharding is disabled, cannot migrate")
            return False
            
        logger.info("Starting migration to sharded database structure...")
        
        # Create a backup of the main database
        backup_path = f"{self.base_db_path}.pre_sharding_backup"
        try:
            shutil.copy2(self.base_db_path, backup_path)
            logger.info(f"Created backup at {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False
        
        # Open the main database
        main_db = Database(self.base_db_path)
        main_conn = main_db.get_connection()
        
        if not main_conn.connect():
            logger.error("Failed to connect to main database")
            return False
        
        try:
            # Get all folders
            cursor = main_conn.execute("SELECT folder_id, path FROM folders")
            if not cursor:
                logger.error("Failed to get folders")
                return False
                
            folders = cursor.fetchall()
            logger.info(f"Found {len(folders)} folders to migrate")
            
            # Process each folder
            for folder in folders:
                folder_id = folder['folder_id']
                
                # Determine which shard to use for this folder
                shard_id = self.sharding_strategy.get_shard_for_folder(folder_id)
                
                # Get the database for this shard
                shard_db = self.get_db_for_shard(shard_id)
                shard_conn = shard_db.get_connection()
                
                if not shard_conn.connect():
                    logger.error(f"Failed to connect to shard database for folder {folder_id}")
                    continue
                
                try:
                    # Begin transaction
                    if not shard_conn.begin_transaction():
                        logger.error(f"Failed to begin transaction in shard for folder {folder_id}")
                        continue
                        
                    # Copy folder to shard
                    shard_conn.execute(
                        "INSERT OR IGNORE INTO folders (folder_id, path, enabled, last_scan_time) VALUES (?, ?, ?, ?)",
                        (folder_id, folder['path'], 1, datetime.now())
                    )
                    
                    # Get images for this folder
                    cursor = main_conn.execute("SELECT * FROM images WHERE folder_id = ?", (folder_id,))
                    if not cursor:
                        logger.error(f"Failed to get images for folder {folder_id}")
                        shard_conn.rollback()
                        continue
                        
                    images = cursor.fetchall()
                    logger.info(f"Migrating {len(images)} images for folder {folder_id} to shard {shard_id}")
                    
                    # Copy images to shard in batches
                    batch_size = 100
                    for i in range(0, len(images), batch_size):
                        batch = images[i:i+batch_size]
                        
                        for image in batch:
                            shard_conn.execute(
                                """
                                INSERT OR IGNORE INTO images (
                                    image_id, folder_id, filename, full_path, file_size, 
                                    file_hash, last_modified_date, thumbnail_path, 
                                    ai_description, user_description, last_scanned
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    image['image_id'], image['folder_id'], image['filename'],
                                    image['full_path'], image['file_size'], image['file_hash'],
                                    image['last_modified_date'], image['thumbnail_path'],
                                    image['ai_description'], image['user_description'],
                                    image['last_scanned']
                                )
                            )
                            
                    # Commit transaction
                    if not shard_conn.commit():
                        logger.error(f"Failed to commit transaction in shard for folder {folder_id}")
                        continue
                    
                    # Record the folder-shard mapping
                    self._update_folder_shard_mapping(folder_id, shard_id)
                    
                except Exception as e:
                    logger.error(f"Error migrating folder {folder_id} to shard: {e}")
                    shard_conn.rollback()
                    
                finally:
                    shard_conn.disconnect()
            
            logger.info("Migration to sharded database structure completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            return False
            
        finally:
            main_conn.disconnect()
    
    def cleanup(self):
        """Clean up resources."""
        # Close all database connections
        for db in self.db_cache.values():
            # No direct way to close a Database object, but it's okay
            # as connections are short-lived and closed after use
            pass
            
        self.db_cache.clear()
        logger.debug("Shard manager cleaned up")
