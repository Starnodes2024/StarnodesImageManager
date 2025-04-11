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
    
    def __init__(self, image_id, thumbnail_path, filename, description=None, original_path=None, width=None, height=None, parent=None):
        """Initialize the thumbnail widget.
        
        Args:
            image_id (int): ID of the image
            thumbnail_path (str): Path to the thumbnail image
            filename (str): Original filename of the image
            description (str, optional): Description of the image
            original_path (str, optional): Path to the original image file
            width (int, optional): Width of the image in pixels
            height (int, optional): Height of the image in pixels
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.image_id = image_id
        self.thumbnail_path = thumbnail_path
        self.filename = filename
        self.description = description
        self.original_path = original_path
        self.selected = False
        self.pixmap = None
        
        # Set image dimensions if provided (from database)
        if width is not None and height is not None:
            self.image_size = (width, height)
        else:
            self.image_size = None
        
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
        
        # Image size label
        self.size_label = QLabel()
        self.size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Match the filename's styling
        
        # Set size text if available
        if self.image_size:
            width, height = self.image_size
            size_text = f"{width}×{height}"
            self.size_label.setText(size_text)
            # Make dimensions use the same style as the filename
            self.size_label.setStyleSheet("font-size: 9pt;")
            logger.debug(f"Using dimensions for {self.filename}: {size_text}")  # Changed to debug level
        else:
            # Don't try to open image files - just show that dimensions aren't available
            self.size_label.setText("Dimensions not available")
            self.size_label.setStyleSheet("font-size: 8pt; font-style: italic;")
            logger.debug(f"No dimensions available for {self.filename}")
        
        layout.addWidget(self.size_label)
        
        # We're completely removing description functionality to prevent flickering
        # This still preserves the dimensions display which was part of the Phase 3 requirements
        
        # Create a hidden description label to maintain API compatibility
        # but never show it or add it to the layout
        self.description_label = QLabel()
        self.description_label.setVisible(False)
        # Don't add it to the layout - this prevents any UI interaction that could cause flickering
        
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
        
        # Get app instance to access theme manager
        app = QApplication.instance()
        main_window = None
        theme_colors = {}
        
        # Try to get theme colors from the main window's theme manager
        if app:
            for widget in app.topLevelWidgets():
                if hasattr(widget, 'theme_manager'):
                    main_window = widget
                    theme = widget.theme_manager.get_current_theme()
                    if theme and 'colors' in theme:
                        if 'thumbnail' in theme['colors']:
                            theme_colors = theme['colors']['thumbnail']
                    break
        
        # Use theme colors if available, otherwise use defaults
        if selected:
            if theme_colors:
                background = theme_colors.get('selected', '#6c06a7')
                text_color = theme_colors.get('selectedText', 'white')
                border_color = theme_colors.get('selectedBorder', background)
            else:
                # Default purple theme
                background = '#6c06a7'
                text_color = 'white'
                border_color = background
                
            self.setStyleSheet(f"""
                QFrame {{ 
                    background-color: {background}; 
                    color: {text_color}; 
                    border-radius: 6px;
                    border: none;
                }}
                QLabel {{ 
                    color: {text_color}; 
                    background-color: transparent;
                    border: none !important;
                }}
            """)
        else:
            if theme_colors:
                background = theme_colors.get('background', 'transparent')
                text_color = theme_colors.get('text', 'black')
                border_color = theme_colors.get('border', '#e0e0e0')
            else:
                # Default clean theme
                background = 'transparent'
                text_color = 'black'
                border_color = '#e0e0e0'
                
            self.setStyleSheet(f"""
                QFrame {{ 
                    background-color: {background}; 
                    color: {text_color}; 
                    border: 1px solid {border_color};
                    border-radius: 6px;
                }}
                QLabel {{ 
                    color: {text_color}; 
                    background-color: transparent;
                    border: none !important;
                }}
            """)
    
    def highlight_search_terms(self, search_terms):
        """Highlight search terms in the description.
        
        This method has been disabled to prevent UI flickering.
        It now does nothing but is kept for API compatibility.
        
        Args:
            search_terms (str): Search terms to highlight (ignored)
        """
        # This is now a no-op function to avoid flickering
        # We've completely removed description functionality
        return
    
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
