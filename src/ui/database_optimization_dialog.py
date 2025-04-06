#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database optimization dialog for StarImageBrowse
Provides a UI for optimizing the database for large image collections.
"""

import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QMessageBox, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize

from src.database.db_optimizer import DatabaseOptimizer

logger = logging.getLogger("StarImageBrowse.ui.database_optimization_dialog")

class OptimizationThread(QThread):
    """Thread for running database optimization."""
    
    progress_signal = pyqtSignal(int, int, str)  # current, total, message
    finished_signal = pyqtSignal(bool, dict)  # success, stats
    
    def __init__(self, db_manager):
        """Initialize the optimization thread.
        
        Args:
            db_manager: Database manager instance
        """
        super().__init__()
        self.db_manager = db_manager
        self.optimizer = DatabaseOptimizer(db_manager)
        
    def run(self):
        """Run the optimization process."""
        try:
            # Report progress
            self.progress_signal.emit(0, 5, "Starting database optimization...")
            
            # Run basic optimizations - this now includes creating a new optimized database
            # which is safer and prevents corruption
            self.progress_signal.emit(1, 5, "Creating optimized database...")
            if not self.optimizer.optimize_database():
                self.finished_signal.emit(False, {"error": "Failed to optimize database"})
                return
            
            # Create virtual tables for full-text search - now part of optimize_database
            self.progress_signal.emit(3, 5, "Creating virtual tables for full-text search...")
            
            # Optimize query performance - now part of optimize_database
            self.progress_signal.emit(4, 5, "Optimizing query performance...")
            
            # Analyze and log database statistics
            self.progress_signal.emit(5, 5, "Analyzing database statistics...")
            stats = self.optimizer.analyze_database_stats()
            logger.info(f"Database statistics: {stats['total_images']} images in {stats['total_folders']} folders")
            logger.info(f"Database size: {stats['database_size_mb']:.2f} MB")
            
            # Report success
            self.finished_signal.emit(True, stats)
            
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            self.finished_signal.emit(False, {"error": str(e)})

class DatabaseOptimizationDialog(QDialog):
    """Dialog for optimizing the database for large image collections."""
    
    def __init__(self, db_manager, parent=None):
        """Initialize the database optimization dialog.
        
        Args:
            db_manager: Database manager instance
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.db_manager = db_manager
        self.optimization_thread = None
        
        self.setWindowTitle("Database Optimization")
        self.setMinimumSize(500, 400)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the dialog UI."""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(
            "This tool will optimize the database for better performance with large image collections. "
            "The optimization process may take several minutes depending on the size of your database."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Database stats
        self.stats_label = QLabel("Analyzing database...")
        layout.addWidget(self.stats_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Ready to optimize")
        layout.addWidget(self.status_label)
        
        # Log output
        log_label = QLabel("Optimization Log:")
        layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(150)
        layout.addWidget(self.log_output)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Optimization")
        self.start_button.clicked.connect(self.start_optimization)
        button_layout.addWidget(self.start_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        # Initialize database stats
        self.update_database_stats()
    
    def update_database_stats(self):
        """Update the database statistics display."""
        try:
            # Connect to database
            if not self.db_manager.connect():
                self.stats_label.setText("Error: Failed to connect to database")
                return
            
            # Get image count
            self.db_manager.cursor.execute("SELECT COUNT(*) FROM images")
            image_count = self.db_manager.cursor.fetchone()[0]
            
            # Get folder count
            self.db_manager.cursor.execute("SELECT COUNT(*) FROM folders")
            folder_count = self.db_manager.cursor.fetchone()[0]
            
            # Get database file size
            db_size_mb = 0
            if os.path.exists(self.db_manager.db_path):
                db_size_mb = os.path.getsize(self.db_manager.db_path) / (1024 * 1024)
            
            # Update stats label
            self.stats_label.setText(
                f"Current Database Statistics:\n"
                f"- Total Images: {image_count}\n"
                f"- Total Folders: {folder_count}\n"
                f"- Database Size: {db_size_mb:.2f} MB"
            )
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            self.stats_label.setText(f"Error getting database stats: {str(e)}")
        finally:
            self.db_manager.disconnect()
    
    def start_optimization(self):
        """Start the database optimization process."""
        # Disable start button
        self.start_button.setEnabled(False)
        self.close_button.setEnabled(False)
        
        # Clear log
        self.log_output.clear()
        
        # Log start
        self.log_message("Starting database optimization...")
        
        # Create and start optimization thread
        self.optimization_thread = OptimizationThread(self.db_manager)
        self.optimization_thread.progress_signal.connect(self.update_progress)
        self.optimization_thread.finished_signal.connect(self.optimization_finished)
        self.optimization_thread.start()
    
    def update_progress(self, current, total, message):
        """Update the progress display.
        
        Args:
            current (int): Current progress value
            total (int): Total progress value
            message (str): Progress message
        """
        # Update progress bar
        progress_percent = int((current / total) * 100)
        self.progress_bar.setValue(progress_percent)
        
        # Update status label
        self.status_label.setText(message)
        
        # Log message
        self.log_message(message)
    
    def log_message(self, message):
        """Add a message to the log output.
        
        Args:
            message (str): Message to log
        """
        self.log_output.append(message)
    
    def optimization_finished(self, success, stats):
        """Handle optimization completion.
        
        Args:
            success (bool): Whether optimization was successful
            stats (dict): Database statistics
        """
        if success:
            # Update progress
            self.progress_bar.setValue(100)
            self.status_label.setText("Optimization completed successfully")
            
            # Log success
            self.log_message("Database optimization completed successfully")
            
            # Log statistics
            total_images = stats.get("total_images", 0)
            total_folders = stats.get("total_folders", 0)
            db_size_mb = stats.get("database_size_mb", 0)
            
            self.log_message(f"Total images: {total_images}")
            self.log_message(f"Total folders: {total_folders}")
            self.log_message(f"Database size: {db_size_mb:.2f} MB")
            
            # Update stats label
            self.stats_label.setText(
                f"Database Statistics After Optimization:\n"
                f"- Total Images: {total_images}\n"
                f"- Total Folders: {total_folders}\n"
                f"- Database Size: {db_size_mb:.2f} MB"
            )
            
            # Show success message
            QMessageBox.information(
                self,
                "Optimization Complete",
                "Database has been optimized for large image collections.",
                QMessageBox.StandardButton.Ok
            )
        else:
            # Update progress
            self.progress_bar.setValue(0)
            self.status_label.setText("Optimization failed")
            
            # Log error
            error_msg = stats.get("error", "Unknown error")
            self.log_message(f"Optimization failed: {error_msg}")
            
            # Show error message
            QMessageBox.critical(
                self,
                "Optimization Failed",
                f"Failed to optimize database: {error_msg}",
                QMessageBox.StandardButton.Ok
            )
        
        # Re-enable buttons
        self.start_button.setEnabled(True)
        self.close_button.setEnabled(True)
    
    def closeEvent(self, event):
        """Handle dialog close event.
        
        Args:
            event: Close event
        """
        # Check if optimization is running
        if self.optimization_thread and self.optimization_thread.isRunning():
            # Ask for confirmation
            response = QMessageBox.question(
                self,
                "Optimization in Progress",
                "Database optimization is still in progress. Are you sure you want to cancel?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if response == QMessageBox.StandardButton.Yes:
                # Terminate thread
                self.optimization_thread.terminate()
                self.optimization_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
