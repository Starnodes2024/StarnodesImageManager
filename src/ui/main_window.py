#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main window UI for STARNODES Image Manager
Implements the main application window and UI components.
"""

import os
import sys
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from PIL import Image, ExifTags
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QLineEdit, QPushButton, QToolBar, QStatusBar,
    QFileDialog, QMenu, QMessageBox, QApplication, QDialog,
    QInputDialog, QListView, QTreeView, QAbstractItemView,
    QListWidget, QListWidgetItem, QDialogButtonBox, QProgressDialog
)
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtCore import Qt, QSize, QDir, pyqtSignal, QThreadPool, QTimer

# Local imports
from .thumbnail_browser_factory import create_thumbnail_browser
from .folder_panel import FolderPanel
from .catalog_panel import CatalogPanel
from .search_panel import SearchPanel
from .metadata_panel import MetadataPanel
from .progress_dialog import ProgressDialog
from .settings_dialog import SettingsDialog
from .database_optimization_dialog import DatabaseOptimizationDialog
from .worker import Worker, BackgroundTaskManager
from .notification_manager import NotificationManager, NotificationType
from .date_search_worker import DateSearchWorker

from src.image_processing.thumbnail_generator import ThumbnailGenerator
from src.image_processing.image_scanner import ImageScanner
from src.ai.image_processor import AIImageProcessor
from src.scanner.background_scanner import BackgroundScanner
from src.config.config_manager import ConfigManager
from src.database.db_optimization_utils import check_and_optimize_if_needed
from src.config.theme_manager import ThemeManager
from src.config.language_manager import LanguageManager
from src.processing.batch_operations import get_batch_operations, BatchOperations
from src.processing.task_manager import get_task_manager
from src.processing.parallel_pipeline import get_pipeline
from src.memory.memory_utils import initialize_memory_management, get_memory_stats, cleanup_memory_pools, force_garbage_collection, get_system_memory_info
from src.database.performance_optimizer import DatabasePerformanceOptimizer
from src.database.enhanced_search import EnhancedSearch
from src.ui.main_window_search_integration import integrate_enhanced_search
from src.ui.main_window_language import apply_language_to_main_window, on_language_changed
from src.database.db_upgrade import upgrade_database_schema

logger = logging.getLogger("STARNODESImageManager.ui")

class MainWindow(QMainWindow):
    """Main application window."""
    
    def on_language_changed(self, language_code=None):
        """Slot to handle language changes and update the UI language immediately."""
        if language_code is None:
            language_code = self.config_manager.get("ui", "language", "en")
        # Update UI with new language
        on_language_changed(self, language_code)

    def on_theme_changed(self, theme_id=None):
        """Slot to handle theme changes and update the UI theme immediately."""
        if theme_id is None:
            theme_id = self.config_manager.get("ui", "theme", None)
        # Set theme using theme manager
        self.theme_manager.apply_theme(theme_id)
        # Apply theme to all UI components
        self.apply_theme_to_ui(theme_id)
        # Update the hover preview widget if present
        try:
            from src.ui.thumbnail_widget import ThumbnailWidget
            if hasattr(ThumbnailWidget, '_hover_preview') and ThumbnailWidget._hover_preview:
                ThumbnailWidget._hover_preview.update_theme()
        except Exception as e:
            logger.error(f"Error updating hover preview widget theme: {e}")

    def apply_theme_to_ui(self, theme_id=None):
        """Apply the selected theme to UI components."""
        if theme_id:
            self.theme_manager.apply_theme(theme_id)
        # Update all widgets that use the theme
        # You may need to add further widget updates here as needed
        # (Stylesheet is already set by ThemeManager.apply_theme())

    def __init__(self, db_manager, language_manager=None):
        """Initialize the main window.
        
        Args:
            db_manager: Database manager instance
            language_manager: Optional LanguageManager instance to use
        """
        super().__init__()
        
        self.db_manager = db_manager
        self.thumbnail_browser = None
        self.folder_panel = None
        self.search_panel = None
        
        # Set up thread pool and task manager
        self.threadpool = QThreadPool()
        self.task_manager = BackgroundTaskManager(self.threadpool)
        
        # Load configuration
        self.config_manager = ConfigManager()
        
        # Initialize theme manager
        self.theme_manager = ThemeManager(config_manager=self.config_manager)
        
        # Initialize language manager (use provided or create new)
        if language_manager is not None:
            self.language_manager = language_manager
        else:
            from src.config.language_manager import LanguageManager
            # Try to get language from config, default to 'en'
            language_code = self.config_manager.get('ui', 'language', 'en')
            self.language_manager = LanguageManager(language_code)
        logger.debug(f"Language set to: {self.language_manager.current_language}")
        
        # Initialize notification manager
        self.notification_manager = NotificationManager(parent_widget=self)
        
        # Initialize components
        self.init_components()
        self.setup_ui()
        
        # Initialize and apply theme
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.theme_manager.initialize(app_dir=app_dir)
        
        # Connect background scanner signals if available
        if hasattr(self, 'background_scanner'):
            if hasattr(self.background_scanner, 'scan_completed'):
                self.background_scanner.scan_completed.connect(self._update_counts_after_background_scan)
        
        # Check if database optimization is needed
        QApplication.processEvents()  # Process events to ensure UI is displayed
        self.check_database_optimization()
        
        # Upgrade database schema if needed to support enhanced search
        self.upgrade_database_for_enhanced_search()
        
        # Make sure window is displayed properly
        self.ensure_window_visible()
        
        # Initialize enhanced search after UI is visible
        QApplication.processEvents()
        self.initialize_enhanced_search()
        
        # Apply language translations
        apply_language_to_main_window(self, self.language_manager)
        
        # Initialize database extensions and add "All Images" view functionality
        from src.database.db_operations_extension import extend_db_operations
        from src.ui.view_all_images import add_view_all_images_to_main_window
        extend_db_operations(self.db_manager)
        add_view_all_images_to_main_window(self)
    
    def init_components(self):
        """Initialize application components."""
        # Create directories if they don't exist
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Create required directories
        required_dirs = [
            "data",
            "data/thumbnails",  # Thumbnails location in data subdirectory
            "data/logs",        # Logs location in data subdirectory
            "temp"               # Temporary files directory for processing
        ]
        
        # Note: The old separate 'logs' directory is no longer used. All logs are now in data/logs.
        
        for dir_name in required_dirs:
            dir_path = os.path.join(app_dir, dir_name)
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Ensured directory exists: {dir_path}")
        
        # Get thumbnails directory from config manager
        # This ensures we use the same path that was set in main.py (/data/thumbnails)
        thumbnails_dir = self.config_manager.get("thumbnails", "path")
        
        # Double-check that the directory exists
        if not os.path.exists(thumbnails_dir):
            logger.warning(f"Thumbnails directory from config does not exist: {thumbnails_dir}")
            os.makedirs(thumbnails_dir, exist_ok=True)
            logger.info(f"Created thumbnails directory: {thumbnails_dir}")
        
        logger.info(f"Using thumbnails directory from config: {thumbnails_dir}")
        
        # Initialize thumbnail generator
        thumb_size = self.config_manager.get("thumbnails", "size", 200)
        self.thumbnail_generator = ThumbnailGenerator(
            thumbnail_dir=thumbnails_dir,
            size=(thumb_size, thumb_size)
        )
        
        # Initialize memory management and parallel processing
        try:
            # Initialize memory management
            initialize_memory_management(self.config_manager)
            
            # Initialize parallel processing pipeline
            self.parallel_pipeline = get_pipeline("main", self.config_manager)
            
            # Initialize batch operations manager
            self.batch_operations = get_batch_operations(self.config_manager, self.db_manager)
            
            # Connect batch operation signals
            self._connect_batch_operation_signals()
            
            logger.info("Parallel processing pipeline initialized")
        except Exception as e:
            logger.error(f"Error initializing parallel processing: {e}")
            # Continue with standard processing if parallel processing fails
        
        try:
            # Initialize AI processor
            # Note: We're now using a simplified version without model loading
            self.ai_processor = AIImageProcessor(
                db_manager=self.db_manager,
                batch_size=self.config_manager.get("ai", "batch_size", 1)
            )
        except Exception as e:
            logger.error(f"Error initializing AI processor: {e}")
            # Create a fallback AI processor that only uses basic image analysis
            self.ai_processor = AIImageProcessor(db_manager=self.db_manager)
        
        try:
            # Initialize image scanner
            self.image_scanner = ImageScanner(
                db_manager=self.db_manager,
                thumbnail_generator=self.thumbnail_generator,
                ai_processor=self.ai_processor
            )
            
            # Initialize background scanner
            self.background_scanner = BackgroundScanner(
                self.image_scanner,
                self.db_manager,
                self.config_manager
            )
            
            # Connect background scanner signals
            self.background_scanner.signals.scan_started.connect(self._on_background_scan_started)
            self.background_scanner.signals.scan_completed.connect(self._on_background_scan_completed)
            self.background_scanner.signals.scan_error.connect(self._on_background_scan_error)
            
            # Start the background scanner if enabled in settings
            if self.config_manager.get("scanning", "enable_background_scanning", False):
                self.background_scanner.start()
        except Exception as e:
            logger.error(f"Error initializing image scanner: {e}")
            # Create placeholders to prevent attribute errors
            self.image_scanner = None
            self.background_scanner = None
    
    def upgrade_database_for_enhanced_search(self):
        """Upgrade the database schema to support enhanced search functionality."""
        try:
            # Show status in status bar
            if hasattr(self, 'status_bar'):
                self.status_bar.showMessage("Upgrading database schema for enhanced search...")
            
            # Upgrade the database schema
            success, message = upgrade_database_schema(self.db_manager.db_path)
            
            if success:
                logger.info(f"Database schema upgrade: {message}")
                if hasattr(self, 'status_bar'):
                    self.status_bar.showMessage(f"Database schema upgrade: {message}", 5000)
            else:
                logger.error(f"Database schema upgrade failed: {message}")
                if hasattr(self, 'status_bar'):
                    self.status_bar.showMessage(f"Database schema upgrade failed: {message}", 5000)
        except Exception as e:
            logger.error(f"Error upgrading database schema: {e}")
            # Non-critical, so continue
            
    def initialize_enhanced_search(self):
        """Initialize the enhanced search functionality."""
        try:
            # Integrate enhanced search into the UI
            integrate_enhanced_search(self)
            logger.info("Enhanced search system initialized")
        except Exception as e:
            logger.error(f"Error initializing enhanced search: {e}")
            # Non-critical, so continue
            
    def check_database_optimization(self):
        """Check if database optimization is needed."""
        try:
            check_and_optimize_if_needed(self.db_manager.db_path)
        except Exception as e:
            logger.error(f"Error checking database optimization: {e}")
            # Non-critical, so continue
            
    def create_progress_dialog(self, title_key, description_key, parent=None, cancellable=True):
        """Create a progress dialog with language support.
        
        Args:
            title_key (str): Translation key for dialog title or default text
            description_key (str): Translation key for description or default text
            parent (QWidget, optional): Parent widget
            cancellable (bool): Whether the operation can be cancelled
            
        Returns:
            ProgressDialog: Configured progress dialog with language support
        """
        try:
            # Translate title and description
            translated_title = self.language_manager.translate('progress', title_key, title_key)
            translated_description = self.language_manager.translate('progress', description_key, description_key)
            
            # Create dialog with language manager
            dialog = ProgressDialog(
                translated_title,
                translated_description,
                parent=parent or self,
                cancellable=cancellable,
                language_manager=self.language_manager
            )
            
            return dialog
        except Exception as e:
            logger.error(f"Error creating progress dialog: {e}")
            # Fallback to basic dialog without translations
            return ProgressDialog(title_key, description_key, parent=parent or self, cancellable=cancellable)
    
    def ensure_window_visible(self):
        """Ensure the main window is properly visible on the screen."""
        try:
            # Get screen geometry
            screen = QApplication.primaryScreen().geometry()
            # Make sure window is not too large for the screen
            if self.width() > screen.width():
                self.resize(screen.width() * 0.9, self.height())
            if self.height() > screen.height():
                self.resize(self.width(), screen.height() * 0.9)
            # Center the window on the screen
            self.setGeometry(
                QStyle.alignedRect(
                    Qt.LayoutDirection.LeftToRight,
                    Qt.AlignmentFlag.AlignCenter,
                    self.size(),
                    screen
                )
            )
            # Ensure window is visible
            self.raise_()
            self.activateWindow()
        except Exception as e:
            logger.error(f"Error ensuring window visibility: {e}")
            QMessageBox.warning(
                self,
                "Component Initialization Error",
                f"An error occurred while initializing the image scanner: {str(e)}\n\n" +
                "Some functionality may be limited."
            )
        
        logger.info("Application components initialized")
        
    def convert_thumbnail_paths(self):
        """Convert absolute thumbnail paths to relative paths in the database.
        
        This improves portability and makes backup/restore operations easier.
        """
        try:
            logger.info("Starting thumbnail path conversion process")
            # Import the conversion utility
            from src.utilities.convert_thumbnail_paths import convert_to_relative_paths
            
            # Define a signal handler for conversion completion if needed
            if not hasattr(self, '_conversion_handler_connected'):
                self._conversion_handler_connected = True
                # Connect the worker's result signal in the run_conversion wrapper
            
            # Ensure we have the thumbnails directory path ready for the conversion
            thumbnails_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "thumbnails"
            )
            
            # Run the conversion in the background using our existing DB connection
            def run_conversion(progress_callback=None):
                # The progress_callback is automatically passed by the Worker class
                try:
                    logger.debug("Starting thumbnail path conversion in background thread")
                    db_path = self.db_manager.db_path
                    success, unchanged, errors = convert_to_relative_paths(
                        db_path=db_path, 
                        dry_run=False,
                        db_manager=self.db_manager  # Pass the existing DB manager
                    )
                    logger.debug(f"Conversion complete: {success} converted, {unchanged} unchanged, {errors} errors")
                    return (success, unchanged, errors)
                except Exception as thread_error:
                    logger.error(f"Error in thumbnail conversion thread: {thread_error}")
                    return (0, 0, 1)  # Return error counts
            
            # Define the completion handler
            def on_conversion_complete(result):
                if result:
                    success, unchanged, errors = result
                    self._on_conversion_complete(success, unchanged, errors)
            
            # Run the conversion in a separate thread
            from src.ui.worker import Worker
            worker = Worker(run_conversion)
            worker.signals.result.connect(on_conversion_complete)
            self.threadpool.start(worker)
            logger.info("Thumbnail path conversion task queued")
            
        except Exception as e:
            logger.error(f"Failed to queue thumbnail path conversion: {e}")

    def _on_conversion_complete(self, success, unchanged, errors):
        """Handle completion of thumbnail path conversion.
        
        Args:
            success (int): Number of paths successfully converted
            unchanged (int): Number of paths that did not need conversion
            errors (int): Number of errors encountered
        """
        if errors > 0:
            logger.warning(f"Thumbnail path conversion completed with {errors} errors")
        else:
            logger.info(f"Thumbnail path conversion completed: {success} converted, {unchanged} unchanged")
        
        # Show notification if paths were converted
        if success > 0:
            from src.ui.notification_manager import NotificationType
            message = f"Optimized {success} thumbnail paths for better portability"
            self.notification_manager.show_notification(
                message, 
                "Thumbnail Paths Optimized", 
                NotificationType.INFO
            )
            
    def on_update_image_dimensions(self):
        """Open the dialog to update image dimensions in the database."""
        try:
            from src.ui.database_dimensions_update_dialog import DatabaseDimensionsUpdateDialog
            from src.utils.image_dimensions_updater import ImageDimensionsUpdater
            from src.database.enhanced_search import EnhancedSearch
            
            # Create an enhanced search instance if needed
            enhanced_search = EnhancedSearch(self.db_manager)
            
            # Create and show the dialog
            dialog = DatabaseDimensionsUpdateDialog(
                parent=self,
                db_manager=self.db_manager,
                enhanced_search=enhanced_search,
                language_manager=self.language_manager
            )
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Error opening dimensions update dialog: {e}")
            self.notification_manager.show_notification(
                "Error",
                f"Could not open dimensions update dialog: {str(e)}",
                NotificationType.ERROR
            )
    
    def on_convert_thumbnail_paths(self):
        """Convert thumbnail paths from absolute to relative.
        
        This utility converts absolute thumbnail paths to relative paths in the database,
        making the application more portable for backup and restore operations.
        """
        from src.utils.thumbnail_path_converter import convert_thumbnail_paths
        convert_thumbnail_paths(self, self.db_manager)
        try:
            # Show confirmation dialog
            confirm = QMessageBox.question(
                self,
                "Convert Thumbnail Paths",
                "This utility will convert absolute thumbnail paths to relative paths in the database, \n"
                "making the application more portable for backup and restore operations.\n\n"
                "Do you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if confirm != QMessageBox.StandardButton.Yes:
                return
            
            # Create progress dialog
            progress_dialog = ProgressDialog(
                "Converting Thumbnail Paths",
                "Preparing to convert thumbnail paths...",
                parent=self,
                cancellable=True
            )
            progress_dialog.show()
            QApplication.processEvents()
            
            # Run the conversion in a background thread
            from src.utilities.convert_thumbnail_paths import convert_to_relative_paths
            
            # Define a function that accepts but ignores progress_callback
            def run_conversion(progress_callback=None):
                # Explicitly accept progress_callback parameter but don't use it
                try:
                    # Simply run the conversion directly
                    db_path = self.db_manager.db_path
                    thumbnails_dir = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "thumbnails"
                    )
                    
                    # Connect to the database directly
                    import sqlite3
                    conn = sqlite3.connect(db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    # Get all images with absolute thumbnail paths
                    cursor.execute("SELECT image_id, thumbnail_path FROM images WHERE thumbnail_path IS NOT NULL")
                    images = cursor.fetchall()
                    
                    success_count = 0
                    unchanged_count = 0
                    error_count = 0
                    
                    for image in images:
                        try:
                            image_id = image['image_id']
                            thumbnail_path = image['thumbnail_path']
                            
                            # Skip if already relative (no directory path)
                            if thumbnail_path and not os.path.dirname(thumbnail_path):
                                unchanged_count += 1
                                continue
                            
                            # Skip if not an absolute path
                            if not thumbnail_path or not os.path.isabs(thumbnail_path):
                                unchanged_count += 1
                                continue
                            
                            # Check if it's within the thumbnails directory
                            thumbnail_rel_path = os.path.relpath(thumbnail_path, thumbnails_dir)
                            if thumbnail_rel_path.startswith(".."): 
                                # Path is outside thumbnails directory, extract filename only
                                thumbnail_rel_path = os.path.basename(thumbnail_path)
                            
                            # Update the database
                            cursor.execute(
                                "UPDATE images SET thumbnail_path = ? WHERE image_id = ?", 
                                (thumbnail_rel_path, image_id)
                            )
                            success_count += 1
                        except Exception as e:
                            logger.error(f"Error processing image {image_id}: {e}")
                            error_count += 1
                    
                    # Commit changes
                    if success_count > 0:
                        conn.commit()
                    
                    # Close connection
                    conn.close()
                    
                    return (success_count, unchanged_count, error_count)
                    
                except Exception as thread_error:
                    logger.error(f"Error in thumbnail conversion thread: {thread_error}")
                    return (0, 0, 1)  # Return error counts
            
            # Define completion handler
            def on_conversion_complete(result):
                if result:
                    success, unchanged, errors = result
                    
                    # Update progress dialog
                    progress_dialog.update_operation("Conversion complete")
                    progress_dialog.update_progress(100, 100)
                    progress_dialog.log_message(f"Paths converted: {success}")
                    progress_dialog.log_message(f"Paths unchanged: {unchanged}")
                    progress_dialog.log_message(f"Errors: {errors}")
                    
                    # Show notification
                    self._on_conversion_complete(success, unchanged, errors)
                    
                    if hasattr(progress_dialog, 'cancel_button'):
                        progress_dialog.cancel_button.setText("Close")
                        try:
                            progress_dialog.cancel_button.clicked.disconnect()
                        except Exception:
                            pass  # Button might not be connected
                        progress_dialog.cancel_button.clicked.connect(progress_dialog.accept)
            
            # Define error handler
            def on_error(error_info):
                error_msg = error_info[0] if isinstance(error_info, tuple) and len(error_info) > 0 else str(error_info)
                progress_dialog.log_message(f"Error: {error_msg}")
                progress_dialog.update_operation("Conversion failed")
                
                # Log error
                logger.error(f"Error during thumbnail path conversion: {error_msg}")
                
                # Show error in status bar
                self.status_bar.showMessage(f"Error converting thumbnail paths: {error_msg}")
                
                # Enable the close button
                if hasattr(progress_dialog, 'cancel_button'):
                    progress_dialog.cancel_button.setText("Close")
                    try:
                        progress_dialog.cancel_button.clicked.disconnect()
                    except Exception:
                        pass  # Button might not be connected
                    progress_dialog.cancel_button.clicked.connect(progress_dialog.accept)
            
            # Create and run worker
            from src.ui.worker import Worker
            worker = Worker(run_conversion)
            worker.signals.result.connect(on_conversion_complete)
            worker.signals.error.connect(on_error)
            
            # Connect cancel button
            if hasattr(progress_dialog, 'cancel_button'):
                progress_dialog.cancel_button.clicked.connect(progress_dialog.reject)
            
            # Start the worker
            self.threadpool.start(worker)
            
        except Exception as e:
            logger.error(f"Error starting thumbnail path conversion: {e}")
            self.notification_manager.show_message_box(
                "Conversion Error",
                f"An error occurred while converting thumbnail paths: {str(e)}",
                NotificationType.ERROR
            )
    
    def setup_menus(self):
        """Set up application menus."""
        # --- FILE MENU ---
        self.file_menu = self.menuBar().addMenu(self.language_manager.translate('main', 'file_menu', 'File'))
        
        # Folder management submenu
        folder_submenu = self.file_menu.addMenu(self.language_manager.translate('file_menu', 'folder_management', 'Folder Management'))
        
        # Add folder action
        self.add_folder_action = folder_submenu.addAction(self.language_manager.translate('file_menu', 'add_folder', 'Add Folder'))
        self.add_folder_action.triggered.connect(self.on_add_folder)
        
        # Remove folder action
        self.remove_folder_action = folder_submenu.addAction(self.language_manager.translate('file_menu', 'remove_folder', 'Remove Folder'))
        self.remove_folder_action.triggered.connect(self.on_remove_folder)
        
        # Scan folder action
        self.scan_folder_action = folder_submenu.addAction(self.language_manager.translate('file_menu', 'scan_folder', 'Scan Folder'))
        self.scan_folder_action.triggered.connect(self.on_scan_folder)
        
        # Add separator
        folder_submenu.addSeparator()
        
        # Empty database action
        self.empty_db_action = folder_submenu.addAction(self.language_manager.translate('file_menu', 'empty_database', 'Empty Database'))
        self.empty_db_action.triggered.connect(self.on_empty_database)
        
        # File operations submenu
        file_ops_submenu = self.file_menu.addMenu(self.language_manager.translate('file_menu', 'file_operations', 'File Operations'))
        
        # Export action
        self.export_action = file_ops_submenu.addAction(self.language_manager.translate('file_menu', 'export_images', 'Export Selected Images...'))
        self.export_action.triggered.connect(self.export_selected_images)
        
        # Copy to folder action
        self.copy_action = file_ops_submenu.addAction(self.language_manager.translate('file_menu', 'copy_to_folder', 'Copy Selected to Folder'))
        self.copy_action.triggered.connect(self.on_batch_copy_images)
        
        # Exit action
        self.file_menu.addSeparator()
        self.exit_action = self.file_menu.addAction(self.language_manager.translate('file_menu', 'exit', 'Exit'))
        self.exit_action.triggered.connect(self.close)
        
        # --- EDIT MENU ---
        self.edit_menu = self.menuBar().addMenu(self.language_manager.translate('main', 'edit_menu', 'Edit'))
        
        # Delete submenu
        delete_submenu = self.edit_menu.addMenu(self.language_manager.translate('edit_menu', 'delete', 'Delete'))
        
        # Delete from database only
        self.delete_db_action = delete_submenu.addAction(self.language_manager.translate('edit_menu', 'delete_db_only', 'Delete from Database Only'))
        self.delete_db_action.triggered.connect(self.on_batch_delete_images_db_only)
        
        # Delete from database and disk
        self.delete_full_action = delete_submenu.addAction(self.language_manager.translate('edit_menu', 'delete_with_files', 'Delete from Database and Disk'))
        self.delete_full_action.triggered.connect(self.on_batch_delete_images_with_files)
        
        # Delete descriptions
        self.delete_desc_action = delete_submenu.addAction(self.language_manager.translate('edit_menu', 'delete_descriptions', 'Delete Descriptions for Selected'))
        self.delete_desc_action.triggered.connect(self.on_batch_delete_descriptions)
        
        # --- AI TOOLS MENU ---
        self.ai_menu = self.menuBar().addMenu(self.language_manager.translate('main', 'ai_tools_menu', 'AI Tools'))
        
        # Generate descriptions with options dialog
        self.ai_menu.addAction(self.language_manager.translate('ai_menu', 'generate_with_options', 'Generate Descriptions with Options...')).triggered.connect(self.on_generate_descriptions)
        
        # Generate descriptions for selected images only
        self.ai_menu.addAction(self.language_manager.translate('ai_menu', 'generate_selected', 'Generate for Selected Images Only')).triggered.connect(self.generate_descriptions_for_selected)
        
        # Generate descriptions for all images in folder
        self.ai_menu.addAction(self.language_manager.translate('ai_menu', 'generate_folder', 'Generate for All Images in Folder')).triggered.connect(self.generate_descriptions_for_folder)
        
        # --- BATCH OPERATIONS MENU ---
        self.batch_menu = self.menuBar().addMenu(self.language_manager.translate('main', 'batch_menu', 'Batch Operations'))
        
        # Image processing submenu
        img_proc_submenu = self.batch_menu.addMenu(self.language_manager.translate('batch_menu', 'image_processing', 'Image Processing'))
        
        # Generate descriptions action
        self.generate_batch_action = img_proc_submenu.addAction(self.language_manager.translate('batch_menu', 'generate_descriptions', 'Generate AI Descriptions'))
        self.generate_batch_action.triggered.connect(self.on_batch_generate_descriptions)
        
        # Export action with enhanced options
        self.export_batch_action = img_proc_submenu.addAction(self.language_manager.translate('batch_menu', 'export_images', 'Export Images...'))
        self.export_batch_action.triggered.connect(self.export_selected_images)
        
        # Rename action
        self.rename_batch_action = img_proc_submenu.addAction(self.language_manager.translate('batch_menu', 'rename_images', 'Rename Images'))
        self.rename_batch_action.triggered.connect(self.on_batch_rename_images)
        
        # File management submenu
        file_mgmt_submenu = self.batch_menu.addMenu(self.language_manager.translate('batch_menu', 'file_management', 'File Management'))
        
        # Copy to folder action
        self.copy_batch_action = file_mgmt_submenu.addAction(self.language_manager.translate('batch_menu', 'copy_to_folder', 'Copy to Folder'))
        self.copy_batch_action.triggered.connect(self.on_batch_copy_images)
        
        # Delete descriptions action
        self.delete_desc_batch_action = file_mgmt_submenu.addAction(self.language_manager.translate('batch_menu', 'delete_descriptions', 'Delete Descriptions'))
        self.delete_desc_batch_action.triggered.connect(self.on_batch_delete_descriptions)
        
        # Delete from database only action
        self.delete_db_batch_action = file_mgmt_submenu.addAction(self.language_manager.translate('batch_menu', 'delete_db_only', 'Delete from Database Only'))
        self.delete_db_batch_action.triggered.connect(self.on_batch_delete_images_db_only)
        
        # Delete from database and disk action
        self.delete_full_batch_action = file_mgmt_submenu.addAction(self.language_manager.translate('batch_menu', 'delete_with_files', 'Delete from Database and Disk'))
        self.delete_full_batch_action.triggered.connect(self.on_batch_delete_images_with_files)
        
        # --- TOOLS MENU ---
        self.tools_menu = self.menuBar().addMenu(self.language_manager.translate('main', 'tools_menu', 'Tools'))
        
        # Database submenu
        db_submenu = self.tools_menu.addMenu(self.language_manager.translate('tools_menu', 'database', 'Database'))
        
        # Comprehensive database maintenance tool
        # maintenance_action = db_submenu.addAction("Database Maintenance")
        # maintenance_action.triggered.connect(self.on_database_maintenance)
        
        # Dedicated database rebuild for corruption issues
        self.rebuild_action = db_submenu.addAction(self.language_manager.translate('tools_menu', 'rebuild_database', 'Rebuild Corrupted Database'))
        self.rebuild_action.triggered.connect(self.on_rebuild_database)
        
        # Add separator before export/import actions
        db_submenu.addSeparator()
        
        # Export database action
        self.export_db_action = db_submenu.addAction(self.language_manager.translate('tools_menu', 'export_database', 'Export Database'))
        self.export_db_action.triggered.connect(self.on_export_database)
        
        # Import database action
        self.import_db_action = db_submenu.addAction(self.language_manager.translate('tools_menu', 'import_database', 'Import Database'))
        self.import_db_action.triggered.connect(self.on_import_database)
        
        # Add separator before utility actions
        db_submenu.addSeparator()
        
        # Update image dimensions action
        self.update_dimensions_action = db_submenu.addAction(self.language_manager.translate('tools_menu', 'update_dimensions', 'Update Image Dimensions'))
        self.update_dimensions_action.triggered.connect(self.on_update_image_dimensions)
        
        # Thumbnail path conversion action
        self.convert_thumbnails_action = db_submenu.addAction(self.language_manager.translate('tools_menu', 'convert_thumbnails', 'Convert Thumbnail Paths to Relative'))
        self.convert_thumbnails_action.triggered.connect(self.on_convert_thumbnail_paths)
        
        # Settings action
        self.tools_menu.addSeparator()
        self.settings_action = self.tools_menu.addAction(self.language_manager.translate('tools_menu', 'settings', 'Settings'))
        self.settings_action.triggered.connect(self.on_settings)
    
    def setup_ui(self):
        """Set up the main window UI."""
        # Window properties
        self.setWindowTitle(self.language_manager.translate('main', 'title', 'STARNODES Image Manager V1.1.0'))
        self.setMinimumSize(1024, 768)
        
        # Create menu bar if it doesn't exist
        self.setup_menus()
        
        # Create central widget
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for main content
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)
        
        # Left panel (folders, catalogs, and search)
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # Split panel for folders and catalogs
        folder_catalog_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Folder browser (top half) - pass language manager explicitly
        self.folder_panel = FolderPanel(self.db_manager, self)
        # Set language manager explicitly to ensure translations work
        self.folder_panel.language_manager = self.language_manager
        folder_catalog_splitter.addWidget(self.folder_panel)
        
        # Catalog browser (bottom half) - pass language manager explicitly
        self.catalog_panel = CatalogPanel(self.db_manager, self)
        # Set language manager explicitly to ensure translations work
        self.catalog_panel.language_manager = self.language_manager
        folder_catalog_splitter.addWidget(self.catalog_panel)
        
        # Set equal sizes for folder and catalog panels
        folder_catalog_splitter.setSizes([250, 250])
        
        # Add splitter to left panel
        left_layout.addWidget(folder_catalog_splitter, 2)  # Give more weight to the folder/catalog section
        
        # Search panel
        self.search_panel = SearchPanel()
        left_layout.addWidget(self.search_panel, 1)
        
        # Add left panel to splitter
        self.main_splitter.addWidget(self.left_panel)
        
        # Create right side container with thumbnail browser and metadata panel
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for thumbnail browser and metadata panel
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(self.right_splitter)
        
        # Thumbnail browser - use factory to create appropriate implementation
        # Thumbnail browser - use factory to create appropriate implementation
        # Pass the language manager to ensure translations work properly
        self.thumbnail_browser = create_thumbnail_browser(
            self.db_manager, 
            self.config_manager,
            parent=self,
            language_manager=self.language_manager
        )
        self.right_splitter.addWidget(self.thumbnail_browser)
        
        # Enable pagination for the thumbnail browser to handle large image collections
        from src.ui.pagination_integration import integrate_pagination
        integrate_pagination(self)

        # Metadata panel
        self.metadata_panel = MetadataPanel(self.db_manager, self.language_manager)
        self.right_splitter.addWidget(self.metadata_panel)
        
        # Set right splitter sizes (thumbnail browser gets more space)
        self.right_splitter.setSizes([700, 300])
        
        # Add right panel to main splitter
        self.main_splitter.addWidget(self.right_panel)
        
        # Set splitter sizes
        self.main_splitter.setSizes([250, 750])
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Set status bar in notification manager
        self.notification_manager.set_status_bar(self.status_bar)
        
        # Connect signals
        self.folder_panel.folder_selected.connect(self.on_folder_selected)
        self.folder_panel.folder_removed.connect(self.on_folder_removed)
        self.folder_panel.add_folder_requested.connect(self.on_add_folder)
        
        self.catalog_panel.catalog_selected.connect(self.on_catalog_selected)
        self.catalog_panel.catalog_removed.connect(self.on_catalog_removed)
        self.catalog_panel.catalog_added.connect(self.on_catalog_added)
        
        self.search_panel.search_requested.connect(self.on_search_requested)
        self.search_panel.date_search_requested.connect(self.on_date_search_requested)
        
        self.thumbnail_browser.thumbnail_selected.connect(self.on_thumbnail_selected)
        self.thumbnail_browser.thumbnail_double_clicked.connect(self.on_thumbnail_double_clicked)
        self.thumbnail_browser.batch_generate_requested.connect(self.on_batch_generate_descriptions)
        self.thumbnail_browser.status_message.connect(self.status_bar.showMessage)
        
        logger.info("Main window UI setup complete")
    
    def create_toolbar(self):
        """Create the main toolbar - empty as we're using only the top menu bar."""
        # Toolbar has been removed to avoid redundancy with the top menu bar
        pass
    
    def on_add_folder(self):
        """Handle the Add Folder action."""
        # Let the user select folders using the standard dialog but without multiple selection
        # We'll handle multiple selection more explicitly
        selected_folders = []
        
        # Create our custom dialog for folder selection
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Folders to Monitor")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
        # Create main layout
        main_layout = QVBoxLayout(dialog)
        
        # Selected folders list
        selected_label = QLabel("Selected Folders:")
        main_layout.addWidget(selected_label)
        
        selected_list = QListWidget()
        main_layout.addWidget(selected_list)
        
        # Buttons for adding/removing
        buttons_layout = QHBoxLayout()
        
        add_btn = QPushButton("Add Folders...")
        remove_btn = QPushButton("Remove")
        buttons_layout.addWidget(add_btn)
        buttons_layout.addWidget(remove_btn)
        main_layout.addLayout(buttons_layout)
        
        # Dialog buttons
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        dialog_buttons.accepted.connect(dialog.accept)
        dialog_buttons.rejected.connect(dialog.reject)
        main_layout.addWidget(dialog_buttons)
        
        # Function to add multiple folders at once
        def add_folders():
            # Create a file dialog that supports multiple selection
            file_dialog = QFileDialog(dialog)
            file_dialog.setFileMode(QFileDialog.FileMode.Directory)
            file_dialog.setOption(QFileDialog.Option.ShowDirsOnly)
            file_dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)  # Required for multi-selection
            file_dialog.setWindowTitle("Select Multiple Folders")
            file_dialog.setDirectory(QDir.homePath())
            
            # Hack to allow multiple directory selection
            list_view = file_dialog.findChild(QListView, "listView")
            if list_view:
                list_view.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
            tree_view = file_dialog.findChild(QTreeView)
            if tree_view:
                tree_view.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
            
            # Get selected folders
            if not file_dialog.exec():
                return
                
            # Get selected folders
            selected_files = file_dialog.selectedFiles()
            
            # Process each selected folder
            for folder in selected_files:
                # Normalize path
                folder = os.path.normpath(folder)
                
                # Check if this folder is already in the list
                for existing_index in range(selected_list.count()):
                    existing_folder = selected_list.item(existing_index).text()
                    existing_folder = os.path.normpath(existing_folder)
                    
                    # If the folder is already in the list, don't add it
                    if folder == existing_folder:
                        QMessageBox.warning(dialog, "Folder Already Selected", 
                            f"'{folder}' is already in the list of selected folders.",
                            QMessageBox.StandardButton.Ok)
                        return
                
                # Now check if this folder is a parent of any existing folder
                # If so, we'll ignore it (prioritizing subfolders over parent folders)
                folders_to_remove = []
                is_parent_of_existing = False
                
                for existing_index in range(selected_list.count()):
                    existing_folder = selected_list.item(existing_index).text()
                    existing_folder = os.path.normpath(existing_folder)
                    
                    # If the new folder is a parent of an existing folder, don't add it (silently skip)
                    if folder != existing_folder and existing_folder.startswith(folder + os.sep):
                        is_parent_of_existing = True
                        break
                    
                    # If the new folder is a child of an existing folder, mark the parent for removal
                    # We'll prioritize this subfolder over its parent (silently)
                    if folder != existing_folder and folder.startswith(existing_folder + os.sep):
                        folders_to_remove.append(existing_folder)
                
                # If this folder is a parent of something we already have, silently skip it
                if is_parent_of_existing:
                    return
                
                # Silently remove any parent folders that contain this folder
                for folder_to_remove in folders_to_remove:
                    # Find and remove the parent folder from the list without notification
                    for i in range(selected_list.count()):
                        if selected_list.item(i).text() == folder_to_remove:
                            removed_item = selected_list.takeItem(i)
                            del removed_item  # Free memory
                            break
                
                # Add the folder to the list
                item = QListWidgetItem(folder)
                selected_list.addItem(item)
        
        # Function to remove a folder
        def remove_folder():
            selected_items = selected_list.selectedItems()
            for item in selected_items:
                selected_list.takeItem(selected_list.row(item))
        
        # Connect buttons
        add_btn.clicked.connect(add_folders)
        remove_btn.clicked.connect(remove_folder)
        
        # Execute the dialog
        if dialog.exec():
            # Get the selected folders
            for i in range(selected_list.count()):
                folder = selected_list.item(i).text()
                selected_folders.append(folder)
        
        if not selected_folders:
            return
            
        # Track results for summary message
        added_folders = []
        skipped_folders = []
        failed_folders = []
        
        # Add each folder to the database
        for folder_path in selected_folders:
            folder_id = self.db_manager.add_folder(folder_path)
            
            if folder_id:
                # Check if this was a new folder or an existing one
                # Use the proper method to count images in the folder
                images_in_folder = self.db_manager.get_images_for_folder(folder_id, limit=1)
                image_count = len(images_in_folder)
                
                if image_count > 0:
                    # This was an existing folder that was skipped
                    skipped_folders.append(folder_path)
                else:
                    # This was a new folder that was added
                    added_folders.append((folder_id, folder_path))
            else:
                failed_folders.append(folder_path)
        
        # Update folder panel
        self.folder_panel.refresh_folders()
        
        # Create summary message
        summary = []
        if added_folders:
            summary.append(f"Added {len(added_folders)} new folder(s).")
        if skipped_folders:
            summary.append(f"Skipped {len(skipped_folders)} existing folder(s).")
        if failed_folders:
            summary.append(f"Failed to add {len(failed_folders)} folder(s).")
        
        summary_message = "\n".join(summary)
        
        # Ask if user wants to scan new folders now
        if added_folders:
            response = QMessageBox.question(
                self, "Scan Folders", 
                f"{summary_message}\n\nDo you want to scan the newly added folders for images now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if response == QMessageBox.StandardButton.Yes:
                # Scan all the new folders using a single batch process
                self.scan_multiple_folders(added_folders)
        else:
            # Just show the summary message
            QMessageBox.information(self, "Add Folders", summary_message)
    
    def on_remove_folder(self):
        """Handle the Remove Folder action."""
        # Get the currently selected folder from the folder panel
        selected_folder = self.folder_panel.folder_tree.currentItem()
        
        if selected_folder:
            folder_id = selected_folder.data(0, Qt.ItemDataRole.UserRole)
            
            if folder_id:
                # Ask for confirmation
                confirm = QMessageBox.question(
                    self, "Confirm Removal", 
                    "Are you sure you want to remove this folder from monitoring? All image records for this folder will be deleted from the database.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if confirm == QMessageBox.StandardButton.Yes:
                    # Remove the folder
                    self.folder_panel.remove_folder(folder_id)
                    
                    # Clear the thumbnail browser if it was showing this folder
                    if self.thumbnail_browser.current_folder_id == folder_id:
                        self.thumbnail_browser.clear_thumbnails()
                        self.status_bar.showMessage("Folder removed")
    
    def on_scan_folder(self):
        """Handle the Scan Folder action."""
        # Get the currently selected folder from the folder panel
        selected_folder = self.folder_panel.folder_tree.currentItem()
        
        if selected_folder:
            folder_id = selected_folder.data(0, Qt.ItemDataRole.UserRole)
            
            if folder_id:
                # Get folder info
                folders = self.db_manager.get_folders()
                folder_info = next((f for f in folders if f["folder_id"] == folder_id), None)
                
                if folder_info:
                    # Scan the folder
                    self.scan_folder(folder_id, folder_info["path"])
                    
                    # Refresh the thumbnail browser if it's showing this folder
                    if self.thumbnail_browser.current_folder_id == folder_id:
                        self.thumbnail_browser.refresh()
    
    def scan_multiple_folders(self, folders):
        """Scan multiple folders for images with a single progress dialog.
        
        Args:
            folders (list): List of (folder_id, folder_path) tuples to scan
        """
        if not folders:
            return
            
        # Create a single progress dialog for all folders
        folder_count = len(folders)
        self.progress_dialog = self.create_progress_dialog(
            'scanning_folders_title',
            'scanning_folders_description',
            parent=self,
            cancellable=True
        )
        
        # Process one folder at a time, but track overall progress
        total_processed = 0
        total_failed = 0
        total_images = 0
        processed_folders = 0
        
        # Define a worker function that processes all folders
        def process_folders_worker(progress_callback=None):
            nonlocal total_processed, total_failed, total_images, processed_folders
            
            results = {}
            
            try:
                # Process each folder
                for index, (folder_id, folder_path) in enumerate(folders):
                    # Use the progress callback to report overall progress
                    if progress_callback:
                        # Report overall progress - emit current folder index and total folder count
                        progress_callback.emit(index + 1, len(folders))
                        
                        # Update progress dialog manually with text information
                        if self.progress_dialog and self.progress_dialog.isVisible():
                            self.progress_dialog.log_message(f"Starting folder {index+1} of {len(folders)}: {folder_path}")
                    # Update progress dialog with current folder
                    if self.progress_dialog and self.progress_dialog.isVisible():
                        self.progress_dialog.update_operation(f"Processing folder {processed_folders + 1} of {folder_count}: {folder_path}")
                        self.progress_dialog.log_message(f"\nStarting scan of folder: {folder_path}")
                    
                    # Check if the folder exists
                    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                        if self.progress_dialog and self.progress_dialog.isVisible():
                            self.progress_dialog.log_message(f"Folder not found or not accessible: {folder_path}")
                        processed_folders += 1
                        continue
                    
                    # Get scanner options from settings
                    config = self.config_manager
                    process_new_only = config.get("scanner", "process_new_only", True)
                    use_ai_descriptions = config.get("scanner", "use_ai_descriptions", True)
                    use_ollama = config.get("ollama", "enabled", False)
                    ollama_url = config.get("ollama", "url", "http://localhost:11434")
                    ollama_model = config.get("ollama", "model", "llava")
                    system_prompt = config.get("ollama", "system_prompt", "Describe this image concisely, start with main colors separated by comma, then the main subject and key visual elements and style at the end.")
                    
                    # Use the existing AI processor and image scanner already initialized in the MainWindow
                    # No need to create new instances for every folder
                    
                    # Callback to update progress for this folder
                    def folder_progress_callback(current, total):
                        if self.progress_dialog and self.progress_dialog.isVisible():
                            # Show both folder progress and overall progress
                            folder_progress = f"Folder {processed_folders + 1}/{folder_count}: Image {current}/{total}"
                            overall_progress = f"Total progress: {processed_folders}/{folder_count} folders"
                            self.progress_dialog.update_operation(folder_progress)
                            self.progress_dialog.update_progress(current, total)
                    
                    # Scan the folder using the existing image_scanner instance
                    folder_result = self.image_scanner.scan_folder(folder_id, folder_path, folder_progress_callback)
                    
                    # Update totals
                    if folder_result:
                        total_processed += folder_result.get('processed', 0)
                        total_failed += folder_result.get('failed', 0)
                        total_images += folder_result.get('total', 0)
                        
                        # Log folder results
                        if self.progress_dialog and self.progress_dialog.isVisible():
                            self.progress_dialog.log_message(f"Completed folder {folder_path}")
                            self.progress_dialog.log_message(f"    Processed: {folder_result.get('processed', 0)} images")
                            self.progress_dialog.log_message(f"    Failed: {folder_result.get('failed', 0)} images")
                    
                    # Increment processed folders count
                    processed_folders += 1
                    
                    # Check if the operation was cancelled
                    if self.task_manager.is_task_cancelled("batch_scan_folders"):
                        if self.progress_dialog and self.progress_dialog.isVisible():
                            self.progress_dialog.log_message("Scan cancelled by user")
                        break
                
                # Store final results
                results = {
                    'processed': total_processed,
                    'failed': total_failed,
                    'total': total_images,
                    'folders_processed': processed_folders,
                    'folders_total': folder_count
                }
                
                return results
                
            except Exception as e:
                logger.error(f"Error in batch folder scan: {str(e)}")
                if self.progress_dialog and self.progress_dialog.isVisible():
                    self.progress_dialog.log_message(f"Error scanning folders: {str(e)}")
                return None
        
        # Define completion callback
        def on_complete(results):
            try:
                if self.progress_dialog and self.progress_dialog.isVisible():
                    self.progress_dialog.update_operation("Scan complete")
                    
                    if results:
                        folders_processed = results.get('folders_processed', 0)
                        folders_total = results.get('folders_total', 0)
                        self.progress_dialog.log_message("\n=== SCAN COMPLETE ===")
                        self.progress_dialog.log_message(f"Folders processed: {folders_processed} of {folders_total}")
                        self.progress_dialog.log_message(f"Total images processed: {results.get('processed', 0)}")
                        self.progress_dialog.log_message(f"Total images failed: {results.get('failed', 0)}")
                    
                    # Enable close button
                    self.progress_dialog.close_when_finished()
                
                # Refresh the thumbnail browser
                self.thumbnail_browser.refresh()
                
                # Update status bar
                if results:
                    self.status_bar.showMessage(f"Folders scan complete: {results.get('processed', 0)} images processed in {results.get('folders_processed', 0)} folders")
                else:
                    self.status_bar.showMessage("Folders scan failed or was cancelled")
                    
            except Exception as e:
                logger.error(f"Error in batch scan completion callback: {str(e)}")
            finally:
                # Remove the task
                self.task_manager.remove_task("batch_scan_folders")
        
        # Define error callback
        def on_error(error_info):
            try:
                error_msg = error_info[0] if error_info and len(error_info) > 0 else "Unknown error"
                logger.error(f"Batch scan error: {error_msg}")
                
                if self.progress_dialog and self.progress_dialog.isVisible():
                    self.progress_dialog.log_message(f"Error scanning folders: {error_msg}")
                    self.progress_dialog.close_when_finished()
                
                # Update status bar
                self.status_bar.showMessage("Folders scan failed")
                
            except Exception as e:
                logger.error(f"Error in batch scan error callback: {str(e)}")
            finally:
                # Remove the task
                self.task_manager.remove_task("batch_scan_folders")
        
        # Define cancel callback
        def on_cancel():
            try:
                # Mark task as cancelled
                self.task_manager.cancel_task("batch_scan_folders")
                
                logger.info("Batch folder scan cancelled by user")
                self.status_bar.showMessage("Folders scan cancelled")
                
                if self.progress_dialog and self.progress_dialog.isVisible():
                    self.progress_dialog.log_message("Scan cancelled by user")
                    self.progress_dialog.enable_close()
                
            except Exception as e:
                logger.error(f"Error in batch scan cancel callback: {str(e)}")
        
        # Set up cancel callback
        if self.progress_dialog:
            self.progress_dialog.cancelled.connect(on_cancel)
        
        # Add the batch task to the task manager
        self.task_manager.start_task(
            "batch_scan_folders",
            process_folders_worker,
            on_result=on_complete,
            on_error=on_error
        )
        
        # Show the progress dialog
        if self.progress_dialog:
            self.progress_dialog.show()
            
    def scan_folder(self, folder_id, folder_path):
        """Scan a folder for images.
        
        Args:
            folder_id (int): ID of the folder to scan
            folder_path (str): Path of the folder
        """
        try:
            # Check if the folder exists
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                self.notification_manager.show_message_box(
                    "Folder Not Found", 
                    f"The folder '{folder_path}' does not exist or is not accessible.",
                    NotificationType.WARNING
                )
                return
            
            # Check if a scan task is already running for this folder
            if self.task_manager.is_task_active(f"scan_folder_{folder_id}"):
                self.notification_manager.show_message_box(
                    "Scan in Progress", 
                    f"A scan is already in progress for folder '{folder_path}'.",
                    NotificationType.INFO
                )
                return
                
            # Create progress dialog
            self.progress_dialog = self.create_progress_dialog(
                'scanning_folder_title',
                'scanning_folder_description',
                parent=self,
                cancellable=True
            )
            # Update with folder path
            self.progress_dialog.update_operation(f"Scanning folder '{folder_path}' for images...")
            
            # Define progress callback
            def progress_callback(current, total):
                try:
                    if self.progress_dialog and self.progress_dialog.isVisible():
                        self.progress_dialog.update_progress(current, total)
                        self.progress_dialog.update_operation(f"Processing image {current} of {total}")
                except Exception as e:
                    logger.error(f"Error in progress callback: {str(e)}")
            
            # Define task completion callback
            def on_task_complete(results):
                try:
                    # Update progress dialog
                    if results:
                        if self.progress_dialog and self.progress_dialog.isVisible():
                            self.progress_dialog.update_operation("Scan complete")
                            self.progress_dialog.log_message(f"Processed: {results.get('processed', 0)} images")
                            self.progress_dialog.log_message(f"Failed: {results.get('failed', 0)} images")
                            self.progress_dialog.log_message(f"Total: {results.get('total', 0)} images")
                            
                            # Enable close button
                            self.progress_dialog.close_when_finished()
                    else:
                        if self.progress_dialog and self.progress_dialog.isVisible():
                            self.progress_dialog.log_message("Scan failed or was cancelled")
                            self.progress_dialog.close_when_finished()
                    
                    # Refresh the thumbnail browser if it's showing this folder
                    if self.thumbnail_browser.current_folder_id == folder_id:
                        self.thumbnail_browser.refresh()
                    
                    # Update status bar
                    processed = results.get('processed', 0) if results else 0
                    self.status_bar.showMessage(f"Folder scan complete: {processed} images processed")
                    
                except Exception as e:
                    logger.error(f"Error in task completion callback: {str(e)}")
                finally:
                    # Remove task from manager
                    self.task_manager.remove_task(f"scan_folder_{folder_id}")
            
            # Define error callback
            def on_task_error(error_info):
                try:
                    error_msg = error_info[0] if error_info and len(error_info) > 0 else "Unknown error"
                    logger.error(f"Scan error: {error_msg}")
                    
                    if self.progress_dialog and self.progress_dialog.isVisible():
                        self.progress_dialog.log_message(f"Error scanning folder: {error_msg}")
                        self.progress_dialog.close_when_finished()
                    
                    # Update status bar
                    self.status_bar.showMessage("Folder scan failed")
                    
                    # Show error message
                    QMessageBox.critical(
                        self, "Scan Error", 
                        f"An error occurred while scanning the folder: {error_msg}",
                        QMessageBox.StandardButton.Ok
                    )
                except Exception as e:
                    logger.error(f"Error in error callback: {str(e)}")
                finally:
                    # Remove task from manager
                    self.task_manager.remove_task(f"scan_folder_{folder_id}")
            
            # Define cancel callback
            def on_cancel():
                try:
                    logger.info("Folder scan cancelled by user")
                    self.status_bar.showMessage("Folder scan cancelled")
                    
                    if self.progress_dialog and self.progress_dialog.isVisible():
                        self.progress_dialog.log_message("Scan cancelled by user")
                        self.progress_dialog.close_when_finished()
                except Exception as e:
                    logger.error(f"Error in cancel callback: {str(e)}")
            
            # Define finished callback
            def on_finished():
                try:
                    logger.info("Folder scan task finished")
                except Exception as e:
                    logger.error(f"Error in finished callback: {str(e)}")
            
            # Show progress dialog
            self.progress_dialog.cancelled.connect(on_cancel)
            self.progress_dialog.show()
            
            # Start scan in background thread
            success = self.task_manager.start_task(
                task_id=f"scan_folder_{folder_id}",
                fn=self.image_scanner.scan_folder,
                folder_id=folder_id,
                folder_path=folder_path,
                progress_callback=progress_callback,  # Fixed parameter name to match image_scanner expectation
                on_result=on_task_complete,
                on_error=on_task_error,
                on_finished=on_finished
            )
            
            if not success:
                logger.error(f"Failed to start scan task for folder {folder_path}")
                self.progress_dialog.close()
                QMessageBox.critical(
                    self, "Scan Error", 
                    f"Failed to start scan task for folder '{folder_path}'.",
                    QMessageBox.StandardButton.Ok
                )
        
        except Exception as e:
            logger.error(f"Exception in scan_folder: {str(e)}")
            QMessageBox.critical(
                self, "Error", 
                f"An unexpected error occurred: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
            
            if hasattr(self, 'progress_dialog') and self.progress_dialog and self.progress_dialog.isVisible():
                self.progress_dialog.close()
    
    def on_generate_descriptions(self):
        """Handle the Generate Descriptions action."""
        # Get the currently selected folder from the folder panel
        selected_folder = self.folder_panel.folder_tree.currentItem()
        
        if selected_folder:
            folder_id = selected_folder.data(0, Qt.ItemDataRole.UserRole)
            
            if folder_id:
                # Get folder info
                folders = self.db_manager.get_folders()
                folder_info = next((f for f in folders if f["folder_id"] == folder_id), None)
                
                if folder_info:
                    # Get Ollama model information
                    from src.config.config_manager import ConfigManager
                    config = ConfigManager()
                    ollama_model = config.get("ollama", "model", "llava")
                    ollama_url = config.get("ollama", "server_url", "http://localhost:11434")
                    
                    # Create a custom message box for confirmation with options
                    message_box = QMessageBox(self)
                    message_box.setWindowTitle("Generate Descriptions")
                    message_box.setText(f"Generate descriptions for images in folder '{folder_info['path']}'?")
                    message_box.setInformativeText(
                        f"Ollama Model: {ollama_model}\n" +
                        f"Server URL: {ollama_url}\n\n" +
                        "If Ollama is not available, basic image analysis will be used as a fallback."
                    )
                    
                    # Add custom buttons
                    new_only_button = message_box.addButton("New Images Only", QMessageBox.ButtonRole.YesRole)
                    all_images_button = message_box.addButton("Update All Images", QMessageBox.ButtonRole.YesRole)
                    cancel_button = message_box.addButton("Cancel", QMessageBox.ButtonRole.NoRole)
                    
                    # Set default button based on configuration
                    default_process_all = config.get("ai", "process_all_images", False)
                    default_button = all_images_button if default_process_all else new_only_button
                    message_box.setDefaultButton(default_button)
                    
                    # Show the message box and get the result
                    message_box.exec()
                    
                    # Determine which button was clicked
                    clicked_button = message_box.clickedButton()
                    
                    if clicked_button == cancel_button:
                        return
                        
                    # Set the process_all flag based on the button clicked
                    process_all = (clicked_button == all_images_button)
                    
                    # Create progress dialog
                    mode_text = "new images only" if not process_all else "all images"
                    progress_dialog = self.create_progress_dialog(
                        'generating_descriptions_title',
                        'generating_descriptions_description',
                        parent=self,
                        cancellable=True
                    )
                    # Update with specific details
                    progress_dialog.update_operation(f"Generating AI descriptions for {mode_text} in '{folder_info['path']}'...\nUsing Ollama model: {ollama_model}")
                    
                    # Define progress callback
                    def progress_callback(current, total, message=None):
                        progress_dialog.update_progress(current, total)
                        if message:
                            progress_dialog.update_operation(message)
                        else:
                            progress_dialog.update_operation(f"Processing image {current} of {total}")
                    
                    # Define task completion callback
                    def on_task_complete(results):
                        # Update progress dialog
                        if results:
                            progress_dialog.update_operation("Description generation complete")
                            progress_dialog.log_message(f"Processed: {results['processed']} images")
                            progress_dialog.log_message(f"Skipped: {results['skipped']} images")
                            progress_dialog.log_message(f"Failed: {results['failed']} images")
                        else:
                            progress_dialog.log_message("Description generation failed or was cancelled")
                        
                        # Enable close button
                        progress_dialog.close_when_finished()
                        
                        # Refresh the thumbnail browser if it's showing this folder
                        if self.thumbnail_browser.current_folder_id == folder_id:
                            self.thumbnail_browser.refresh()
                        
                        # Update status bar
                        self.status_bar.showMessage(f"Description generation complete: {results['processed']} images processed")
                        
                        # Remove task from manager
                        self.task_manager.remove_task(f"generate_descriptions_{folder_id}")
                    
                    # Define error callback
                    def on_task_error(error_info):
                        progress_dialog.log_message(f"Error generating descriptions: {error_info[0]}")
                        progress_dialog.close_when_finished()
                        
                        # Update status bar
                        self.status_bar.showMessage("Description generation failed")
                        
                        # Remove task from manager
                        self.task_manager.remove_task(f"generate_descriptions_{folder_id}")
                    
                    # Define cancel callback
                    def on_cancel():
                        self.status_bar.showMessage("Description generation cancelled")
                    
                    # Show progress dialog
                    progress_dialog.cancelled.connect(on_cancel)
                    progress_dialog.show()
                    
                    # Start description generation in background thread
                    self.task_manager.start_task(
                        task_id=f"generate_descriptions_{folder_id}",
                        fn=self.ai_processor.batch_process_folder,
                        folder_id=folder_id,
                        process_all=process_all,  # Pass the process_all flag
                        progress_callback=progress_callback,
                        on_result=on_task_complete,
                        on_error=on_task_error
                    )
    
    def on_settings(self):
        """Handle the Settings action."""
        settings_dialog = SettingsDialog(self.config_manager, self.theme_manager, self.language_manager, self)
        settings_dialog.theme_changed.connect(self.on_theme_changed)
        settings_dialog.language_changed.connect(self.on_language_changed)
        theme_before = self.config_manager.get("ui", "theme", None)
        language_before = self.config_manager.get("ui", "language", "en")
        
        if settings_dialog.exec() == QDialog.DialogCode.Accepted:
            # Reload component settings
            thumb_size = self.config_manager.get("thumbnails", "size", 200)
            self.thumbnail_generator.size = (thumb_size, thumb_size)
            
            # Reinitialize AI processor with updated settings
            self.ai_processor = AIImageProcessor(
                db_manager=self.db_manager,
                batch_size=self.config_manager.get("ai", "batch_size", 1)
            )
            
            # Update the image scanner to use the new AI processor
            self.image_scanner.ai_processor = self.ai_processor
            
            # Update background scanner settings
            self.update_background_scanner_settings()
            
            # Check if the theme was changed and update immediately
            theme_after = self.config_manager.get("ui", "theme", None)
            if theme_after != theme_before:
                self.on_theme_changed(theme_after)
                
            # Check if the language was changed and update immediately
            language_after = self.config_manager.get("ui", "language", "en")
            if language_after != language_before:
                # Re-initialize the language manager with the new language
                from src.config.language_manager import LanguageManager
                self.language_manager = LanguageManager(self.config_manager)
                # Apply language to the main window and all panels
                from src.ui.main_window_language import apply_language_to_main_window
                apply_language_to_main_window(self, self.language_manager)
                # Also update language_manager for all relevant panels/dialogs
                if hasattr(self, 'metadata_panel') and hasattr(self.metadata_panel, 'set_language_manager'):
                    self.metadata_panel.set_language_manager(self.language_manager)
                if hasattr(self, 'enhanced_search_panel') and hasattr(self.enhanced_search_panel, 'set_language_manager'):
                    self.enhanced_search_panel.set_language_manager(self.language_manager)
                if hasattr(self, 'settings_dialog') and hasattr(self.settings_dialog, 'set_language_manager'):
                    self.settings_dialog.set_language_manager(self.language_manager)
                # Retranslate main window UI elements
                if hasattr(self, 'retranslateUi'):
                    self.retranslateUi()

    
    def on_folder_selected(self, folder_id, folder_path):
        """Handle folder selection from the folder panel.
        
        Args:
            folder_id (int): ID of the selected folder
            folder_path (str): Path of the selected folder
        """
        # Special case for All Images (-1)
        if folder_id == -1:
            # Update status bar
            self.status_bar.showMessage("Search across all images")
            
            # Prompt for a search across all images
            self.search_all_images()
            return
        
        # Update status bar
        self.status_bar.showMessage(f"Selected folder: {folder_path}")
        
        # Update thumbnail browser with images from the selected folder
        self.thumbnail_browser.set_folder(folder_id)
        
        # Store the current folder ID for search context
        self.current_folder_id = folder_id
    
    def on_folder_removed(self, folder_id):
        """Handle folder removal from the folder panel.
        
        Args:
            folder_id (int): ID of the removed folder
        """
        # Clear the thumbnail browser if it was showing this folder
        if self.thumbnail_browser.current_folder_id == folder_id:
            self.thumbnail_browser.clear_thumbnails()
            self.status_bar.showMessage("Folder removed")
            
    def on_catalog_selected(self, catalog_id, catalog_name):
        """Handle catalog selection from the catalog panel.
        
        Args:
            catalog_id (int): ID of the selected catalog
            catalog_name (str): Name of the selected catalog
        """
        # Set the thumbnail browser to show the selected catalog
        self.thumbnail_browser.set_catalog(catalog_id)
        self.status_bar.showMessage(f"Viewing catalog: {catalog_name}")
    
    def on_catalog_removed(self, catalog_id):
        """Handle catalog removal from the catalog panel.
        
        Args:
            catalog_id (int): ID of the removed catalog
        """
        # Clear the thumbnail browser if it was showing this catalog
        if hasattr(self.thumbnail_browser, 'current_catalog_id') and self.thumbnail_browser.current_catalog_id == catalog_id:
            self.thumbnail_browser.clear_thumbnails()
            self.status_bar.showMessage("Catalog removed")
    
    def on_catalog_added(self, catalog_id, catalog_name):
        """Handle catalog addition from the catalog panel.
        
        Args:
            catalog_id (int): ID of the added catalog
            catalog_name (str): Name of the added catalog
        """
        # Update status bar
        self.status_bar.showMessage(f"Added catalog: {catalog_name}")
        
    def on_upgrade_database_for_catalogs(self):
        """Upgrade the database schema to support catalogs."""
        from PyQt6.QtWidgets import QMessageBox, QApplication
        from src.database.db_upgrade import upgrade_database_schema
        
        # Show confirmation dialog
        confirm = QMessageBox.question(
            self, "Upgrade Database",
            "This will upgrade your database to support the Catalogs feature.\n\n"
            "This operation is safe and will not affect your existing data.\n\n"
            "Continue with database upgrade?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # Update status bar
        self.status_bar.showMessage("Upgrading database schema for Catalogs feature...")
        QApplication.processEvents()  # Update UI
        
        # Perform the upgrade directly (database operations are typically fast)
        success, message = upgrade_database_schema(self.db_manager.db_path)
        
        # Show result in a message box
        if success:
            QMessageBox.information(self, "Database Upgraded", message)
            self.status_bar.showMessage("Database upgraded successfully")
            
            # Refresh the catalog panel if it exists
            if hasattr(self, 'catalog_panel'):
                self.catalog_panel.refresh_catalogs()
        else:
            QMessageBox.critical(self, "Upgrade Failed", message)
            self.status_bar.showMessage("Database upgrade failed")
    

    
    def show_all_images(self):
        """Legacy method - redirects to search_all_images."""
        self.search_all_images()
            
    def search_all_images(self):
        """Prompt for search query and search across all images."""
        # Clear the current folder selection to indicate we're searching all images
        self.current_folder_id = None
        self.thumbnail_browser.current_folder_id = None
        
        # Prompt for a search query using an input dialog
        search_query, ok = QInputDialog.getText(
            self,
            "Search All Images",
            "Enter search query:",
            QLineEdit.EchoMode.Normal
        )
        
        if not ok or not search_query.strip():
            # User cancelled or entered empty query
            self.status_bar.showMessage("Search cancelled")
            
            # Clear thumbnails and show message
            self.thumbnail_browser.clear_thumbnails()
            empty_label = QLabel("Please enter a search query to search across all images")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.thumbnail_browser.grid_layout.addWidget(empty_label, 0, 0)
            self.thumbnail_browser.header_label.setText("Search All Images")
            return
        
        # Update status bar
        self.status_bar.showMessage(f"Searching for: {search_query} across all images")
        
        # Clear thumbnails
        self.thumbnail_browser.clear_thumbnails()
        
        # Set header
        self.thumbnail_browser.header_label.setText(f"Searching for: {search_query} (All Images)")
        
        # Show loading message
        loading_label = QLabel(f"Searching for '{search_query}' across all images...")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_browser.grid_layout.addWidget(loading_label, 0, 0)
        QApplication.processEvents()  # Update UI
        
        # Start the search (using the optimized method)
        images = self.db_manager.search_images(search_query, limit=1000000)
        
        # Remove loading label
        for i in reversed(range(self.thumbnail_browser.grid_layout.count())): 
            widget = self.thumbnail_browser.grid_layout.itemAt(i).widget()
            if widget is not None and isinstance(widget, QLabel):
                widget.setParent(None)
                widget.deleteLater()
        
        if not images:
            # No images found
            empty_label = QLabel(f"No images found for query: {search_query}")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.thumbnail_browser.grid_layout.addWidget(empty_label, 0, 0)
            self.thumbnail_browser.header_label.setText(f"No results for: {search_query} (All Images)")
            return
        
        # Update header with count
        self.thumbnail_browser.header_label.setText(f"Search results for: {search_query} (Found {len(images)} images)")
        
        # Add thumbnails to browser
        self.thumbnail_browser.add_thumbnails(images)
        self.status_bar.showMessage(f"Found {len(images)} images matching '{search_query}'")
    
    def load_all_images_worker(self, progress_callback=None):
        """Worker function to load all images using the optimized database query.
        
        Args:
            progress_callback (function, optional): Callback for progress updates
            
        Returns:
            list: List of all images
        """
        try:
            # Get image count first (for UI feedback)
            folders = self.db_manager.get_folders(enabled_only=True)
            
            if not folders:
                return []
            
            # Use the optimized database query to get all images in one go
            # This is much more efficient than loading from each folder separately
            # With virtualized grid, we can safely load many more images at once
            all_images = self.db_manager.get_all_images(limit=1000000)
            return all_images
            
        except Exception as e:
            logger.error(f"Error loading all images: {e}")
            return []
    
    def on_all_images_loaded(self, all_images):
        """Handle completion of all images loading.
        
        Args:
            all_images (list): List of all images loaded
        """
        # Check if we're using traditional or virtualized browser
        if hasattr(self.thumbnail_browser, 'grid_layout'):
            # Traditional browser - clear any loading widgets
            for i in reversed(range(self.thumbnail_browser.grid_layout.count())): 
                widget = self.thumbnail_browser.grid_layout.itemAt(i).widget()
                if widget is not None and isinstance(widget, QLabel):
                    widget.setParent(None)
                    widget.deleteLater()
        
        if not all_images:
            # No images found
            if hasattr(self.thumbnail_browser, 'grid_layout'):
                # Traditional browser - show empty message
                empty_label = QLabel("No images found in any folder")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.thumbnail_browser.grid_layout.addWidget(empty_label, 0, 0)
            self.status_bar.showMessage("No images found")
            return
        
        # Update header with count
        self.thumbnail_browser.header_label.setText(f"All Images ({len(all_images)})")
        
        # Add thumbnails to browser (using the optimized method that supports pagination)
        self.thumbnail_browser.add_thumbnails(all_images)
        self.status_bar.showMessage(f"Loaded {len(all_images)} images from all folders")
    
    def on_all_images_error(self, error):
        """Handle errors in all images loading.
        
        Args:
            error (tuple): (error_type, error_message)
        """
        error_type, error_message = error
        logger.error(f"Error loading all images: {error_type}: {error_message}")
        self.status_bar.showMessage(f"Error loading images: {error_message}")
        self.thumbnail_browser.header_label.setText("All Images (Error Loading)")
    
    def on_search_requested(self, query, search_all_folders=False):
        """Handle search request from the search panel.
        
        Args:
            query (str): Search query
            search_all_folders (bool): Whether to search across all folders
        """
        # Get the current folder ID (could be None for "All Images")
        folder_id = getattr(self, 'current_folder_id', None)
        
        # Determine search scope based on radio button selection
        if search_all_folders or folder_id is None or folder_id == -1:
            # Update status bar for global search
            self.status_bar.showMessage(f"Searching for: {query} across all folders")
            
            # Clear thumbnails
            self.thumbnail_browser.clear_thumbnails()
            
            # Set header
            self.thumbnail_browser.header_label.setText(f"Search results for: {query} (All Folders)")
            
            # Search across all folders
            self.thumbnail_browser.search(query)
        else:
            # Search only within the specific folder
            folder_info = next((f for f in self.db_manager.get_folders() if f["folder_id"] == folder_id), None)
            folder_name = folder_info.get("path", "Unknown") if folder_info else "Unknown"
            
            # Update status bar
            self.status_bar.showMessage(f"Searching for: {query} in folder: {folder_name}")
            
            # Clear thumbnails
            self.thumbnail_browser.clear_thumbnails()
            
            # Set header
            self.thumbnail_browser.header_label.setText(f"Search results for: {query} in folder: {os.path.basename(folder_name)}")
            
            # Search only within this folder
            images = self.db_manager.search_images_in_folder(folder_id, query, limit=1000000)
            
            if not images:
                # No images found
                empty_label = QLabel(f"No images found for query: {query} in this folder")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.thumbnail_browser.grid_layout.addWidget(empty_label, 0, 0)
                return
            
            # Add thumbnails
            self.thumbnail_browser.add_thumbnails(images)
            self.status_bar.showMessage(f"Searching for: {query} across all folders")
            
            # Search across all folders
            self.thumbnail_browser.search(query)
        
    def on_thumbnail_selected(self, image_id):
        """Handle thumbnail selection event.
        
        Args:
            image_id (int): ID of the selected image
        """
        # Update metadata panel with selected image
        self.metadata_panel.display_metadata(image_id)
        
        # Update status bar
        self.status_bar.showMessage(f"Selected image ID: {image_id}")
    
    def on_thumbnail_double_clicked(self, image_id, full_path):
        """Handle thumbnail double-click.
        
        Args:
            image_id (int): ID of the clicked image
            full_path (str): Full path to the image file
        """
        # Open the image with the default application
        if os.path.exists(full_path):
            import subprocess
            try:
                os.startfile(full_path)
            except AttributeError:
                # os.startfile is only available on Windows
                subprocess.call(['xdg-open', full_path])
    
    def on_batch_generate_from_context_menu(self, image_ids):
        """Handle batch description generation requested from context menu.
        
        Args:
            image_ids (list): List of image IDs to generate descriptions for
        """
        if not image_ids:
            return
            
        # Start the description generation process directly
        self.on_batch_generate_descriptions(image_ids)
    
    def on_batch_generate_descriptions(self, image_ids=None):
        """Generate descriptions for selected images.
        
        Args:
            image_ids (list, optional): List of specific image IDs to process. If None,
                                        uses currently selected thumbnails.
        """
        # If image_ids is not provided or is not a list, get selected images from the thumbnail browser
        if image_ids is None or not isinstance(image_ids, list):
            # Log the issue if it's not None but also not a list (helps with debugging)
            if image_ids is not None and not isinstance(image_ids, list):
                logger.warning(f"Invalid image_ids type received: {type(image_ids)}. Using selected thumbnails instead.")
                
            if not hasattr(self.thumbnail_browser, 'selected_thumbnails') or not self.thumbnail_browser.selected_thumbnails:
                QMessageBox.information(self, "No Images Selected", "Please select one or more images first.")
                return
            image_ids = self.thumbnail_browser.selected_thumbnails 
            # print(f"Selected image IDs from main_window: {image_ids}") # Debug print

        # Ensure we have a valid list
        if not image_ids:
            QMessageBox.information(self, "No Images Selected", "Please select one or more images first.")
            return
            
        num_selected = len(image_ids)
        
        # Get Ollama model information
        config = ConfigManager()
        ollama_model = config.get("ollama", "model", "llava")
        ollama_url = config.get("ollama", "server_url", "http://localhost:11434")
        process_all = config.get("ai", "process_all_images", False)
        
        # Create confirmation dialog
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Generate Descriptions")
        message_box.setText(f"Generate descriptions for {num_selected} selected images?")
        message_box.setInformativeText(
            f"Ollama Model: {ollama_model}\n" +
            f"Server URL: {ollama_url}\n\n" +
            "If Ollama is not available, basic image analysis will be used as a fallback."
        )
        
        # Add custom buttons
        yes_button = message_box.addButton("Yes", QMessageBox.ButtonRole.YesRole)
        cancel_button = message_box.addButton("Cancel", QMessageBox.ButtonRole.NoRole)
        
        message_box.setDefaultButton(yes_button)
        
        # Show the message box and get the result
        message_box.exec()
        
        # Determine which button was clicked
        clicked_button = message_box.clickedButton()
        
        if clicked_button == cancel_button:
            return
        
        # Create progress dialog
        progress_dialog = ProgressDialog(
            "Generating Descriptions",
            f"Generating AI descriptions for {num_selected} selected images...\n" +
            f"Using Ollama model: {ollama_model}",
            self
        )
        
        # Define progress callback
        def progress_callback(current, total, message=None):
            progress_dialog.update_progress(current, total)
            if message:
                progress_dialog.update_operation(message)
            else:
                progress_dialog.update_operation(f"Processing image {current} of {total}")
        
        # Define task completion callback
        def on_task_complete(results):
            # Update progress dialog
            if results:
                progress_dialog.update_operation("Description generation complete")
                progress_dialog.log_message(f"Processed: {results['processed']} images")
                progress_dialog.log_message(f"Skipped: {results['skipped']} images")
                progress_dialog.log_message(f"Failed: {results['failed']} images")
            else:
                progress_dialog.log_message("Description generation failed or was cancelled")
            
            # Enable close button
            progress_dialog.close_when_finished()
            
            # Refresh the thumbnail browser
            self.thumbnail_browser.refresh()
            
            # Update status bar
            if results:
                self.status_bar.showMessage(f"Description generation complete: {results['processed']} images processed")
        
        # Define error callback
        def on_task_error(error_info):
            progress_dialog.log_message(f"Error generating descriptions: {error_info[0]}")
            progress_dialog.close_when_finished()
            
            # Update status bar
            self.status_bar.showMessage("Error generating descriptions")
        
        # Define cancel callback
        def on_cancel():
            self.status_bar.showMessage("Description generation cancelled")
        
        # Show progress dialog
        progress_dialog.cancelled.connect(on_cancel)
        progress_dialog.show()
        
        # Define the batch processing function
        def process_selected_images(image_ids, progress_callback=None):
            results = {
                "processed": 0,
                "failed": 0,
                "skipped": 0,
                "total": len(image_ids)
            }
            
            total = len(image_ids)
            
            for i, image_id in enumerate(image_ids):
                # Get image info
                image_info = self.db_manager.get_image_by_id(image_id)
                
                if not image_info:
                    results["failed"] += 1
                    continue
                
                # Skip if already has description and not processing all
                if not process_all and image_info.get("ai_description"):
                    results["skipped"] += 1
                    continue
                
                # Generate description
                image_path = image_info.get("full_path")
                description = self.ai_processor.generate_description(image_path)
                
                if description:
                    # Try to update using the safe operations module first
                    try:
                        from src.database.db_safe_operations import safe_update_description
                        
                        # Get the database path from the manager
                        db_path = self.db_manager.db_path
                        
                        # Use the safe update method
                        success = safe_update_description(db_path, image_id, ai_description=description)
                        
                        if success:
                            results["processed"] += 1
                        else:
                            # Fall back to the regular method if safe update fails
                            if self.db_manager.update_image_description(image_id, ai_description=description):
                                results["processed"] += 1
                            else:
                                results["failed"] += 1
                    except Exception as e:
                        logger.error(f"Error using safe operations: {e}")
                        # Fall back to the regular method
                        if self.db_manager.update_image_description(image_id, ai_description=description):
                            results["processed"] += 1
                        else:
                            results["failed"] += 1
                else:
                    results["failed"] += 1
                
                # Update progress
                if progress_callback:
                    progress_callback(i + 1, total)
            
            return results
        
        # Generate a unique task ID with timestamp
        import time
        timestamp = int(time.time() * 1000)  # Millisecond timestamp for uniqueness
        task_id = f"batch_generate_descriptions_{id(self)}_{timestamp}"
        
        # Start description generation in background thread
        self.task_manager.start_task(
            task_id=task_id,
            fn=process_selected_images,
            image_ids=image_ids,
            progress_callback=progress_callback,
            on_result=on_task_complete,
            on_error=on_task_error
        )
    
    def on_batch_export_images(self):
        """Export selected images to a folder."""
        # Get selected images from the thumbnail browser
        if not hasattr(self.thumbnail_browser, 'selected_thumbnails') or not self.thumbnail_browser.selected_thumbnails:
            QMessageBox.information(self, "No Images Selected", "Please select one or more images first.")
            return
        
        # Delegate to the thumbnail browser's copy function
        # This is essentially the same as copying, but we'll rename it for clarity
        self.thumbnail_browser.copy_selected_images(export_mode=True)
    
    def on_batch_rename_images(self):
        """Rename selected images with a pattern."""
        # Get selected images from the thumbnail browser
        if not hasattr(self.thumbnail_browser, 'selected_thumbnails') or not self.thumbnail_browser.selected_thumbnails:
            QMessageBox.information(self, "No Images Selected", "Please select one or more images first.")
            return
        
        # Get selected image IDs
        image_ids = list(self.thumbnail_browser.selected_thumbnails)
        num_selected = len(image_ids)
        
        # Get rename pattern from user
        pattern, ok = QInputDialog.getText(
            self, "Rename Images", 
            f"Enter rename pattern for {num_selected} images:\n\n" +
            "Use {n} for sequence number, {ext} for extension\n" +
            "Example: 'vacation_{n}' becomes 'vacation_1.jpg', 'vacation_2.png', etc.",
            QLineEdit.EchoMode.Normal,
            "image_{n}"
        )
        
        if not ok or not pattern:
            return
        
        # Create progress dialog
        progress_dialog = ProgressDialog(
            "Renaming Images",
            f"Renaming {num_selected} selected images...",
            self
        )
        progress_dialog.log_message(f"Starting rename operation with pattern: {pattern}")
        
        # Define progress callback
        def progress_callback(current, total, message=None):
            progress_dialog.update_progress(current, total)
            if message:
                progress_dialog.update_operation(message)
            else:
                progress_dialog.update_operation(f"Renaming image {current} of {total}")
        
        # Define task completion callback
        def on_task_complete(results):
            # Update progress dialog
            if results:
                progress_dialog.update_operation("Rename operation complete")
                progress_dialog.log_message(f"Successfully renamed: {results['success']} images")
                if results['failed'] > 0:
                    progress_dialog.log_message(f"Failed to rename: {results['failed']} images")
            else:
                progress_dialog.log_message("Rename operation failed or was cancelled")
            
            # Enable close button
            progress_dialog.close_when_finished()
            
            # Refresh the thumbnail browser
            self.thumbnail_browser.refresh()
            
            # Update status bar
            if results:
                self.status_bar.showMessage(f"Rename complete: {results['success']} images renamed")
        
        # Define error callback
        def on_task_error(error_info):
            progress_dialog.log_message(f"Error renaming images: {error_info[0]}")
            progress_dialog.close_when_finished()
            
            # Update status bar
            self.status_bar.showMessage("Error renaming images")
        
        # Define cancel callback
        def on_cancel():
            self.status_bar.showMessage("Rename operation cancelled")
        
        # Show progress dialog
        progress_dialog.cancelled.connect(on_cancel)
        progress_dialog.show()
        
        # Define the rename function
        def rename_images_task(image_ids, pattern, progress_callback=None):
            import os
            import shutil
            import time
            
            results = {
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "cleaned": 0,  # Count of database entries cleaned up for missing files
                "renamed_files": []
            }
            
            total = len(image_ids)
            start_time = time.time()
            
            # Log start of operation
            logger.info(f"Starting batch rename of {total} images with pattern '{pattern}'")
            if progress_callback:
                progress_callback(0, total, f"Starting rename operation on {total} images")
            
            for i, image_id in enumerate(image_ids):
                try:
                    # Get image info
                    image_info = self.db_manager.get_image_by_id(image_id)
                    
                    if not image_info:
                        logger.warning(f"Image ID {image_id} not found in database")
                        results["failed"] += 1
                        if progress_callback:
                            progress_callback(i + 1, total, f"Error: Image ID {image_id} not found")
                        continue
                    
                    # Normalize the source path to handle mixed slash types
                    source_path = image_info["full_path"]
                    source_path = os.path.normpath(source_path)
                    
                    # Debug info to help diagnose issues
                    logger.debug(f"Processing image: ID={image_id}, Path={source_path}")
                    logger.debug(f"File exists check: {os.path.exists(source_path)}")
                    
                    # Advanced file existence checks
                    # Extract directory and filename
                    dir_path = os.path.dirname(source_path)
                    base_filename = os.path.basename(source_path)
                    
                    # Check 1: Does the directory exist?
                    if not os.path.exists(dir_path):
                        logger.warning(f"Directory does not exist: {dir_path}")
                    else:
                        logger.debug(f"Directory exists: {dir_path}")
                        
                        # Check 2: List files in directory to see if our file exists with a slightly different name
                        try:
                            files_in_dir = os.listdir(dir_path)
                            logger.debug(f"Files in directory ({len(files_in_dir)} files): {files_in_dir[:10]}{'...' if len(files_in_dir) > 10 else ''}")
                            
                            # Look for similar filenames
                            timestamp_part = None
                            if 'Screenshot' in base_filename and ' ' in base_filename:
                                # Extract timestamp part for matching
                                parts = base_filename.split(' ')
                                if len(parts) > 1:
                                    timestamp_part = parts[1].split('.')[0]  # Get the timestamp without extension
                            
                            if timestamp_part:
                                logger.debug(f"Looking for files matching timestamp: {timestamp_part}")
                                similar_files = [f for f in files_in_dir if timestamp_part in f]
                                if similar_files:
                                    logger.debug(f"Found similar files: {similar_files}")
                                    # If we found a match, use it instead
                                    if len(similar_files) == 1:
                                        new_path = os.path.join(dir_path, similar_files[0])
                                        logger.debug(f"Using similar file instead: {new_path}")
                                        source_path = new_path
                            
                        except Exception as e:
                            logger.error(f"Error listing directory: {e}")
                    
                    # Try additional path fixing if needed
                    if not os.path.exists(source_path):
                        # Try alternate normalization
                        alt_path = source_path.replace('\\', '/')
                        logger.debug(f"Trying alternate path: {alt_path}")
                        
                        if os.path.exists(alt_path):
                            source_path = alt_path
                            logger.debug(f"Using alternate path instead: {source_path}")
                    
                    if not os.path.exists(source_path):
                        logger.warning(f"Source file not found: {source_path}")
                        
                        # Get more information about the file from the database for debugging
                        detailed_info = self.db_manager.get_image_by_id(image_id)
                        logger.debug(f"Database record details: {detailed_info}")
                        
                        # Ask user if they want to remove this entry from the database
                        from PyQt6.QtWidgets import QMessageBox
                        msg_box = QMessageBox()
                        msg_box.setIcon(QMessageBox.Icon.Question)
                        msg_box.setText(f"File not found: {os.path.basename(source_path)}")
                        msg_box.setInformativeText("Do you want to remove this missing file from the database?")
                        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.YesToAll | QMessageBox.StandardButton.NoToAll)
                        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                        
                        # Use a class variable to remember user's choice for YesToAll/NoToAll
                        if not hasattr(self, '_clean_missing_files_choice'):
                            self._clean_missing_files_choice = None
                            
                        if self._clean_missing_files_choice == 'always':
                            # Automatically remove the file
                            self.db_manager.delete_image(image_id)
                            logger.info(f"Removed missing file from database: ID={image_id}, Path={source_path}")
                            results["cleaned"] = results.get("cleaned", 0) + 1
                        elif self._clean_missing_files_choice == 'never':
                            # Skip without asking
                            pass
                        else:
                            # Ask user
                            response = msg_box.exec()
                            
                            if response == QMessageBox.StandardButton.YesToAll:
                                self._clean_missing_files_choice = 'always'
                                self.db_manager.delete_image(image_id)
                                logger.info(f"Removed missing file from database: ID={image_id}, Path={source_path}")
                                results["cleaned"] = results.get("cleaned", 0) + 1
                            elif response == QMessageBox.StandardButton.NoToAll:
                                self._clean_missing_files_choice = 'never'
                            elif response == QMessageBox.StandardButton.Yes:
                                self.db_manager.delete_image(image_id)
                                logger.info(f"Removed missing file from database: ID={image_id}, Path={source_path}")
                                results["cleaned"] = results.get("cleaned", 0) + 1
                        
                        results["failed"] += 1
                        if progress_callback:
                            progress_callback(i + 1, total, f"Error: Source file not found: {os.path.basename(source_path)}")
                        continue
                    
                    # Get directory and extension
                    directory = os.path.dirname(source_path)
                    filename = os.path.basename(source_path)
                    name, ext = os.path.splitext(filename)
                    
                    # Create new filename based on pattern
                    # Use both sequential number and image ID for more flexibility
                    new_filename = pattern.replace("{n}", str(i + 1))
                    new_filename = new_filename.replace("{id}", str(image_id))
                    new_filename = new_filename.replace("{ext}", ext[1:]) + ext
                    
                    dest_path = os.path.join(directory, new_filename)
                    
                    # Check if destination already exists
                    counter = 1
                    orig_new_filename = new_filename
                    while os.path.exists(dest_path) and dest_path != source_path:
                        new_filename = orig_new_filename.replace(ext, f"_{counter}{ext}")
                        dest_path = os.path.join(directory, new_filename)
                        counter += 1
                        # Prevent infinite loop
                        if counter > 100:
                            raise ValueError("Too many name conflicts, cannot create unique filename")
                    
                    # Skip if source and destination are the same
                    if dest_path == source_path:
                        logger.info(f"Skipping file (already has target name): {source_path}")
                        results["skipped"] += 1
                        if progress_callback:
                            progress_callback(i + 1, total, f"Skipped: {os.path.basename(source_path)} (already named correctly)")
                        continue
                    
                    # Rename the file
                    logger.debug(f"Renaming {source_path} to {dest_path}")
                    shutil.move(source_path, dest_path)
                    
                    # Update database with new path - note the parameter order: ID, filename, path
                    update_result = self.db_manager.update_image_path(image_id, new_filename, dest_path)
                    if not update_result:
                        logger.warning(f"Database update failed for image {image_id}")
                    
                    results["success"] += 1
                    results["renamed_files"].append(dest_path)
                    
                    # Update progress
                    if progress_callback:
                        progress_callback(i + 1, total, f"Renamed: {os.path.basename(source_path)} to {new_filename}")
                        
                except Exception as e:
                    logger.error(f"Error renaming {image_id}: {str(e)}")
                    results["failed"] += 1
                    
                    # Update progress with error info
                    if progress_callback:
                        progress_callback(i + 1, total, f"Error renaming image ID {image_id}: {str(e)}")
            
            # Log completion
            elapsed_time = time.time() - start_time
            logger.info(f"Batch rename completed in {elapsed_time:.2f}s: {results['success']} succeeded, {results['failed']} failed, {results['skipped']} skipped, {results.get('cleaned', 0)} database entries cleaned")
            
            return results
        
        # Start rename operation in background thread
        self.task_manager.start_task(
            task_id=f"batch_rename_images_{id(self)}",
            fn=rename_images_task,
            image_ids=image_ids,
            pattern=pattern,
            progress_callback=progress_callback,
            on_result=on_task_complete,
            on_error=on_task_error
        )
    
    def on_batch_copy_images(self):
        """Copy selected images to a folder."""
        # Delegate to the thumbnail browser's copy function
        self.thumbnail_browser.copy_selected_images()
    
    def on_batch_delete_descriptions(self):
        """Delete descriptions for selected images."""
        # Delegate to the thumbnail browser's delete descriptions function
        self.thumbnail_browser.delete_selected_descriptions()
    
    def on_batch_delete_images(self):
        """Delete selected images (legacy method)."""
        # Delegate to the thumbnail browser's delete images function (database only for backward compatibility)
        self.thumbnail_browser.delete_selected_images(delete_from_disk=False)
        
    def on_batch_delete_images_db_only(self):
        """Delete selected images from database only."""
        # Delegate to the thumbnail browser's delete images function with delete_from_disk=False
        self.thumbnail_browser.delete_selected_images(delete_from_disk=False)
    
    def on_batch_delete_images_with_files(self):
        """Delete selected images from both database and disk."""
        # Delegate to the thumbnail browser's delete images function with delete_from_disk=True
        self.thumbnail_browser.delete_selected_images(delete_from_disk=True)
    
    def toggle_virtualized_grid(self, enabled):
        """Toggle virtualized grid option.
        
        Args:
            enabled (bool): Whether to enable virtualized grid
        """
        # Save setting
        self.config_manager.set("performance", "use_virtualized_grid", enabled)
        
        # Get current image count to provide context
        image_count = self.db_manager.get_image_count()
        
        # Determine appropriate notification message based on image count
        status_message = "Virtualized grid " + ("enabled" if enabled else "disabled") + " (restart required)"
        self.status_bar.showMessage(status_message)
        
        # Additional details for the dialog
        details = ""
        if enabled:
            details = (
                "The virtualized grid will provide better performance for large collections by only rendering visible thumbnails. "
                f"Your collection currently has {image_count} images. "
                f"The virtualized grid is {'recommended' if image_count > 1000 else 'optional'} for your collection size."
            )
        else:
            details = (
                "Standard grid will be used. This is suitable for smaller collections but may slow down with larger image sets. "
                f"Your collection currently has {image_count} images. "
                f"The virtualized grid is {'recommended' if image_count > 1000 else 'optional'} for your collection size."
            )
        
        # Show restart dialog
        QMessageBox.information(
            self,
            "Restart Required",
            f"The virtualized grid setting has been changed. {details}\n\nPlease restart the application for the change to take effect."
        )
    
    def on_optimize_database(self):
        """Open the database optimization dialog."""
        try:
            # Create and show the optimization dialog
            optimization_dialog = DatabaseOptimizationDialog(self.db_manager, self)
            optimization_dialog.exec()
            
            # Check if we need to refresh the UI after optimization
            current_folder_id = self.folder_panel.get_selected_folder_id()
            if current_folder_id:
                # Refresh thumbnails if a folder is selected
                self.on_folder_selected(current_folder_id, self.folder_panel.get_selected_folder_path())
                
                # Show success message
                self.notification_manager.show_status_message(
                    "Database optimized and view refreshed", 
                    NotificationType.SUCCESS
                )
        except Exception as e:
            logger.error(f"Error opening database optimization dialog: {e}")
            self.notification_manager.show_message_box(
                "Optimization Error",
                f"An error occurred while trying to optimize the database: {str(e)}",
                NotificationType.ERROR
            )
            
    def on_repair_database(self):
        """Repair the database if it's corrupted."""
        try:
            # Confirm with user
            confirm = QMessageBox.question(
                self,
                "Repair Database",
                "This will attempt to repair the database if it's corrupted. "
                "The application will close after repair and you'll need to restart it. "
                "\n\nA backup of your current database will be created before repair. "
                "\n\nDo you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if confirm != QMessageBox.StandardButton.Yes:
                return
            
            # Create progress dialog
            progress_dialog = ProgressDialog(
                "Repairing Database",
                "Preparing to repair database...",
                self,
                cancellable=False
            )
            progress_dialog.show()
            
            # Import the repair module
            from src.database.db_repair import check_and_repair_if_needed
            
            # Define task function
            def repair_task(progress_callback=None):
                try:
                    # Update progress
                    progress_dialog.update_operation("Creating database backup...")
                    
                    # Get database path
                    db_path = self.db_manager.db_path
                    
                    # Force-repair the database (don't check integrity first)
                    from src.database.db_repair import repair_database
                    
                    # Custom progress callback that updates the dialog
                    def update_progress(current, total, message=None):
                        if progress_callback:
                            progress_callback(current, total, message)
                        if message:
                            progress_dialog.update_operation(message)
                    
                    success = repair_database(db_path)
                    
                    return {"success": success}
                except Exception as e:
                    logger.error(f"Error during database repair: {e}")
                    return {"success": False, "error": str(e)}
            
            # Define completion callback
            def on_task_complete(results):
                try:
                    if results and results.get("success"):
                        # Update progress dialog
                        progress_dialog.update_operation("Repair complete")
                        progress_dialog.log_message("Database has been repaired successfully")
                        progress_dialog.close_when_finished()
                        
                        # Show success message
                        QMessageBox.information(
                            self,
                            "Repair Complete",
                            "Database has been repaired successfully. "
                            "The application will now close. Please restart it.",
                            QMessageBox.StandardButton.Ok
                        )
                        
                        # Close the application
                        QApplication.quit()
                    else:
                        error_msg = results.get("error", "Unknown error")
                        progress_dialog.log_message(f"Repair failed: {error_msg}")
                        progress_dialog.close_when_finished()
                        
                        # Show error message
                        QMessageBox.critical(
                            self,
                            "Repair Failed",
                            f"Failed to repair database: {error_msg}",
                            QMessageBox.StandardButton.Ok
                        )
                except Exception as e:
                    logger.error(f"Error in repair completion callback: {e}")
                    if progress_dialog and progress_dialog.isVisible():
                        progress_dialog.close()
            
            # Define error callback
            def on_task_error(error_info):
                try:
                    error_msg = error_info[0] if error_info and len(error_info) > 0 else "Unknown error"
                    logger.error(f"Repair error: {error_msg}")
                    
                    if progress_dialog and progress_dialog.isVisible():
                        progress_dialog.log_message(f"Error during repair: {error_msg}")
                        progress_dialog.close_when_finished()
                    
                    # Show error message
                    QMessageBox.critical(
                        self,
                        "Repair Error",
                        f"An error occurred during database repair: {error_msg}",
                        QMessageBox.StandardButton.Ok
                    )
                except Exception as e:
                    logger.error(f"Error in repair error callback: {e}")
                    if progress_dialog and progress_dialog.isVisible():
                        progress_dialog.close()
            
            # Start repair in background thread
            self.task_manager.start_task(
                task_id="repair_database",
                fn=repair_task,
                on_result=on_task_complete,
                on_error=on_task_error
            )
            
        except Exception as e:
            logger.error(f"Error initiating database repair: {e}")
            self.notification_manager.show_message_box(
                "Repair Error",
                f"An error occurred while trying to repair the database: {str(e)}",
                NotificationType.ERROR
            )
    
    def check_database_optimization(self):
        """Check if database optimization is needed and perform it if necessary.
        Also repairs the database if it's corrupted.
        """
        try:
            # First, always check and repair the database if needed
            logger.info("Checking database integrity at startup...")
            self._repair_database_if_needed(silent=True)
            
            # Then check if optimization is needed (only if auto-optimization is enabled)
            auto_optimize = self.config_manager.get("database", "auto_optimize", True)
            
            if auto_optimize:
                # Check if optimization is needed
                logger.info("Checking if database optimization is needed...")
                optimization_needed = check_and_optimize_if_needed(self)
                
                if optimization_needed:
                    logger.info("Database optimization was performed")
                    
                    # Refresh the current view if a folder is selected
                    current_folder_id = self.folder_panel.get_selected_folder_id()
                    if current_folder_id:
                        self.on_folder_selected(current_folder_id, self.folder_panel.get_selected_folder_path())
        except Exception as e:
            logger.error(f"Error checking database optimization: {e}")
            # Don't show error to user during startup, just log it
    
    def _repair_database_if_needed(self, silent=False):
        """Check and repair the database if it's corrupted.
        
        Args:
            silent (bool): If True, don't show any UI dialogs during repair
        
        Returns:
            bool: True if repair was performed, False otherwise
        """
        try:
            # Import the repair module
            from src.database.db_repair import check_database_integrity, repair_database
            
            # Check database integrity
            db_path = self.db_manager.db_path
            integrity_result = check_database_integrity(db_path)
            
            if integrity_result is False:
                logger.warning("Database integrity check failed, performing automatic repair")
                
                if silent:
                    # Create a progress dialog but don't show it
                    progress_dialog = None
                    
                    # Define repair task
                    def repair_task(progress_callback=None):
                        try:
                            # Perform repair
                            result = repair_database(db_path, parent_widget=None)
                            return {"success": result}
                        except Exception as e:
                            logger.error(f"Error in repair task: {e}")
                            return {"success": False, "error": str(e)}
                    
                    # Define completion callback
                    def on_task_complete(results):
                        success = results.get("success", False)
                        if success:
                            logger.info("Database repair completed successfully")
                        else:
                            error_msg = results.get("error", "Unknown error")
                            logger.error(f"Database repair failed: {error_msg}")
                    
                    # Define error callback
                    def on_task_error(error_info):
                        error_msg = error_info[0] if error_info and len(error_info) > 0 else "Unknown error"
                        logger.error(f"Error during database repair: {error_msg}")
                    
                    # Start repair in background thread
                    self.task_manager.start_task(
                        task_id="silent_repair_database",
                        fn=repair_task,
                        on_result=on_task_complete,
                        on_error=on_task_error
                    )
                    
                    # Wait for task to complete (since this is during startup)
                    while self.task_manager.is_task_active("silent_repair_database"):
                        QApplication.processEvents()
                    
                    return True
                else:
                    # Use the regular repair method with UI
                    self.on_repair_database()
                    return True
            else:
                logger.info("Database integrity check passed")
                return False
                
        except Exception as e:
            logger.error(f"Error checking/repairing database: {e}")
            return False
    
    def ensure_window_visible(self):
        """Ensure the window is visible, active and in the foreground."""
        # Workaround to ensure window appears and is brought to front
        self.show()
        self.setWindowState((self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
        self.activateWindow()  # For Windows
        self.raise_()          # For macOS
        
        # Process events to ensure UI updates are applied immediately
        QApplication.processEvents()
    
    def on_date_search_requested(self, from_date, to_date):
        """Handle date range search request from the search panel.
        
        Args:
            from_date (datetime): Start date
            to_date (datetime): End date
        """
        # Update status bar
        self.status_bar.showMessage(f"Searching images by date between {from_date.date()} and {to_date.date()}")
        
        # Show searching message in thumbnail browser
        self.thumbnail_browser.clear_thumbnails()
        
        # Custom header for search in progress
        date_range_text = f"{from_date.date()} to {to_date.date()}"
        self.thumbnail_browser.header_label.setText(f"Searching for images between {date_range_text}...")
        
        # Create a progress dialog
        progress_dialog = ProgressDialog(
            "Date Search",
            f"Searching for images between {date_range_text}...",
            self,
            cancellable=True
        )
        
        # Create the search worker
        search_worker = DateSearchWorker(self.db_manager, from_date, to_date)
        
        # Connect signals
        def progress_callback(current, total, message=None):
            try:
                if progress_dialog and progress_dialog.isVisible():
                    # Avoid updating the progress if the dialog has been completed or cancellation already requested
                    if progress_dialog.is_complete or progress_dialog.user_cancelled:
                        return
                        
                    # Update the progress normally
                    progress_dialog.update_progress(current, total)
                    
                    # Only update operation message if one was provided
                    if message:
                        progress_dialog.update_operation(message)
                        logger.debug(f"Date search progress: {current}/{total} - {message}")
            except Exception as e:
                logger.error(f"Error in date search progress callback: {e}")
        
        def on_search_complete(results):
            try:
                # First handle updating the thumbnail browser with results
                logger.debug(f"Date search completed with {len(results)} results")
                
                if progress_dialog and progress_dialog.isVisible():
                    # Mark the dialog as completed
                    progress_dialog.update_operation(f"Found {len(results)} images in date range")
                    progress_dialog.update_progress(100, 100)
                    # Force the dialog to close and clean up properly
                    progress_dialog.is_complete = True
                    progress_dialog.accept()
                
                # Set up the custom state for the thumbnail browser
                self.thumbnail_browser.current_folder_id = None
                self.thumbnail_browser.current_search_query = None  # Not setting search query to avoid FTS5 query
                self.thumbnail_browser.selected_thumbnails.clear()
                
                # Clear the existing thumbnails
                self.thumbnail_browser.clear_thumbnails()
                
                # Set custom header
                self.thumbnail_browser.header_label.setText(f"Images by date between {date_range_text} ({len(results)} found)")
                
                if not results:
                    # No images found
                    empty_label = QLabel(f"No images found in date range: {date_range_text}")
                    empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.thumbnail_browser.grid_layout.addWidget(empty_label, 0, 0)
                else:
                    # Add thumbnails for results directly
                    self.thumbnail_browser.add_thumbnails(results)
                    
                # Update status bar
                self.status_bar.showMessage(f"Found {len(results)} images between {date_range_text}")
                
            except Exception as e:
                logger.error(f"Error handling date search results: {e}")
                if progress_dialog and progress_dialog.isVisible():
                    progress_dialog.close()
        
        def on_search_error(error_msg):
            try:
                logger.error(f"Date search error: {error_msg}")
                
                if progress_dialog and progress_dialog.isVisible():
                    progress_dialog.log_message(f"Error during search: {error_msg}")
                    progress_dialog.close_when_finished()
                
                # Show error in thumbnail browser
                self.thumbnail_browser.clear_thumbnails()
                self.thumbnail_browser.header_label.setText(f"Error searching for images: {error_msg}")
                
                # Update status bar
                self.status_bar.showMessage(f"Error during date search: {error_msg}")
                
            except Exception as e:
                logger.error(f"Error in date search error handler: {e}")
                if progress_dialog and progress_dialog.isVisible():
                    progress_dialog.close()
        
        def on_cancel():
            try:
                # Cancel the worker
                search_worker.cancel()
                self.status_bar.showMessage("Date search cancelled")
                self.thumbnail_browser.header_label.setText("Date search cancelled")
            except Exception as e:
                logger.error(f"Error cancelling date search: {e}")
        
        # Connect signals
        search_worker.signals.progress.connect(progress_callback)
        search_worker.signals.finished.connect(on_search_complete)
        search_worker.signals.error.connect(on_search_error)
        
        # Connect progress dialog's cancel signal to our handler
        # This ensures we handle cancellation requests properly
        if progress_dialog.cancellable:
            progress_dialog.cancelled.connect(on_cancel)
            
        # Ensure we can properly close the dialog regardless of state
        progress_dialog.setModal(False)  # Allow interaction with main window
        
        # Show progress dialog first so it's visible before starting the worker
        progress_dialog.show()
        
        # Process events to ensure dialog is fully displayed
        QApplication.processEvents()
        
        # Add additional logging
        logger.debug("Starting date search worker thread")
        
        # Start the worker
        self.threadpool.start(search_worker)
    
    def closeEvent(self, event):
        """Handle window close event.
        
        Args:
            event: Close event
        """
        try:
            # Stop any background tasks
            if hasattr(self, 'task_manager'):
                self.task_manager.cancel_all_tasks()
            
            # Hide the window instead of closing the application
            self.hide()
            event.ignore()
            
        except Exception as e:
            logger.error(f"Error in closeEvent: {e}")
            event.accept()
            
    def generate_descriptions_for_selected(self):
        """Generate AI descriptions for selected images."""
        # Get selected images
        selected_images = list(self.thumbnail_browser.selected_thumbnails)
        
        if not selected_images:
            self.notification_manager.show_notification(
                "No Images Selected",
                "Please select one or more images to generate descriptions."
            )
            return
        
        # Initialize batch processor if not already initialized
        if not hasattr(self, 'batch_processor'):
            from src.ai.batch_processor import BatchProcessor
            from src.ai.image_processor import AIImageProcessor
            
            # Create AI processor
            ai_processor = AIImageProcessor(self.db_manager)
            self.batch_processor = BatchProcessor(ai_processor, self.db_manager)
        
        # Create progress dialog
        progress_dialog = ProgressDialog("Generating Descriptions", "Preparing images...", parent=self)
        progress_dialog.setModal(True)
        progress_dialog.show()
        
        # Get image IDs
        image_ids = selected_images
        
        # Create worker
        worker = Worker(
            self.batch_processor.process_selected_images,
            image_ids=image_ids,
            progress_callback=lambda current, total, message: progress_dialog.update_progress(current, total, message)
        )
        
        def on_complete(result):
            # Close progress dialog
            progress_dialog.close()
            
            # Show completion notification
            if result.get("cancelled", False):
                self.notification_manager.show_notification(
                    "Operation Cancelled",
                    f"Processing cancelled. {result.get('processed', 0)} images processed."
                )
            else:
                self.notification_manager.show_notification(
                    "Generation Complete",
                    f"Processed: {result.get('processed', 0)}, " \
                    f"Failed: {result.get('failed', 0)}"
                )
            
            # Refresh the current view to show updated descriptions
            if hasattr(self, 'current_folder_id') and self.current_folder_id is not None:
                self.on_folder_selected(self.current_folder_id, None)
            else:
                self.search_all_images()
        
        def on_error(error):
            # Close progress dialog
            progress_dialog.close()
            
            # Show error notification
            self.notification_manager.show_notification(
                "Error Generating Descriptions",
                f"An error occurred: {str(error)}"
            )
        
        def on_cancel():
            # Cancel the batch processing
            self.batch_processor.cancel_processing()
            self.status_bar.showMessage("Cancelling batch processing...")
        
        # Connect signals - Fix: connect on_complete to result signal, not finished signal
        worker.signals.result.connect(on_complete)
        worker.signals.error.connect(on_error)
        
        # Connect cancel button
        if progress_dialog.cancel_button:
            progress_dialog.cancel_button.clicked.connect(on_cancel)
        
        # Start processing
        self.threadpool.start(worker)
        
    def generate_descriptions_for_folder(self):
        """Generate AI descriptions for all images in the current folder."""
        # Check if a folder is selected
        if not hasattr(self, 'current_folder_id') or self.current_folder_id is None:
            self.notification_manager.show_notification(
                "No Folder Selected",
                "Please select a folder to generate descriptions."
            )
            return
        
        # Ask if user wants to process all images or only those without descriptions
        process_all = self._confirm_process_all()
        if process_all is None:  # User cancelled
            return
        
        # Initialize batch processor if not already initialized
        if not hasattr(self, 'batch_processor'):
            from src.ai.batch_processor import BatchProcessor
            from src.ai.image_processor import AIImageProcessor
            
            # Create AI processor
            ai_processor = AIImageProcessor(self.db_manager)
            self.batch_processor = BatchProcessor(ai_processor, self.db_manager)
        
        # Create progress dialog
        progress_dialog = ProgressDialog("Generating Descriptions", "Preparing images...", parent=self)
        progress_dialog.setModal(True)
        progress_dialog.show()
        
        # Create worker
        worker = Worker(
            self.batch_processor.process_folder,
            folder_id=self.current_folder_id,
            process_all=process_all,
            progress_callback=lambda current, total, message: progress_dialog.update_progress(current, total, message)
        )
        
        def on_complete(result):
            # Close progress dialog
            progress_dialog.close()
            
            # Show completion notification
            if result.get("cancelled", False):
                self.notification_manager.show_notification(
                    "Operation Cancelled",
                    f"Processing cancelled. {result.get('processed', 0)} images processed."
                )
            else:
                self.notification_manager.show_notification(
                    "Generation Complete",
                    f"Processed: {result.get('processed', 0)}, " \
                    f"Failed: {result.get('failed', 0)}, " \
                    f"Skipped: {result.get('skipped', 0)}"
                )
            
            # Refresh the current view
            self.on_folder_selected(self.current_folder_id, None)
        
        def on_error(error):
            # Close progress dialog
            progress_dialog.close()
            
            # Show error notification
            self.notification_manager.show_notification(
                "Error Generating Descriptions",
                f"An error occurred: {str(error)}"
            )
        
        def on_cancel():
            # Cancel the batch processing
            self.batch_processor.cancel_processing()
            self.status_bar.showMessage("Cancelling batch processing...")
        
        # Connect signals - Fix: connect on_complete to result signal, not finished signal
        worker.signals.result.connect(on_complete)
        worker.signals.error.connect(on_error)
        
        # Connect cancel button
        if progress_dialog.cancel_button:
            progress_dialog.cancel_button.clicked.connect(on_cancel)
        
        # Start processing
        self.threadpool.start(worker)
    
    def _confirm_process_all(self):
        """Confirm whether to process all images or only those without descriptions.
        
        Returns:
            bool or None: True to process all, False to process only new, None if cancelled
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Generate Descriptions")
        msg_box.setText("Do you want to generate descriptions for all images or only images without descriptions?")
        
        # Add buttons
        all_button = msg_box.addButton("All Images", QMessageBox.ButtonRole.YesRole)
        new_button = msg_box.addButton("Only New Images", QMessageBox.ButtonRole.NoRole)
        msg_box.addButton(QMessageBox.StandardButton.Cancel)
        
        # Show dialog
        msg_box.exec()
        
        # Check which button was clicked
        clicked_button = msg_box.clickedButton()
        
        if clicked_button == all_button:
            return True
        elif clicked_button == new_button:
            return False
        else:
            return None
    
    def export_selected_images(self):
        """Export selected images to a folder with various format options."""
        # Get selected images
        selected_images = list(self.thumbnail_browser.selected_thumbnails)
        
        if not selected_images:
            self.notification_manager.show_notification(
                "No Images Selected",
                "Please select one or more images to export."
            )
            return
            
        # Get image information for all selected thumbnails
        image_ids = list(selected_images)
        images_to_export = []
        
        for image_id in image_ids:
            image_info = self.db_manager.get_image_by_id(image_id)
            if image_info and os.path.exists(image_info['full_path']):
                images_to_export.append(image_info)
        
        if not images_to_export:
            self.notification_manager.show_notification(
                "Export Failed",
                "No valid images selected for exporting.",
                NotificationType.ERROR
            )
            return
            
        # Show export options dialog
        from .export_dialog import ExportDialog
        export_dialog = ExportDialog(self, len(images_to_export))
        if export_dialog.exec() != QDialog.DialogCode.Accepted:
            return  # User cancelled
        
        # Get export options
        options = export_dialog.get_export_options()
        dest_folder = options['destination']
        export_format = options['format']
        include_description = options['include_description']
        description_only = options['description_only']
        
        # Create progress dialog
        from .progress_dialog import ProgressDialog
        progress_dialog = ProgressDialog(
            "Exporting Images",
            f"Exporting {len(images_to_export)} images to {dest_folder}...",
            self
        )
        
        # Define progress callback
        def progress_callback(current, total, message=None):
            progress_dialog.update_progress(current, total)
            if message:
                progress_dialog.update_operation(message)
            else:
                progress_dialog.update_operation(f"Exporting image {current} of {total}")
        
        # Define task completion callback
        def on_task_complete(results):
            # Update progress dialog
            progress_dialog.update_operation("Export operation complete")
            progress_dialog.log_message(f"Successfully exported: {results['success']} items")
            if results['failed'] > 0:
                progress_dialog.log_message(f"Failed to export: {results['failed']} items")
            
            # Enable close button
            progress_dialog.close_when_finished()
            
            # Show notification
            self.notification_manager.show_notification(
                "Export Complete",
                f"Successfully exported {results['success']} items\nFailed: {results['failed']}",
                NotificationType.SUCCESS if results['failed'] == 0 else NotificationType.WARNING
            )
        
        # Define error callback
        def on_task_error(error_info):
            progress_dialog.log_message(f"Error exporting images: {error_info[0]}")
            progress_dialog.close_when_finished()
            
            # Show error notification
            self.notification_manager.show_notification(
                "Export Error",
                f"Error: {error_info[0]}",
                NotificationType.ERROR
            )
        
        # Define cancel callback
        def on_cancel():
            progress_dialog.log_message("Export operation cancelled")
            self.notification_manager.show_notification(
                "Export Cancelled",
                "The export operation was cancelled.",
                NotificationType.INFO
            )
        
        # Show progress dialog
        progress_dialog.cancelled.connect(on_cancel)
        progress_dialog.show()
        
        # Define the export function to run in the background thread
        def export_images_task(images, destination, export_format, include_description, description_only, progress_callback=None):
            import shutil
            import os
            from PIL import Image
            
            results = {
                'success': 0,
                'failed': 0,
                'exported_files': []
            }
            
            total = len(images)
            
            for i, image in enumerate(images):
                try:
                    source_path = image['full_path']
                    filename = os.path.basename(source_path)
                    base_name, ext = os.path.splitext(filename)
                    
                    # Handle description-only export
                    if description_only:
                        # Get description
                        description = image.get('ai_description', '')
                        if not description:
                            description = image.get('user_description', '')
                        if not description:
                            description = "No description available for this image."
                        
                        # Create text file with description
                        txt_filename = f"{base_name}.txt"
                        txt_path = os.path.join(destination, txt_filename)
                        
                        # Handle duplicate filenames
                        counter = 1
                        while os.path.exists(txt_path):
                            txt_filename = f"{base_name}_{counter}.txt"
                            txt_path = os.path.join(destination, txt_filename)
                            counter += 1
                        
                        # Write description to file
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(description)
                        
                        results['success'] += 1
                        results['exported_files'].append(txt_path)
                        
                        # Update progress
                        if progress_callback:
                            progress_callback(i + 1, total, f"Exported description: {txt_filename}")
                            
                        continue  # Skip to next image
                    
                    # Handle image export
                    if export_format == 'original':
                        # Keep original format
                        dest_path = os.path.join(destination, filename)
                        
                        # Handle duplicate filenames
                        counter = 1
                        while os.path.exists(dest_path):
                            new_filename = f"{base_name}_{counter}{ext}"
                            dest_path = os.path.join(destination, new_filename)
                            counter += 1
                        
                        # Copy the file
                        shutil.copy2(source_path, dest_path)
                        results['exported_files'].append(dest_path)
                        
                    else:  # Convert to jpg or png
                        # Set new extension
                        new_ext = '.jpg' if export_format == 'jpg' else '.png'
                        new_filename = f"{base_name}{new_ext}"
                        dest_path = os.path.join(destination, new_filename)
                        
                        # Handle duplicate filenames
                        counter = 1
                        while os.path.exists(dest_path):
                            new_filename = f"{base_name}_{counter}{new_ext}"
                            dest_path = os.path.join(destination, new_filename)
                            counter += 1
                        
                        # Convert and save the image
                        with Image.open(source_path) as img:
                            if export_format == 'jpg':
                                # Convert to RGB for JPG (in case it's an RGBA image)
                                if img.mode == 'RGBA':
                                    img = img.convert('RGB')
                                img.save(dest_path, 'JPEG', quality=95)
                            else:  # PNG
                                img.save(dest_path, 'PNG')
                                
                        results['exported_files'].append(dest_path)
                    
                    # Handle description export if requested
                    if include_description:
                        # Get description
                        description = image.get('ai_description', '')
                        if not description:
                            description = image.get('user_description', '')
                        if not description:
                            description = "No description available for this image."
                        
                        # Create text file with description
                        txt_filename = f"{base_name}.txt"
                        txt_path = os.path.join(destination, txt_filename)
                        
                        # Handle duplicate filenames
                        counter = 1
                        while os.path.exists(txt_path):
                            txt_filename = f"{base_name}_{counter}.txt"
                            txt_path = os.path.join(destination, txt_filename)
                            counter += 1
                        
                        # Write description to file
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(description)
                        
                        results['exported_files'].append(txt_path)
                    
                    results['success'] += 1
                    
                    # Update progress
                    if progress_callback:
                        progress_callback(i + 1, total, f"Exported: {os.path.basename(source_path)}")
                        
                except Exception as e:
                    logger.error(f"Error exporting {image['filename']}: {str(e)}")
                    results['failed'] += 1
                    
                    # Update progress with error info
                    if progress_callback:
                        progress_callback(i + 1, total, f"Error exporting: {os.path.basename(source_path)}")
            
            return results
        
        # Start export operation in background thread
        self.task_manager.start_task(
            task_id=f"export_images_{id(self)}",
            fn=export_images_task,
            images=images_to_export,
            destination=dest_folder,
            export_format=export_format,
            include_description=include_description,
            description_only=description_only,
            progress_callback=progress_callback,
            on_result=on_task_complete,
            on_error=on_task_error
        )
    
    def rename_selected_images(self):
        """Rename selected images using a pattern."""
        # Get selected images
        selected_images = list(self.thumbnail_browser.selected_thumbnails)
        
        if not selected_images:
            self.notification_manager.show_notification(
                "No Images Selected",
                "Please select one or more images to rename."
            )
            return
        
        # TODO: Implement rename dialog and functionality
        self.notification_manager.show_notification(
            "Rename Feature",
            "This feature will be implemented in a future update."
        )
    
    # ===== Parallel Processing Batch Operations Methods =====
    
    def _connect_batch_operation_signals(self):
        """Connect signals from batch operations manager."""
        try:
            if not hasattr(self, 'batch_operations'):
                logger.warning("Batch operations manager not initialized")
                return
                
            # Connect signals
            self.batch_operations.signals.operation_started.connect(self._on_batch_operation_started)
            self.batch_operations.signals.operation_progress.connect(self._on_batch_operation_progress)
            self.batch_operations.signals.operation_completed.connect(self._on_batch_operation_completed)
            self.batch_operations.signals.operation_failed.connect(self._on_batch_operation_failed)
            self.batch_operations.signals.operation_cancelled.connect(self._on_batch_operation_cancelled)
            
            logger.debug("Batch operation signals connected")
        except Exception as e:
            logger.error(f"Error connecting batch operation signals: {e}")
    
    def _on_batch_operation_started(self, operation_id):
        """Handle batch operation started signal.
        
        Args:
            operation_id (str): Operation ID
        """
        logger.debug(f"Batch operation started: {operation_id}")
        self.status_bar.showMessage(f"Batch operation started: {operation_id}")
    
    def _on_batch_operation_progress(self, operation_id, current, total, message):
        """Handle batch operation progress signal.
        
        Args:
            operation_id (str): Operation ID
            current (int): Current progress
            total (int): Total operations
            message (str): Progress message
        """
        # Update status bar
        self.status_bar.showMessage(f"{message} - {current}/{total} ({int(current/total*100)}%)")
    
    def _on_batch_operation_completed(self, operation_id, results):
        """Handle batch operation completed signal.
        
        Args:
            operation_id (str): Operation ID
            results (dict): Operation results
        """
        logger.debug(f"Batch operation completed: {operation_id}")
        
        # Get operation type
        operation_type = results.get('operation_type', '')
        
        # Process results based on operation type
        if operation_type == 'ai_description':
            # Get stats
            total = results.get('total_tasks', 0)
            completed = results.get('completed_tasks', 0)
            failed = results.get('failed_tasks', 0)
            
            # Show notification
            self.notification_manager.show_notification(
                "AI Descriptions Generated",
                f"Successfully generated {completed} description(s)\n" \
                f"Failed: {failed}\n" \
                f"Total: {total}",
                NotificationType.SUCCESS if failed == 0 else NotificationType.WARNING
            )
            
            # Refresh the current view to show updated descriptions
            self.refresh_current_view()
        
        elif operation_type == 'thumbnail':
            # Get stats
            total = results.get('total_tasks', 0)
            completed = results.get('completed_tasks', 0)
            failed = results.get('failed_tasks', 0)
            
            # Show notification
            self.notification_manager.show_notification(
                "Thumbnails Generated",
                f"Successfully generated {completed} thumbnail(s)\n" \
                f"Failed: {failed}\n" \
                f"Total: {total}",
                NotificationType.SUCCESS if failed == 0 else NotificationType.WARNING
            )
            
            # Refresh thumbnails in the current view
            self.refresh_current_view()
        
        # Clear status bar
        self.status_bar.showMessage("Ready")
    
    def _on_batch_operation_failed(self, operation_id, error):
        """Handle batch operation failed signal.
        
        Args:
            operation_id (str): Operation ID
            error (str): Error message
        """
        logger.error(f"Batch operation failed: {operation_id} - {error}")
        
        # Show error notification
        self.notification_manager.show_notification(
            "Batch Operation Failed",
            f"Error: {error}",
            NotificationType.ERROR
        )
        
        # Clear status bar
        self.status_bar.showMessage("Ready")
    
    def _on_batch_operation_cancelled(self, operation_id):
        """Handle batch operation cancelled signal.
        
        Args:
            operation_id (str): Operation ID
        """
        logger.debug(f"Batch operation cancelled: {operation_id}")
        
        # Show notification
        self.notification_manager.show_notification(
            "Operation Cancelled",
            "The batch operation was cancelled.",
            NotificationType.INFO
        )
        
        # Clear status bar
        self.status_bar.showMessage("Ready")
    
    def _on_background_scan_started(self, folder_path):
        """Handle background scan started signal.
        
        Args:
            folder_path (str): Path of the folder being scanned
        """
        logger.info(f"Background scan started: {folder_path}")
        # For background scans, we don't need to show a progress dialog
        # Just update the status bar briefly
        self.status_bar.showMessage(f"Background scan started: {os.path.basename(folder_path)}")
    
    def _on_background_scan_completed(self, new_images_count, folders_scanned):
        """Handle background scan completed signal.
        
        Args:
            new_images_count (int): Number of new images found
            folders_scanned (int): Number of folders with new images
        """
        logger.info(f"Background scan completed: {new_images_count} new images in {folders_scanned} folders")
        
        # Only show a notification if new images were found
        if new_images_count > 0:
            self.notification_manager.show_notification(
                "New Images Found",
                f"Found {new_images_count} new image(s) in {folders_scanned} folder(s)",
                NotificationType.INFO
            )
            
            # Refresh the view if this is the current folder
            if hasattr(self, 'current_folder_id'):
                # Get folder ID for this path
                folder_info = next((f for f in self.db_manager.get_folders() 
                                   if f["path"] == folder_path), None)
                if folder_info and folder_info["folder_id"] == self.current_folder_id:
                    # Refresh view with a slight delay to ensure DB is updated
                    QApplication.processEvents()
                    self.refresh_current_view()
        
        # Reset status bar
        self.status_bar.showMessage("Ready")
    
    def _on_background_scan_error(self, folder_path, error_message):
        """Handle background scan error signal.
        
        Args:
            folder_path (str): Path of the folder that was being scanned
            error_message (str): Error message
        """
        logger.error(f"Background scan error in {folder_path}: {error_message}")
        
        # Only show a notification for significant errors, not just for individual file errors
        if "permission" in error_message.lower() or "access" in error_message.lower():
            self.notification_manager.show_notification(
                "Background Scan Error",
                f"Error scanning {os.path.basename(folder_path)}: {error_message}",
                NotificationType.ERROR
            )
        
        # Reset status bar
        self.status_bar.showMessage("Ready")
    
    def update_background_scanner_settings(self):
        """Update background scanner settings when configuration changes."""
        if hasattr(self, 'background_scanner'):
            self.background_scanner.update_settings()
            
    def on_empty_database(self):
        """Handle the Empty Database action.
        
        This will remove all images and folders from the database,
        but will not delete any files from disk.
        """
        # First confirmation dialog with warning message
        confirm_msg = (
            "WARNING: This will remove ALL images and folders from the database.\n\n"
            "This action cannot be undone.\n"
            "Your image files will remain on disk but all metadata and descriptions will be lost.\n\n"
            "Are you sure you want to empty the database?"
        )
        
        confirm = QMessageBox.warning(
            self, 
            "Empty Database Confirmation", 
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            self.status_bar.showMessage("Database emptying cancelled")
            return
            
        # Second confirmation with type-to-confirm pattern for extra safety
        confirm_text, ok = QInputDialog.getText(
            self,
            "Final Confirmation",
            "Type 'EMPTY' to confirm emptying the database:",
            QLineEdit.EchoMode.Normal
        )
        
        if not ok or confirm_text != "EMPTY":
            self.status_bar.showMessage("Database emptying cancelled")
            return
            
        # Show progress dialog
        progress_dialog = ProgressDialog(
            "Emptying Database", 
            "Removing all data from database...", 
            parent=self,
            cancellable=False
        )
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            # Set progress to 25%
            progress_dialog.update_progress(25, 100)
            QApplication.processEvents()
            
            # Windows-friendly approach: Use in-memory operations to avoid file locking issues
            try:
                # Create an in-memory database
                temp_conn = sqlite3.connect(':memory:')
                temp_cursor = temp_conn.cursor()
                
                # Create empty tables with the same schema
                temp_cursor.execute('''
                CREATE TABLE IF NOT EXISTS folders (
                    folder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    enabled INTEGER DEFAULT 1,
                    last_scan_time TEXT
                )''')
                
                temp_cursor.execute('''
                CREATE TABLE IF NOT EXISTS images (
                    image_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_id INTEGER,
                    filename TEXT NOT NULL,
                    full_path TEXT NOT NULL UNIQUE,
                    thumbnail_path TEXT,
                    ai_description TEXT,
                    user_description TEXT,
                    file_size INTEGER,
                    file_hash TEXT,
                    date_added TEXT,
                    date_modified TEXT,
                    width INTEGER,
                    height INTEGER,
                    image_format TEXT,
                    FOREIGN KEY (folder_id) REFERENCES folders(folder_id)
                )''')
                
                temp_cursor.execute('''
                CREATE TABLE IF NOT EXISTS catalogs (
                    catalog_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_date TEXT
                )''')
                
                temp_cursor.execute('''
                CREATE TABLE IF NOT EXISTS catalog_images (
                    catalog_id INTEGER,
                    image_id INTEGER,
                    added_date TEXT,
                    PRIMARY KEY (catalog_id, image_id),
                    FOREIGN KEY (catalog_id) REFERENCES catalogs(catalog_id),
                    FOREIGN KEY (image_id) REFERENCES images(image_id)
                )''')
                
                # Disconnect from existing database
                self.db_manager.disconnect()
                
                # Give time for connections to be released
                QApplication.processEvents()
                
                # Create a new connection to the database file
                db_path = self.db_manager.db_path
                
                # Make sure the directory exists
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                
                # Use vacuum into approach instead of delete/recreate
                new_conn = sqlite3.connect(db_path)
                temp_conn.backup(new_conn)
                new_conn.close()
                temp_conn.close()
                
                # Force database recreation by reconnecting
                self.db_manager = type(self.db_manager)(db_path)
                logger.info("Database emptied and recreated with fresh schema")
                
            except Exception as e:
                logger.error(f"Error recreating database: {e}")
                raise
            
            # Set progress to 75%
            progress_dialog.update_progress(75, 100)
            QApplication.processEvents()
            
            # Clear thumbnails folder
            thumbnails_dir = self.thumbnail_generator.thumbnail_dir
            if os.path.exists(thumbnails_dir):
                try:
                    # Remove thumbnail files
                    for file in os.listdir(thumbnails_dir):
                        if file.endswith(".jpg") or file.endswith(".png"):
                            os.unlink(os.path.join(thumbnails_dir, file))
                except Exception as e:
                    logger.error(f"Error clearing thumbnail directory: {e}")
            
            # Set progress to 100%
            progress_dialog.update_progress(100, 100, "Complete")
            QApplication.processEvents()
            
            # Force the progress dialog to close
            try:
                # First try the proper way using close_when_finished
                progress_dialog.close_when_finished()
                # Also force the dialog to close if it's still visible after a short delay
                QTimer.singleShot(1000, progress_dialog.accept)
            except Exception as dialog_err:
                logger.error(f"Error closing dialog: {dialog_err}")
                try:
                    # Fallback to direct close if the dialog is still visible
                    progress_dialog.accept()
                except:
                    pass
            
            # Clear UI
            try:
                # Use refresh_folders instead of refresh if it exists
                if hasattr(self.folder_panel, 'refresh_folders'):
                    self.folder_panel.refresh_folders()
                elif hasattr(self.folder_panel, 'refresh'):
                    self.folder_panel.refresh()
                
                # Clear the thumbnail browser
                self.thumbnail_browser.clear_thumbnails()
                
                # Update header
                self.thumbnail_browser.header_label.setText("Database Emptied")
            except Exception as ui_err:
                logger.warning(f"Non-critical UI update error: {ui_err}")
            
            # Show success message
            self.notification_manager.show_notification(
                "Database Emptied",
                "All images and folders have been removed from the database.",
                NotificationType.INFO
            )
            self.status_bar.showMessage("Database has been emptied successfully")
            
        except Exception as e:
            # Make sure progress dialog closes properly in error cases
            try:
                # Try proper close with finished state
                progress_dialog.close_when_finished()
                # Also force accept after a delay if needed
                QTimer.singleShot(1000, progress_dialog.accept)
            except Exception as dialog_err:
                logger.error(f"Error closing dialog in exception handler: {dialog_err}")
                try:
                    # Fallback to direct close/accept
                    progress_dialog.accept()
                except:
                    # Last resort close if accept fails
                    progress_dialog.close()
            
            # Show error message
            logger.error(f"Error emptying database: {e}")
            error_msg = f"An error occurred while emptying the database:\n{str(e)}"
            
            QMessageBox.critical(
                self, 
                "Error", 
                error_msg,
                QMessageBox.StandardButton.Ok
            )
            
            self.status_bar.showMessage("Error emptying database")
        
    def on_export_database(self):
        """Handle the Export Database action.
        
        Exports the database to a file selected by the user.
        Optionally includes thumbnails as a ZIP file.
        """
        # Ask user if they want to include thumbnails
        include_thumbnails_msg = QMessageBox(
            QMessageBox.Icon.Question,
            "Export Options",
            "Would you like to include thumbnails in the export?\n\n" +
            "This will create a ZIP file with the same name as the database export.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self
        )
        
        include_thumbnails_msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        include_thumbnails = include_thumbnails_msg.exec() == QMessageBox.StandardButton.Yes
        
        # Show file dialog to select export location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Database",
            os.path.expanduser("~"),
            "SQLite Database Files (*.db);;All Files (*)"
        )
        
        if not file_path:
            return  # User cancelled
            
        # Create progress dialog
        progress_dialog = ProgressDialog(
            "Exporting Database",
            "Preparing to export database...",
            parent=self,
            cancellable=False
        )
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            # Update progress
            progress_dialog.update_progress(20, 100, "Preparing database for export...")
            QApplication.processEvents()
            
            # Get database size
            source_size = os.path.getsize(self.db_manager.db_path)
            size_formatted = self._format_file_size(source_size)
            
            # Update progress
            progress_dialog.update_progress(40, 100, "Copying database file...")
            QApplication.processEvents()
            
            # Copy the database file
            import shutil
            shutil.copy2(self.db_manager.db_path, file_path)
            
            # Export thumbnails if requested
            thumbnails_exported = False
            thumbnails_size = 0
            if include_thumbnails:
                # Update progress
                progress_dialog.update_progress(60, 100, "Exporting thumbnails...")
                QApplication.processEvents()
                
                # Create ZIP file with thumbnails
                import zipfile
                import glob
                
                # Create ZIP file with same name as database but .zip extension
                zip_path = os.path.splitext(file_path)[0] + ".zip"
                
                # Get the correct thumbnails directory path
                # Use the same directory structure as in the import function
                if getattr(sys, 'frozen', False):
                    # Portable mode - use directory next to executable
                    exe_dir = os.path.dirname(sys.executable)
                    app_thumbnails_dir = os.path.join(exe_dir, "data", "thumbnails")
                else:
                    # Script mode - use directory relative to database
                    db_dir = os.path.dirname(self.db_manager.db_path)
                    app_dir = os.path.dirname(os.path.dirname(self.db_manager.db_path))
                    app_thumbnails_dir = os.path.join(app_dir, "data", "thumbnails")
                    
                    # If that doesn't exist, try alternative paths
                    if not os.path.exists(app_thumbnails_dir) or not os.path.isdir(app_thumbnails_dir):
                        # Try without the data subdirectory
                        app_thumbnails_dir = os.path.join(app_dir, "thumbnails")
                        
                    if not os.path.exists(app_thumbnails_dir) or not os.path.isdir(app_thumbnails_dir):
                        # Try in the database directory
                        app_thumbnails_dir = os.path.join(db_dir, "thumbnails")
                
                # Log the paths we're checking
                logger.info(f"Looking for thumbnails in: {app_thumbnails_dir}")
                
                # Initialize variables
                thumbnail_count = 0
                thumbnail_files = []
                thumbnails_found = False
                
                # Check if thumbnails directory exists
                if os.path.exists(app_thumbnails_dir) and os.path.isdir(app_thumbnails_dir):
                    # Log that we found the thumbnails directory
                    logger.info(f"Found thumbnails directory: {app_thumbnails_dir}")
                    
                    # Check if there are any thumbnail files
                    thumbnail_files = glob.glob(os.path.join(app_thumbnails_dir, "*.*"))
                    total_files = len(thumbnail_files)
                    
                    if total_files == 0:
                        logger.warning(f"No thumbnail files found in {app_thumbnails_dir}")
                        progress_dialog.update_progress(70, 100, "No thumbnail files found. Creating empty ZIP...")
                        QApplication.processEvents()
                    else:
                        logger.info(f"Found {total_files} thumbnail files to export")
                        thumbnails_found = True
                else:
                    # Thumbnails directory not found
                    logger.warning(f"Thumbnails directory not found at {app_thumbnails_dir}")
                    progress_dialog.update_progress(70, 100, "Thumbnails directory not found. Creating empty ZIP...")
                    QApplication.processEvents()
                    total_files = 0
                
                # Always create the ZIP file, even if empty
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    logger.info(f"Creating ZIP file at: {zip_path}")
                    
                    # Add a README file to the ZIP if no thumbnails found
                    if not thumbnails_found:
                        readme_content = "This ZIP file is part of the database export but contains no thumbnails.\n"
                        zipf.writestr("README.txt", readme_content)
                        logger.info("Added README.txt to empty ZIP file")
                    
                    # Add thumbnails if found
                    if thumbnails_found:
                        logger.info(f"Exporting {total_files} thumbnails to {zip_path}")
                        
                        for i, file in enumerate(thumbnail_files):
                            # Update progress periodically
                            if i % 100 == 0:
                                progress_percent = 60 + min(20, int((i / total_files) * 20))
                                progress_dialog.update_progress(
                                    progress_percent, 100,
                                    f"Adding thumbnails to export ({i}/{total_files})..."
                                )
                                QApplication.processEvents()
                            
                            try:
                                # Get just the filename without path
                                filename = os.path.basename(file)
                                # Add file to ZIP with path inside 'thumbnails' directory
                                zipf.write(file, f"thumbnails/{filename}")
                                thumbnail_count += 1
                                
                                # Log every 1000 files
                                if thumbnail_count % 1000 == 0:
                                    logger.debug(f"Added {thumbnail_count} thumbnails to ZIP")
                                    
                            except Exception as e:
                                logger.error(f"Error adding thumbnail to ZIP: {file} - {e}")
                    
                    # Verify the ZIP file was created
                    if os.path.exists(zip_path):
                        thumbnails_exported = True
                        thumbnails_size = os.path.getsize(zip_path)
                        logger.info(f"Successfully created thumbnails ZIP file: {zip_path}, size: {self._format_file_size(thumbnails_size)}")
                    else:
                        thumbnails_exported = False
                        thumbnails_size = 0
                        logger.error(f"Failed to create thumbnails ZIP file: {zip_path}")
            
            # Update progress
            progress_dialog.update_progress(80, 100, "Verifying export...")
            QApplication.processEvents()
            
            # Verify export was successful
            if not os.path.exists(file_path):
                raise Exception("Export file not found after export operation")
            
            # Get exported file size
            dest_size = os.path.getsize(file_path)
            if dest_size != source_size:
                raise Exception(f"Export file size mismatch: {dest_size} != {source_size}")
            
            # Update progress
            progress_dialog.update_progress(100, 100, "Export completed successfully")
            QApplication.processEvents()
            
            # Close progress dialog properly
            progress_dialog.close_when_finished()
            
            # Show success message with thumbnail info if applicable
            success_msg = f"Database was successfully exported to:\n{file_path}\nSize: {size_formatted}"
            if thumbnails_exported:
                thumbnails_size_formatted = self._format_file_size(thumbnails_size)
                success_msg += f"\n\nThumbnails were exported to:\n{zip_path}\nSize: {thumbnails_size_formatted}"
            
            self.notification_manager.show_notification(
                "Database Export Complete",
                success_msg,
                NotificationType.SUCCESS
            )
            
            if thumbnails_exported:
                self.status_bar.showMessage(f"Database and thumbnails exported successfully")
            else:
                self.status_bar.showMessage(f"Database exported to: {file_path}")
            
        except Exception as e:
            # Close progress dialog properly
            progress_dialog.close_when_finished()
            
            # Show error message
            logger.error(f"Error exporting database: {e}")
            error_msg = f"An error occurred while exporting the database:\n{str(e)}"
            
            QMessageBox.critical(
                self, 
                "Error", 
                error_msg,
                QMessageBox.StandardButton.Ok
            )
            
            self.status_bar.showMessage("Error exporting database")
    
    def on_import_database(self):
        """Handle the Import Database action.
        
        Imports a database from a file selected by the user.
        If the target database already contains data, the imported data will be merged.
        Also checks for and optionally imports thumbnails from a ZIP file if available.
        """
        # Show file dialog to select import file
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Database",
            os.path.expanduser("~"),
            "SQLite Database Files (*.db);;All Files (*)"
        )
        
        if not file_path:
            return  # User cancelled
        
        # Check if the file exists
        if not os.path.exists(file_path):
            QMessageBox.critical(
                self,
                "Error",
                f"The selected file does not exist: {file_path}",
                QMessageBox.StandardButton.Ok
            )
            return
            
        # Check if a corresponding thumbnail ZIP file exists
        thumbnail_zip_path = os.path.splitext(file_path)[0] + ".zip"
        has_thumbnail_zip = os.path.exists(thumbnail_zip_path)
        
        # Show confirmation dialog with options
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QLabel, QDialogButtonBox, QCheckBox, QGroupBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Import Options")
        dialog.setMinimumWidth(450)
        
        layout = QVBoxLayout(dialog)
        
        # Add description label
        layout.addWidget(QLabel("Select how to handle the imported database:"))
        
        # Create group box for database options
        db_group = QGroupBox("Database Import Options")
        db_layout = QVBoxLayout(db_group)
        
        # Add option radio buttons
        merge_option = QRadioButton("Merge with existing database (add new images and folders)")
        replace_option = QRadioButton("Replace existing database (this will remove all current data)")
        
        # Set replace as default
        replace_option.setChecked(True)
        
        db_layout.addWidget(merge_option)
        db_layout.addWidget(replace_option)
        
        # Add warning label for replace option
        warning_label = QLabel("Warning: Replacing the database will remove all current data!")
        warning_label.setStyleSheet("color: red;")
        db_layout.addWidget(warning_label)
        
        layout.addWidget(db_group)
        
        # Add thumbnail import option if a ZIP file exists
        import_thumbnails_checkbox = None
        if has_thumbnail_zip:
            thumb_group = QGroupBox("Thumbnail Options")
            thumb_layout = QVBoxLayout(thumb_group)
            
            # Create radio buttons for thumbnail options to match the database options style
            import_thumbnails_option = QRadioButton("Import thumbnails from the associated ZIP file")
            skip_thumbnails_option = QRadioButton("Skip importing thumbnails")
            
            # Set import as default
            import_thumbnails_option.setChecked(True)
            
            # Add to layout
            thumb_layout.addWidget(import_thumbnails_option)
            thumb_layout.addWidget(skip_thumbnails_option)
            
            # Add information about the ZIP file
            import zipfile
            try:
                with zipfile.ZipFile(thumbnail_zip_path, 'r') as zipf:
                    thumbnail_count = len(zipf.namelist())
                    thumb_info_label = QLabel(f"Found {thumbnail_count} thumbnails in:\n{thumbnail_zip_path}")
                    thumb_layout.addWidget(thumb_info_label)
            except Exception as e:
                thumb_error_label = QLabel(f"Error reading the thumbnail ZIP file: {str(e)}")
                thumb_error_label.setStyleSheet("color: red;")
                thumb_layout.addWidget(thumb_error_label)
                import_thumbnails_option.setChecked(False)
                skip_thumbnails_option.setChecked(True)
                import_thumbnails_option.setEnabled(False)
            
            layout.addWidget(thumb_group)
        
        # Add button box
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                    QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Show dialog
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return  # User cancelled
        
        # Get selected options
        import_mode = "merge" if merge_option.isChecked() else "replace"
        import_thumbnails = has_thumbnail_zip and import_thumbnails_option and import_thumbnails_option.isChecked()
        
        # Additional confirmation for replace mode
        if import_mode == "replace":
            confirm = QMessageBox.warning(
                self,
                "Confirm Replace",
                "This will REPLACE your entire database with the imported one.\n\n"
                "All existing data will be lost.\n\n"
                "Are you sure you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if confirm != QMessageBox.StandardButton.Yes:
                self.status_bar.showMessage("Database import cancelled")
                return
        
        # Create progress dialog
        progress_dialog = ProgressDialog(
            "Importing Database",
            f"Preparing to import database in {import_mode} mode...",
            parent=self,
            cancellable=False
        )
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            import sqlite3
            
            # Verify it's a valid SQLite database
            progress_dialog.update_progress(10, 100, "Validating import database...")
            QApplication.processEvents()
            
            try:
                # Attempt to open the database
                conn = sqlite3.connect(file_path)
                cursor = conn.cursor()
                
                # Check if it has the required tables
                tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
                tables = [row[0] for row in cursor.execute(tables_query).fetchall()]
                
                required_tables = ['folders', 'images']
                missing_tables = [table for table in required_tables if table not in tables]
                
                if missing_tables:
                    conn.close()
                    raise Exception(f"Invalid database format. Missing tables: {', '.join(missing_tables)}")
                
                # Get folder and image counts from import file
                folder_count = cursor.execute("SELECT COUNT(*) FROM folders").fetchone()[0]
                image_count = cursor.execute("SELECT COUNT(*) FROM images").fetchone()[0]
                
                # Close the connection as we'll use the upgrade function
                conn.close()
                
                # Ensure the source database has the required schema
                # This will add any missing columns and tables
                progress_dialog.update_progress(15, 100, "Upgrading import database schema if needed...")
                QApplication.processEvents()
                
                from src.database.db_upgrade import upgrade_database_schema
                success, message = upgrade_database_schema(file_path)
                if not success:
                    raise Exception(f"Failed to upgrade import database: {message}")
                    
                logger.info(f"Import database schema check: {message}")
                
            except sqlite3.Error as e:
                raise Exception(f"Invalid SQLite database: {str(e)}")
            
            # Handle different import modes
            if import_mode == "replace":
                # Update progress
                progress_dialog.update_progress(25, 100, f"Replacing database with {folder_count} folders and {image_count} images...")
                QApplication.processEvents()
                
                # Create a backup of the current database
                import shutil
                backup_path = self.db_manager.db_path + ".backup"
                shutil.copy2(self.db_manager.db_path, backup_path)
                
                progress_dialog.update_progress(50, 100, "Preparing database for replacement...")
                QApplication.processEvents()
                
                # First disconnect from the database
                self.db_manager.disconnect()
                
                try:
                    # Copy the import file over the existing database
                    shutil.copy2(file_path, self.db_manager.db_path)
                    
                    # Update progress
                    progress_dialog.update_progress(75, 100, "Reconnecting to database...")
                    QApplication.processEvents()
                    
                    # Reconnect to the database
                    self.db_manager.connect()
                    
                    # Update progress
                    progress_dialog.update_progress(90, 100, "Finalizing database replacement...")
                    QApplication.processEvents()
                    
                    # Remove backup if everything was successful
                    try:
                        os.remove(backup_path)
                    except Exception:
                        # Not critical if this fails
                        pass
                    
                    # Update progress
                    progress_dialog.update_progress(90, 100, "Database import completed")
                    QApplication.processEvents()
                    
                    # Import thumbnails if requested
                    thumbnails_imported = False
                    if import_thumbnails:
                        try:
                            progress_dialog.update_progress(92, 100, "Importing thumbnails...")
                            QApplication.processEvents()
                            
                            import zipfile
                            import shutil
                            
                            # CRITICAL FIX: Always use the /data/thumbnails directory structure for both portable and script modes
                            if getattr(sys, 'frozen', False):
                                # Portable mode - use directory next to executable
                                exe_dir = os.path.dirname(sys.executable)
                                thumbnails_dir = os.path.join(exe_dir, "data", "thumbnails")
                            else:
                                # Script mode - use directory relative to database
                                app_dir = os.path.dirname(os.path.dirname(self.db_manager.db_path))
                                thumbnails_dir = os.path.join(app_dir, "data", "thumbnails")
                            
                            # Create thumbnails directory if it doesn't exist
                            os.makedirs(thumbnails_dir, exist_ok=True)
                            
                            logger.info(f"Importing thumbnails to: {thumbnails_dir}")
                            
                            # Extract the ZIP file
                            with zipfile.ZipFile(thumbnail_zip_path, 'r') as zipf:
                                # Get list of files to extract
                                file_list = zipf.namelist()
                                total_files = len(file_list)
                                
                                # Extract files
                                for i, file in enumerate(file_list):
                                    # Update progress periodically
                                    if i % 100 == 0:
                                        progress_percent = 92 + min(7, int((i / total_files) * 7))
                                        progress_dialog.update_progress(
                                            progress_percent, 100,
                                            f"Extracting thumbnails ({i}/{total_files})..."
                                        )
                                        QApplication.processEvents()
                                    
                                    # Debugging to see what files are being extracted
                                    logger.debug(f"Extracting thumbnail file: {file}")
                                    
                                    # Extract file to thumbnails directory
                                    # Get the basename regardless of path structure
                                    filename = os.path.basename(file)
                                    target_path = os.path.join(thumbnails_dir, filename)
                                    
                                    try:
                                        # First, extract the file to a temporary buffer
                                        content = zipf.read(file)
                                        
                                        # Write the content directly to the target path
                                        with open(target_path, 'wb') as f:
                                            f.write(content)
                                        
                                        logger.debug(f"Successfully extracted {filename} to {target_path}")
                                    except Exception as e:
                                        logger.error(f"Error extracting {file}: {e}")
                                        # Try the old extraction method as fallback
                                        try:
                                            # Handle different path formats in ZIP
                                            if '/' in file or '\\' in file:
                                                # For files in subdirectories, we need to extract the file structure
                                                # and then copy the file to the thumbnails directory
                                                
                                                # Create a temporary extraction directory
                                                temp_path = os.path.join(os.path.dirname(thumbnails_dir), "temp_extract")
                                                os.makedirs(temp_path, exist_ok=True)
                                                
                                                # Extract the file to the temp directory
                                                zipf.extract(file, temp_path)
                                                
                                                # Find the extracted file
                                                extracted_file = os.path.join(temp_path, file)
                                                
                                                # Check if the file was extracted successfully
                                                if os.path.exists(extracted_file):
                                                    # Copy to final destination
                                                    shutil.copy2(extracted_file, target_path)
                                                    logger.debug(f"Copied extracted file from {extracted_file} to {target_path}")
                                                else:
                                                    # Try to find the file with normalized path
                                                    normalized_path = os.path.normpath(file)
                                                    extracted_file = os.path.join(temp_path, normalized_path)
                                                    if os.path.exists(extracted_file):
                                                        shutil.copy2(extracted_file, target_path)
                                                        logger.debug(f"Copied extracted file from normalized path {extracted_file} to {target_path}")
                                                    else:
                                                        logger.error(f"Extracted file not found at {extracted_file}")
                                            else:
                                                # Direct extraction to thumbnails directory
                                                zipf.extract(file, thumbnails_dir)
                                                logger.debug(f"Directly extracted {file} to {thumbnails_dir}")
                                                
                                        except Exception as e2:
                                            logger.error(f"Fallback extraction also failed for {file}: {e2}")
                            
                            thumbnails_imported = True
                        except Exception as e:
                            logger.error(f"Error importing thumbnails: {e}")
                    
                    # Update progress
                    progress_dialog.update_progress(100, 100, "Database import completed successfully")
                    QApplication.processEvents()
                    
                    # Close progress dialog properly
                    progress_dialog.close_when_finished()
                    
                    # Clear and update UI
                    self.folder_panel.refresh_folders()
                    self.thumbnail_browser.clear_thumbnails()
                    
                    # Show success message
                    success_msg = f"Successfully replaced database with {folder_count} folders and {image_count} images."
                    if thumbnails_imported:
                        success_msg += "\n\nThumbnails were successfully imported."
                    
                    self.notification_manager.show_notification(
                        "Database Import Complete",
                        success_msg,
                        NotificationType.SUCCESS
                    )
                    
                    if thumbnails_imported:
                        self.status_bar.showMessage("Database and thumbnails have been successfully replaced")
                    else:
                        self.status_bar.showMessage("Database has been successfully replaced")
                    
                except Exception as e:
                    # Restore from backup if copy fails
                    try:
                        shutil.copy2(backup_path, self.db_manager.db_path)
                        self.db_manager.connect()
                    except Exception:
                        pass
                        
                    raise Exception(f"Failed to replace database: {str(e)}")
                
            else:  # merge mode
                # Update progress
                progress_dialog.update_progress(20, 100, f"Preparing to merge {folder_count} folders and {image_count} images...")
                QApplication.processEvents()
                
                # Connect to both databases
                source_conn = sqlite3.connect(file_path)
                source_conn.row_factory = sqlite3.Row
                source_cursor = source_conn.cursor()
                
                # Get existing folders from target database
                existing_folders = {folder['path']: folder for folder in self.db_manager.get_folders(enabled_only=False)}
                
                # Import folders
                progress_dialog.update_progress(30, 100, "Importing folders...")
                QApplication.processEvents()
                
                added_folders = 0
                folder_id_mapping = {}
                
                for row in source_cursor.execute("SELECT * FROM folders").fetchall():
                    folder = dict(row)
                    
                    # Skip if folder already exists
                    if folder['path'] in existing_folders:
                        # Map the source folder_id to the existing folder_id for image import
                        folder_id_mapping[folder['folder_id']] = existing_folders[folder['path']]['folder_id']
                        continue
                    
                    # Add folder to target database
                    try:
                        new_folder_id = self.db_manager.add_folder(folder['path'])
                        if new_folder_id:
                            # Map the source folder_id to the new folder_id for image import
                            folder_id_mapping[folder['folder_id']] = new_folder_id
                            added_folders += 1
                    except Exception as e:
                        logger.error(f"Error importing folder {folder['path']}: {e}")
                
                # Get existing images from target database
                progress_dialog.update_progress(40, 100, "Preparing to import images...")
                QApplication.processEvents()
                
                # Build a mapping of existing images: full_path -> set of file_hashes
                existing_hashes = dict()  # full_path -> set of hashes
                for folder_id in folder_id_mapping.values():
                    images = self.db_manager.get_images_for_folder(folder_id, limit=1000000)
                    for img in images:
                        if img['full_path'] not in existing_hashes:
                            existing_hashes[img['full_path']] = set()
                        if img.get('file_hash'):
                            existing_hashes[img['full_path']].add(img['file_hash'])
                
                # Import images
                progress_dialog.update_progress(50, 100, "Importing images...")
                QApplication.processEvents()
                
                added_images = 0
                skipped_images = 0
                total_images = source_cursor.execute("SELECT COUNT(*) FROM images").fetchone()[0]
                
                for i, row in enumerate(source_cursor.execute("SELECT * FROM images").fetchall()):
                    image = dict(row)
                    
                    # Update progress periodically
                    if i % 100 == 0:
                        progress_percent = 50 + min(40, int((i / total_images) * 40))
                        progress_dialog.update_progress(progress_percent, 100, f"Imported {added_images} of {total_images} images...")
                        QApplication.processEvents()
                    
                    # Skip if image with same full_path AND file_hash already exists in target
                    if image['full_path'] in existing_hashes and image.get('file_hash') in existing_hashes[image['full_path']]:
                        skipped_images += 1
                        continue
                    
                    # Get the new folder ID if the folder was mapped
                    if image['folder_id'] not in folder_id_mapping:
                        # Skip images for folders that weren't imported/mapped
                        skipped_images += 1
                        continue
                    
                    new_folder_id = folder_id_mapping[image['folder_id']]
                    
                    # Add image to target database
                    try:
                        # Only import images if the file exists
                        if not os.path.exists(image['full_path']):
                            continue
                        
                        # Determine thumbnail_path for merge:
                        thumbnail_path = image.get('thumbnail_path')
                        if thumbnail_path:
                            # Check if thumbnail file exists (either already present or will be imported from ZIP)
                            if getattr(sys, 'frozen', False):
                                exe_dir = os.path.dirname(sys.executable)
                                thumbnails_dir = os.path.join(exe_dir, "data", "thumbnails")
                            else:
                                app_dir = os.path.dirname(os.path.dirname(self.db_manager.db_path))
                                thumbnails_dir = os.path.join(app_dir, "data", "thumbnails")
                            thumbnail_file_path = os.path.join(thumbnails_dir, thumbnail_path)
                            if not os.path.exists(thumbnail_file_path):
                                # If the file does not exist now but will be imported from ZIP, allow it
                                if not import_thumbnails:
                                    thumbnail_path = None
                        else:
                            thumbnail_path = None

                        self.db_manager.add_image(
                            folder_id=new_folder_id,
                            filename=image['filename'],
                            full_path=image['full_path'],
                            file_size=image['file_size'],
                            file_hash=image.get('file_hash'),
                            thumbnail_path=thumbnail_path,
                            ai_description=image.get('ai_description')
                        )

                        # Update user description if present
                        if image.get('user_description'):
                            new_images = self.db_manager.get_images_for_folder(new_folder_id, limit=1)
                            for new_img in new_images:
                                if new_img['full_path'] == image['full_path']:
                                    self.db_manager.update_image_description(
                                        new_img['image_id'],
                                        user_description=image.get('user_description')
                                    )
                                    break
                        
                        added_images += 1
                            
                    except Exception as e:
                        logger.error(f"Error importing image {image['full_path']}: {e}")
                        skipped_images += 1
                
                # Close source connection
                source_conn.close()
                
                # Import thumbnails if requested
                thumbnails_imported = False
                if import_thumbnails:
                    try:
                        progress_dialog.update_progress(90, 100, "Importing thumbnails...")
                        QApplication.processEvents()
                        
                        import zipfile
                        import shutil
                        
                        # CRITICAL FIX: Always use the /data/thumbnails directory structure for both portable and script modes
                        if getattr(sys, 'frozen', False):
                            # Portable mode - use directory next to executable
                            exe_dir = os.path.dirname(sys.executable)
                            thumbnails_dir = os.path.join(exe_dir, "data", "thumbnails")
                        else:
                            # Script mode - use directory relative to database
                            app_dir = os.path.dirname(os.path.dirname(self.db_manager.db_path))
                            thumbnails_dir = os.path.join(app_dir, "data", "thumbnails")
                        
                        # Create thumbnails directory if it doesn't exist
                        os.makedirs(thumbnails_dir, exist_ok=True)
                        
                        logger.info(f"Importing thumbnails to: {thumbnails_dir}")
                        
                        # Extract the ZIP file
                        with zipfile.ZipFile(thumbnail_zip_path, 'r') as zipf:
                            # Get list of files to extract
                            file_list = zipf.namelist()
                            total_files = len(file_list)
                            
                            # Extract files
                            for i, file in enumerate(file_list):
                                # Update progress periodically
                                if i % 100 == 0:
                                    progress_percent = 90 + min(5, int((i / total_files) * 5))
                                    progress_dialog.update_progress(
                                        progress_percent, 100,
                                        f"Extracting thumbnails ({i}/{total_files})..."
                                    )
                                    QApplication.processEvents()
                                
                                # Debugging to see what files are being extracted
                                logger.debug(f"Extracting thumbnail file: {file}")
                                
                                # Extract file to thumbnails directory
                                # Get the basename regardless of path structure
                                filename = os.path.basename(file)
                                target_path = os.path.join(thumbnails_dir, filename)
                                
                                try:
                                    # First, extract the file to a temporary buffer
                                    content = zipf.read(file)
                                    
                                    # Write the content directly to the target path
                                    with open(target_path, 'wb') as f:
                                        f.write(content)
                                    
                                    logger.debug(f"Successfully extracted {filename} to {target_path}")
                                except Exception as e:
                                    logger.error(f"Error extracting {file}: {e}")
                                    # Try the old extraction method as fallback
                                    try:
                                        if '/' in file or '\\' in file:
                                            # Extract to parent directory first
                                            temp_path = os.path.join(os.path.dirname(thumbnails_dir), "temp_extract")
                                            os.makedirs(temp_path, exist_ok=True)
                                            zipf.extract(file, temp_path)
                                            
                                            # Move the file to final destination
                                            extracted_file = os.path.join(temp_path, file)
                                            if os.path.exists(extracted_file):
                                                shutil.copy2(extracted_file, target_path)
                                        else:
                                            # Direct extraction to thumbnails directory
                                            zipf.extract(file, thumbnails_dir)
                                    except Exception as e2:
                                        logger.error(f"Fallback extraction also failed for {file}: {e2}")
                        
                        thumbnails_imported = True
                        
                        # Update the database to link images to their thumbnails
                        try:
                            progress_dialog.update_progress(97, 100, "Updating thumbnail paths in database...")
                            QApplication.processEvents()
                            
                            # For both replace and merge modes, we need to update the thumbnail paths
                            # Get a list of all images in the database
                            all_images = []
                            for folder in self.db_manager.get_folders():
                                images = self.db_manager.get_images_for_folder(folder['folder_id'])
                                all_images.extend(images)
                            
                            # Connect to database directly for bulk update
                            conn = sqlite3.connect(self.db_manager.db_path)
                            cursor = conn.cursor()
                            
                            update_count = 0
                            for image in all_images:
                                # Only process images that don't have a thumbnail yet
                                if not image.get('thumbnail_path'):
                                    # Use the filename hash as the thumbnail filename
                                    filename = image['filename']
                                    # Get just the filename without path
                                    base_filename = os.path.basename(filename)
                                    # Calculate hash for the filename to match the thumbnail naming convention
                                    import hashlib
                                    filename_hash = hashlib.md5(base_filename.encode()).hexdigest()
                                    thumbnail_filename = f"{filename_hash}.jpg"
                                    
                                    # Check if this thumbnail exists in the extracted files
                                    thumbnail_path = os.path.join(thumbnails_dir, thumbnail_filename)
                                    if os.path.exists(thumbnail_path):
                                        # Update the database with the thumbnail path
                                        cursor.execute(
                                            "UPDATE images SET thumbnail_path = ? WHERE image_id = ?", 
                                            (thumbnail_filename, image['image_id'])
                                        )
                                        update_count += 1
                            
                            conn.commit()
                            conn.close()
                            
                            logger.info(f"Updated {update_count} thumbnail paths in database")
                        except Exception as e:
                            logger.error(f"Error updating thumbnail paths: {e}")
                    except Exception as e:
                        logger.error(f"Error importing thumbnails: {e}")
                
                # Update progress
                progress_dialog.update_progress(95, 100, "Finalizing database import...")
                QApplication.processEvents()
                
                # Optimize database after import
                from src.database.db_optimizer import DatabaseOptimizer
                optimizer = DatabaseOptimizer(self.db_manager)
                optimizer.optimize_database()
                
                # Upgrade database schema if needed
                from src.database.db_upgrade import upgrade_database_schema
                success, message = upgrade_database_schema(self.db_manager.db_path)
                if success:
                    logger.info(f"Target database schema check: {message}")
                else:
                    logger.warning(f"Failed to upgrade target database: {message}")
                
                # Update progress
                progress_dialog.update_progress(100, 100, "Import completed successfully")
                QApplication.processEvents()
                
                # Close progress dialog properly
                progress_dialog.close_when_finished()
                
                # Refresh UI with updated counts
                self.update_ui_counts()
                self.refresh_current_view()
                
                # Show success message with thumbnail info if applicable
                success_msg = f"Successfully merged database with {added_folders} new folders and {added_images} new images.\n"
                success_msg += f"Skipped: {skipped_images} duplicate/invalid images."
                
                if thumbnails_imported:
                    success_msg += "\n\nThumbnails were successfully imported."
                
                self.notification_manager.show_notification(
                    "Database Import Complete",
                    success_msg,
                    NotificationType.SUCCESS
                )
                
                if thumbnails_imported:
                    self.status_bar.showMessage("Database and thumbnails have been successfully merged")
                else:
                    self.status_bar.showMessage("Database has been successfully merged")
        
        except Exception as e:
            # Close progress dialog
            progress_dialog.close()
            
            # Show error message
            logger.error(f"Error importing database: {e}")
            error_msg = f"An error occurred while importing the database:\n{str(e)}"
            
            QMessageBox.critical(
                self, 
                "Error", 
                error_msg,
                QMessageBox.StandardButton.Ok
            )
            
            self.status_bar.showMessage("Error importing database")
    
    def _format_file_size(self, size_bytes):
        """Format a file size in bytes to a human-readable format.
        
        Args:
            size_bytes (int): Size in bytes
            
        Returns:
            str: Formatted file size (e.g., '1.2 MB')
        """
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def refresh_current_view(self):
        """Refresh the current view."""
        if hasattr(self, 'current_folder_id') and self.current_folder_id:
            # Refresh folder view
            self.on_folder_selected(self.current_folder_id, None)
        else:
            # Refresh all images view - use search if there's an existing query
            if hasattr(self.thumbnail_browser, 'current_search_query') and self.thumbnail_browser.current_search_query:
                self.thumbnail_browser.search(self.thumbnail_browser.current_search_query)
            else:
                self.search_all_images()
                
    def update_ui_counts(self):
        """Update all count labels in the UI: folders, catalogs, and All Images view."""
        try:
            # Only proceed if we have necessary components initialized
            if not hasattr(self, 'db_manager') or not self.db_manager:
                return
                
            # Initialize database extensions if needed
            if not hasattr(self.db_manager, 'get_all_images_count'):
                from src.database.db_operations_extension import extend_db_operations
                extend_db_operations(self.db_manager)
                
            # Update All Images count in header if available and we're in All Images view
            if hasattr(self.thumbnail_browser, 'header_label'):
                # Get total count
                total_count = self.db_manager.get_all_images_count()
                
                # Check if we're in the All Images view
                if (not hasattr(self, 'current_folder_id') or not self.current_folder_id) and \
                   (not hasattr(self.thumbnail_browser, 'current_search_query') or not self.thumbnail_browser.current_search_query):
                    self.thumbnail_browser.header_label.setText(f"All Images ({total_count} total)")
                    
            # Update folder panel if available
            if hasattr(self, 'folder_panel') and self.folder_panel:
                self.folder_panel.refresh_folders()
                
            # Update catalog panel if available
            if hasattr(self, 'catalog_panel') and self.catalog_panel:
                self.catalog_panel.refresh_catalogs()
                
        except Exception as e:
            logger.error(f"Error updating UI counts: {e}")
            
    def _update_counts_after_background_scan(self, *args, **kwargs):
        """Update UI counts after a background scan operation completes.
        
        This is designed to be connected to signal handlers from background operations.
        The arguments are not used but allow this to be connected to various signals.
        """
        try:
            logger.debug("Updating UI counts after background operation")
            # Update UI counts
            self.update_ui_counts()
            
            # Refresh current view if we're showing all images
            if not hasattr(self, 'current_folder_id') or not self.current_folder_id:
                # Use QTimer to ensure this happens after the current event loop cycle
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(100, self.refresh_current_view)
        except Exception as e:
            logger.error(f"Error in _update_counts_after_background_scan: {e}")
                
    def on_database_maintenance(self):
        """Handler for the comprehensive Database Maintenance menu action."""
        try:
            # Import required components
            from src.ui.database_maintenance_dialog import DatabaseMaintenanceDialog
            
            # Show the dialog
            dialog = DatabaseMaintenanceDialog(
                self, 
                self.db_manager, 
                self.db_manager.enhanced_search
            )
            dialog.exec()
            
            # Refresh view after maintenance
            self.refresh_current_view()
            
        except Exception as e:
            logger.error(f"Error showing database maintenance dialog: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while showing the database maintenance dialog:\n{str(e)}",
                QMessageBox.StandardButton.Ok
            )
    
    def on_rebuild_database(self):
        """Handler for the dedicated Rebuild Corrupted Database menu action.
        
        This directly rebuilds a database from scratch to fix corruption issues.
        """
        try:
            # Confirm user wants to proceed with rebuild
            response = QMessageBox.warning(
                self,
                "Rebuild Database",
                "This will completely rebuild the database from scratch to fix corruption.\n\n"
                "A backup of your current database will be created before rebuilding.\n\n"
                "This operation may take several minutes. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if response != QMessageBox.StandardButton.Yes:
                return
            
            # Show progress dialog
            progress_dialog = QProgressDialog("Rebuilding database...", "", 0, 100, self)
            progress_dialog.setWindowTitle("Database Rebuild")
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setCancelButton(None)  # No cancel button
            progress_dialog.setMinimumDuration(0)  # Show immediately
            progress_dialog.setValue(0)
            QApplication.processEvents()
            
            # Disconnect from database
            progress_dialog.setLabelText("Closing database connections...")
            progress_dialog.setValue(10)
            QApplication.processEvents()
            self.db_manager.disconnect()
            
            # Import database repair function
            progress_dialog.setLabelText("Preparing for database rebuild...")
            progress_dialog.setValue(20)
            QApplication.processEvents()
            from src.database.db_repair import rebuild_database
            
            # Perform rebuild
            progress_dialog.setLabelText("Rebuilding database... This may take several minutes.")
            progress_dialog.setValue(30)
            QApplication.processEvents()
            db_path = self.db_manager.db_path
            success = rebuild_database(db_path)
            
            # Reconnect to database
            progress_dialog.setLabelText("Reconnecting to database...")
            progress_dialog.setValue(80)
            QApplication.processEvents()
            self.db_manager.connect()
            
            # Reset connections in enhanced search
            progress_dialog.setLabelText("Resetting connections...")
            progress_dialog.setValue(90)
            QApplication.processEvents()
            if hasattr(self.db_manager, 'enhanced_search') and self.db_manager.enhanced_search:
                if hasattr(self.db_manager.enhanced_search, 'reset_connection'):
                    self.db_manager.enhanced_search.reset_connection()
            
            # Complete
            progress_dialog.setLabelText("Database rebuild complete.")
            progress_dialog.setValue(100)
            QApplication.processEvents()
            
            # Close dialog
            progress_dialog.close()
            
            # Show result message
            if success:
                QMessageBox.information(
                    self,
                    "Database Rebuild Complete",
                    "The database has been successfully rebuilt.\n\n"
                    "A backup of your previous database was created at:\n"
                    f"{db_path}.backup",
                    QMessageBox.StandardButton.Ok
                )
                
                # Refresh view
                self.refresh_current_view()
            else:
                QMessageBox.critical(
                    self,
                    "Database Rebuild Failed",
                    "The database could not be rebuilt.\n\n"
                    "Please check the log file for more information.",
                    QMessageBox.StandardButton.Ok
                )
            
        except Exception as e:
            logger.error(f"Error rebuilding database: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred during database rebuild:\n{str(e)}",
                QMessageBox.StandardButton.Ok
            )
    
    def view_all_images(self):
        """Display all images in the database with pagination"""
        try:
            # Update the thumbnail browser UI to show we're loading
            # This ensures UI responsiveness during loading
            self.status_bar.showMessage("Loading all images...")
            QApplication.processEvents()  # Process events to update the UI
            
            # Initialize database extensions if needed
            if not hasattr(self.db_manager, 'get_all_images_count'):
                logger.info("Initializing database extensions for view_all_images")
                from src.database.db_operations_extension import extend_db_operations
                extend_db_operations(self.db_manager)
            
            # Get total count of images for pagination
            total_count = self.db_manager.get_all_images_count()
            
            # Clear any previous search or folder selection
            if hasattr(self.thumbnail_browser, 'current_folder_id'):
                self.thumbnail_browser.current_folder_id = None
            if hasattr(self.thumbnail_browser, 'current_catalog_id'):
                self.thumbnail_browser.current_catalog_id = None
            if hasattr(self.thumbnail_browser, 'current_search_query'):
                self.thumbnail_browser.current_search_query = None
            if hasattr(self.thumbnail_browser, 'last_search_params'):
                self.thumbnail_browser.last_search_params = None
            
            # Set flag to indicate this is the "All Images" view
            self.thumbnail_browser.all_images_view = True
            
            # Reset pagination to first page
            self.thumbnail_browser.current_page = 0
            
            # Get the page size from pagination if available
            page_size = 200  # Default
            if hasattr(self.thumbnail_browser, 'page_size'):
                page_size = self.thumbnail_browser.page_size
            
            # Enable pagination
            self.thumbnail_browser.is_paginated = True
            self.thumbnail_browser.total_items = total_count
            self.thumbnail_browser.total_pages = (total_count + page_size - 1) // page_size
            
            # Get first page of images
            images = self.db_manager.get_all_images(limit=page_size, offset=0)
            
            # Clear thumbnails and add the first page
            self.thumbnail_browser.clear_thumbnails()
            self.thumbnail_browser.add_thumbnails(images)
            
            # Update header with count
            if hasattr(self.thumbnail_browser, 'header_label'):
                self.thumbnail_browser.header_label.setText(f"All Images ({total_count} total)")
            
            # Update status
            page_count = (total_count + page_size - 1) // page_size
            if page_count > 1:
                self.status_bar.showMessage(
                    f"Showing page 1 of {page_count} ({len(images)} of {total_count} images)"
                )
            else:
                self.status_bar.showMessage(f"Showing all {len(images)} images")
                
            # Update pagination controls if available
            if hasattr(self.thumbnail_browser, 'thumbnail_pagination') and \
               hasattr(self.thumbnail_browser.thumbnail_pagination, 'update_pagination_controls'):
                self.thumbnail_browser.thumbnail_pagination.update_pagination_controls()
                
            # Update window title
            if hasattr(self, 'setWindowTitle'):
                self.setWindowTitle("STARNODES Image Manager - All Images")
                
        except Exception as e:
            logger.error(f"Error viewing all images: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while loading all images:\n{str(e)}",
                QMessageBox.StandardButton.Ok
            )
            
    def on_update_image_dimensions(self):
        """Handler for Update Image Dimensions menu action."""
        try:
            # Import required components
            from src.ui.database_dimensions_update_dialog import DatabaseDimensionsUpdateDialog
            
            # Show the dialog
            dialog = DatabaseDimensionsUpdateDialog(
                self, 
                self.db_manager, 
                self.db_manager.enhanced_search
            )
            dialog.exec()
            
            # Refresh view after update
            self.refresh_current_view()
            
        except Exception as e:
            logger.error(f"Error showing dimensions update dialog: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while showing the dimensions update dialog:\n{str(e)}",
                QMessageBox.StandardButton.Ok
            )
    
    def process_batch_with_parallel_pipeline(self, images, operation_type):
        """Process a batch of images using the parallel processing pipeline.
        
        Args:
            images (list): List of image dictionaries with 'id', 'path' keys
            operation_type (str): Type of operation to perform
            
        Returns:
            bool: True if operation was started, False otherwise
        """
        if not hasattr(self, 'batch_operations'):
            logger.warning("Batch operations manager not initialized, using standard processing")
            return False
        
        # Check if we have a valid batch operations manager
        if not self.batch_operations:
            logger.warning("Batch operations manager is None, using standard processing")
            return False
        
        try:
            # Check operation type
            if operation_type == 'ai_description':
                # Generate descriptions for images
                self.batch_operations.generate_descriptions(
                    images, parent=self, show_progress=True
                )
                return True
            
            elif operation_type == 'thumbnail':
                # Generate thumbnails for images
                self.batch_operations.process_thumbnails(
                    images, parent=self, show_progress=True
                )
                return True
            
            else:
                logger.warning(f"Unsupported operation type: {operation_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting batch operation: {e}")
            return False
