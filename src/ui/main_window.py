#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main window UI for STARNODES Image Manager
Implements the main application window and UI components.
"""

import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QLineEdit, QPushButton, QToolBar, QStatusBar,
    QFileDialog, QMenu, QMessageBox, QApplication, QDialog
)
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtCore import Qt, QSize, QDir, pyqtSignal, QThreadPool

# Local imports
from .thumbnail_browser import ThumbnailBrowser
from .folder_panel import FolderPanel
from .search_panel import SearchPanel
from .metadata_panel import MetadataPanel
from .progress_dialog import ProgressDialog
from .settings_dialog import SettingsDialog
from .database_optimization_dialog import DatabaseOptimizationDialog
from .worker import Worker, BackgroundTaskManager
from .notification_manager import NotificationManager, NotificationType

from src.image_processing.thumbnail_generator import ThumbnailGenerator
from src.image_processing.image_scanner import ImageScanner
from src.ai.image_processor import AIImageProcessor
from src.config.config_manager import ConfigManager
from src.database.db_optimization_utils import check_and_optimize_if_needed
from src.config.theme_manager import ThemeManager

logger = logging.getLogger("STARNODESImageManager.ui")

class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self, db_manager):
        """Initialize the main window.
        
        Args:
            db_manager: Database manager instance
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
        
        # Initialize notification manager
        self.notification_manager = NotificationManager(parent_widget=self)
        
        # Initialize components
        self.init_components()
        self.setup_ui()
        
        # Initialize and apply theme
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.theme_manager.initialize(app_dir=app_dir)
        
        # Check if database optimization is needed
        QApplication.processEvents()  # Process events to ensure UI is displayed
        self.check_database_optimization()
        
        # Make sure window is displayed properly
        self.ensure_window_visible()
    
    def init_components(self):
        """Initialize application components."""
        # Create directories if they don't exist
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Create required directories
        required_dirs = [
            "thumbnails",
            "logs",
            "data"
        ]
        
        for dir_name in required_dirs:
            dir_path = os.path.join(app_dir, dir_name)
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Ensured directory exists: {dir_path}")
        
        # Set thumbnails directory
        thumbnails_dir = os.path.join(app_dir, "thumbnails")
        
        # Initialize thumbnail generator
        thumb_size = self.config_manager.get("thumbnails", "size", 200)
        self.thumbnail_generator = ThumbnailGenerator(
            thumbnail_dir=thumbnails_dir,
            size=(thumb_size, thumb_size)
        )
        
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
        except Exception as e:
            logger.error(f"Error initializing image scanner: {e}")
            # Show error message but continue with application
            QMessageBox.warning(
                self,
                "Component Initialization Error",
                f"An error occurred while initializing the image scanner: {str(e)}\n\n" +
                "Some functionality may be limited."
            )
        
        logger.info("Application components initialized")
    
    def setup_ui(self):
        """Set up the main window UI."""
        # Window properties
        self.setWindowTitle("STARNODES Image Manager")
        self.setMinimumSize(1024, 768)
        
        # Create central widget
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create splitter for main content
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)
        
        # Left panel (folders and search)
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # Folder browser
        self.folder_panel = FolderPanel(self.db_manager)
        left_layout.addWidget(self.folder_panel)
        
        # Search panel
        self.search_panel = SearchPanel()
        left_layout.addWidget(self.search_panel)
        
        # Add left panel to splitter
        self.main_splitter.addWidget(self.left_panel)
        
        # Create right side container with thumbnail browser and metadata panel
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for thumbnail browser and metadata panel
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(self.right_splitter)
        
        # Thumbnail browser
        self.thumbnail_browser = ThumbnailBrowser(self.db_manager)
        self.right_splitter.addWidget(self.thumbnail_browser)
        
        # Metadata panel
        self.metadata_panel = MetadataPanel(self.db_manager)
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
        
        self.search_panel.search_requested.connect(self.on_search_requested)
        
        self.thumbnail_browser.thumbnail_selected.connect(self.on_thumbnail_selected)
        self.thumbnail_browser.thumbnail_double_clicked.connect(self.on_thumbnail_double_clicked)
        self.thumbnail_browser.batch_generate_requested.connect(self.on_batch_generate_from_context_menu)
        self.thumbnail_browser.status_message.connect(self.status_bar.showMessage)
        
        logger.info("Main window UI setup complete")
    
    def create_toolbar(self):
        """Create the main toolbar."""
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(self.toolbar)
        
        # Add folder action
        add_folder_action = QAction("Add Folder", self)
        add_folder_action.setStatusTip("Add a folder to monitor for images")
        add_folder_action.triggered.connect(self.on_add_folder)
        self.toolbar.addAction(add_folder_action)
        
        # Remove folder action
        remove_folder_action = QAction("Remove Folder", self)
        remove_folder_action.setStatusTip("Remove a folder from monitoring")
        remove_folder_action.triggered.connect(self.on_remove_folder)
        self.toolbar.addAction(remove_folder_action)
        
        self.toolbar.addSeparator()
        
        # Scan folder action
        scan_folder_action = QAction("Scan Folder", self)
        scan_folder_action.setStatusTip("Scan the selected folder for new images")
        scan_folder_action.triggered.connect(self.on_scan_folder)
        self.toolbar.addAction(scan_folder_action)
        
        # Generate descriptions action
        generate_descriptions_action = QAction("Generate Descriptions", self)
        generate_descriptions_action.setStatusTip("Generate AI descriptions for images in the selected folder")
        generate_descriptions_action.triggered.connect(self.on_generate_descriptions)
        self.toolbar.addAction(generate_descriptions_action)
        
        self.toolbar.addSeparator()
        
        # Batch operations menu
        self.batch_menu = QMenu("Batch Operations", self)
        batch_action = QAction("Batch Operations", self)
        batch_action.setStatusTip("Perform operations on multiple selected images")
        batch_action.setMenu(self.batch_menu)
        self.toolbar.addAction(batch_action)
        
        # Tools menu
        self.tools_menu = QMenu("Tools", self)
        tools_action = QAction("Tools", self)
        tools_action.setStatusTip("Additional tools and utilities")
        tools_action.setMenu(self.tools_menu)
        self.toolbar.addAction(tools_action)
        
        # Add database optimization action (now also handles repair)
        optimize_db_action = QAction("Optimize & Repair Database", self)
        optimize_db_action.setStatusTip("Optimize and repair the database for better performance and reliability")
        optimize_db_action.triggered.connect(self.on_optimize_database)
        self.tools_menu.addAction(optimize_db_action)
        
        # Add batch operations
        self.batch_generate_action = QAction("Generate Descriptions for Selected", self)
        self.batch_generate_action.setStatusTip("Generate AI descriptions for selected images")
        self.batch_generate_action.triggered.connect(self.on_batch_generate_descriptions)
        self.batch_menu.addAction(self.batch_generate_action)
        
        self.batch_export_action = QAction("Export Selected Images", self)
        self.batch_export_action.setStatusTip("Export selected images to a folder")
        self.batch_export_action.triggered.connect(self.on_batch_export_images)
        self.batch_menu.addAction(self.batch_export_action)
        
        self.batch_rename_action = QAction("Rename Selected Images", self)
        self.batch_rename_action.setStatusTip("Rename selected images with a pattern")
        self.batch_rename_action.triggered.connect(self.on_batch_rename_images)
        self.batch_menu.addAction(self.batch_rename_action)
        
        self.batch_menu.addSeparator()
        
        self.batch_copy_action = QAction("Copy Selected to Folder", self)
        self.batch_copy_action.setStatusTip("Copy selected images to a folder")
        self.batch_copy_action.triggered.connect(self.on_batch_copy_images)
        self.batch_menu.addAction(self.batch_copy_action)
        
        self.batch_delete_desc_action = QAction("Delete Descriptions for Selected", self)
        self.batch_delete_desc_action.setStatusTip("Delete descriptions for selected images")
        self.batch_delete_desc_action.triggered.connect(self.on_batch_delete_descriptions)
        self.batch_menu.addAction(self.batch_delete_desc_action)
        
        self.batch_delete_action = QAction("Delete Selected Images", self)
        self.batch_delete_action.setStatusTip("Delete selected images")
        self.batch_delete_action.triggered.connect(self.on_batch_delete_images)
        self.batch_menu.addAction(self.batch_delete_action)
        
        self.toolbar.addSeparator()
        
        # Settings action
        settings_action = QAction("Settings", self)
        settings_action.setStatusTip("Open application settings")
        settings_action.triggered.connect(self.on_settings)
        self.toolbar.addAction(settings_action)
    
    def on_add_folder(self):
        """Handle the Add Folder action."""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder to Monitor", 
            QDir.homePath(), 
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder_path:
            # Add folder to the database
            folder_id = self.db_manager.add_folder(folder_path)
            
            if folder_id:
                # Update folder panel
                self.folder_panel.refresh_folders()
                
                # Ask if user wants to scan now
                response = QMessageBox.question(
                    self, "Scan Folder", 
                    f"Folder '{folder_path}' added successfully. Do you want to scan it for images now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if response == QMessageBox.StandardButton.Yes:
                    # Scan the folder
                    self.scan_folder(folder_id, folder_path)
            else:
                QMessageBox.critical(
                    self, "Error", 
                    f"Failed to add folder '{folder_path}' to the database.",
                    QMessageBox.StandardButton.Ok
                )
    
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
            self.progress_dialog = ProgressDialog(
                "Scanning Folder",
                f"Scanning folder '{folder_path}' for images...",
                self,
                cancellable=True
            )
            
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
                    progress_dialog = ProgressDialog(
                        "Generating Descriptions",
                        f"Generating AI descriptions for {mode_text} in '{folder_info['path']}'...\n" +
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
        settings_dialog = SettingsDialog(self.config_manager, self.theme_manager, self)
        
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
    
    def on_folder_selected(self, folder_id, folder_path):
        """Handle folder selection from the folder panel.
        
        Args:
            folder_id (int): ID of the selected folder
            folder_path (str): Path of the selected folder
        """
        # Update status bar
        self.status_bar.showMessage(f"Selected folder: {folder_path}")
        
        # Update thumbnail browser with images from the selected folder
        self.thumbnail_browser.set_folder(folder_id)
    
    def on_folder_removed(self, folder_id):
        """Handle folder removal from the folder panel.
        
        Args:
            folder_id (int): ID of the removed folder
        """
        # Clear the thumbnail browser if it was showing this folder
        if self.thumbnail_browser.current_folder_id == folder_id:
            self.thumbnail_browser.clear_thumbnails()
            self.status_bar.showMessage("Folder removed")
    
    def on_search_requested(self, query):
        """Handle search request from the search panel.
        
        Args:
            query (str): Search query
        """
        # Update status bar
        self.status_bar.showMessage(f"Searching for: {query}")
        
        # Update thumbnail browser with search results
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
        # If image_ids is not provided, get selected images from the thumbnail browser
        if image_ids is None:
            if not hasattr(self.thumbnail_browser, 'selected_thumbnails') or not self.thumbnail_browser.selected_thumbnails:
                QMessageBox.information(self, "No Images Selected", "Please select one or more images first.")
                return
            image_ids = list(self.thumbnail_browser.selected_thumbnails)
            
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
            
            results = {
                "success": 0,
                "failed": 0,
                "renamed_files": []
            }
            
            total = len(image_ids)
            
            for i, image_id in enumerate(image_ids):
                try:
                    # Get image info
                    image_info = self.db_manager.get_image_by_id(image_id)
                    
                    if not image_info:
                        results["failed"] += 1
                        continue
                    
                    source_path = image_info["full_path"]
                    if not os.path.exists(source_path):
                        results["failed"] += 1
                        continue
                    
                    # Get directory and extension
                    directory = os.path.dirname(source_path)
                    _, ext = os.path.splitext(source_path)
                    
                    # Create new filename based on pattern
                    new_filename = pattern.replace("{n}", str(i + 1)).replace("{ext}", ext[1:]) + ext
                    dest_path = os.path.join(directory, new_filename)
                    
                    # Check if destination already exists
                    counter = 1
                    while os.path.exists(dest_path) and dest_path != source_path:
                        new_filename = pattern.replace("{n}", f"{i + 1}_{counter}").replace("{ext}", ext[1:]) + ext
                        dest_path = os.path.join(directory, new_filename)
                        counter += 1
                    
                    # Skip if source and destination are the same
                    if dest_path == source_path:
                        if progress_callback:
                            progress_callback(i + 1, total, f"Skipped: {os.path.basename(source_path)} (already named correctly)")
                        continue
                    
                    # Rename the file
                    shutil.move(source_path, dest_path)
                    
                    # Update database with new path
                    self.db_manager.update_image_path(image_id, dest_path, new_filename)
                    
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
        """Delete selected images."""
        # Delegate to the thumbnail browser's delete images function
        self.thumbnail_browser.delete_selected_images()
    
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
