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
    
    def __init__(self, db_manager, parent=None, language_manager=None):
        """Initialize the database optimization dialog.
        
        Args:
            db_manager: Database manager instance
            parent (QWidget, optional): Parent widget
            language_manager: Language manager instance
        """
        super().__init__(parent)
        
        self.db_manager = db_manager
        self.language_manager = language_manager
        self.optimization_thread = None
        
        self.setWindowTitle(self.get_translation('dialog_title', 'Database Optimization'))
        self.setMinimumSize(500, 400)
        
        self.setup_ui()
    
    def get_translation(self, key, default=None):
        """Get a translation for a key.
        
        Args:
            key (str): Key in the db_optimization section
            default (str, optional): Default value if translation not found
            
        Returns:
            str: Translated string or default value
        """
        if hasattr(self, 'language_manager') and self.language_manager:
            return self.language_manager.translate('db_optimization', key, default)
        return default
    
    def setup_ui(self):
        """Set up the dialog UI."""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Info label
        info_text = self.get_translation('info_text', 
            "This tool will optimize the database for better performance with large image collections. "
            "The optimization process may take several minutes depending on the size of your database."
        )
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Database stats
        self.stats_label = QLabel(self.get_translation('analyzing_database', 'Analyzing database...'))
        layout.addWidget(self.stats_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel(self.get_translation('ready_to_optimize', 'Ready to optimize'))
        layout.addWidget(self.status_label)
        
        # Log output
        log_group = QLabel(self.get_translation('optimization_log', 'Optimization Log:'))
        layout.addWidget(log_group)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(150)
        layout.addWidget(self.log_output)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Start button
        self.start_button = QPushButton(self.get_translation('start_optimization', 'Start Optimization'))
        self.start_button.clicked.connect(self.start_optimization)
        button_layout.addWidget(self.start_button)
        
        # Close button
        self.close_button = QPushButton(self.get_translation('close', 'Close'))
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        # Update database stats
        self.update_database_stats()
    
    def update_database_stats(self):
        """Update the database statistics display."""
        try:
            # Connect to database
            if not self.db_manager.connect():
                self.stats_label.setText("Error: Failed to connect to database")
                return
            
            # Get database statistics
            stats = self.db_manager.get_database_stats()
            
            # Update stats label
            stats_text = self.get_translation('database_statistics', 'Database Statistics:\n- Total Images: {images}\n- Total Folders: {folders}\n- Database Size: {size} MB')
            stats_text = stats_text.format(
                images=stats['total_images'],
                folders=stats['total_folders'],
                size=f"{stats['database_size_mb']:.2f}"
            )
            self.stats_label.setText(stats_text)
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            self.stats_label.setText(f"Error getting database stats: {str(e)}")
        finally:
            self.db_manager.disconnect()
    
    def start_optimization(self):
        """Start the database optimization process."""
        # Disable buttons during optimization
        self.start_button.setEnabled(False)
        self.close_button.setEnabled(False)
        
        # Reset progress
        self.progress_bar.setValue(0)
        self.status_label.setText(self.get_translation('starting_optimization', 'Starting optimization...'))
        self.log_output.clear()
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
            self.status_label.setText(self.get_translation('optimization_completed', 'Optimization completed successfully'))
            
            # Log success
            self.log_message(self.get_translation('optimization_success', 'Database optimization completed successfully'))
            
            # Log statistics
            total_images = stats.get("total_images", 0)
            total_folders = stats.get("total_folders", 0)
            db_size_mb = stats.get("database_size_mb", 0)
            
            self.log_message(self.get_translation('total_images', 'Total images: {count}').format(count=total_images))
            self.log_message(self.get_translation('total_folders', 'Total folders: {count}').format(count=total_folders))
            self.log_message(self.get_translation('database_size', 'Database size: {size} MB').format(size=f"{db_size_mb:.2f}"))
            
            # Update stats label
            stats_text = self.get_translation('database_statistics_after', 'Database Statistics After Optimization:\n- Total Images: {images}\n- Total Folders: {folders}\n- Database Size: {size} MB')
            stats_text = stats_text.format(
                images=total_images,
                folders=total_folders,
                size=f"{db_size_mb:.2f}"
            )
            self.stats_label.setText(stats_text)
            
            # Show success message
            QMessageBox.information(
                self,
                self.get_translation('optimization_complete_title', 'Optimization Complete'),
                self.get_translation('optimization_complete_message', 'Database has been optimized for large image collections.'),
                QMessageBox.StandardButton.Ok
            )
        else:
            # Update progress
            self.progress_bar.setValue(0)
            self.status_label.setText(self.get_translation('optimization_failed', 'Optimization failed'))
            
            # Log error
            error_msg = stats.get("error", self.get_translation('unknown_error', 'Unknown error'))
            self.log_message(self.get_translation('optimization_failed_log', 'Optimization failed: {error}').format(error=error_msg))
            
            # Show error message
            QMessageBox.critical(
                self,
                self.get_translation('optimization_failed_title', 'Optimization Failed'),
                self.get_translation('optimization_failed_message', 'Failed to optimize database: {error}').format(error=error_msg),
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
                self.get_translation('optimization_in_progress_title', 'Optimization in Progress'),
                self.get_translation('optimization_in_progress_message', 'Database optimization is still in progress. Are you sure you want to cancel?'),
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
