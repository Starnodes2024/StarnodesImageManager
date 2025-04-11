#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Metadata panel UI component for StarImageBrowse
Displays detailed metadata for selected images.
"""

import os
import logging
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QFrame, QGridLayout, QSizePolicy,
    QTabWidget, QGroupBox, QFormLayout
)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot

logger = logging.getLogger("StarImageBrowse.ui.metadata_panel")

class MetadataPanel(QWidget):
    """Panel for displaying image metadata."""
    
    def __init__(self, db_manager, parent=None):
        """Initialize the metadata panel.
        
        Args:
            db_manager: Database manager instance
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.db_manager = db_manager
        self.current_image_id = None
        self.current_image_info = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the metadata panel UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header_label = QLabel("Image Metadata")
        header_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(header_label)
        
        # Scroll area for metadata content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(scroll_area)
        
        # Container widget for metadata
        self.container = QWidget()
        scroll_area.setWidget(self.container)
        
        # Container layout
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(10, 10, 10, 10)
        self.container_layout.setSpacing(10)
        
        # Empty space for when no image is selected
        self.no_selection_label = QLabel("")
        self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_selection_label.setStyleSheet("color: gray; font-style: italic;")
        self.container_layout.addWidget(self.no_selection_label)
        
        # Preview section removed as per user request - thumbnail is already visible in the browser
        
        # Basic info
        self.info_group = QGroupBox("Basic Information")
        self.info_layout = QFormLayout(self.info_group)
        
        self.filename_label = QLabel()
        self.info_layout.addRow("Filename:", self.filename_label)
        
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        self.info_layout.addRow("Path:", self.path_label)
        
        self.size_label = QLabel()
        self.info_layout.addRow("Size:", self.size_label)
        
        self.dimensions_label = QLabel()
        self.info_layout.addRow("Dimensions:", self.dimensions_label)
        
        self.format_label = QLabel()
        self.info_layout.addRow("Format:", self.format_label)
        
        self.date_added_label = QLabel()
        self.info_layout.addRow("Date Added:", self.date_added_label)
        
        self.last_modified_label = QLabel()
        self.info_layout.addRow("Last Modified:", self.last_modified_label)
        
        self.container_layout.addWidget(self.info_group)
        
        # Description group
        self.description_group = QGroupBox("Description")
        description_layout = QVBoxLayout(self.description_group)
        
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.description_label.setMinimumHeight(100)
        description_layout.addWidget(self.description_label)
        
        self.container_layout.addWidget(self.description_group)
        
        # Add stretch to push everything to the top
        self.container_layout.addStretch(1)
        
        # Initially hide all groups until an image is selected
        self.info_group.setVisible(False)
        self.description_group.setVisible(False)
        
        # Add no selection message
        self.no_selection_label = QLabel("No image selected")
        self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_selection_label.setStyleSheet("color: #666; font-style: italic;")
        self.container_layout.insertWidget(0, self.no_selection_label)
    
    def display_metadata(self, image_id):
        """Display metadata for the specified image.
        
        Args:
            image_id (int): ID of the image to display metadata for
        """
        if not image_id:
            self.clear_metadata()
            return
        
        # Get image info from database
        image_info = self.db_manager.get_image_by_id(image_id)
        if not image_info:
            logger.warning(f"No image found with ID: {image_id}")
            self.clear_metadata()
            return
        
        # Store current image info
        self.current_image_id = image_id
        self.current_image_info = image_info
        
        # Hide no selection message and show metadata groups
        self.no_selection_label.setVisible(False)
        self.no_selection_label.hide()  # Force hide with both methods
        self.info_group.setVisible(True)
        self.description_group.setVisible(True)
        
        # Force layout update to ensure message visibility changes are applied
        self.container.updateGeometry()
        self.container_layout.update()
        
        # Preview section removed as per user request - thumbnail is already visible in the browser
        
        # Update basic info
        self.filename_label.setText(image_info.get("filename", "Unknown"))
        self.path_label.setText(image_info.get("full_path", "Unknown"))
        
        # Get file size
        full_path = image_info.get("full_path")
        if full_path and os.path.exists(full_path):
            size_bytes = os.path.getsize(full_path)
            if size_bytes < 1024:
                size_str = f"{size_bytes} bytes"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            self.size_label.setText(size_str)
        else:
            self.size_label.setText("Unknown")
        
        # Update dimensions - try to get from the original file if not in database
        width = image_info.get("width")
        height = image_info.get("height")
        
        # If dimensions are not in the database, try to get them from the file
        if not (width and height) and full_path and os.path.exists(full_path):
            try:
                from PIL import Image
                with Image.open(full_path) as img:
                    width, height = img.size
                    logger.debug(f"Got dimensions from file: {width}×{height}")
            except Exception as e:
                logger.error(f"Error getting image dimensions from file: {e}")
        
        if width and height:
            self.dimensions_label.setText(f"{width} × {height} pixels")
        else:
            self.dimensions_label.setText("Unknown")
        
        # Update format - if not in database, try to get it from the file
        format_value = image_info.get("format")
        if not format_value and full_path and os.path.exists(full_path):
            try:
                from PIL import Image
                with Image.open(full_path) as img:
                    format_value = img.format
                    logger.debug(f"Got format from file: {format_value}")
            except Exception as e:
                logger.error(f"Error getting image format from file: {e}")
        
        self.format_label.setText(format_value or "Unknown")
        
        # Update dates
        date_added = image_info.get("date_added")
        if date_added:
            try:
                # Handle both string and datetime objects
                if isinstance(date_added, str):
                    date_obj = datetime.fromisoformat(date_added)
                else:
                    date_obj = date_added
                self.date_added_label.setText(date_obj.strftime("%Y-%m-%d %H:%M:%S"))
            except (ValueError, TypeError) as e:
                logger.error(f"Error formatting date_added: {e}")
                self.date_added_label.setText(str(date_added))
        else:
            self.date_added_label.setText("Unknown")
        
        last_modified = image_info.get("last_modified_date")
        if last_modified:
            try:
                # Handle both string and datetime objects
                if isinstance(last_modified, str):
                    date_obj = datetime.fromisoformat(last_modified)
                else:
                    date_obj = last_modified
                self.last_modified_label.setText(date_obj.strftime("%Y-%m-%d %H:%M:%S"))
            except (ValueError, TypeError) as e:
                logger.error(f"Error formatting last_modified_date: {e}")
                self.last_modified_label.setText(str(last_modified))
        else:
            # Try to get from file if available
            if full_path and os.path.exists(full_path):
                try:
                    mtime = os.path.getmtime(full_path)
                    date_obj = datetime.fromtimestamp(mtime)
                    self.last_modified_label.setText(date_obj.strftime("%Y-%m-%d %H:%M:%S"))
                except Exception as e:
                    logger.error(f"Error getting file modification time: {e}")
                    self.last_modified_label.setText("Unknown")
            else:
                self.last_modified_label.setText("Unknown")
        
        # Update description
        description = image_info.get("user_description") or image_info.get("ai_description")
        if description:
            self.description_label.setText(description)
            self.description_group.setVisible(True)
        else:
            self.description_label.setText("No description available")
            self.description_group.setVisible(True)
    
    def clear_metadata(self):
        """Clear all metadata and show the no selection message."""
        self.current_image_id = None
        self.current_image_info = None
        
        # Show no selection message and hide metadata groups
        self.no_selection_label.setVisible(True)
        self.info_group.setVisible(False)
        self.description_group.setVisible(False)
        
        # Force layout update to ensure message visibility changes are applied
        self.container.updateGeometry()
        self.container_layout.update()
        
        # Clear all fields
        self.filename_label.clear()
        self.path_label.clear()
        self.size_label.clear()
        self.dimensions_label.clear()
        self.format_label.clear()
        self.date_added_label.clear()
        self.last_modified_label.clear()
        self.description_label.clear()
    
    def refresh(self):
        """Refresh the current metadata display."""
        if self.current_image_id:
            self.display_metadata(self.current_image_id)
        else:
            self.clear_metadata()
