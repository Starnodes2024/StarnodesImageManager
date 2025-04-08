#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Virtualized thumbnail browser for StarImageBrowse
Uses a virtualized grid for efficient display of large image collections
"""

import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSizePolicy, QMenu, QApplication, QFileDialog, QMessageBox
)
from PyQt6.QtGui import QPixmap, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool

from .virtualized_thumbnail_grid import VirtualizedGridWidget
from .thumbnail_widget import ThumbnailWidget
from .lazy_thumbnail_loader import LazyThumbnailLoader

logger = logging.getLogger("StarImageBrowse.ui.virtualized_thumbnail_browser")

class VirtualizedThumbnailBrowser(QWidget):
    """Browser for displaying image thumbnails using a virtualized grid."""
    
    thumbnail_selected = pyqtSignal(int)  # Signal emitted when a thumbnail is selected (image_id)
    thumbnail_double_clicked = pyqtSignal(int, str)  # Signal emitted when a thumbnail is double-clicked (image_id, path)
    batch_generate_requested = pyqtSignal(list)  # Signal emitted when batch generate is requested (list of image_ids)
    status_message = pyqtSignal(str)  # Signal emitted when a status message should be displayed
    
    def __init__(self, db_manager, parent=None):
        """Initialize the virtualized thumbnail browser.
        
        Args:
            db_manager: Database manager instance
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.db_manager = db_manager
        self.current_folder_id = None
        self.current_search_query = None
        self.all_images = []  # List of all images in the current context
        self.thumbnails = {}  # Dictionary of visible thumbnails {image_id: widget}
        self.selected_thumbnails = set()  # Set of selected thumbnail image_ids
        
        # Setup UI
        self.setup_ui()
        
        # Thumbnail loader for background loading with multi-level caching
        # Get the config manager from the main window if available
        config_manager = None
        if parent and hasattr(parent, 'config_manager'):
            config_manager = parent.config_manager
        self.thumbnail_loader = LazyThumbnailLoader(config_manager=config_manager)
        
        # Thread pool for background tasks
        self.thread_pool = QThreadPool.globalInstance()
        
    def setup_ui(self):
        """Set up the virtualized thumbnail browser UI."""
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Header with folder/search info
        self.header_frame = QFrame()
        self.header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.header_frame.setMaximumHeight(40)
        self.header_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        self.header_label = QLabel()
        self.header_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.header_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.header_label)
        
        self.layout.addWidget(self.header_frame)
        
        # Virtualized grid for thumbnails
        self.grid = VirtualizedGridWidget()
        self.grid.set_item_provider(self.create_thumbnail_widget)
        self.grid.range_changed.connect(self.on_visible_range_changed)
        
        self.layout.addWidget(self.grid)
        
    def create_thumbnail_widget(self, index, recycled_widget=None):
        """Create or update a thumbnail widget for the given index.
        
        Args:
            index (int): Index in the all_images list
            recycled_widget (QWidget, optional): Recycled widget to update
            
        Returns:
            ThumbnailWidget: The created or updated thumbnail widget
        """
        if index < 0 or index >= len(self.all_images):
            return QLabel("Invalid Index")
            
        # Get image data for the index
        image = self.all_images[index]
        image_id = image.get('image_id')
        thumbnail_path = image.get('thumbnail_path', '')
        filename = image.get('filename', 'Unknown')
        
        # Get description (AI or user)
        description = image.get('user_description') or image.get('ai_description') or ""
        
        # Create or update thumbnail widget
        if recycled_widget and isinstance(recycled_widget, ThumbnailWidget):
            # Update recycled widget
            widget = recycled_widget
            widget.image_id = image_id
            widget.thumbnail_path = thumbnail_path
            widget.filename = filename
            widget.description = description
            
            # Update UI elements
            widget.filename_label.setText(filename)
            
            # Set description text (with truncation)
            if description:
                max_length = 100
                display_text = description[:max_length] + "..." if len(description) > max_length else description
                widget.description_label.setText(display_text)
                widget.description_label.setToolTip(description)
            else:
                widget.description_label.setText("")
                widget.description_label.setToolTip("")
            
            # Reset thumbnail image
            widget.load_thumbnail()
            
            # Update selected state
            widget.set_selected(image_id in self.selected_thumbnails)
        else:
            # Create new thumbnail widget
            widget = ThumbnailWidget(image_id, thumbnail_path, filename, description)
            widget.clicked.connect(self.on_thumbnail_clicked)
            widget.double_clicked.connect(self.on_thumbnail_double_clicked)
            widget.context_menu_requested.connect(self.on_thumbnail_context_menu)
            widget.set_selected(image_id in self.selected_thumbnails)
        
        # Store widget reference
        self.thumbnails[image_id] = widget
        
        # Queue thumbnail loading (if not already loaded)
        if thumbnail_path and os.path.exists(thumbnail_path):
            # Use callback mechanism instead of signal
            self.thumbnail_loader.queue_thumbnail(image_id, thumbnail_path, lambda pixmap: self.on_thumbnail_loaded(image_id, pixmap))
        
        return widget
    
    def on_visible_range_changed(self, start_index, end_index):
        """Handle changes to the visible range of thumbnails.
        
        Args:
            start_index (int): Start index of visible range
            end_index (int): End index of visible range
        """
        logger.debug(f"Visible range changed: {start_index} - {end_index}")
        
        # Prioritize loading thumbnails in the visible range
        for i in range(start_index, min(end_index + 1, len(self.all_images))):
            image = self.all_images[i]
            image_id = image.get('image_id')
            thumbnail_path = image.get('thumbnail_path', '')
            
            if thumbnail_path and os.path.exists(thumbnail_path):
                # Use callback mechanism for visible thumbnails
                self.thumbnail_loader.queue_thumbnail(image_id, thumbnail_path, lambda pixmap: self.on_thumbnail_loaded(image_id, pixmap))
    
    def set_folder(self, folder_id):
        """Display thumbnails for the specified folder.
        
        Args:
            folder_id (int): ID of the folder to display
        """
        self.current_folder_id = folder_id
        self.current_search_query = None
        
        # Clear thumbnails
        self.clear_thumbnails()
        
        # Get folder info
        folder_info = next((f for f in self.db_manager.get_folders() if f["folder_id"] == folder_id), None)
        folder_name = folder_info.get("path", "Unknown") if folder_info else "Unknown"
        
        # Update header
        self.header_label.setText(f"Folder: {os.path.basename(folder_name)}")
        
        # Get images for the folder from the database
        # With virtualized grid, we can safely load many more images
        images = self.db_manager.get_images_for_folder(folder_id, limit=100000)
        
        if not images:
            # No images found
            empty_label = QLabel("No images found in this folder")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Add to layout temporarily - will be removed when adding thumbnails
            self.layout.addWidget(empty_label)
            return
        
        # Store all images
        self.all_images = images
        
        # Update header with count
        self.header_label.setText(f"Folder: {os.path.basename(folder_name)} ({len(images)} images)")
        
        # Set total items in the virtualized grid
        self.grid.set_total_items(len(images))
    
    def search(self, query):
        """Display thumbnails for search results.
        
        Args:
            query (str): Search query
        """
        self.current_folder_id = None
        self.current_search_query = query
        
        # Clear thumbnails
        self.clear_thumbnails()
        
        # Update header
        self.header_label.setText(f"Search results for: {query}")
        
        # Search images
        images = self.db_manager.search_images(query, limit=1000)
        
        if not images:
            # No images found
            empty_label = QLabel(f"No images found for query: {query}")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Add to layout temporarily - will be removed when adding thumbnails
            self.layout.addWidget(empty_label)
            return
        
        # Store all images
        self.all_images = images
        
        # Update header with count
        self.header_label.setText(f"Search results for: {query} ({len(images)} images)")
        
        # Highlight search terms in the description
        for image_id, thumbnail in self.thumbnails.items():
            thumbnail.highlight_search_terms(query)
        
        # Set total items in the virtualized grid
        self.grid.set_total_items(len(images))
    
    def add_thumbnails(self, images):
        """Add thumbnails for the specified images.
        
        Args:
            images (list): List of image dictionaries from the database
        """
        # Store all images
        self.all_images = images
        
        # Set total items in the virtualized grid
        self.grid.set_total_items(len(images))
    
    def clear_thumbnails(self):
        """Clear all thumbnails from the browser."""
        # Clear the thumbnails dictionary
        self.thumbnails.clear()
        
        # Clear selected thumbnails
        self.selected_thumbnails.clear()
        
        # Clear all images list
        self.all_images.clear()
        
        # Reset virtualized grid
        self.grid.set_total_items(0)
    
    def on_thumbnail_loaded(self, image_id, pixmap):
        """Handle thumbnail loading completion.
        
        Args:
            image_id (int): ID of the image
            pixmap (QPixmap): Loaded thumbnail pixmap
        """
        if image_id in self.thumbnails:
            self.thumbnails[image_id].set_thumbnail(pixmap)
    
    def on_thumbnail_clicked(self, image_id):
        """Handle thumbnail click.
        
        Args:
            image_id (int): ID of the clicked image
        """
        # Toggle selection if Ctrl is pressed
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if image_id in self.selected_thumbnails:
                self.selected_thumbnails.remove(image_id)
            else:
                self.selected_thumbnails.add(image_id)
                
            # Update selected state
            if image_id in self.thumbnails:
                self.thumbnails[image_id].set_selected(image_id in self.selected_thumbnails)
        else:
            # Single selection
            previously_selected = set(self.selected_thumbnails)
            self.selected_thumbnails.clear()
            self.selected_thumbnails.add(image_id)
            
            # Update selected state for all thumbnails
            for prev_id in previously_selected:
                if prev_id in self.thumbnails:
                    self.thumbnails[prev_id].set_selected(False)
                    
            if image_id in self.thumbnails:
                self.thumbnails[image_id].set_selected(True)
        
        # Emit signal
        self.thumbnail_selected.emit(image_id)
    
    def on_thumbnail_double_clicked(self, image_id, thumbnail_path):
        """Handle thumbnail double-click.
        
        Args:
            image_id (int): ID of the double-clicked image
            thumbnail_path (str): Path to the thumbnail image
        """
        # Emit signal
        self.thumbnail_double_clicked.emit(image_id, thumbnail_path)
    
    def on_thumbnail_context_menu(self, image_id, position):
        """Handle thumbnail context menu request.
        
        Args:
            image_id (int): ID of the image
            position: Global position for the menu
        """
        # Create context menu
        menu = QMenu(self)
        
        # Get image info
        image_info = self.db_manager.get_image_by_id(image_id)
        if not image_info:
            return
            
        # Open image action
        open_action = menu.addAction("Open Image")
        
        # Copy to folder action
        copy_action = menu.addAction("Copy to Folder...")
        
        menu.addSeparator()
        
        # Generate AI description action
        generate_action = menu.addAction("Generate AI Description")
        
        # Edit description action
        edit_action = menu.addAction("Edit Description")
        
        # Delete description action
        delete_desc_action = menu.addAction("Delete Description")
        
        menu.addSeparator()
        
        # Delete from database action
        delete_db_action = menu.addAction("Remove from Database")
        
        # Delete from disk action
        delete_disk_action = menu.addAction("Delete from Disk")
        
        # If multiple thumbnails are selected
        if len(self.selected_thumbnails) > 1 and image_id in self.selected_thumbnails:
            num_selected = len(self.selected_thumbnails)
            batch_menu = QMenu(f"Batch Operations ({num_selected} images)", self)
            
            batch_copy_action = batch_menu.addAction("Copy Selected to Folder...")
            batch_generate_action = batch_menu.addAction("Generate AI Descriptions")
            batch_delete_desc_action = batch_menu.addAction("Delete Descriptions")
            batch_menu.addSeparator()
            batch_delete_db_action = batch_menu.addAction("Remove Selected from Database")
            batch_delete_disk_action = batch_menu.addAction("Delete Selected from Disk")
            
            menu.addSeparator()
            menu.addMenu(batch_menu)
        
        # Show the menu and get the selected action
        action = menu.exec(position)
        
        # Process the selected action
        # (Implementation similar to the original ThumbnailBrowser)
        if action:
            # Handle individual actions
            if action == open_action:
                self.open_image(image_id)
            elif action == copy_action:
                self.copy_image_to_folder(image_id)
            elif action == generate_action:
                self.generate_description(image_id)
            elif action == edit_action:
                self.edit_description(image_id)
            elif action == delete_desc_action:
                self.delete_description(image_id)
            elif action == delete_db_action:
                self.delete_images([image_id], False)
            elif action == delete_disk_action:
                self.delete_images([image_id], True)
                
            # Handle batch operations if multiple thumbnails are selected
            elif len(self.selected_thumbnails) > 1 and image_id in self.selected_thumbnails:
                selected_ids = list(self.selected_thumbnails)
                
                if action == batch_copy_action:
                    self.copy_images_to_folder(selected_ids)
                elif action == batch_generate_action:
                    self.batch_generate_requested.emit(selected_ids)
                elif action == batch_delete_desc_action:
                    self.delete_descriptions(selected_ids)
                elif action == batch_delete_db_action:
                    self.delete_images(selected_ids, False)
                elif action == batch_delete_disk_action:
                    self.delete_images(selected_ids, True)
    
    # Implementation of context menu actions
    # (These methods would be similar to the original ThumbnailBrowser implementation)
    
    def open_image(self, image_id):
        """Open the original image using the system default application.
        
        Args:
            image_id (int): ID of the image to open
        """
        # Get image info
        image_info = self.db_manager.get_image_by_id(image_id)
        if not image_info:
            return
            
        # Get full path
        full_path = image_info.get('full_path')
        if not full_path or not os.path.exists(full_path):
            self.status_message.emit(f"Error: Image file not found at {full_path}")
            return
            
        # Open the image using the system default application
        try:
            logger.info(f"Opening image: {full_path}")
            
            # Open file with default application
            if os.name == 'nt':  # Windows
                os.startfile(full_path)
            else:
                subprocess.run(['open', full_path], check=True)
                
            self.status_message.emit(f"Opened image: {os.path.basename(full_path)}")
        except Exception as e:
            logger.error(f"Error opening image: {e}")
            self.status_message.emit(f"Error opening image: {e}")
    
    def copy_image_to_folder(self, image_id):
        """Copy the image to a selected folder.
        
        Args:
            image_id (int): ID of the image to copy
        """
        self.copy_images_to_folder([image_id])
    
    def copy_images_to_folder(self, image_ids):
        """Copy multiple images to a selected folder.
        
        Args:
            image_ids (list): List of image IDs to copy
        """
        if not image_ids:
            return
            
        # Get folder to copy to
        target_dir = QFileDialog.getExistingDirectory(
            self, "Select Target Folder",
            os.path.expanduser("~"),
            QFileDialog.Option.ShowDirsOnly
        )
        
        if not target_dir:
            return
            
        # Copy each image
        copied_count = 0
        error_count = 0
        
        for image_id in image_ids:
            # Get image info
            image_info = self.db_manager.get_image_by_id(image_id)
            if not image_info:
                error_count += 1
                continue
                
            # Get full path
            full_path = image_info.get('full_path')
            if not full_path or not os.path.exists(full_path):
                error_count += 1
                continue
                
            # Get filename
            filename = os.path.basename(full_path)
            target_path = os.path.join(target_dir, filename)
            
            # Handle filename conflicts
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(target_path):
                target_path = os.path.join(target_dir, f"{base_name}_{counter}{ext}")
                counter += 1
                
            # Copy the file
            try:
                import shutil
                shutil.copy2(full_path, target_path)
                copied_count += 1
            except Exception as e:
                logger.error(f"Error copying image: {e}")
                error_count += 1
        
        # Show status message
        self.status_message.emit(f"Copied {copied_count} images to {target_dir}" + 
                               (f", {error_count} errors" if error_count > 0 else ""))
    
    def generate_description(self, image_id):
        """Generate AI description for a single image.
        
        Args:
            image_id (int): ID of the image
        """
        # Emit signal for the main window to handle generation
        self.batch_generate_requested.emit([image_id])
    
    def edit_description(self, image_id):
        """Edit the description for an image.
        
        Args:
            image_id (int): ID of the image
        """
        # Get image info
        image_info = self.db_manager.get_image_by_id(image_id)
        if not image_info:
            return
            
        # Get current description
        current_description = image_info.get('user_description') or image_info.get('ai_description') or ""
        
        # Get new description from user
        new_description, ok = QInputDialog.getMultiLineText(
            self, "Edit Description", "Description:", current_description
        )
        
        if ok:
            # Update the description in the database
            result = self.db_manager.update_image_description(image_id, user_description=new_description)
            
            if result:
                # Update the thumbnail widget
                if image_id in self.thumbnails:
                    # Truncate description if too long
                    max_length = 100
                    display_text = new_description[:max_length] + "..." if len(new_description) > max_length else new_description
                    self.thumbnails[image_id].description_label.setText(display_text)
                    self.thumbnails[image_id].description_label.setToolTip(new_description)
                    self.thumbnails[image_id].description = new_description
                
                self.status_message.emit(f"Updated description for {image_info.get('filename', 'image')}")
            else:
                self.status_message.emit("Error updating description")
    
    def delete_description(self, image_id):
        """Delete the description for an image.
        
        Args:
            image_id (int): ID of the image
        """
        self.delete_descriptions([image_id])
    
    def delete_descriptions(self, image_ids):
        """Delete descriptions for multiple images.
        
        Args:
            image_ids (list): List of image IDs
        """
        if not image_ids:
            return
            
        # Confirm deletion
        num_images = len(image_ids)
        confirm = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete the descriptions for {num_images} image{'s' if num_images > 1 else ''}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # Delete descriptions
        success_count = 0
        error_count = 0
        
        for image_id in image_ids:
            # Update the database
            result = self.db_manager.update_image_description(image_id, ai_description="", user_description="")
            
            if result:
                success_count += 1
                
                # Update the thumbnail widget
                if image_id in self.thumbnails:
                    self.thumbnails[image_id].description_label.setText("")
                    self.thumbnails[image_id].description_label.setToolTip("")
                    self.thumbnails[image_id].description = ""
            else:
                error_count += 1
        
        # Show status message
        self.status_message.emit(f"Deleted {success_count} descriptions" + 
                               (f", {error_count} errors" if error_count > 0 else ""))
    
    def delete_images(self, image_ids, delete_from_disk=False):
        """Delete images from the database and optionally from disk.
        
        Args:
            image_ids (list): List of image IDs to delete
            delete_from_disk (bool): Whether to delete from disk as well
        """
        if not image_ids:
            return
            
        # Confirm deletion
        num_selected = len(image_ids)
        if delete_from_disk:
            message = f"Are you sure you want to PERMANENTLY DELETE {num_selected} image{'s' if num_selected > 1 else ''} from disk? This cannot be undone."
            title = "Confirm Permanent Deletion"
        else:
            message = f"Are you sure you want to remove {num_selected} image{'s' if num_selected > 1 else ''} from the database? The original files will remain on disk."
            title = "Confirm Database Removal"
        
        confirm = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        # Track statistics for status message
        deleted_count = 0
        disk_deleted_count = 0
        error_count = 0
        
        # Delete each selected image
        for image_id in image_ids:
            # Get image path first (we need it for disk deletion)
            image_info = self.db_manager.get_image_by_id(image_id)
            original_path = image_info.get("full_path") if image_info else None
            
            # Delete from database
            result = self.db_manager.delete_image(image_id)
            
            if result:
                deleted_count += 1
                
                # Remove thumbnail from UI
                if image_id in self.thumbnails:
                    # Note: The virtualized grid will handle removal automatically
                    # during the next refresh, so we just need to remove from our dictionary
                    del self.thumbnails[image_id]
                
                # Remove from selection
                self.selected_thumbnails.discard(image_id)
                
                # Delete from disk if requested
                if delete_from_disk and original_path and os.path.exists(original_path):
                    try:
                        os.remove(original_path)
                        disk_deleted_count += 1
                        logger.info(f"Deleted file from disk: {original_path}")
                    except Exception as e:
                        logger.error(f"Error deleting file from disk: {original_path} - {e}")
                        error_count += 1
            else:
                error_count += 1
        
        # Show status message
        if delete_from_disk:
            self.status_message.emit(f"Deleted {deleted_count} images from database, {disk_deleted_count} from disk" + 
                                   (f", {error_count} errors" if error_count > 0 else ""))
        else:
            self.status_message.emit(f"Deleted {deleted_count} images from database" + 
                                   (f", {error_count} errors" if error_count > 0 else ""))
        
        # Refresh display
        self.refresh()
    
    def refresh(self):
        """Refresh the thumbnail display."""
        if self.current_folder_id is not None:
            self.set_folder(self.current_folder_id)
        elif self.current_search_query is not None:
            self.search(self.current_search_query)
        else:
            self.clear_thumbnails()
