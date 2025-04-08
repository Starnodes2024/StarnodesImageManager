#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Prepared statement caching for StarImageBrowse
Improves query performance by caching and reusing prepared statements.
"""

import logging
import time
import sqlite3
from collections import OrderedDict

logger = logging.getLogger("StarImageBrowse.database.db_statement_cache")

class PreparedStatementCache:
    """Cache for SQLite prepared statements to improve query performance."""
    
    def __init__(self, max_size=100, expiration_seconds=300):
        """Initialize the prepared statement cache.
        
        Args:
            max_size (int): Maximum number of statements to cache
            expiration_seconds (int): Number of seconds before a statement expires
        """
        self.max_size = max_size
        self.expiration_seconds = expiration_seconds
        self.cache = OrderedDict()  # {query_hash: (statement, last_used_time)}
        
    def _get_hash(self, query, params=None):
        """Get a hash for a query and its parameters.
        
        Args:
            query (str): SQL query
            params (tuple, optional): Query parameters
            
        Returns:
            int: Hash of the query and parameters
        """
        # Include parameter types in the hash to ensure type safety
        param_types = None
        if params:
            if isinstance(params, (list, tuple)):
                param_types = tuple(type(p).__name__ for p in params)
            elif isinstance(params, dict):
                param_types = tuple((k, type(v).__name__) for k, v in params.items())
                
        return hash((query, param_types))
        
    def get(self, conn, query, params=None):
        """Get a prepared statement from the cache or prepare a new one.
        
        Args:
            conn (sqlite3.Connection): Database connection
            query (str): SQL query
            params (tuple, optional): Query parameters
            
        Returns:
            sqlite3.Cursor: Prepared statement
        """
        query_hash = self._get_hash(query, params)
        
        # Check if the statement is in the cache
        if query_hash in self.cache:
            statement, last_used_time = self.cache[query_hash]
            
            # Check if the statement has expired
            if time.time() - last_used_time > self.expiration_seconds:
                # Remove from cache and prepare a new statement
                del self.cache[query_hash]
                logger.debug(f"Statement expired: {query}")
            else:
                # Move to the end of the OrderedDict (most recently used)
                self.cache.move_to_end(query_hash)
                self.cache[query_hash] = (statement, time.time())
                logger.debug(f"Using cached statement: {query}")
                return statement
        
        # Prepare a new statement
        try:
            statement = conn.cursor()
            if params is None:
                statement.execute(query)
            else:
                statement.execute(query, params)
                
            # Add to cache
            self.cache[query_hash] = (statement, time.time())
            
            # If the cache is too large, remove the least recently used statement
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
                
            logger.debug(f"Prepared new statement: {query}")
            return statement
            
        except sqlite3.Error as e:
            logger.error(f"Error preparing statement: {e}")
            raise
            
    def clear(self):
        """Clear the statement cache."""
        self.cache.clear()
        logger.debug("Statement cache cleared")
        
    def remove(self, query, params=None):
        """Remove a specific statement from the cache.
        
        Args:
            query (str): SQL query
            params (tuple, optional): Query parameters
        """
        query_hash = self._get_hash(query, params)
        if query_hash in self.cache:
            del self.cache[query_hash]
            logger.debug(f"Removed statement from cache: {query}")
            
    def get_stats(self):
        """Get statistics about the cache.
        
        Returns:
            dict: Cache statistics
        """
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_ratio": 0,  # Would need to track hits and misses over time
            "oldest_statement_age": max(time.time() - self.cache[k][1] for k in self.cache) if self.cache else 0
        }


# Enhancement to DatabaseConnection for statement caching
class CachedDatabaseConnection:
    """Enhances DatabaseConnection with prepared statement caching."""
    
    def __init__(self, db_path, max_cache_size=100, expiration_seconds=300):
        """Initialize a cached database connection.
        
        Args:
            db_path (str): Path to the SQLite database file
            max_cache_size (int): Maximum number of statements to cache
            expiration_seconds (int): Number of seconds before a statement expires
        """
        from .db_core import DatabaseConnection
        self.db_connection = DatabaseConnection(db_path)
        self.statement_cache = PreparedStatementCache(max_cache_size, expiration_seconds)
        
    def __getattr__(self, name):
        """Delegate attribute access to the underlying DatabaseConnection."""
        return getattr(self.db_connection, name)
        
    def execute_cached(self, query, params=None):
        """Execute a SQL query using a cached prepared statement.
        
        Args:
            query (str): SQL query to execute
            params (tuple, optional): Parameters for the query
            
        Returns:
            cursor: Database cursor for fetching results
        """
        if self.db_connection.conn is None:
            if not self.db_connection.connect():
                return None
                
        try:
            return self.statement_cache.get(self.db_connection.conn, query, params)
        except sqlite3.Error as e:
            logger.error(f"Error executing cached statement: {e}")
            return None
