#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database maintenance dialog for StarImageBrowse
Provides a single interface for all database maintenance and upgrade tasks.
"""

import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox, QDialogButtonBox, QGroupBox,
    QCheckBox, QFrame, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QThread

from src.utils.image_dimensions_updater import ImageDimensionsUpdater
from src.database.db_upgrade import upgrade_database_schema

logger = logging.getLogger("StarImageBrowse.ui.database_maintenance_dialog")

class DatabaseMaintenanceDialog(QDialog):
    """Dialog for performing all database maintenance tasks in one place."""
    
    def __init__(self, parent, db_manager, enhanced_search=None, language_manager=None):
        """Initialize the dialog.
        
        Args:
            parent: Parent widget
            db_manager: Database manager instance
            enhanced_search: Enhanced search instance (optional)
            language_manager: Language manager instance
        """
        super().__init__(parent)
        self.db_manager = db_manager
        self.enhanced_search = enhanced_search or db_manager.enhanced_search
        self.language_manager = language_manager
        self.updater = ImageDimensionsUpdater(db_manager, self.enhanced_search)
        
        # Set up task tracking
        self.tasks = {
            "repair_database": {
                "name": self.get_translation('repair_database_name', 'Database Repair & Integrity Check'),
                "description": self.get_translation('repair_database_desc', 'Checks and repairs database corruption issues'),
                "enabled": True,
                "completed": False,
                "in_progress": False,
                "result": "",
                "critical": True  # This task must run first and successfully
            },
            "schema_upgrade": {
                "name": self.get_translation('schema_upgrade_name', 'Database Schema Upgrade'),
                "description": self.get_translation('schema_upgrade_desc', 'Upgrades the database schema to add missing tables, columns, and indexes'),
                "enabled": True,
                "completed": False,
                "in_progress": False,
                "result": ""
            },
            "metadata_update": {
                "name": self.get_translation('metadata_update_name', 'Image Metadata Update'),
                "description": self.get_translation('metadata_update_desc', 'Updates file format, date added, and last modified information for all images'),
                "enabled": True,
                "completed": False,
                "in_progress": False,
                "result": ""
            },
            "dimensions_update": {
                "name": self.get_translation('dimensions_update_name', 'Image Dimensions Update'),
                "description": self.get_translation('dimensions_update_desc', 'Updates width and height information for all images in the database'),
                "enabled": True,
                "completed": False,
                "in_progress": False,
                "result": ""
            },
            "fts_rebuild": {
                "name": self.get_translation('fts_rebuild_name', 'Full-Text Search Rebuild'),
                "description": self.get_translation('fts_rebuild_desc', 'Rebuilds the full-text search index for faster text searching'),
                "enabled": True,
                "completed": False,
                "in_progress": False,
                "result": ""
            },
            "optimize_database": {
                "name": self.get_translation('optimize_database_name', 'Database Optimization'),
                "description": self.get_translation('optimize_database_desc', 'Optimizes the database file for better performance'),
                "enabled": True,
                "completed": False,
                "in_progress": False,
                "result": ""
            }
        }
        
        self.setup_ui()
        self.retranslateUi()
        
    def get_translation(self, key, default=None):
        """Get a translation for a key.
        
        Args:
            key (str): Key in the db_maintenance section
            default (str, optional): Default value if translation not found
            
        Returns:
            str: Translated string or default value
        """
        if hasattr(self, 'language_manager') and self.language_manager:
            return self.language_manager.translate('db_maintenance', key, default)
        return default
    
    def setup_ui(self):
        """Set up the dialog UI."""
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        main_layout = QVBoxLayout(self)
        
        # Info label
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        main_layout.addWidget(self.info_label)
            "This tool performs comprehensive database maintenance to ensure optimal performance "
            "and compatibility with the latest features. Select the tasks you want to perform:"
        )
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        # Task selection area
        self.task_area = QScrollArea()
        self.task_area.setWidgetResizable(True)
        
        # Tasks group
        tasks_group = QGroupBox(self.get_translation('tasks_group', 'Maintenance Tasks'))
        tasks_layout = QVBoxLayout(tasks_group)
        
        task_widget = QWidget()
        self.task_layout = QVBoxLayout(task_widget)
        
        # Add each task as a check box with description
        self.task_checkboxes = {}
        self.task_status_labels = {}
        
        for task_id, task_info in self.tasks.items():
            task_frame = QFrame()
            task_frame.setFrameShape(QFrame.Shape.StyledPanel)
            task_frame.setFrameShadow(QFrame.Shadow.Raised)
            task_frame.setLineWidth(1)
            
            task_layout = QVBoxLayout(task_frame)
            
            # Header with checkbox and label
            header_layout = QHBoxLayout()
            
            checkbox = QCheckBox(task_info["name"])
            checkbox.setChecked(task_info["enabled"])
            self.task_checkboxes[task_id] = checkbox
            header_layout.addWidget(checkbox)
            
            header_layout.addStretch(1)
            
            # Status label (initially empty)
            status_label = QLabel("")
            status_label.setStyleSheet("font-weight: bold;")
            self.task_status_labels[task_id] = status_label
            header_layout.addWidget(status_label)
            
            task_layout.addLayout(header_layout)
            
            # Description
            desc_label = QLabel(task_info["description"])
            desc_label.setWordWrap(True)
            task_layout.addWidget(desc_label)
            
            # Add the frame to the task layout
            self.task_layout.addWidget(task_frame)
        
        tasks_layout.addLayout(self.task_layout)
        self.task_area.setWidget(task_widget)
        main_layout.addWidget(tasks_group)
        
        # Progress group
        progress_group = QGroupBox(self.get_translation('progress_group', 'Progress'))
        progress_layout = QVBoxLayout(progress_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel(self.get_translation('ready_status', 'Ready to perform maintenance'))
        self.status_label.setWordWrap(True)
        progress_layout.addWidget(self.status_label)
        
        main_layout.addWidget(progress_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.start_maintenance)
        button_box.rejected.connect(self.reject)
        
        # Rename the buttons
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText(self.get_translation('start_maintenance', 'Start Maintenance'))
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText(self.get_translation('close', 'Close'))
        
        main_layout.addWidget(button_box)
        
        # Store buttons for later enabling/disabling
        self.start_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.close_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
    
    def start_maintenance(self):
        """Start the maintenance process."""
        # Disable start button and checkboxes during maintenance
        self.start_button.setEnabled(False)
        for checkbox in self.task_checkboxes.values():
            checkbox.setEnabled(False)
        
        # Update task enabled status based on checkboxes
        for task_id, checkbox in self.task_checkboxes.items():
            self.tasks[task_id]["enabled"] = checkbox.isChecked()
        
        # Count enabled tasks
        enabled_tasks = sum(1 for task in self.tasks.values() if task["enabled"])
        if enabled_tasks == 0:
            QMessageBox.warning(
                self,
                "No Tasks Selected",
                "Please select at least one maintenance task to perform.",
                QMessageBox.StandardButton.Ok
            )
            # Re-enable UI elements
            self.start_button.setEnabled(True)
            for checkbox in self.task_checkboxes.values():
                checkbox.setEnabled(True)
            return
        
        # Create and start the maintenance thread
        self.maintenance_thread = MaintenanceThread(
            self.db_manager,
            self.enhanced_search,
            self.tasks,
            self.updater
        )
        self.maintenance_thread.update_progress.connect(self.update_progress)
        self.maintenance_thread.update_task_status.connect(self.update_task_status)
        self.maintenance_thread.maintenance_completed.connect(self.maintenance_completed)
        self.maintenance_thread.maintenance_error.connect(self.maintenance_error)
        self.maintenance_thread.start()
        
        # Update status
        self.status_label.setText(self.get_translation('starting_maintenance', 'Starting maintenance...'))
    
    @pyqtSlot(int, int, str)
    def update_progress(self, current, total, message):
        """Update the progress bar.
        
        Args:
            current (int): Current progress
            total (int): Total items to process
            message (str): Status message
        """
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
        self.status_label.setText(message)
    
    @pyqtSlot(str, bool, str)
    def update_task_status(self, task_id, success, message):
        """Update task status.
        
        Args:
            task_id (str): ID of the task
            success (bool): Whether the task was successful
            message (str): Status message
        """
        if task_id in self.task_status_labels:
            status_label = self.task_status_labels[task_id]
            if success:
                status_label.setText("✓ Completed")
                status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                status_label.setText("✗ Failed")
                status_label.setStyleSheet("color: red; font-weight: bold;")
            
            # Update task info
            self.tasks[task_id]["completed"] = True
            self.tasks[task_id]["in_progress"] = False
            self.tasks[task_id]["result"] = message
    
    @pyqtSlot(dict)
    def maintenance_completed(self, results):
        """Handle maintenance completion.
        
        Args:
            results (dict): Results of all tasks
        """
        self.progress_bar.setValue(100)
        
        # Update status
        completed_count = sum(1 for task in self.tasks.values() 
                            if task["enabled"] and task["completed"])
        failed_count = sum(1 for task in self.tasks.values() 
                          if task["enabled"] and task["completed"] and "Failed" in task.get("result", ""))
        
        status = (
            f"Maintenance complete: {completed_count} tasks completed, "
            f"{failed_count} failed"
        )
        self.status_label.setText(status)
        
        # Change close button text
        self.close_button.setText("Close")
        
        # Show completion message
        details = "\n".join(f"• {task['name']}: {task['result']}" 
                           for task_id, task in self.tasks.items() 
                           if task["enabled"] and task["completed"])
        
        QMessageBox.information(
            self,
            self.get_translation('maintenance_complete_title', 'Maintenance Complete'),
            self.get_translation('maintenance_complete_message', 'Database maintenance completed with {success} tasks successful and {failed} failed.').format(
                success=completed_count,
                failed=failed_count
            ),
            QMessageBox.StandardButton.Ok
        )
    
    @pyqtSlot(str)
    def maintenance_error(self, error_message):
        """Handle maintenance error.
        
        Args:
            error_message (str): Error message
        """
        self.status_label.setText(f"Error: {error_message}")
        
        # Re-enable start button and checkboxes
        self.start_button.setEnabled(True)
        for checkbox in self.task_checkboxes.values():
            checkbox.setEnabled(True)
        
        # Show error message
        QMessageBox.critical(
            self,
            self.get_translation('maintenance_error_title', 'Maintenance Error'),
            self.get_translation('maintenance_error_message', 'An error occurred during database maintenance:\n{error}').format(error=error_message),
            QMessageBox.StandardButton.Ok
        )


class MaintenanceThread(QThread):
    """Thread for performing database maintenance tasks."""
    
    update_progress = pyqtSignal(int, int, str)
    update_task_status = pyqtSignal(str, bool, str)
    maintenance_completed = pyqtSignal(dict)
    maintenance_error = pyqtSignal(str)
    
    def __init__(self, db_manager, enhanced_search, tasks, updater):
        """Initialize the maintenance thread.
        
        Args:
            db_manager: Database manager instance
            enhanced_search: Enhanced search instance
            tasks (dict): Tasks to perform
            updater: ImageDimensionsUpdater instance
        """
        super().__init__()
        self.db_manager = db_manager
        self.enhanced_search = enhanced_search
        self.tasks = tasks
        self.updater = updater
    
    def run(self):
        """Run the maintenance tasks."""
        results = {}
        
        try:
            total_tasks = sum(1 for task in self.tasks.values() if task["enabled"])
            completed_tasks = 0
            
            # 0. Database Repair (must run first)
            if self.tasks["repair_database"]["enabled"]:
                self.update_progress.emit(
                    completed_tasks, total_tasks,
                    "Checking and repairing database..."
                )
                self.tasks["repair_database"]["in_progress"] = True
                
                try:
                    # Import database repair functions
                    from src.database.db_repair import rebuild_database
                    
                    # We need to close database connections before repair
                    self.db_manager.disconnect()
                    
                    # First, check if we can detect corruption through basic queries
                    try:
                        import sqlite3
                        conn = sqlite3.connect(self.db_manager.db_path)
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA integrity_check")
                        integrity_result = cursor.fetchone()
                        conn.close()
                        
                        if integrity_result and integrity_result[0] == "ok":
                            # Database passes integrity check
                            status_msg = "Database integrity check passed"
                            needs_rebuild = False
                        else:
                            # Database is definitely corrupted
                            status_msg = "Database is corrupted, performing complete rebuild"
                            needs_rebuild = True
                    except Exception as e:
                        # Error running integrity check suggests corruption
                        status_msg = f"Database check failed: {e}, performing complete rebuild"
                        needs_rebuild = True
                    
                    # If database is corrupted, perform a complete rebuild
                    if needs_rebuild:
                        self.update_progress.emit(
                            completed_tasks, total_tasks,
                            "Rebuilding database from scratch..."
                        )
                        
                        # Use more aggressive rebuild function that recreates the entire DB
                        rebuild_success = rebuild_database(self.db_manager.db_path)
                        
                        if rebuild_success:
                            status_msg = "Database successfully rebuilt"
                        else:
                            # Critical failure
                            raise Exception("Failed to rebuild corrupted database")
                    
                    # Reconnect to the freshly repaired database
                    self.db_manager.connect()
                    
                    # Ensure all components use the rebuilt database
                    if hasattr(self.db_manager, 'enhanced_search') and self.db_manager.enhanced_search:
                        # Reset the search connection
                        if hasattr(self.db_manager.enhanced_search, 'reset_connection'):
                            self.db_manager.enhanced_search.reset_connection()
                    
                    # Reload our instance of enhanced search as well
                    if self.enhanced_search and hasattr(self.enhanced_search, 'reset_connection'):
                        self.enhanced_search.reset_connection()
                    
                    # Update task results
                    results["repair_database"] = {"success": True, "message": status_msg}
                    self.update_task_status.emit(
                        "repair_database",
                        True,
                        status_msg
                    )
                except Exception as e:
                    logger.error(f"Error repairing database: {e}")
                    results["repair_database"] = {"success": False, "message": str(e)}
                    self.update_task_status.emit(
                        "repair_database",
                        False,
                        f"Failed: {str(e)}"
                    )
                    
                    # Critical failure - abort remaining tasks
                    self.maintenance_error.emit("Critical database repair failed: " + str(e))
                    return
                
                completed_tasks += 1
            
            # 1. Schema Upgrade
            if self.tasks["schema_upgrade"]["enabled"]:
                self.update_progress.emit(
                    completed_tasks, total_tasks,
                    "Upgrading database schema..."
                )
                self.tasks["schema_upgrade"]["in_progress"] = True
                
                try:
                    success, message = upgrade_database_schema(self.db_manager.db_path)
                    results["schema_upgrade"] = {"success": success, "message": message}
                    
                    self.update_task_status.emit(
                        "schema_upgrade",
                        success,
                        message
                    )
                except Exception as e:
                    logger.error(f"Error upgrading schema: {e}")
                    results["schema_upgrade"] = {"success": False, "message": str(e)}
                    self.update_task_status.emit(
                        "schema_upgrade",
                        False,
                        f"Failed: {str(e)}"
                    )
                
                completed_tasks += 1
            
            # 2. Metadata Update
            if self.tasks["metadata_update"]["enabled"]:
                self.update_progress.emit(
                    completed_tasks, total_tasks,
                    "Updating image metadata (format, dates)..."
                )
                self.tasks["metadata_update"]["in_progress"] = True
                
                try:
                    # Ensure database connection is active
                    logger.info("Ensuring database connection is active before metadata update...")
                    self.db_manager.disconnect()  # Close any existing connections
                    self.db_manager.connect()     # Create fresh connections
                    
                    # Import the metadata updater
                    from src.utils.update_metadata import update_image_metadata
                    
                    # Create progress callback for the metadata update
                    def metadata_progress_callback(current, total):
                        self.update_progress.emit(
                            completed_tasks, total_tasks,
                            f"Updating metadata: {current} of {total} images..."
                        )
                    
                    # Run the metadata update with progress callback
                    stats = update_image_metadata(self.db_manager.db_path, metadata_progress_callback)
                    
                    status_msg = (
                        f"Updated format information for {stats['format_updated']} images, "
                        f"date information for {stats['date_updated']} images, "
                        f"{stats['failed']} failed"
                    )
                    
                    results["metadata_update"] = {
                        "success": stats['format_updated'] > 0 or stats['date_updated'] > 0, 
                        "message": status_msg
                    }
                    
                    self.update_task_status.emit(
                        "metadata_update",
                        stats['format_updated'] > 0 or stats['date_updated'] > 0,
                        status_msg
                    )
                except Exception as e:
                    logger.error(f"Error updating metadata: {e}")
                    results["metadata_update"] = {"success": False, "message": str(e)}
                    self.update_task_status.emit(
                        "metadata_update",
                        False,
                        f"Failed: {str(e)}"
                    )
                
                completed_tasks += 1
            
            # 3. Dimensions Update
            if self.tasks["dimensions_update"]["enabled"]:
                self.update_progress.emit(
                    completed_tasks, total_tasks,
                    "Updating image dimensions..."
                )
                self.tasks["dimensions_update"]["in_progress"] = True
                
                try:
                    # Ensure database connection is active
                    logger.info("Ensuring database connection is active before dimensions update...")
                    self.db_manager.disconnect()  # Close any existing connections
                    self.db_manager.connect()     # Create fresh connections
                    
                    # Reset enhanced search connections
                    if self.enhanced_search and hasattr(self.enhanced_search, 'reset_connection'):
                        self.enhanced_search.reset_connection()
                    
                    # Create a fresh updater with newly connected instances
                    from src.utils.image_dimensions_updater import ImageDimensionsUpdater
                    fresh_updater = ImageDimensionsUpdater(self.db_manager, self.enhanced_search)
                    
                    def progress_callback(current, total):
                        self.update_progress.emit(
                            completed_tasks, total_tasks,
                            f"Updating dimensions: {current} of {total} images..."
                        )
                    
                    # Use our fresh updater instance
                    update_results = fresh_updater.update_all_images(progress_callback)
                    
                    status_msg = (
                        f"Updated {update_results['updated_count']} images, "
                        f"{update_results['failed_count']} failed, "
                        f"{update_results['not_found_count']} not found"
                    )
                    
                    results["dimensions_update"] = {
                        "success": update_results['updated_count'] > 0, 
                        "message": status_msg
                    }
                    
                    self.update_task_status.emit(
                        "dimensions_update",
                        update_results['updated_count'] > 0,
                        status_msg
                    )
                except Exception as e:
                    logger.error(f"Error updating dimensions: {e}")
                    results["dimensions_update"] = {"success": False, "message": str(e)}
                    self.update_task_status.emit(
                        "dimensions_update",
                        False,
                        f"Failed: {str(e)}"
                    )
                
                completed_tasks += 1
            
            # 3. FTS Rebuild
            if self.tasks["fts_rebuild"]["enabled"]:
                self.update_progress.emit(
                    completed_tasks, total_tasks,
                    "Rebuilding full-text search index..."
                )
                self.tasks["fts_rebuild"]["in_progress"] = True
                
                try:
                    # Ensure database connection is active
                    logger.info("Ensuring database connection is active before FTS rebuild...")
                    self.db_manager.disconnect()  # Close any existing connections
                    self.db_manager.connect()     # Create fresh connections
                    
                    # Create a fresh connection for FTS operations
                    import sqlite3
                    
                    # Verify database integrity before proceeding
                    from src.database.db_repair import check_database_integrity
                    db_integrity = check_database_integrity(self.db_manager.db_path)
                    if not db_integrity:
                        raise Exception("Database integrity check failed - cannot rebuild FTS")
                    
                    # Create fresh connection
                    conn = sqlite3.connect(self.db_manager.db_path)
                    cursor = conn.cursor()
                    
                    # Get count of images to process
                    image_count = cursor.execute(
                        "SELECT COUNT(*) FROM images"
                    ).fetchone()[0]
                    
                    # Set up batch parameters
                    batch_size = 5000
                    total_processed = 0
                    error_count = 0
                    
                    # Always drop and recreate the FTS table to avoid structure issues
                    try:
                        # Drop existing table if it exists
                        cursor.execute("DROP TABLE IF EXISTS image_fts")
                        conn.commit()
                        logger.info("Dropped existing FTS table")
                    except Exception as drop_error:
                        logger.warning(f"Error dropping FTS table: {drop_error}")
                        # Continue anyway - we'll create a new one
                    
                    # Create fresh FTS table
                    try:
                        cursor.execute("""
                            CREATE VIRTUAL TABLE image_fts USING fts5(
                                image_id UNINDEXED,
                                filename,
                                user_description,
                                ai_description,
                                full_path UNINDEXED,
                                content='images',
                                content_rowid='image_id'
                            )
                        """)
                        conn.commit()
                        logger.info("Created new FTS table with proper schema")
                    except Exception as create_error:
                        # Try without content/content_rowid if that failed
                        logger.warning(f"Error creating external content FTS table: {create_error}")
                        try:
                            cursor.execute("""
                                CREATE VIRTUAL TABLE image_fts USING fts5(
                                    image_id,
                                    filename,
                                    user_description,
                                    ai_description,
                                    full_path
                                )
                            """)
                            conn.commit()
                            logger.info("Created new standalone FTS table")
                        except Exception as alt_create_error:
                            raise Exception(f"Failed to create FTS table: {alt_create_error}")
                    
                    # Process in batches
                    while total_processed < image_count:
                        try:
                            # Get batch of images
                            cursor.execute("""
                                SELECT image_id, ai_description, user_description, filename
                                FROM images
                                ORDER BY image_id
                                LIMIT ? OFFSET ?
                            """, (batch_size, total_processed))
                            
                            # Fetch all rows
                            batch = cursor.fetchall()
                            if not batch:
                                break
                            
                            # Insert batch into FTS
                            cursor.executemany("""
                                INSERT INTO image_fts(image_id, ai_description, user_description, filename)
                                VALUES (?, ?, ?, ?)
                            """, batch)
                            
                            # Commit each batch
                            conn.commit()
                            
                            # Update progress
                            total_processed += len(batch)
                            self.update_progress.emit(
                                completed_tasks, total_tasks,
                                f"Rebuilding FTS index: {total_processed}/{image_count} images processed"
                            )
                                
                        except Exception as batch_error:
                            logger.error(f"Error processing FTS batch at offset {total_processed}: {batch_error}")
                            error_count += 1
                            total_processed += batch_size  # Skip problematic batch
                            
                            if error_count >= 3:
                                raise Exception(f"Too many errors ({error_count}) during FTS rebuild")
                        
                        status_msg = f"Successfully rebuilt FTS index with {total_processed} images"
                        if error_count > 0:
                            status_msg += f" ({error_count} errors encountered)"
                            
                        results["fts_rebuild"] = {"success": True, "message": status_msg}
                        
                        self.update_task_status.emit(
                            "fts_rebuild",
                            True,
                            status_msg
                        )
                    else:
                        # Handle case where table doesn't exist
                        success, message = upgrade_database_schema(self.db_manager.db_path)
                        status_msg = "Created and populated FTS table"
                        
                        results["fts_rebuild"] = {"success": True, "message": status_msg}
                        self.update_task_status.emit(
                            "fts_rebuild",
                            True,
                            status_msg
                        )
                    
                    conn.close()
                    
                except Exception as e:
                    logger.error(f"Error rebuilding FTS: {e}")
                    results["fts_rebuild"] = {"success": False, "message": str(e)}
                    self.update_task_status.emit(
                        "fts_rebuild",
                        False,
                        f"Failed: {str(e)}"
                    )
                
                completed_tasks += 1
            
            # 4. Database Optimization
            if self.tasks["optimize_database"]["enabled"]:
                self.update_progress.emit(
                    completed_tasks, total_tasks,
                    "Optimizing database..."
                )
                self.tasks["optimize_database"]["in_progress"] = True
                
                try:
                    # Use vacuum to optimize the database
                    self.db_manager.disconnect()  # Close all connections first
                    optimize_result = self.db_manager.db_ops.vacuum_database()
                    self.db_manager.connect()     # Reconnect after vacuum
                    
                    status_msg = "Database optimized successfully"
                    if isinstance(optimize_result, dict) and "message" in optimize_result:
                        status_msg = optimize_result["message"]
                    
                    results["optimize_database"] = {"success": True, "message": status_msg}
                    
                    self.update_task_status.emit(
                        "optimize_database",
                        True,
                        status_msg
                    )
                except Exception as e:
                    logger.error(f"Error optimizing database: {e}")
                    results["optimize_database"] = {"success": False, "message": str(e)}
                    self.update_task_status.emit(
                        "optimize_database",
                        False,
                        f"Failed: {str(e)}"
                    )
                
                completed_tasks += 1
            
            # Complete
            self.update_progress.emit(total_tasks, total_tasks, "Maintenance completed")
            self.maintenance_completed.emit(results)
            
        except Exception as e:
            logger.error(f"Error during maintenance: {e}")
            self.maintenance_error.emit(str(e))
