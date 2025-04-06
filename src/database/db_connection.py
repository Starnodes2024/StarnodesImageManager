#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database connection manager for StarImageBrowse
Implements a connection pool pattern for stable database connections
"""

import os
import sqlite3
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger("StarImageBrowse.database.db_connection")

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
        self.last_used = time.time()
        
    def connect(self):
        """Establish a connection to the database."""
        if self.conn is not None:
            return True
            
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            self.cursor = self.conn.cursor()
            self.last_used = time.time()
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
            self.last_used = time.time()
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
            self.last_used = time.time()
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
            self.last_used = time.time()
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
            self.last_used = time.time()
            return self.cursor
        except sqlite3.Error as e:
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
            self.last_used = time.time()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error executing query with multiple parameters: {e}")
            return False
            
    def is_idle(self, idle_timeout=60):
        """Check if the connection has been idle for too long.
        
        Args:
            idle_timeout (int): Timeout in seconds
            
        Returns:
            bool: True if the connection has been idle for longer than the timeout
        """
        return (time.time() - self.last_used) > idle_timeout


class ConnectionPool:
    """A pool of database connections."""
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls, db_path=None):
        """Get the singleton instance of the connection pool.
        
        Args:
            db_path (str, optional): Path to the SQLite database file
            
        Returns:
            ConnectionPool: Singleton instance of the connection pool
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if db_path is None:
                        raise ValueError("Database path must be provided when creating the connection pool")
                    cls._instance = cls(db_path)
        return cls._instance
    
    def __init__(self, db_path):
        """Initialize the connection pool.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self.pool = []
        self.in_use = {}
        self.lock = threading.Lock()
        self.max_connections = 5
        self.idle_timeout = 60  # seconds
        
        # Ensure the database directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize the database if it doesn't exist
        self._initialize_database_if_needed()
        
        # Start a background thread to clean up idle connections
        self._start_cleanup_thread()
        
    def _initialize_database_if_needed(self):
        """Initialize the database if it doesn't exist."""
        if not os.path.exists(self.db_path):
            logger.info(f"Creating new database at {self.db_path}")
            conn = self.get_connection()
            try:
                # Create the database schema
                from src.database.db_startup_repair import create_schema
                create_schema(conn.conn, conn.cursor)
                logger.info("Database schema created successfully")
            finally:
                self.release_connection(conn)
        else:
            # Check and repair the database if needed
            from src.database.db_startup_repair import ensure_database_integrity
            ensure_database_integrity(self.db_path)
        
    def _start_cleanup_thread(self):
        """Start a background thread to clean up idle connections."""
        def cleanup_idle_connections():
            while True:
                time.sleep(30)  # Check every 30 seconds
                self._cleanup_idle_connections()
                
        thread = threading.Thread(target=cleanup_idle_connections, daemon=True)
        thread.start()
        
    def _cleanup_idle_connections(self):
        """Clean up idle connections."""
        with self.lock:
            idle_connections = [conn for conn in self.pool if conn.is_idle(self.idle_timeout)]
            for conn in idle_connections:
                conn.disconnect()
                self.pool.remove(conn)
            
    def get_connection(self):
        """Get a connection from the pool.
        
        Returns:
            DatabaseConnection: A database connection
        """
        with self.lock:
            # Check if there's an available connection in the pool
            if self.pool:
                conn = self.pool.pop(0)
                if conn.connect():  # Ensure the connection is still valid
                    thread_id = threading.get_ident()
                    self.in_use[thread_id] = conn
                    return conn
                
            # Create a new connection if we haven't reached the maximum
            if len(self.in_use) < self.max_connections:
                conn = DatabaseConnection(self.db_path)
                if conn.connect():
                    thread_id = threading.get_ident()
                    self.in_use[thread_id] = conn
                    return conn
                    
            # Wait for a connection to become available
            logger.warning("Connection pool exhausted, waiting for a connection to become available")
            return None
            
    def release_connection(self, conn):
        """Release a connection back to the pool.
        
        Args:
            conn (DatabaseConnection): The connection to release
        """
        if conn is None:
            return
            
        with self.lock:
            thread_id = threading.get_ident()
            if thread_id in self.in_use:
                del self.in_use[thread_id]
                
            # Only add the connection back to the pool if it's still valid
            if conn.conn is not None:
                self.pool.append(conn)
                
    def close_all_connections(self):
        """Close all connections in the pool."""
        with self.lock:
            # Close all connections in the pool
            for conn in self.pool:
                conn.disconnect()
            self.pool = []
            
            # Close all in-use connections
            for thread_id, conn in self.in_use.items():
                conn.disconnect()
            self.in_use = {}
            
    def get_stats(self):
        """Get statistics about the connection pool.
        
        Returns:
            dict: Statistics about the connection pool
        """
        with self.lock:
            return {
                "pool_size": len(self.pool),
                "in_use": len(self.in_use),
                "max_connections": self.max_connections
            }
