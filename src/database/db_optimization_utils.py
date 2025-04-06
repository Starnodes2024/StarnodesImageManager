#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database optimization utilities for StarImageBrowse
Provides functions to optimize the database for large image collections.
"""

import os
import logging
import time
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal, QThreadPool

from .db_optimizer import DatabaseOptimizer
from src.ui.progress_dialog import ProgressDialog

logger = logging.getLogger("StarImageBrowse.database.db_optimization_utils")

class OptimizationSignals(QObject):
    """Signals for database optimization."""
    finished = pyqtSignal(dict)  # Results dictionary
    error = pyqtSignal(tuple)  # Error info
    progress = pyqtSignal(int, int, str)  # current, total, message

class OptimizationTask(QRunnable):
    """Task for optimizing the database in a background thread."""
    
    def __init__(self, db_manager):
        """Initialize the optimization task.
        
        Args:
            db_manager: Database manager instance
        """
        super().__init__()
        self.db_manager = db_manager
        self.signals = OptimizationSignals()
        self.optimizer = DatabaseOptimizer(db_manager)
        
    def run(self):
        """Run the optimization task."""
        try:
            # Report progress
            self.signals.progress.emit(0, 4, "Starting database optimization...")
            
            # Run basic optimizations
            self.signals.progress.emit(1, 4, "Running basic database optimizations...")
            if not self.optimizer.optimize_database():
                self.signals.error.emit(("Failed to run basic database optimizations",))
                return
            
            # Create virtual tables for full-text search
            self.signals.progress.emit(2, 4, "Creating virtual tables for full-text search...")
            if not self.optimizer.create_virtual_tables():
                logger.warning("Failed to create virtual tables for full-text search")
                # Continue anyway as this is not critical
            
            # Optimize query performance
            self.signals.progress.emit(3, 4, "Optimizing query performance...")
            if not self.optimizer.optimize_query_performance():
                logger.warning("Failed to optimize query performance")
                # Continue anyway as this is not critical
            
            # Analyze and log database statistics
            self.signals.progress.emit(4, 4, "Analyzing database statistics...")
            stats = self.optimizer.analyze_database_stats()
            logger.info(f"Database statistics: {stats['total_images']} images in {stats['total_folders']} folders")
            logger.info(f"Database size: {stats['database_size_mb']:.2f} MB")
            
            # Report success
            self.signals.finished.emit({
                "success": True,
                "stats": stats
            })
            
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            self.signals.error.emit((str(e),))

def optimize_database_for_large_collections(main_window):
    """Optimize the database for large image collections.
    
    Args:
        main_window: Main window instance
    """
    # Create progress dialog
    progress_dialog = ProgressDialog(
        "Optimizing Database",
        "Optimizing database for large image collections...",
        main_window,
        cancellable=False
    )
    
    # Define progress callback
    def progress_callback(current, total, message=None):
        try:
            if progress_dialog and progress_dialog.isVisible():
                progress_dialog.update_progress(current, total)
                if message:
                    progress_dialog.update_operation(message)
        except Exception as e:
            logger.error(f"Error in progress callback: {e}")
    
    # Define completion callback
    def on_task_complete(results):
        try:
            if results and results.get("success"):
                # Get statistics
                stats = results.get("stats", {})
                total_images = stats.get("total_images", 0)
                total_folders = stats.get("total_folders", 0)
                db_size = stats.get("database_size_mb", 0)
                
                # Update progress dialog
                progress_dialog.update_operation("Optimization complete")
                progress_dialog.log_message("Database has been optimized for large image collections")
                progress_dialog.log_message(f"Total images: {total_images}")
                progress_dialog.log_message(f"Total folders: {total_folders}")
                progress_dialog.log_message(f"Database size: {db_size:.2f} MB")
                progress_dialog.close_when_finished()
                
                # Update status bar
                main_window.status_bar.showMessage("Database optimization completed successfully")
                
                # Show success message
                QMessageBox.information(
                    main_window,
                    "Optimization Complete",
                    f"Database has been optimized for large image collections.\n\n"
                    f"Total images: {total_images}\n"
                    f"Total folders: {total_folders}\n"
                    f"Database size: {db_size:.2f} MB",
                    QMessageBox.StandardButton.Ok
                )
            else:
                error_msg = results.get("error", "Unknown error")
                progress_dialog.log_message(f"Optimization failed: {error_msg}")
                progress_dialog.close_when_finished()
                
                # Show error message
                QMessageBox.critical(
                    main_window,
                    "Optimization Failed",
                    f"Failed to optimize database: {error_msg}",
                    QMessageBox.StandardButton.Ok
                )
        except Exception as e:
            logger.error(f"Error in optimization completion callback: {e}")
            if progress_dialog and progress_dialog.isVisible():
                progress_dialog.close()
    
    # Define error callback
    def on_task_error(error_info):
        try:
            error_msg = error_info[0] if error_info and len(error_info) > 0 else "Unknown error"
            logger.error(f"Optimization error: {error_msg}")
            
            if progress_dialog and progress_dialog.isVisible():
                progress_dialog.log_message(f"Error during optimization: {error_msg}")
                progress_dialog.close_when_finished()
            
            # Show error message
            QMessageBox.critical(
                main_window,
                "Optimization Error",
                f"An error occurred during database optimization: {error_msg}",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            logger.error(f"Error in optimization error callback: {e}")
            if progress_dialog and progress_dialog.isVisible():
                progress_dialog.close()
    
    # Create optimization task
    task = OptimizationTask(main_window.db_manager)
    task.signals.progress.connect(progress_callback)
    task.signals.finished.connect(on_task_complete)
    task.signals.error.connect(on_task_error)
    
    # Show progress dialog
    progress_dialog.show()
    
    # Start task in thread pool
    QThreadPool.globalInstance().start(task)

def check_and_optimize_if_needed(main_window):
    """Check if database optimization is needed and perform it if necessary.
    
    Args:
        main_window: Main window instance
        
    Returns:
        bool: True if optimization was performed, False otherwise
    """
    try:
        # Connect to database
        if not main_window.db_manager.connect():
            logger.error("Failed to connect to database for optimization check")
            return False
        
        # Get image count
        main_window.db_manager.cursor.execute("SELECT COUNT(*) FROM images")
        image_count = main_window.db_manager.cursor.fetchone()[0]
        
        # Get database file size
        db_size_mb = 0
        if os.path.exists(main_window.db_manager.db_path):
            db_size_mb = os.path.getsize(main_window.db_manager.db_path) / (1024 * 1024)
        
        # Check if optimization is needed
        # Optimize if more than 1000 images or database larger than 100MB
        needs_optimization = (image_count > 1000 or db_size_mb > 100)
        
        # Disconnect from database
        main_window.db_manager.disconnect()
        
        if needs_optimization:
            # Ask user if they want to optimize
            response = QMessageBox.question(
                main_window,
                "Database Optimization",
                f"Your image collection is getting large ({image_count} images, {db_size_mb:.2f} MB).\n\n"
                f"Would you like to optimize the database for better performance?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if response == QMessageBox.StandardButton.Yes:
                # Perform optimization
                optimize_database_for_large_collections(main_window)
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking if optimization is needed: {e}")
        if main_window.db_manager.conn:
            main_window.db_manager.disconnect()
        return False
