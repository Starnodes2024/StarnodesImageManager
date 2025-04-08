#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Thumbnail widget for StarImageBrowse
Represents a single thumbnail in the grid with its metadata
"""

import os
import re
import logging
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QSizePolicy, QApplication
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger("StarImageBrowse.ui.thumbnail_widget")

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
        self.pixmap = None
        
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
        if not self.thumbnail_path or not os.path.exists(self.thumbnail_path):
            # Set placeholder
            self.thumbnail_label.setText("No Thumbnail")
            return
            
        # Actual loading is done by the LazyThumbnailLoader
        self.thumbnail_label.setText("Loading...")
    
    def set_thumbnail(self, pixmap):
        """Set the thumbnail pixmap.
        
        Args:
            pixmap (QPixmap): The thumbnail pixmap to display, or None for error
        """
        if pixmap and not pixmap.isNull():
            self.pixmap = pixmap
            scaled_pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled_pixmap)
        else:
            self.thumbnail_label.setText("Error")
    
    def set_selected(self, selected):
        """Set the selected state of the thumbnail.
        
        Args:
            selected (bool): Whether the thumbnail is selected
        """
        if selected == self.selected:
            return
            
        self.selected = selected
        
        if selected:
            # Use a more obvious selection style with blue background
            # This is better than just a border because it's more visible
            self.setStyleSheet("""
                QFrame {
                    background-color: #E3F2FD;
                    border: 2px solid #2196F3;
                    border-radius: 4px;
                }
                QLabel {
                    background-color: transparent;
                }
            """)
        else:
            # Reset to default style
            self.setStyleSheet("")
    
    def highlight_search_terms(self, search_terms):
        """Highlight search terms in the description.
        
        Args:
            search_terms (str): Search terms to highlight
        """
        if not self.description or not search_terms:
            return
            
        # Escape special characters in search terms
        escaped_terms = re.escape(search_terms)
        
        # Split search terms into individual words
        terms = escaped_terms.split(r"\ ")
        
        # Create a copy of the description
        highlighted_text = self.description
        
        # Apply highlighting using HTML
        for term in terms:
            if term:
                # Case-insensitive search
                pattern = re.compile(f"({term})", re.IGNORECASE)
                highlighted_text = pattern.sub(r"<span style='background-color: yellow; color: black;'>\1</span>", highlighted_text)
        
        # Truncate with ellipsis if too long
        max_length = 100
        if len(highlighted_text) > max_length:
            # Find a good breaking point (space) near the limit
            break_point = highlighted_text.rfind(" ", 0, max_length)
            if break_point == -1:
                break_point = max_length
                
            display_text = highlighted_text[:break_point] + "..."
        else:
            display_text = highlighted_text
        
        # Set the highlighted text
        self.description_label.setText(display_text)
        self.description_label.setTextFormat(Qt.TextFormat.RichText)
        
        # Keep full description in tooltip
        self.description_label.setToolTip(self.description)
    
    def mousePressEvent(self, event):
        """Handle mouse press event.
        
        Args:
            event: Mouse event
        """
        super().mousePressEvent(event)
        
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.image_id)
    
    def mouseDoubleClickEvent(self, event):
        """Handle mouse double-click event.
        
        Args:
            event: Mouse event
        """
        super().mouseDoubleClickEvent(event)
        
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.image_id, self.thumbnail_path)
    
    def on_context_menu(self, point):
        """Handle context menu request.
        
        Args:
            point: Point where context menu was requested
        """
        # Convert to global coordinates
        global_point = self.mapToGlobal(point)
        
        # Emit signal with image_id and global position
        self.context_menu_requested.emit(self.image_id, global_point)
