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

logger = logging.getLogger("StarImageBrowse.ui.thumbnail_browser")

class ThumbnailWidget(QFrame):
    """Widget for displaying a single thumbnail with its metadata."""
    
    clicked = pyqtSignal(int)  # Signal emitted when thumbnail is clicked (image_id)
    double_clicked = pyqtSignal(int, str)  # Signal emitted when thumbnail is double-clicked (image_id, path)
    context_menu_requested = pyqtSignal(int, object)  # Signal emitted when context menu is requested (image_id, QPoint)
    
    def __init__(self, image_id, thumbnail_path, filename, description=None, parent=None):
        """Initialize the thumbnail widget.
        
        Args:
            image_id (int): ID of the image
            thumbnail_path (str): Path to the thumbnail image
            filename (str): Original filename of the image
            description (str, optional): Description of the image
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.image_id = image_id
        self.thumbnail_path = thumbnail_path
        self.filename = filename
        self.description = description
        self.selected = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the thumbnail widget UI."""
        # Set frame style
        self.setFrameShape(QFrame.Shape.Box)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setLineWidth(1)
        
        # Fixed size
        self.setFixedSize(220, 300)  # Increased height to accommodate description
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Thumbnail image
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setMinimumSize(200, 200)
        self.thumbnail_label.setMaximumSize(200, 200)
        
        # Load thumbnail image
        self.load_thumbnail()
        
        layout.addWidget(self.thumbnail_label)
        
        # Filename label
        self.filename_label = QLabel(self.filename)
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setWordWrap(True)
        self.filename_label.setMaximumHeight(40)
        layout.addWidget(self.filename_label)
        
        # Description label (truncated with ellipsis)
        self.description_label = QLabel()
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.description_label.setWordWrap(True)
        self.description_label.setMaximumHeight(60)
        self.description_label.setStyleSheet("font-size: 9pt; color: #666;")
        
        # Set description text (with truncation)
        if self.description:
            # Truncate description if too long
            max_length = 100
            display_text = self.description[:max_length] + "..." if len(self.description) > max_length else self.description
            self.description_label.setText(display_text)
            self.description_label.setToolTip(self.description)  # Full description on hover
        
        layout.addWidget(self.description_label)
        
        # Enable context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu)
    
    def load_thumbnail(self):
        """Load the thumbnail image."""
        # Show loading placeholder initially
        self.thumbnail_label.setText("Loading...")
        
        # The actual loading will be done by the LazyThumbnailLoader
        # This method is now just setting up the initial state
    
    def set_thumbnail(self, pixmap):
        """Set the thumbnail pixmap.
        
        Args:
            pixmap (QPixmap): The thumbnail pixmap to display, or None for error
        """
        if pixmap and not pixmap.isNull():
            self.thumbnail_label.setPixmap(pixmap)
        else:
            # Display placeholder for missing image
            self.thumbnail_label.setText("No Image")
    
    def set_selected(self, selected):
        """Set the selected state of the thumbnail.
        
        Args:
            selected (bool): Whether the thumbnail is selected
        """
        self.selected = selected
        
        if selected:
            # Purple background with white text for better readability
            self.setStyleSheet("""
                ThumbnailWidget { 
                    background-color: #6c06a7; 
                    color: white; 
                }
                QLabel { 
                    color: white; 
                }
            """)
        else:
            # Reset to default style
            self.setStyleSheet("""
                ThumbnailWidget { 
                    background-color: none; 
                    color: black; 
                }
                QLabel { 
                    color: black; 
                }
            """)
    
    def highlight_search_terms(self, search_terms):
        """Highlight search terms in the description.
        
        Args:
            search_terms (str): Search terms to highlight
        """
        if not self.description or not search_terms:
            return
        
        # Split search terms and filter out empty strings
        terms = [term.strip() for term in search_terms.split() if term.strip()]
        
        if not terms:
            return
        
        # Create a copy of the description for highlighting
        highlighted_text = self.description
        
        # Truncate description if too long
        max_length = 100
        display_text = highlighted_text
        truncated = False
        
        # Find the first match position to ensure we show relevant part
        first_match_pos = float('inf')
        for term in terms:
            pos = highlighted_text.lower().find(term.lower())
            if pos != -1 and pos < first_match_pos:
                first_match_pos = pos
        
        # If we found a match and it's beyond our display limit
        if first_match_pos != float('inf'):
            # Start a bit before the match for context
            start_pos = max(0, first_match_pos - 20)
            if start_pos > 0:
                display_text = "..." + highlighted_text[start_pos:]
                truncated = True
        
        # Truncate the end if still too long
        if len(display_text) > max_length:
            display_text = display_text[:max_length] + "..."
            truncated = True
        
        # Apply HTML highlighting for each term
        html_text = display_text
        for term in terms:
            # Case-insensitive replacement with HTML highlighting
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            html_text = pattern.sub(f'<span style="background-color: #FFFF66; color: black;">\g<0></span>', html_text)
        
        # Set the highlighted text
        self.description_label.setText(html_text)
        self.description_label.setTextFormat(Qt.TextFormat.RichText)
        
        # Set tooltip to show full description
        if truncated or len(self.description) > max_length:
            self.description_label.setToolTip(self.description)
    
    def mousePressEvent(self, event):
        """Handle mouse press event.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.image_id)
        
        super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """Handle mouse double-click event.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.image_id, self.thumbnail_path)
        
        super().mouseDoubleClickEvent(event)
    
    def on_context_menu(self, point):
        """Handle context menu request.
        
        Args:
            point: Point where context menu was requested
        """
        self.context_menu_requested.emit(self.image_id, self.mapToGlobal(point))


class ThumbnailBrowser(QWidget):
    """Browser for displaying image thumbnails."""
    
    thumbnail_selected = pyqtSignal(int)  # Signal emitted when a thumbnail is selected
    thumbnail_double_clicked = pyqtSignal(int, str)  # Signal emitted when a thumbnail is double-clicked
    batch_generate_requested = pyqtSignal(list)  # Signal emitted to request batch description generation
    status_message = pyqtSignal(str)  # Signal emitted to display status messages
    
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
        self.thumbnails = {}  # Dictionary of thumbnail widgets by image_id
        self.selected_thumbnails = set()  # Set of selected thumbnail image_ids
        
        # Initialize lazy thumbnail loader
        # Determine optimal number of concurrent threads based on CPU cores
        max_concurrent = min(4, QThreadPool.globalInstance().maxThreadCount())
        self.thumbnail_loader = LazyThumbnailLoader(max_concurrent=max_concurrent)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the thumbnail browser UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Header with information
        self.header_label = QLabel("No folder selected")
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
        images = self.db_manager.get_images_for_folder(folder_id, limit=1000)
        
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
        images = self.db_manager.search_images(query, limit=1000)
        
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
            thumbnail = ThumbnailWidget(
                image_id=image["image_id"],
                thumbnail_path=image["thumbnail_path"],
                filename=image["filename"],
                description=image.get("ai_description") or image.get("user_description")
            )
            
            # Connect signals
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
        # Clear selection
        self.selected_thumbnails.clear()
        
        # Cancel any pending thumbnail loads
        self.thumbnail_loader.cancel_pending()
        
        # Remove all thumbnails from the grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Clear thumbnail references
        self.thumbnails.clear()
        
        # Clear thumbnail cache if we have a lot of thumbnails
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
        copy_action = menu.addAction(f"Copy to folder... ({num_selected} selected)" if num_selected > 1 else "Copy to folder...")
        open_action = menu.addAction(f"Open ({num_selected} selected)" if num_selected > 1 else "Open")
        locate_action = menu.addAction(f"Locate on disk ({num_selected} selected)" if num_selected > 1 else "Locate on disk")
        copy_image_action = menu.addAction(f"Copy image to clipboard ({num_selected} selected)" if num_selected > 1 else "Copy image to clipboard")
        
        # Add description-related actions
        menu.addSeparator()
        edit_action = menu.addAction(f"Edit description ({num_selected} selected)" if num_selected > 1 else "Edit description")
        generate_desc_action = menu.addAction(f"Generate AI description ({num_selected} selected)" if num_selected > 1 else "Generate AI description")
        delete_desc_action = menu.addAction(f"Delete description ({num_selected} selected)" if num_selected > 1 else "Delete description")
        
        # Add delete action with separator
        menu.addSeparator()
        delete_action = menu.addAction(f"Delete image ({num_selected} selected)" if num_selected > 1 else "Delete image")
        
        # Show menu and get selected action
        action = menu.exec(position)
        
        # Handle selected action
        if action == copy_action:
            self.copy_selected_images()
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
        elif action == delete_action:
            self.delete_selected_images()
    
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
            
        # Create progress dialog
        from .progress_dialog import ProgressDialog
        operation_type = "Exporting" if export_mode else "Copying"
        progress_dialog = ProgressDialog(
            f"{operation_type} Images",
            f"{operation_type} {len(images_to_copy)} images to {dest_folder}...",
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
                images=images_to_copy,
                destination=dest_folder,
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
        
        import subprocess
            
        # Open each selected image with the default program
        for image_id in self.selected_thumbnails:
            try:
                # Get image information from database
                image_info = self.db_manager.get_image_by_id(image_id)
                
                if not image_info or 'full_path' not in image_info:
                    continue
                    
                image_path = image_info.get('full_path')
                
                # Check if file exists
                if not os.path.exists(image_path):
                    logger.warning(f"File not found: {image_path}")
                    continue
                
                # Open with default application
                if os.name == 'nt':  # Windows
                    os.startfile(image_path)
                else:  # Linux/Mac
                    subprocess.call(['xdg-open', image_path])
                    
            except Exception as e:
                logger.error(f"Error opening image {image_id}: {e}")
    
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
    
    def delete_selected_descriptions(self):
        """Delete descriptions for selected images."""
        if not self.selected_thumbnails:
            return
            
        # Confirm deletion
        num_selected = len(self.selected_thumbnails)
        confirm = QMessageBox.question(
            self, "Confirm Delete Description", 
            f"Are you sure you want to delete the description{'s' if num_selected > 1 else ''} for {num_selected} selected image{'s' if num_selected > 1 else ''}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        # Delete descriptions for each selected image
        for image_id in list(self.selected_thumbnails):
            # Clear both AI and user descriptions
            self.db_manager.update_image_description(image_id, ai_description="", user_description="")
            
        # Refresh the display to show the changes
        self.refresh()
        
        # Show confirmation message
        self.status_message.emit(f"Description{'s' if num_selected > 1 else ''} deleted for {num_selected} image{'s' if num_selected > 1 else ''}")
    
    def locate_selected_images_on_disk(self):
        """Open file explorer showing the location of the selected images."""
        if not self.selected_thumbnails:
            return
            
        import subprocess
        
        # Open location for each selected image
        for image_id in self.selected_thumbnails:
            try:
                # Get image information from database
                image_info = self.db_manager.get_image_by_id(image_id)
                
                if not image_info or 'full_path' not in image_info:
                    continue
                    
                image_path = image_info.get('full_path')
                
                # Check if file exists
                if not os.path.exists(image_path):
                    logger.warning(f"File not found: {image_path}")
                    continue
                
                # Make sure we have an absolute path
                absolute_path = os.path.abspath(image_path)
                logger.info(f"Attempting to locate image: {absolute_path}")
                
                # Open file explorer with file selected
                if os.name == 'nt':  # Windows
                    try:
                        # Use shell=True approach with properly quoted path
                        cmd = f'explorer /select,"{absolute_path}"'
                        logger.info(f"Running command: {cmd}")
                        subprocess.run(cmd, shell=True)
                    except Exception as e:
                        logger.error(f"Error with explorer command: {e}")
                        # Fallback to opening the containing folder
                        folder_path = os.path.dirname(absolute_path)
                        logger.info(f"Falling back to opening folder: {folder_path}")
                        subprocess.run(["explorer", folder_path])
                else:  # Linux/Mac
                    # Open the containing folder
                    folder_path = os.path.dirname(absolute_path)
                    subprocess.call(['xdg-open', folder_path])
                    
            except Exception as e:
                logger.error(f"Error locating image {image_id} on disk: {e}")
    
    def copy_selected_images_to_clipboard(self):
        """Copy selected image(s) to the clipboard."""
        if not self.selected_thumbnails:
            return
            
        from PyQt6.QtGui import QImage, QPixmap
        from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
        
        # We can only copy one image to clipboard
        # If multiple are selected, use the first one
        image_id = next(iter(self.selected_thumbnails))
        
        try:
            # Get image information from database
            image_info = self.db_manager.get_image_by_id(image_id)
            
            if not image_info or 'full_path' not in image_info:
                return
                
            image_path = image_info.get('full_path')
            
            # Check if file exists
            if not os.path.exists(image_path):
                logger.warning(f"File not found: {image_path}")
                return
            
            # Load the image
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Get the application clipboard
                clipboard = QApplication.clipboard()
                # Set the pixmap as the clipboard content
                clipboard.setPixmap(pixmap)
                logger.info(f"Copied image {image_id} to clipboard")
                
                # Show status message via main application
                message = "First selected image copied to clipboard" if len(self.selected_thumbnails) > 1 else "Image copied to clipboard"
                logger.info(message)
                try:
                    # Use signal if connected, otherwise just log
                    self.status_message.emit(message)
                except Exception:
                    # Signal might not be connected yet
                    pass
            else:
                error_msg = f"Error loading image {image_id} for clipboard"
                logger.error(error_msg)
                try:
                    self.status_message.emit("Error copying image to clipboard")
                except Exception:
                    pass
                
        except Exception as e:
            error_msg = f"Error copying image {image_id} to clipboard: {e}"
            logger.error(error_msg)
            try:
                self.status_message.emit(f"Error copying image to clipboard")
            except Exception:
                pass
        
        # Refresh display
        self.refresh()
    
    def delete_selected_images(self):
        """Delete selected images."""
        if not self.selected_thumbnails:
            return
        
        # Confirm deletion
        num_selected = len(self.selected_thumbnails)
        confirm = QMessageBox.question(
            self, "Confirm Delete", 
            f"Are you sure you want to delete {num_selected} selected image{'s' if num_selected > 1 else ''}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        # Delete each selected image
        for image_id in list(self.selected_thumbnails):
            result = self.db_manager.delete_image(image_id)
            
            if result and result.get("success"):
                # Remove thumbnail from UI
                if image_id in self.thumbnails:
                    thumbnail = self.thumbnails[image_id]
                    self.grid_layout.removeWidget(thumbnail)
                    thumbnail.deleteLater()
                    del self.thumbnails[image_id]
                
                # Remove from selection
                self.selected_thumbnails.discard(image_id)
                
                # TODO: Handle physical deletion of images if needed
        
        # Refresh display
        self.refresh()
        
    def generate_descriptions_for_selected(self):
        """Generate AI descriptions for selected images."""
        if not self.selected_thumbnails:
            return
            
        # Emit signal for the main window to handle generation
        # This will be connected to the batch generate descriptions method
        self.batch_generate_requested.emit(list(self.selected_thumbnails))
    
    def refresh(self):
        """Refresh the thumbnail display."""
        if self.current_folder_id is not None:
            self.set_folder(self.current_folder_id)
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
        
        # Refresh layout if we have thumbnails
        if self.thumbnails:
            self.refresh()
