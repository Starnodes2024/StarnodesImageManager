#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main window UI for STARNODES Image Manager
Implements the main application window and UI components.
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from PIL import Image, ExifTags
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QLineEdit, QPushButton, QToolBar, QStatusBar,
    QFileDialog, QMenu, QMessageBox, QApplication, QDialog,
    QInputDialog, QListView, QTreeView, QAbstractItemView,
    QListWidget, QListWidgetItem, QDialogButtonBox
)
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtCore import Qt, QSize, QDir, pyqtSignal, QThreadPool

# Local imports
from .thumbnail_browser_factory import create_thumbnail_browser
from .folder_panel import FolderPanel
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
from src.config.config_manager import ConfigManager
from src.database.db_optimization_utils import check_and_optimize_if_needed
from src.config.theme_manager import ThemeManager
from src.processing.batch_operations import get_batch_operations, BatchOperations
from src.processing.task_manager import get_task_manager
from src.processing.parallel_pipeline import get_pipeline
from src.memory.memory_utils import initialize_memory_management, get_memory_stats, cleanup_memory_pools, force_garbage_collection, get_system_memory_info
from src.database.performance_optimizer import DatabasePerformanceOptimizer

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
            "data",
            "temp"  # Temporary files directory for processing
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
    
    def setup_menus(self):
        """Set up application menus."""
        # --- FILE MENU ---
        file_menu = self.menuBar().addMenu("File")
        
        # Folder management submenu
        folder_submenu = file_menu.addMenu("Folder Management")
        
        # Add folder action
        add_folder_action = folder_submenu.addAction("Add Folder")
        add_folder_action.triggered.connect(self.on_add_folder)
        
        # Remove folder action
        remove_folder_action = folder_submenu.addAction("Remove Folder")
        remove_folder_action.triggered.connect(self.on_remove_folder)
        
        # Scan folder action
        scan_folder_action = folder_submenu.addAction("Scan Folder")
        scan_folder_action.triggered.connect(self.on_scan_folder)
        
        # File operations submenu
        file_ops_submenu = file_menu.addMenu("File Operations")
        
        # Export action
        export_action = file_ops_submenu.addAction("Export Selected Images...")
        export_action.triggered.connect(self.export_selected_images)
        
        # Copy to folder action
        copy_action = file_ops_submenu.addAction("Copy Selected to Folder")
        copy_action.triggered.connect(self.on_batch_copy_images)
        
        # Exit action
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        
        # --- VIEW MENU ---
        view_menu = self.menuBar().addMenu("View")
        
        # Show all images action
        view_menu.addAction("Show All Images").triggered.connect(self.show_all_images)
        
        # --- EDIT MENU ---
        edit_menu = self.menuBar().addMenu("Edit")
        
        # Rename action
        rename_action = edit_menu.addAction("Rename Selected Images...")
        rename_action.triggered.connect(self.rename_selected_images)
        
        # Delete submenu
        delete_submenu = edit_menu.addMenu("Delete")
        
        # Delete from database only
        delete_db_action = delete_submenu.addAction("Delete from Database Only")
        delete_db_action.triggered.connect(self.on_batch_delete_images_db_only)
        
        # Delete from database and disk
        delete_full_action = delete_submenu.addAction("Delete from Database and Disk")
        delete_full_action.triggered.connect(self.on_batch_delete_images_with_files)
        
        # Delete descriptions
        delete_desc_action = delete_submenu.addAction("Delete Descriptions for Selected")
        delete_desc_action.triggered.connect(self.on_batch_delete_descriptions)
        
        # --- AI TOOLS MENU ---
        ai_menu = self.menuBar().addMenu("AI Tools")
        
        # Generate descriptions with options dialog
        ai_menu.addAction("Generate Descriptions with Options...").triggered.connect(self.on_generate_descriptions)
        
        # Generate descriptions for selected images only
        ai_menu.addAction("Generate for Selected Images Only").triggered.connect(self.generate_descriptions_for_selected)
        
        # Generate descriptions for all images in folder
        ai_menu.addAction("Generate for All Images in Folder").triggered.connect(self.generate_descriptions_for_folder)
        
        # --- BATCH OPERATIONS MENU ---
        batch_menu = self.menuBar().addMenu("Batch Operations")
        
        # Image processing submenu
        img_proc_submenu = batch_menu.addMenu("Image Processing")
        
        # Generate descriptions action
        generate_batch_action = img_proc_submenu.addAction("Generate AI Descriptions")
        generate_batch_action.triggered.connect(self.on_batch_generate_descriptions)
        
        # Export action
        export_batch_action = img_proc_submenu.addAction("Export Images")
        export_batch_action.triggered.connect(self.on_batch_export_images)
        
        # Rename action
        rename_batch_action = img_proc_submenu.addAction("Rename Images")
        rename_batch_action.triggered.connect(self.on_batch_rename_images)
        
        # File management submenu
        file_mgmt_submenu = batch_menu.addMenu("File Management")
        
        # Copy to folder action
        copy_batch_action = file_mgmt_submenu.addAction("Copy to Folder")
        copy_batch_action.triggered.connect(self.on_batch_copy_images)
        
        # Delete descriptions action
        delete_desc_batch_action = file_mgmt_submenu.addAction("Delete Descriptions")
        delete_desc_batch_action.triggered.connect(self.on_batch_delete_descriptions)
        
        # Delete from database only action
        delete_db_batch_action = file_mgmt_submenu.addAction("Delete from Database Only")
        delete_db_batch_action.triggered.connect(self.on_batch_delete_images_db_only)
        
        # Delete from database and disk action
        delete_full_batch_action = file_mgmt_submenu.addAction("Delete from Database and Disk")
        delete_full_batch_action.triggered.connect(self.on_batch_delete_images_with_files)
        
        # --- TOOLS MENU ---
        tools_menu = self.menuBar().addMenu("Tools")
        
        # Database submenu
        db_submenu = tools_menu.addMenu("Database")
        
        # Optimize database action
        optimize_db_action = db_submenu.addAction("Optimize & Repair Database")
        optimize_db_action.triggered.connect(self.on_optimize_database)
        
        # Settings action
        tools_menu.addSeparator()
        settings_action = tools_menu.addAction("Settings")
        settings_action.triggered.connect(self.on_settings)
    
    def setup_ui(self):
        """Set up the main window UI."""
        # Window properties
        self.setWindowTitle("STARNODES Image Manager V0.9.5")
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
        
        # Thumbnail browser - use factory to create appropriate implementation
        self.thumbnail_browser = create_thumbnail_browser(self.db_manager, self.config_manager)
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
        self.folder_panel.add_folder_requested.connect(self.on_add_folder)
        
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
        self.progress_dialog = ProgressDialog(
            "Scanning Folders",
            f"Scanning {folder_count} folders for images...",
            self,
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
        # Special case for All Images (-1)
        if folder_id == -1:
            # Update status bar
            self.status_bar.showMessage("Viewing all images")
            
            # Show all images from all folders
            self.show_all_images()
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
    
    def show_all_images(self):
        """Show all images from all folders using an optimized database query."""
        # Clear the current folder selection
        self.current_folder_id = None
        self.thumbnail_browser.current_folder_id = None
        self.thumbnail_browser.current_search_query = None
        
        # Clear existing thumbnails
        self.thumbnail_browser.clear_thumbnails()
        
        # Set header
        self.thumbnail_browser.header_label.setText("All Images (Loading...)")
        self.status_bar.showMessage("Loading all images...")
        
        # Show loading message - handle both browser types
        loading_label = QLabel("Loading all images...")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Check which type of browser we're using
        if hasattr(self.thumbnail_browser, 'grid_layout'):
            # Traditional thumbnail browser
            self.thumbnail_browser.grid_layout.addWidget(loading_label, 0, 0)
        else:
            # Virtualized thumbnail browser - update the header only
            # (virtualized browser doesn't have a grid_layout)
            pass
            
        QApplication.processEvents()  # Update UI
        
        # Create a worker to load all images in the background using the optimized method
        worker = Worker(self.load_all_images_worker)
        
        # Connect signals
        worker.signals.result.connect(self.on_all_images_loaded)
        worker.signals.error.connect(self.on_all_images_error)
        
        # Start the worker
        self.status_bar.showMessage("Loading all images in background...")
        QThreadPool.globalInstance().start(worker)
    
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
            all_images = self.db_manager.get_all_images(limit=100000)
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
    
    def on_search_requested(self, query):
        """Handle search request from the search panel.
        
        Args:
            query (str): Search query
        """
        # Get the current folder ID (could be None for "All Images")
        folder_id = getattr(self, 'current_folder_id', None)
        
        # If we have a specific folder selected, search only within that folder
        if folder_id is not None and folder_id != -1:
            folder_info = next((f for f in self.db_manager.get_folders() if f["folder_id"] == folder_id), None)
            folder_name = folder_info.get("path", "Unknown") if folder_info else "Unknown"
            
            # Update status bar
            self.status_bar.showMessage(f"Searching for: {query} in folder: {folder_name}")
            
            # Clear thumbnails
            self.thumbnail_browser.clear_thumbnails()
            
            # Set header
            self.thumbnail_browser.header_label.setText(f"Search results for: {query} in folder: {os.path.basename(folder_name)}")
            
            # Search only within this folder
            images = self.db_manager.search_images_in_folder(folder_id, query, limit=1000)
            
            if not images:
                # No images found
                empty_label = QLabel(f"No images found for query: {query} in this folder")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.thumbnail_browser.grid_layout.addWidget(empty_label, 0, 0)
                return
            
            # Add thumbnails
            self.thumbnail_browser.add_thumbnails(images)
        else:
            # Update status bar for global search
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
                self.show_all_images()
        
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
        """Export selected images to a folder."""
        # Get selected images
        selected_images = list(self.thumbnail_browser.selected_thumbnails)
        
        if not selected_images:
            self.notification_manager.show_notification(
                "No Images Selected",
                "Please select one or more images to export."
            )
            return
        
        # Get export folder
        export_folder = QFileDialog.getExistingDirectory(
            self, "Select Export Folder", os.path.expanduser("~"),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        
        if not export_folder:
            return  # User cancelled
        
        # TODO: Implement export functionality with progress dialog
        self.notification_manager.show_notification(
            "Export Feature",
            "This feature will be implemented in a future update."
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
        
    def refresh_current_view(self):
        """Refresh the current view."""
        if hasattr(self, 'current_folder_id') and self.current_folder_id:
            # Refresh folder view
            self.on_folder_selected(self.current_folder_id, None)
        else:
            # Refresh all images view
            self.show_all_images()
    
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
