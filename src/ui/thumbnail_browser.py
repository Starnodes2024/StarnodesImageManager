#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Thumbnail browser UI component for StarImageBrowse
Displays image thumbnails in a grid layout with various viewing options.
"""

import os
import re
import logging
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
    QFrame, QSizePolicy, QGridLayout, QMenu, QApplication,
    QFileDialog, QInputDialog, QMessageBox
)
from PyQt6.QtGui import QPixmap, QImage, QCursor, QIcon
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, QThreadPool, QRunnable, QMetaObject, Q_ARG

from .lazy_thumbnail_loader import LazyThumbnailLoader
from .thumbnail_widget import ThumbnailWidget

logger = logging.getLogger("StarImageBrowse.ui.thumbnail_browser")

# Use the ThumbnailWidget imported from thumbnail_widget.py


class ThumbnailBrowser(QWidget):
    """Browser for displaying image thumbnails."""
    
    thumbnail_selected = pyqtSignal(int)  # Signal emitted when a thumbnail is selected
    thumbnail_double_clicked = pyqtSignal(int, str)  # Signal emitted when a thumbnail is double-clicked
    batch_generate_requested = pyqtSignal(list)  # Signal emitted to request batch description generation
    status_message = pyqtSignal(str)  # Signal emitted to display status messages
    
    def get_translation(self, section, key, default=None):
        """Get a translation for a key.
        
        Args:
            section (str): Section in the translations
            key (str): Key in the section
            default (str, optional): Default value if translation not found
            
        Returns:
            str: Translated string or default value
        """
        if self.language_manager:
            return self.language_manager.get_translation(section, key, default)
        return default
    
    def __init__(self, db_manager, parent=None):
        """Initialize the thumbnail browser.
        
        Args:
            db_manager: Database manager instance
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.db_manager = db_manager
        self.current_folder_id = None
        self.current_search_query = None
        self.current_catalog_id = None  # Current catalog being displayed
        self.thumbnails = {}  # Dictionary of thumbnail widgets by image_id
        self.selected_thumbnails = set()  # Set of selected thumbnail image_ids
        
        # Try to get language manager from parent window
        self.language_manager = None
        parent_widget = self
        while parent_widget.parent() is not None:
            parent_widget = parent_widget.parent()
            if hasattr(parent_widget, 'language_manager'):
                self.language_manager = parent_widget.language_manager
                break
        
        # Initialize lazy thumbnail loader with multi-level caching
        # Determine optimal number of concurrent threads based on CPU cores
        max_concurrent = min(4, QThreadPool.globalInstance().maxThreadCount())
        
        # Get the config manager from the main window if available
        config_manager = None
        thumbnails_dir = None
        if parent and hasattr(parent, 'config_manager'):
            config_manager = parent.config_manager
        
        # Get the thumbnails directory
        if parent and hasattr(parent, 'thumbnail_generator'):
            thumbnails_dir = parent.thumbnail_generator.thumbnail_dir
        else:
            # Use default thumbnails directory
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            thumbnails_dir = os.path.join(app_dir, "thumbnails")
            
        self.thumbnail_loader = LazyThumbnailLoader(
            max_concurrent=max_concurrent,
            config_manager=config_manager,
            thumbnails_dir=thumbnails_dir
        )
        
        # Initialize preview size settings from config
        if config_manager:
            from .thumbnail_widget import ThumbnailWidget
            preview_size = config_manager.get("thumbnails", "preview_size", 700)
            preview_delay = config_manager.get("thumbnails", "preview_delay", 300)
            ThumbnailWidget.set_preview_size(preview_size)
            ThumbnailWidget.set_hover_delay(preview_delay)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the thumbnail browser UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Header with information
        self.header_label = QLabel("")
        main_layout.addWidget(self.header_label)
        
        # Scroll area for thumbnails
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        main_layout.addWidget(self.scroll_area)
        
        # Container widget for the grid
        self.container = QWidget()
        self.scroll_area.setWidget(self.container)
        
        # Grid layout for thumbnails
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(10)
    
    def set_folder(self, folder_id):
        """Display thumbnails for the specified folder.
        
        Args:
            folder_id (int): ID of the folder to display
        """
        self.current_folder_id = folder_id
        self.current_search_query = None
        self.selected_thumbnails.clear()
        
        # Get folder info
        folders = self.db_manager.get_folders()
        folder_info = next((f for f in folders if f["folder_id"] == folder_id), None)
        
        if folder_info:
            self.header_label.setText(f"Folder: {folder_info['path']}")
        else:
            self.header_label.setText("Unknown Folder")
        
        # Clear existing thumbnails
        self.clear_thumbnails()
        
        # Get images for this folder
        images = self.db_manager.get_images_for_folder(folder_id, limit=1000000)
        
        if not images:
            # No images found
            empty_label = QLabel("No images found in this folder")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(empty_label, 0, 0)
            return
        
        # Create and add thumbnail widgets
        self.add_thumbnails(images)
    
    def search(self, query):
        """Display thumbnails for search results.
        
        Args:
            query (str): Search query
        """
        if not query:
            # If empty query, clear results
            self.clear_thumbnails()
            self.header_label.setText("No search query")
            return
        
        self.current_folder_id = None
        self.current_search_query = query
        self.selected_thumbnails.clear()
        
        self.header_label.setText(f"Search results for: {query}")
        
        # Clear existing thumbnails
        self.clear_thumbnails()
        
        # Get search results
        images = self.db_manager.search_images(query, limit=1000000)
        
        if not images:
            # No images found
            empty_label = QLabel(f"No images found for query: {query}")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(empty_label, 0, 0)
            return
        
        # Create and add thumbnail widgets
        self.add_thumbnails(images)
    
    def add_thumbnails(self, images):
        """Add thumbnails for the specified images.
        
        Args:
            images (list): List of image dictionaries from the database
        """
        # Calculate grid columns based on widget width
        width = self.width()
        columns = max(1, (width - 20) // 230)  # 230 = thumbnail width (220) + spacing (10)
        
        # Clear any pending thumbnail loads
        self.thumbnail_loader.cancel_pending()
        
        # Add thumbnails to the grid
        for i, image in enumerate(images):
            row = i // columns
            col = i % columns
            
            # Create thumbnail widget
            # Ensure we have the full path to the original image for dimensions
            original_path = image.get("full_path")
            if original_path:
                logger.debug(f"Creating thumbnail with original path: {original_path}")
            else:
                logger.debug(f"No original path for image ID {image['image_id']}")
                
            # Get dimensions from the database if available
            width = image.get("width")
            height = image.get("height")
            
            # Create the thumbnail widget with all available data
            thumbnail = ThumbnailWidget(
                image_id=image["image_id"],
                thumbnail_path=image["thumbnail_path"],
                filename=image["filename"],
                description=image.get("ai_description") or image.get("user_description"),
                original_path=original_path,
                width=width,
                height=height
            )
            
            # Connect signals to handlers
            thumbnail.clicked.connect(self.on_thumbnail_clicked)
            thumbnail.double_clicked.connect(self.on_thumbnail_double_clicked)
            thumbnail.context_menu_requested.connect(self.on_thumbnail_context_menu)
            
            # Add to grid and store reference
            self.grid_layout.addWidget(thumbnail, row, col)
            self.thumbnails[image["image_id"]] = thumbnail
            
            # Queue thumbnail for lazy loading
            image_id = image["image_id"]
            thumbnail_path = image["thumbnail_path"]
            
            # Use a lambda with default arguments to capture the current thumbnail
            # This avoids the common closure problem in loops
            def create_callback(thumb):
                return lambda pixmap: thumb.set_thumbnail(pixmap)
                
            callback = create_callback(thumbnail)
            self.thumbnail_loader.queue_thumbnail(image_id, thumbnail_path, callback)
    
    def clear_thumbnails(self):
        """Clear all thumbnails from the browser."""
        # Cancel any pending thumbnail loading tasks
        self.thumbnail_loader.cancel_pending()
        
        # Clear thumbnail dictionary
        self.thumbnails = {}
        
        # Clear selected thumbnails
        self.selected_thumbnails.clear()
        
        # Clear the grid layout
        if self.grid_layout:
            # Remove all widgets from the grid
            while self.grid_layout.count():
                item = self.grid_layout.takeAt(0)
                if item and item.widget():
                    widget = item.widget()
                    widget.setParent(None)
                    widget.deleteLater()
        
        # Update header
        self.header_label.setText("No images to display")
        
        # Emit selection signal with no selection
        self.thumbnail_selected.emit(-1)
        # This helps prevent memory leaks when browsing large folders
        if len(self.thumbnails) > 100:
            self.thumbnail_loader.clear_cache()
    

    
    def on_thumbnail_clicked(self, image_id):
        """Handle thumbnail click.
        
        Args:
            image_id (int): ID of the clicked image
        """
        # Check keyboard modifiers
        modifiers = QApplication.keyboardModifiers()
        ctrl_pressed = modifiers & Qt.KeyboardModifier.ControlModifier
        shift_pressed = modifiers & Qt.KeyboardModifier.ShiftModifier
        
        if ctrl_pressed:
            # Toggle selection
            if image_id in self.selected_thumbnails:
                self.selected_thumbnails.remove(image_id)
                self.thumbnails[image_id].set_selected(False)
            else:
                self.selected_thumbnails.add(image_id)
                self.thumbnails[image_id].set_selected(True)
        elif shift_pressed and self.selected_thumbnails:
            # Range selection (from last selected to current)
            # Find all thumbnails between the last selected and current
            all_ids = list(self.thumbnails.keys())
            if all_ids:
                try:
                    # Get the last selected thumbnail
                    last_selected = next(iter(self.selected_thumbnails))
                    
                    # Find indices
                    start_idx = all_ids.index(last_selected)
                    end_idx = all_ids.index(image_id)
                    
                    # Swap if needed to ensure start < end
                    if start_idx > end_idx:
                        start_idx, end_idx = end_idx, start_idx
                    
                    # Clear previous selection
                    for selected_id in self.selected_thumbnails:
                        if selected_id in self.thumbnails:
                            self.thumbnails[selected_id].set_selected(False)
                    self.selected_thumbnails.clear()
                    
                    # Select all thumbnails in the range
                    for idx in range(start_idx, end_idx + 1):
                        select_id = all_ids[idx]
                        self.selected_thumbnails.add(select_id)
                        self.thumbnails[select_id].set_selected(True)
                except ValueError:
                    # Handle case where ID is not in the list
                    self.selected_thumbnails = {image_id}
                    self.thumbnails[image_id].set_selected(True)
        else:
            # Clear previous selection
            for selected_id in self.selected_thumbnails:
                if selected_id in self.thumbnails:
                    self.thumbnails[selected_id].set_selected(False)
            
            # Select this thumbnail
            self.selected_thumbnails = {image_id}
            self.thumbnails[image_id].set_selected(True)
        
        # Emit signal
        self.thumbnail_selected.emit(image_id)
    
    def on_thumbnail_double_clicked(self, image_id, thumbnail_path):
        """Handle thumbnail double-click.
        
        Args:
            image_id (int): ID of the double-clicked image
            thumbnail_path (str): Path to the thumbnail image
        """
        # Get full image info
        image_info = self.db_manager.get_image_by_id(image_id)
        
        if image_info:
            # Emit signal with image ID and full path
            self.thumbnail_double_clicked.emit(image_id, image_info["full_path"])
    
    def on_thumbnail_context_menu(self, image_id, position):
        """Handle thumbnail context menu request.
        
        Args:
            image_id (int): ID of the image
            position: Global position for the menu
        """
        # Make sure the thumbnail is selected
        if image_id not in self.selected_thumbnails:
            # Clear previous selection
            for selected_id in self.selected_thumbnails:
                if selected_id in self.thumbnails:
                    self.thumbnails[selected_id].set_selected(False)
            
            # Select this thumbnail
            self.selected_thumbnails = {image_id}
            self.thumbnails[image_id].set_selected(True)
        
        # Create context menu
        menu = QMenu()
        
        # Get the number of selected thumbnails
        num_selected = len(self.selected_thumbnails)
        
        # Menu actions
        # Add debug logging to check language manager and translations
        logger.debug(f"Language manager exists: {self.language_manager is not None}")
        if self.language_manager:
            logger.debug(f"Current language: {self.language_manager.current_language}")
        
        copy_text = self.get_translation('thumbnails', 'copy_to_folder', 'Copy to folder...')
        export_text = self.get_translation('thumbnails', 'export_with_options', 'Export with options...')
        open_text = self.get_translation('thumbnails', 'open', 'Open')
        locate_text = self.get_translation('thumbnails', 'locate_on_disk', 'Locate on disk')
        copy_image_text = self.get_translation('thumbnails', 'copy_to_clipboard', 'Copy image to clipboard')
        selected_suffix = self.get_translation('thumbnails', 'selected_suffix', '({} selected)')
        
        # Log translations for debugging
        logger.debug(f"Translation for copy_to_folder: {copy_text}")
        logger.debug(f"Translation for export_with_options: {export_text}")
        logger.debug(f"Translation for open: {open_text}")
        
        copy_action = menu.addAction(f"{copy_text} {selected_suffix.format(num_selected)}" if num_selected > 1 else copy_text)
        export_action = menu.addAction(f"{export_text} {selected_suffix.format(num_selected)}" if num_selected > 1 else export_text)
        open_action = menu.addAction(f"{open_text} {selected_suffix.format(num_selected)}" if num_selected > 1 else open_text)
        locate_action = menu.addAction(f"{locate_text} {selected_suffix.format(num_selected)}" if num_selected > 1 else locate_text)
        copy_image_action = menu.addAction(f"{copy_image_text} {selected_suffix.format(num_selected)}" if num_selected > 1 else copy_image_text)
        
        # Add catalog-related actions
        add_to_catalog_text = self.get_translation('thumbnails', 'add_to_catalog', 'Add to Catalog')
        catalog_menu = QMenu(f"{add_to_catalog_text} {selected_suffix.format(num_selected)}" if num_selected > 1 else add_to_catalog_text)
        
        # Get all catalogs
        catalogs = self.db_manager.get_catalogs()
        catalog_actions = []
        
        # Add an action for each catalog
        for catalog in catalogs:
            catalog_action = catalog_menu.addAction(catalog["name"])
            catalog_actions.append((catalog_action, catalog["catalog_id"]))
        
        # Add a separator and "New Catalog..." option if there are any catalogs
        if catalogs:
            catalog_menu.addSeparator()
        
        # Add "New Catalog..." option
        new_catalog_action = catalog_menu.addAction(self.get_translation('thumbnails', 'new_catalog', 'New Catalog...'))
        
        # Add the catalog submenu to the main menu
        menu.addMenu(catalog_menu)
        
        # Add "Remove from Catalog" option if we're viewing a catalog
        if self.current_catalog_id is not None:
            remove_from_catalog_action = menu.addAction(self.get_translation('thumbnails', 'remove_from_catalog', 'Remove from Catalog'))
        
        # Add description-related actions
        menu.addSeparator()
        edit_desc_text = self.get_translation('thumbnails', 'edit_description', 'Edit description')
        generate_desc_text = self.get_translation('thumbnails', 'generate_description', 'Generate AI description')
        delete_desc_text = self.get_translation('thumbnails', 'delete_description', 'Delete description')
        
        edit_action = menu.addAction(f"{edit_desc_text} {selected_suffix.format(num_selected)}" if num_selected > 1 else edit_desc_text)
        generate_desc_action = menu.addAction(f"{generate_desc_text} {selected_suffix.format(num_selected)}" if num_selected > 1 else generate_desc_text)
        delete_desc_action = menu.addAction(f"{delete_desc_text} {selected_suffix.format(num_selected)}" if num_selected > 1 else delete_desc_text)
        
        # Add delete actions with separator
        menu.addSeparator()
        delete_db_text = self.get_translation('thumbnails', 'delete_from_db', 'Delete from database')
        delete_full_text = self.get_translation('thumbnails', 'delete_from_db_and_disk', 'Delete from database and disk')
        
        delete_db_action = menu.addAction(f"{delete_db_text} {selected_suffix.format(num_selected)}" if num_selected > 1 else delete_db_text)
        delete_full_action = menu.addAction(f"{delete_full_text} {selected_suffix.format(num_selected)}" if num_selected > 1 else delete_full_text)
        
        # Show menu and get selected action
        action = menu.exec(position)
        
        # Handle selected action
        if action == copy_action:
            self.copy_selected_images()
        elif action == export_action:
            self.export_selected_images()
        elif action == open_action:
            self.open_selected_images()
        elif action == locate_action:
            self.locate_selected_images_on_disk()
        elif action == copy_image_action:
            self.copy_selected_images_to_clipboard()
        elif action == edit_action:
            self.edit_selected_descriptions()
        elif action == generate_desc_action:
            self.generate_descriptions_for_selected()
        elif action == delete_desc_action:
            self.delete_selected_descriptions()
        elif action == delete_db_action:
            self.delete_selected_images(delete_from_disk=False)
        elif action == delete_full_action:
            self.delete_selected_images(delete_from_disk=True)
        elif 'new_catalog_action' in locals() and action == new_catalog_action:
            self.add_to_new_catalog()
        elif self.current_catalog_id is not None and 'remove_from_catalog_action' in locals() and action == remove_from_catalog_action:
            self.remove_from_catalog()
        else:
            # Check catalog actions
            for catalog_action, catalog_id in catalog_actions:
                if action == catalog_action:
                    self.add_to_catalog(catalog_id)
                    break
    
    def export_selected_images(self):
        """Export selected images with extended format options."""
        if not self.selected_thumbnails:
            return
        
        # Show export dialog to get export options
        from PyQt6.QtWidgets import QDialog
        from .export_dialog import ExportDialog
        export_dialog = ExportDialog(parent=self, num_images=len(self.selected_thumbnails))
        
        if export_dialog.exec() == QDialog.DialogCode.Accepted:
            # Get export options
            export_options = export_dialog.get_export_options()
            
            # Get image information for all selected thumbnails
            image_ids = list(self.selected_thumbnails)
            images_to_export = []
            
            for image_id in image_ids:
                image_info = self.db_manager.get_image_by_id(image_id)
                if image_info and os.path.exists(image_info['full_path']):
                    images_to_export.append(image_info)
            
            if not images_to_export:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Export Failed", "No valid images selected for exporting.")
                return
            
            # Start the export process
            self.start_export_process(images_to_export, export_options)
    
    def copy_selected_images(self, export_mode=False):
        """Copy selected images to a folder.
        
        Args:
            export_mode (bool): If True, the operation is presented as an export rather than a copy
        """
        if not self.selected_thumbnails:
            return
        
        # Get destination folder
        dialog_title = "Select Export Destination" if export_mode else "Select Destination Folder"
        dest_folder = QFileDialog.getExistingDirectory(
            self, dialog_title, 
            os.path.expanduser("~"), 
            QFileDialog.Option.ShowDirsOnly
        )
        
        if not dest_folder:
            return
            
        # Get image information for all selected thumbnails
        image_ids = list(self.selected_thumbnails)
        images_to_copy = []
        
        for image_id in image_ids:
            image_info = self.db_manager.get_image_by_id(image_id)
            if image_info and os.path.exists(image_info['full_path']):
                images_to_copy.append(image_info)
        
        if not images_to_copy:
            QMessageBox.warning(self, "Copy Failed", "No valid images selected for copying.")
            return
            
        # For simple copy mode (not export), we don't need to show the export dialog
        if not export_mode:
            self.start_copy_process(images_to_copy, dest_folder, export_mode=False)
            
    def start_export_process(self, images, export_options):
        """Start the export process with the given options.
        
        Args:
            images (list): List of image dictionaries to export
            export_options (dict): Dictionary of export options from ExportDialog
        """
        dest_folder = export_options["destination"]
        export_format = export_options["format"]
        include_description = export_options["include_description"]
        description_only = export_options["description_only"]
        export_workflow = export_options["export_workflow"]
        
        # Create progress dialog
        from .progress_dialog import ProgressDialog
        progress_dialog = ProgressDialog(
            "Exporting Images",
            f"Exporting {len(images)} images to {dest_folder}...",
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
            if results:
                progress_dialog.update_operation("Export operation complete")
                progress_dialog.log_message(f"Successfully exported: {results['success']} items")
                if results['failed'] > 0:
                    progress_dialog.log_message(f"Failed to export: {results['failed']} items")
            else:
                progress_dialog.log_message("Export operation failed or was cancelled")
            
            # Enable close button
            progress_dialog.close_when_finished()
        
        # Define error callback
        def on_task_error(error_info):
            progress_dialog.log_message(f"Error exporting images: {error_info[0]}")
            progress_dialog.close_when_finished()
        
        # Define cancel callback
        def on_cancel():
            progress_dialog.log_message("Export operation cancelled")
        
        # Show progress dialog
        progress_dialog.cancelled.connect(on_cancel)
        progress_dialog.show()
        
        # Define the export function to run in the background thread
        def export_images_task(images, destination, export_format, include_description, description_only, export_workflow, progress_callback=None):
            import shutil
            import os
            from PIL import Image
            from src.utils.image_utils import extract_comfyui_workflow
            
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
                        
                        results['exported_files'].append(txt_path)
                        results['success'] += 1
                        
                        # Update progress
                        if progress_callback:
                            progress_callback(i + 1, total, f"Exported description: {txt_filename}")
                            
                        continue
                    
                    # Handle image export with potentially different format
                    dest_filename = base_name
                    if export_format == "jpg":
                        dest_filename += ".jpg"
                    elif export_format == "png":
                        dest_filename += ".png"
                    else:  # Original format
                        dest_filename = filename
                    
                    dest_path = os.path.join(destination, dest_filename)
                    
                    # Handle duplicate filenames
                    counter = 1
                    orig_dest_filename = dest_filename
                    while os.path.exists(dest_path):
                        name_without_ext, ext = os.path.splitext(orig_dest_filename)
                        dest_filename = f"{name_without_ext}_{counter}{ext}"
                        dest_path = os.path.join(destination, dest_filename)
                        counter += 1
                    
                    # Handle format conversion if needed
                    if export_format in ["jpg", "png"] and os.path.splitext(source_path)[1].lower() != f".{export_format}":
                        try:
                            # Convert image format
                            img = Image.open(source_path)
                            img.save(dest_path, quality=95 if export_format == "jpg" else None)
                        except Exception as e:
                            logger.error(f"Error converting image format for {source_path}: {e}")
                            # Fallback to direct copy
                            shutil.copy2(source_path, dest_path)
                    else:
                        # Direct copy for original format
                        shutil.copy2(source_path, dest_path)
                    
                    results['exported_files'].append(dest_path)
                    
                    # Handle description export if requested
                    if include_description:
                        # Get description
                        description = image.get('ai_description', '')
                        if not description:
                            description = image.get('user_description', '')
                        if not description:
                            description = "No description available for this image."
                        
                        # Create text file with same base name
                        txt_filename = os.path.splitext(dest_filename)[0] + ".txt"
                        txt_path = os.path.join(destination, txt_filename)
                        
                        # Write description to file
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(description)
                        
                        results['exported_files'].append(txt_path)
                    
                    # Handle ComfyUI workflow export if requested
                    if export_workflow:
                        # Extract and save workflow
                        workflow_filename = os.path.splitext(dest_filename)[0] + "_workflow.json"
                        workflow_path = os.path.join(destination, workflow_filename)
                        
                        # Use the extract_comfyui_workflow utility function
                        success, message, exported_path = extract_comfyui_workflow(source_path, workflow_path)
                        
                        if success:
                            results['exported_files'].append(exported_path)
                            if progress_callback:
                                progress_callback(i + 1, total, f"Exported workflow: {workflow_filename}")
                    

                    
                    results['success'] += 1
                    
                    # Update progress
                    if progress_callback:
                        progress_callback(i + 1, total, f"Exported: {dest_filename}")
                        
                except Exception as e:
                    logger.error(f"Error exporting {image['filename']}: {str(e)}")
                    results['failed'] += 1
                    
                    # Update progress with error info
                    if progress_callback:
                        progress_callback(i + 1, total, f"Error exporting: {os.path.basename(source_path)}")
            
            return results
        
        # Get the task manager from the parent window
        from PyQt6.QtWidgets import QApplication
        main_window = None
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == "MainWindow":
                main_window = widget
                break
        
        if main_window and hasattr(main_window, 'task_manager'):
            # Start export operation in background thread
            main_window.task_manager.start_task(
                task_id=f"export_images_{id(self)}",
                fn=export_images_task,
                images=images,
                destination=dest_folder,
                export_format=export_format,
                include_description=include_description,
                description_only=description_only,
                export_workflow=export_workflow,
                progress_callback=progress_callback,
                on_result=on_task_complete,
                on_error=on_task_error
            )
        else:
            # Fallback if task manager not available
            QMessageBox.warning(self, "Export Failed", "Background task manager not available.")
            progress_dialog.close()
    
    def start_copy_process(self, images, destination, export_mode=False):
        """Start the copy process for the selected images.
        
        Args:
            images (list): List of image dictionaries to copy
            destination (str): Destination folder path
            export_mode (bool): Whether this is an export operation
        """
        # Create progress dialog
        from .progress_dialog import ProgressDialog
        operation_type = "Exporting" if export_mode else "Copying"
        progress_dialog = ProgressDialog(
            f"{operation_type} Images",
            f"{operation_type} {len(images)} images to {destination}...",
            self
        )
        
        # Define progress callback
        def progress_callback(current, total, message=None):
            progress_dialog.update_progress(current, total)
            if message:
                progress_dialog.update_operation(message)
            else:
                operation = "Exporting" if export_mode else "Copying"
                progress_dialog.update_operation(f"{operation} image {current} of {total}")
        
        # Define task completion callback
        def on_task_complete(results):
            # Update progress dialog
            operation_type = "Export" if export_mode else "Copy"
            if results:
                progress_dialog.update_operation(f"{operation_type} operation complete")
                progress_dialog.log_message(f"Successfully {operation_type.lower()}ed: {results['success']} images")
                if results['failed'] > 0:
                    progress_dialog.log_message(f"Failed to {operation_type.lower()}: {results['failed']} images")
            else:
                progress_dialog.log_message(f"{operation_type} operation failed or was cancelled")
            
            # Enable close button
            progress_dialog.close_when_finished()
        
        # Define error callback
        def on_task_error(error_info):
            operation = "exporting" if export_mode else "copying"
            progress_dialog.log_message(f"Error {operation} images: {error_info[0]}")
            progress_dialog.close_when_finished()
        
        # Define cancel callback
        def on_cancel():
            operation = "Export" if export_mode else "Copy"
            progress_dialog.log_message(f"{operation} operation cancelled")
        
        # Show progress dialog
        progress_dialog.cancelled.connect(on_cancel)
        progress_dialog.show()
        
        # Define the copy function to run in the background thread
        def copy_images_task(images, destination, progress_callback=None):
            import shutil
            import os
            
            results = {
                'success': 0,
                'failed': 0,
                'copied_files': []
            }
            
            total = len(images)
            
            for i, image in enumerate(images):
                try:
                    source_path = image['full_path']
                    filename = os.path.basename(source_path)
                    dest_path = os.path.join(destination, filename)
                    
                    # Check if file already exists in destination
                    if os.path.exists(dest_path):
                        base_name, ext = os.path.splitext(filename)
                        counter = 1
                        while os.path.exists(dest_path):
                            new_filename = f"{base_name}_{counter}{ext}"
                            dest_path = os.path.join(destination, new_filename)
                            counter += 1
                    
                    # Copy the file
                    shutil.copy2(source_path, dest_path)
                    results['success'] += 1
                    results['copied_files'].append(dest_path)
                    
                    # Update progress
                    if progress_callback:
                        operation = "Exported" if export_mode else "Copied"
                        progress_callback(i + 1, total, f"{operation}: {os.path.basename(source_path)}")
                        
                except Exception as e:
                    operation = "exporting" if export_mode else "copying"
                    logger.error(f"Error {operation} {image['filename']}: {str(e)}")
                    results['failed'] += 1
                    
                    # Update progress with error info
                    if progress_callback:
                        operation = "exporting" if export_mode else "copying"
                        progress_callback(i + 1, total, f"Error {operation}: {os.path.basename(source_path)}")
            
            return results
        
        # Get the task manager from the parent window
        from PyQt6.QtWidgets import QApplication
        main_window = None
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == "MainWindow":
                main_window = widget
                break
        
        if main_window and hasattr(main_window, 'task_manager'):
            # Start copy operation in background thread
            operation = "export" if export_mode else "copy"
            main_window.task_manager.start_task(
                task_id=f"{operation}_images_{id(self)}",
                fn=copy_images_task,
                images=images,
                destination=destination,
                progress_callback=progress_callback,
                on_result=on_task_complete,
                on_error=on_task_error
            )
        else:
            # Fallback if task manager not available
            operation = "Export" if export_mode else "Copy"
            QMessageBox.warning(self, f"{operation} Failed", "Background task manager not available.")
            progress_dialog.close()
    
    def open_selected_images(self):
        """Open selected images with the default system application."""
        if not self.selected_thumbnails:
            return
            
        # Get image information for all selected thumbnails
        image_ids = list(self.selected_thumbnails)
        
        for image_id in image_ids:
            image_info = self.db_manager.get_image_by_id(image_id)
            if image_info and os.path.exists(image_info['full_path']):
                # Use the appropriate method to open the file with the default application
                try:
                    if os.name == 'nt':  # Windows
                        os.startfile(image_info['full_path'])
                    elif os.name == 'posix':  # macOS, Linux
                        if sys.platform == 'darwin':  # macOS
                            subprocess.call(('open', image_info['full_path']))
                        else:  # Linux
                            subprocess.call(('xdg-open', image_info['full_path']))
                except Exception as e:
                    logger.error(f"Error opening file {image_info['full_path']}: {e}")
                    QMessageBox.warning(
                        self,
                        "Error Opening File",
                        f"Could not open {image_info['filename']}. Error: {str(e)}"
                    )
    
    def locate_selected_images_on_disk(self):
        """Locate selected images in the file explorer."""
        if not self.selected_thumbnails:
            return
            
        # Get image information for all selected thumbnails
        image_ids = list(self.selected_thumbnails)
        
        for image_id in image_ids:
            image_info = self.db_manager.get_image_by_id(image_id)
            if image_info and os.path.exists(image_info['full_path']):
                # Get the directory containing the file
                file_dir = os.path.dirname(image_info['full_path'])
                
                # Open the file explorer and select the file
                try:
                    if os.name == 'nt':  # Windows
                        # Use explorer to open the folder and select the file
                        subprocess.run(['explorer', '/select,', os.path.normpath(image_info['full_path'])])
                    elif os.name == 'posix':  # macOS, Linux
                        if sys.platform == 'darwin':  # macOS
                            # On macOS, open the folder in Finder
                            subprocess.call(['open', file_dir])
                        else:  # Linux
                            # On Linux, open the folder in the default file manager
                            subprocess.call(['xdg-open', file_dir])
                except Exception as e:
                    logger.error(f"Error locating file {image_info['full_path']}: {e}")
                    QMessageBox.warning(
                        self,
                        "Error Locating File",
                        f"Could not locate {image_info['filename']} in file explorer. Error: {str(e)}"
                    )
    
    def copy_selected_images_to_clipboard(self):
        """Copy selected images to clipboard."""
        if not self.selected_thumbnails:
            return
            
        # We can only copy one image to clipboard at a time
        # If multiple images are selected, use the first one
        image_id = next(iter(self.selected_thumbnails))
        image_info = self.db_manager.get_image_by_id(image_id)
        
        if not image_info or not os.path.exists(image_info['full_path']):
            QMessageBox.warning(
                self,
                "Copy Failed",
                "Could not find the selected image file."
            )
            return
            
        try:
            # Load the image using QImage
            image_path = image_info['full_path']
            qimage = QImage(image_path)
            
            if qimage.isNull():
                QMessageBox.warning(
                    self,
                    "Copy Failed",
                    f"Could not load image: {image_info['filename']}"
                )
                return
                
            # Create a pixmap from the image and copy to clipboard
            pixmap = QPixmap.fromImage(qimage)
            QApplication.clipboard().setPixmap(pixmap)
            
            # Show success message
            self.status_message.emit(f"Copied image to clipboard: {image_info['filename']}")
            
        except Exception as e:
            logger.error(f"Error copying image to clipboard: {e}")
            QMessageBox.warning(
                self,
                "Copy Failed",
                f"Could not copy image to clipboard. Error: {str(e)}"
            )
    
    def edit_selected_descriptions(self):
        """Edit descriptions for selected images."""
        if not self.selected_thumbnails:
            return
            
        # If only one image is selected
        if len(self.selected_thumbnails) == 1:
            image_id = next(iter(self.selected_thumbnails))
            image_info = self.db_manager.get_image_by_id(image_id)
            
            if not image_info:
                return
            
            # Get current description
            current_description = image_info.get("user_description") or image_info.get("ai_description") or ""
            
            # Get new description
            new_description, ok = QInputDialog.getMultiLineText(
                self, "Edit Description", "Description:", current_description
            )
            
            if ok:
                # Update description in database
                self.db_manager.update_image_description(image_id, user_description=new_description)
                
                # Refresh display
                self.refresh()
        else:
            # Multiple images selected
            # TODO: Implement batch description editing
            pass
    
    def generate_descriptions_for_selected(self):
        """Generate AI descriptions for selected images."""
        if not self.selected_thumbnails:
            return
            
        # Get image IDs for selected thumbnails
        image_ids = list(self.selected_thumbnails)
        
        # Check if we have any images to process
        if not image_ids:
            return
            
        # Confirm generation
        num_selected = len(image_ids)
        confirm = QMessageBox.question(
            self,
            self.get_translation('thumbnails', 'confirm_generation_title', "Confirm Generation"),
            self.get_translation('thumbnails', 'confirm_description_generation', "Generate AI descriptions for {} selected image{}?").format(
                num_selected,
                's' if num_selected > 1 else ''
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # Verify that the selected images exist
        valid_image_ids = []
        for image_id in image_ids:
            image_info = self.db_manager.get_image_by_id(image_id)
            if image_info and os.path.exists(image_info['full_path']):
                valid_image_ids.append(image_id)  # Only pass the ID, not the entire image_info dictionary
        
        if not valid_image_ids:
            QMessageBox.warning(
                self,
                "Generation Failed",
                "No valid images selected for description generation."
            )
            return
            
        # Emit signal to request batch generation with just the image IDs
        # This will be handled by the main window or another component
        self.batch_generate_requested.emit(valid_image_ids)
        
        # Show status message
        msg_template = self.get_translation('thumbnails', 'descriptions_generation_started', "Started AI description generation for {} image{}")
        self.status_message.emit(msg_template.format(
            len(valid_image_ids),
            's' if len(valid_image_ids) != 1 else ''
        ))
    
    def delete_selected_descriptions(self):
        """Delete descriptions for selected images."""
        if not self.selected_thumbnails:
            return
            
        # Confirm deletion
        num_selected = len(self.selected_thumbnails)
        confirm = QMessageBox.question(
            self,
            self.get_translation('thumbnails', 'confirm_deletion_title', "Confirm Deletion"),
            self.get_translation('thumbnails', 'confirm_description_deletion', "Delete descriptions for {} selected image{}?").format(
                num_selected,
                's' if num_selected > 1 else ''
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # Delete descriptions for each selected image
        success_count = 0
        for image_id in self.selected_thumbnails:
            # Pass both ai_description and user_description as empty strings to clear both
            if self.db_manager.update_image_description(image_id, ai_description="", user_description=""):
                success_count += 1
                
                # Update thumbnail widget if it exists
                if image_id in self.thumbnails:
                    self.thumbnails[image_id].description = ""
        
        # Show status message
        msg_template = self.get_translation('thumbnails', 'descriptions_deleted', "Deleted descriptions for {} image{}")
        # Make sure we're only passing the exact number of arguments needed for the format string
        # Check the template to see how many placeholders it has
        try:
            self.status_message.emit(msg_template.format(
                success_count,
                's' if success_count != 1 else ''
            ))
        except IndexError:
            # Fallback in case the translation has a different number of placeholders
            self.status_message.emit(f"Deleted descriptions for {success_count} image{'s' if success_count != 1 else ''}")
    
    def delete_selected_images(self, delete_from_disk=False):
        """Delete selected images from database and optionally from disk.
        
        Args:
            delete_from_disk (bool): If True, also delete image files from disk
        """
        if not self.selected_thumbnails:
            return
            
        # Confirm deletion
        num_selected = len(self.selected_thumbnails)
        if delete_from_disk:
            confirm_key = 'confirm_full_deletion'
            default_msg = "Delete {} selected image{} from database AND disk? This cannot be undone!"
        else:
            confirm_key = 'confirm_db_deletion'
            default_msg = "Delete {} selected image{} from database? The image files will remain on disk."
            
        confirm = QMessageBox.question(
            self,
            self.get_translation('thumbnails', 'confirm_deletion_title', "Confirm Deletion"),
            self.get_translation('thumbnails', confirm_key, default_msg).format(
                num_selected,
                's' if num_selected > 1 else ''
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # Delete each selected image
        success_count = 0
        for image_id in list(self.selected_thumbnails):
            # Get image path before deleting from database if we need to delete from disk
            image_path = None
            if delete_from_disk:
                image_info = self.db_manager.get_image_by_id(image_id)
                if image_info:
                    image_path = image_info.get('path')
            
            # Delete from database
            if self.db_manager.delete_image(image_id):
                success_count += 1
                
                # Delete from disk if requested
                if delete_from_disk and image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                        logger.info(f"Deleted image file: {image_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete image file {image_path}: {e}")
                
                # Remove from UI
                if image_id in self.thumbnails:
                    thumbnail = self.thumbnails[image_id]
                    self.grid_layout.removeWidget(thumbnail)
                    thumbnail.deleteLater()
                    del self.thumbnails[image_id]
                
                # Remove from selection
                self.selected_thumbnails.discard(image_id)
        
        # Show status message
        if delete_from_disk:
            msg_template = self.get_translation('thumbnails', 'images_deleted_full', "Deleted {} image{} from database and disk")
        else:
            msg_template = self.get_translation('thumbnails', 'images_deleted_db', "Deleted {} image{} from database")
            
        self.status_message.emit(msg_template.format(
            success_count,
            's' if success_count != 1 else ''
        ))
    
    def set_catalog(self, catalog_id):
        """Display thumbnails for the specified catalog.
        
        Args:
            catalog_id (int): ID of the catalog to display
        """
        # Store current catalog ID
        self.current_folder_id = None
        self.current_search_query = None
        self.current_catalog_id = catalog_id
        
        # Get catalog info
        catalog = self.db_manager.get_catalog_by_id(catalog_id)
        if not catalog:
            return
            
        # Get images in catalog
        images = self.db_manager.get_images_for_catalog(catalog_id)
        
        # Clear and add thumbnails
        self.clear_thumbnails()
        self.add_thumbnails(images)
    
    def add_to_catalog(self, catalog_id):
        """Add selected images to the specified catalog.
        
        Args:
            catalog_id (int): ID of the catalog to add images to
        """
        if not self.selected_thumbnails:
            return
            
        # Get catalog info
        catalog = self.db_manager.get_catalog_by_id(catalog_id)
        if not catalog:
            return
            
        # Add each selected image to the catalog
        success_count = 0
        for image_id in self.selected_thumbnails:
            if self.db_manager.add_image_to_catalog(image_id, catalog_id):
                success_count += 1
                
        # Show status message
        msg_template = self.get_translation('thumbnails', 'images_added_to_catalog', "Added {} image{} to catalog '{}'")
        self.status_message.emit(msg_template.format(
            success_count,
            's' if success_count != 1 else '',
            catalog['name']
        ))
    
    def add_to_new_catalog(self):
        """Create a new catalog and add selected images to it."""
        if not self.selected_thumbnails:
            return
            
        # Prompt for catalog name
        catalog_name, ok = QInputDialog.getText(
            self, 
            self.get_translation('thumbnails', 'new_catalog_title', "New Catalog"), 
            self.get_translation('thumbnails', 'new_catalog_prompt', "Enter a name for the new catalog:")
        )
        
        if not ok or not catalog_name.strip():
            return
            
        # Prompt for catalog description (optional)
        catalog_desc, ok = QInputDialog.getText(
            self, "New Catalog", "Enter a description (optional):"
        )
        
        if not ok:
            return
            
        # Create the catalog
        catalog_id = self.db_manager.create_catalog(catalog_name, catalog_desc)
        
        if not catalog_id:
            QMessageBox.warning(
                self, 
                self.get_translation('common', 'error', "Error"), 
                self.get_translation('thumbnails', 'create_catalog_failed', "Failed to create catalog")
            )
            return
            
        # Add selected images to the catalog
        success_count = 0
        for image_id in self.selected_thumbnails:
            if self.db_manager.add_image_to_catalog(image_id, catalog_id):
                success_count += 1
                
        # Show status message
        msg_template = self.get_translation('thumbnails', 'catalog_created', "Created catalog '{}' and added {} image{}")
        self.status_message.emit(msg_template.format(
            catalog_name,
            success_count,
            's' if success_count != 1 else ''
        ))
    
    def remove_from_catalog(self):
        """Remove selected images from the current catalog."""
        if not self.selected_thumbnails or self.current_catalog_id is None:
            return
            
        # Get catalog info
        catalog = self.db_manager.get_catalog_by_id(self.current_catalog_id)
        if not catalog:
            return
            
        # Confirm removal
        num_selected = len(self.selected_thumbnails)
        
        # Get the translation template with placeholders
        template = self.get_translation('thumbnails', 'confirm_catalog_removal', 
                                      "Remove {0} selected image{1} from catalog '{2}'?")
        
        # Check if we're using the German translation which has 4 placeholders
        if template.count('{}') == 4:
            # German format: "{} ausgewählte{} Bild{} aus Katalog '{}' entfernen?"
            translated_message = template.format(
                num_selected,
                '' if num_selected == 1 else 's',  # German adjective ending
                '' if num_selected == 1 else 'er',  # German plural for Bild/Bilder
                catalog['name']
            )
        else:
            # Default format with 3 placeholders
            translated_message = template.format(
                num_selected,
                's' if num_selected > 1 else '',
                catalog['name']
            )
        
        confirm = QMessageBox.question(
            self,
            self.get_translation('thumbnails', 'confirm_removal_title', "Confirm Removal"),
            translated_message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # Remove each selected image from the catalog
        success_count = 0
        for image_id in list(self.selected_thumbnails):
            if self.db_manager.remove_image_from_catalog(image_id, self.current_catalog_id):
                success_count += 1
                
                # Remove from UI if we're viewing the catalog
                if self.current_catalog_id is not None:
                    if image_id in self.thumbnails:
                        thumbnail = self.thumbnails[image_id]
                        self.grid_layout.removeWidget(thumbnail)
                        thumbnail.deleteLater()
                        del self.thumbnails[image_id]
                    
                    # Remove from selection
                    self.selected_thumbnails.discard(image_id)
        
        # Show status message
        # Get the translation template with placeholders
        template = self.get_translation('thumbnails', 'images_removed_from_catalog', 
                                      "Removed {0} image{1} from catalog '{2}'")
        
        # Check if we're using the German translation which might have 4 placeholders
        if template.count('{}') == 4:
            # German format might be similar to the confirmation dialog
            translated_status = template.format(
                success_count,
                '' if success_count == 1 else 's',  # German adjective ending
                '' if success_count == 1 else 'er',  # German plural for Bild/Bilder
                catalog['name']
            )
        else:
            # Default format with 3 placeholders
            translated_status = template.format(
                success_count,
                's' if success_count > 1 else '',
                catalog['name']
            )
        
        self.status_message.emit(translated_status)
        
        # Refresh if we're viewing the catalog
        if self.current_catalog_id is not None:
            self.refresh()
    
    def refresh(self):
        """Refresh the thumbnail display."""
        if self.current_folder_id is not None:
            self.set_folder(self.current_folder_id)
        elif self.current_catalog_id is not None:
            self.set_catalog(self.current_catalog_id)
        elif self.current_search_query is not None:
            self.search(self.current_search_query)
        else:
            self.clear_thumbnails()
    
    def resizeEvent(self, event):
        """Handle resize event to adjust the grid layout.
        
        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        
        # Prevent excessive refreshes during continuous resize events
        if not hasattr(self, '_resize_timer'):
            from PyQt6.QtCore import QTimer
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._delayed_resize_refresh)
        
        # Restart timer to prevent multiple refreshes during continuous resizing
        self._resize_timer.start(200)  # 200ms delay before refreshing
    
    def _delayed_resize_refresh(self):
        """Perform a refresh after resize events have settled."""
        # Cancel any pending thumbnail loads before refreshing
        if hasattr(self, 'thumbnail_loader'):
            self.thumbnail_loader.cancel_pending()
            
        # Refresh layout if we have thumbnails
        if self.thumbnails:
            self.refresh()
