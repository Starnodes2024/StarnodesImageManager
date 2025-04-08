#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database performance optimizer for StarImageBrowse
Integrates and manages various optimization strategies.
"""

import os
import logging
import time
import sqlite3
from pathlib import Path

from .db_indexing import DatabaseIndexOptimizer
from .db_core import Database, DatabaseConnection
from .db_statement_cache import CachedDatabaseConnection
from .db_optimizer import DatabaseOptimizer

logger = logging.getLogger("StarImageBrowse.database.performance_optimizer")

class DatabasePerformanceOptimizer:
    """Comprehensive database performance optimizer."""
    
    def __init__(self, db_path):
        """Initialize the database performance optimizer.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self.index_optimizer = DatabaseIndexOptimizer(db_path)
        self.optimizer = DatabaseOptimizer(None)  # Will be initialized on demand
        
    def run_quick_optimizations(self):
        """Run quick optimization strategies.
        
        Returns:
            dict: Optimization results with metrics
        """
        start_time = time.time()
        results = {
            "success": True,
            "steps_completed": [],
            "errors": [],
            "metrics": {
                "total_time_seconds": 0,
                "size_before_mb": 0,
                "size_after_mb": 0
            }
        }
        
        try:
            # Record initial database size
            if os.path.exists(self.db_path):
                results["metrics"]["size_before_mb"] = os.path.getsize(self.db_path) / (1024 * 1024)
            
            # Step 1: Create optimized indexes
            logger.info("Step 1: Creating optimized indexes")
            if self.index_optimizer.create_optimized_indexes():
                results["steps_completed"].append("index_optimization")
            else:
                results["errors"].append("Failed to create optimized indexes")
                results["success"] = False
            
            # Step 2: Run ANALYZE to update statistics
            logger.info("Step 2: Running ANALYZE")
            conn = DatabaseConnection(self.db_path)
            try:
                if conn.connect():
                    conn.execute("ANALYZE")
                    conn.commit()
                    results["steps_completed"].append("analyze")
                else:
                    results["errors"].append("Failed to connect to database for ANALYZE")
                    results["success"] = False
            except Exception as e:
                logger.error(f"Error running ANALYZE: {e}")
                results["errors"].append(f"Error running ANALYZE: {e}")
                results["success"] = False
            finally:
                conn.disconnect()
            
            # Step 3: Run pragma optimizations
            logger.info("Step 3: Setting performance pragmas")
            conn = DatabaseConnection(self.db_path)
            try:
                if conn.connect():
                    # Set performance optimizations
                    performance_pragmas = [
                        "PRAGMA journal_mode = WAL",          # Use WAL mode for better concurrency
                        "PRAGMA synchronous = NORMAL",        # Reasonable durability with better performance
                        "PRAGMA cache_size = -8000",         # 8MB page cache (negative means KB)
                        "PRAGMA temp_store = MEMORY",        # Store temp tables in memory
                        "PRAGMA mmap_size = 268435456",      # Memory-map up to 256MB of the database file
                        "PRAGMA auto_vacuum = INCREMENTAL"   # Incremental vacuum to reduce file size
                    ]
                    
                    for pragma in performance_pragmas:
                        conn.execute(pragma)
                    
                    conn.commit()
                    results["steps_completed"].append("performance_pragmas")
                else:
                    results["errors"].append("Failed to connect to database for pragmas")
                    results["success"] = False
            except Exception as e:
                logger.error(f"Error setting performance pragmas: {e}")
                results["errors"].append(f"Error setting performance pragmas: {e}")
                results["success"] = False
            finally:
                conn.disconnect()
            
            # Record final database size
            if os.path.exists(self.db_path):
                results["metrics"]["size_after_mb"] = os.path.getsize(self.db_path) / (1024 * 1024)
            
            # Calculate metrics
            results["metrics"]["total_time_seconds"] = time.time() - start_time
            
            logger.info(f"Quick optimizations completed in {results['metrics']['total_time_seconds']:.2f} seconds")
            return results
            
        except Exception as e:
            logger.error(f"Error running quick optimizations: {e}")
            results["success"] = False
            results["errors"].append(f"Unexpected error: {e}")
            results["metrics"]["total_time_seconds"] = time.time() - start_time
            return results
    
    def measure_query_performance(self, queries):
        """Measure the performance of specific queries.
        
        Args:
            queries (dict): Dictionary of query_name -> SQL query
            
        Returns:
            dict: Query performance metrics
        """
        results = {}
        
        conn = DatabaseConnection(self.db_path)
        try:
            if not conn.connect():
                return {"error": "Failed to connect to database"}
            
            for name, query in queries.items():
                start_time = time.time()
                cursor = conn.execute(query)
                
                if cursor:
                    # Just fetch the results to complete the query
                    rows = cursor.fetchall()
                    execution_time = time.time() - start_time
                    
                    results[name] = {
                        "execution_time_ms": execution_time * 1000,
                        "row_count": len(rows)
                    }
                else:
                    results[name] = {
                        "error": "Query execution failed"
                    }
        except Exception as e:
            logger.error(f"Error measuring query performance: {e}")
            return {"error": str(e)}
        finally:
            conn.disconnect()
        
        return results
    
    def get_cached_connection(self, max_cache_size=100, expiration_seconds=300):
        """Get a cached database connection with prepared statement caching.
        
        Args:
            max_cache_size (int): Maximum size of the statement cache
            expiration_seconds (int): Expiration time for cached statements
            
        Returns:
            CachedDatabaseConnection: A database connection with statement caching
        """
        return CachedDatabaseConnection(
            self.db_path, 
            max_cache_size=max_cache_size, 
            expiration_seconds=expiration_seconds
        )
    
    def get_index_usage_stats(self):
        """Get statistics about index usage.
        
        Returns:
            dict: Index usage statistics
        """
        return self.index_optimizer.check_index_usage()
    
    def get_database_stats(self):
        """Get comprehensive database statistics.
        
        Returns:
            dict: Database statistics
        """
        stats = {
            "file_size_mb": 0,
            "wal_size_mb": 0,
            "total_images": 0,
            "total_folders": 0,
            "images_with_descriptions": 0,
            "avg_description_length": 0,
            "index_count": 0,
            "storage_overhead_percent": 0
        }
        
        try:
            # Get file sizes
            if os.path.exists(self.db_path):
                stats["file_size_mb"] = os.path.getsize(self.db_path) / (1024 * 1024)
            
            wal_path = f"{self.db_path}-wal"
            if os.path.exists(wal_path):
                stats["wal_size_mb"] = os.path.getsize(wal_path) / (1024 * 1024)
            
            # Connect to the database
            conn = DatabaseConnection(self.db_path)
            if not conn.connect():
                return {"error": "Failed to connect to database"}
            
            try:
                # Get basic counts
                cursor = conn.execute("SELECT COUNT(*) FROM images")
                if cursor:
                    stats["total_images"] = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM folders")
                if cursor:
                    stats["total_folders"] = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM images WHERE ai_description IS NOT NULL AND ai_description != ''")
                if cursor:
                    stats["images_with_descriptions"] = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT AVG(LENGTH(ai_description)) FROM images WHERE ai_description IS NOT NULL AND ai_description != ''")
                if cursor:
                    avg_length = cursor.fetchone()[0]
                    stats["avg_description_length"] = avg_length if avg_length else 0
                
                # Get index count
                cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
                if cursor:
                    stats["index_count"] = cursor.fetchone()[0]
                
                # Get storage overhead
                cursor = conn.execute("PRAGMA page_count")
                if cursor:
                    page_count = cursor.fetchone()[0]
                    
                    cursor = conn.execute("PRAGMA page_size")
                    if cursor:
                        page_size = cursor.fetchone()[0]
                        
                        cursor = conn.execute("PRAGMA freelist_count")
                        if cursor:
                            freelist_count = cursor.fetchone()[0]
                            
                            if page_count > 0:
                                stats["storage_overhead_percent"] = (freelist_count / page_count) * 100
                
            finally:
                conn.disconnect()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {"error": str(e)}
