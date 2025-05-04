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
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

# Import the hover preview widget
from .hover_preview_widget import HoverPreviewWidget

logger = logging.getLogger("StarImageBrowse.ui.thumbnail_widget")

class ThumbnailWidget(QFrame):
    """Widget for displaying a single thumbnail with its metadata."""
    
    clicked = pyqtSignal(int)  # Signal emitted when thumbnail is clicked (image_id)
    double_clicked = pyqtSignal(int, str)  # Signal emitted when thumbnail is double-clicked (image_id, path)
    context_menu_requested = pyqtSignal(int, object)  # Signal emitted when context menu is requested (image_id, QPoint)
    
    # Shared preview widget for all thumbnails
    _hover_preview = None
    _hover_timer = None
    _hover_delay = 300  # milliseconds
    _max_preview_size = 700  # Default max preview size
    
    def __init__(self, image_id, thumbnail_path, filename, description=None, original_path=None, width=None, height=None, parent=None, language_manager=None):
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
            language_manager: Language manager instance for translations
        """
        super().__init__(parent)
        
        self.image_id = image_id
        self.thumbnail_path = thumbnail_path
        self.filename = filename
        self.description = description
        self.original_path = original_path
        self.selected = False
        self.pixmap = None
        self._deleted = False
        self._is_hovering = False
        self.language_manager = language_manager
        
        # Set image dimensions if provided (from database)
        if width is not None and height is not None:
            self.image_size = (width, height)
        else:
            self.image_size = None
        
        # Initialize preview if this is the first thumbnail
        if ThumbnailWidget._hover_preview is None:
            ThumbnailWidget._hover_preview = HoverPreviewWidget(language_manager=language_manager)
            
        # Initialize hover timer if this is the first thumbnail
        if ThumbnailWidget._hover_timer is None:
            ThumbnailWidget._hover_timer = QTimer()
            ThumbnailWidget._hover_timer.setSingleShot(True)
            
        # Enable mouse tracking for hover events
        self.setMouseTracking(True)
        
        self.setup_ui()
    
    def __del__(self):
        """Clean up resources when the widget is deleted."""
        self._deleted = True
        # Note: we don't attempt to disconnect signals in the destructor
        # as Qt will handle this automatically and attempts to do so
        # can lead to issues when the Python interpreter is shutting down
    
    def get_translation(self, key, default=None):
        """Get a translation for a key.
        
        Args:
            key (str): Key in the thumbnail section
            default (str, optional): Default value if translation not found
            
        Returns:
            str: Translated string or default value
        """
        if hasattr(self, 'language_manager') and self.language_manager:
            return self.language_manager.translate('thumbnail', key, default)
        return default
    
    def set_language_manager(self, language_manager):
        """Set the language manager for translations.
        
        Args:
            language_manager: Language manager instance
        """
        self.language_manager = language_manager
        # Update the hover preview widget if it exists
        if ThumbnailWidget._hover_preview:
            ThumbnailWidget._hover_preview.set_language_manager(language_manager)
    
    def setup_ui(self):
        """Set up the thumbnail widget UI."""
        # Set frame style
        self.setFrameShape(QFrame.Shape.Box)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setLineWidth(1)
        
        # Fixed size
        self.setFixedSize(220, 250)  # Reduced height to minimize space between elements
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Thumbnail image
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setMinimumSize(200, 200)
        # self.thumbnail_label.setMaximumSize(200, 200)
        
        # Load thumbnail image
        self.load_thumbnail()
        
        layout.addWidget(self.thumbnail_label)
        
        # Filename label
        self.filename_label = QLabel(self.filename.strip())
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setWordWrap(False)
        self.filename_label.setMaximumHeight(24)
        self.filename_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.filename_label)
        
        # Image size label
        self.size_label = QLabel()
        self.size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.size_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        # Match the filename's styling
        
        # Set image dimensions if available from database
        if self.image_size:
            width, height = self.image_size
            self.size_label.setText(f"{width} × {height}")
        # If dimensions not available from database, try to get them from the file
        elif self.original_path and os.path.exists(self.original_path):
            try:
                # Import PIL here to avoid dependency issues if not installed
                from PIL import Image
                with Image.open(self.original_path) as img:
                    width, height = img.size
                    # Store the dimensions for future use
                    self.image_size = (width, height)
                    self.size_label.setText(f"{width} × {height}")
                    logger.debug(f"Got dimensions from file for {self.filename}: {width}×{height}")
            except Exception as e:
                logger.error(f"Error getting image dimensions from file: {e}")
                self.size_label.setText(self.get_translation('dimensions_unknown', 'Dimensions unknown'))
                self.size_label.setStyleSheet("font-size: 9pt;")
        else:
            self.size_label.setText(self.get_translation('dimensions_unknown', 'Dimensions unknown'))
            # Make dimensions use the same style as the filename
            self.size_label.setStyleSheet("font-size: 9pt;")
            logger.debug(f"Using dimensions for {self.filename}: {self.size_label.text()}")
        
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
            # Set placeholder with translation
            self.thumbnail_label.setText(self.get_translation('no_thumbnail', 'No Thumbnail'))
            return
            
        # Actual loading is done by the LazyThumbnailLoader
        self.thumbnail_label.setText(self.get_translation('loading', 'Loading...'))
    
    def set_thumbnail(self, pixmap):
        """Set the thumbnail pixmap.
        
        Args:
            pixmap (QPixmap): The thumbnail pixmap to display, or None for error
        """
        # Safety check - ensure widget is still valid before proceeding
        # First check if the widget is marked as deleted
        if hasattr(self, '_deleted') and self._deleted:
            return
            
        try:
            # Check if widget is still visible and has necessary components
            if not self.isVisible() or not hasattr(self, 'thumbnail_label'):
                return
                
            self.pixmap = pixmap
            
            if pixmap and not pixmap.isNull():
                # Scale pixmap to fit in the thumbnail label
                scaled_pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.thumbnail_label.setPixmap(scaled_pixmap)
            else:
                # Use a default thumbnail or placeholder for missing images
                self.thumbnail_label.setText(self.get_translation('no_image', 'No image'))
        except RuntimeError:
            # Widget was deleted between our check and the attempt to update it
            pass
        except Exception as e:
            # Log other errors but don't crash
            import logging
            logger = logging.getLogger("StarImageBrowse.ui.thumbnail_widget")
            logger.debug(f"Error setting thumbnail: {str(e)}")
    
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
    
    def enterEvent(self, event):
        """Handle mouse enter event.
        
        Args:
            event: Mouse event
        """
        super().enterEvent(event)
        self._is_hovering = True
        
        # Start hover timer - safely disconnect any previous connections first
        try:
            # Only try to disconnect if there are connections
            ThumbnailWidget._hover_timer.timeout.disconnect()
        except (TypeError, RuntimeError):
            # If disconnect fails, it's because there were no connections yet
            pass
            
        # Connect and start the timer
        ThumbnailWidget._hover_timer.timeout.connect(self.show_preview)
        ThumbnailWidget._hover_timer.start(ThumbnailWidget._hover_delay)
    
    def leaveEvent(self, event):
        """Handle mouse leave event.
        
        Args:
            event: Mouse event
        """
        super().leaveEvent(event)
        self._is_hovering = False
        
        # Stop hover timer and hide preview
        ThumbnailWidget._hover_timer.stop()
        if ThumbnailWidget._hover_preview and ThumbnailWidget._hover_preview.isVisible():
            ThumbnailWidget._hover_preview.hide()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move event.
        
        Args:
            event: Mouse event
        """
        super().mouseMoveEvent(event)
        
        # Update preview position if it's visible
        if self._is_hovering and ThumbnailWidget._hover_preview and ThumbnailWidget._hover_preview.isVisible():
            global_pos = self.mapToGlobal(event.pos())
            ThumbnailWidget._hover_preview.show_at(global_pos)
    
    def show_preview(self):
        """Show the hover preview for this thumbnail."""
        if not self._is_hovering or self._deleted:
            return
            
        # Get the original image path
        image_path = self.original_path
        if not image_path or not os.path.exists(image_path):
            # If no original path or file doesn't exist, fallback to thumbnail
            image_path = self.thumbnail_path
            
        if image_path and os.path.exists(image_path):
            # Get the cursor position
            cursor_pos = self.mapToGlobal(self.rect().center())
            
            # Load the image and show preview
            if ThumbnailWidget._hover_preview.load_preview(image_path, ThumbnailWidget._max_preview_size):
                ThumbnailWidget._hover_preview.show_at(cursor_pos)
    
    @classmethod
    def set_preview_size(cls, size):
        """Set the maximum preview size for all thumbnails.
        
        Args:
            size (int): Maximum preview size in pixels
        """
        cls._max_preview_size = size
        if cls._hover_preview:
            # Update existing preview widget with new size
            cls._hover_preview.max_preview_size = size
    
    @classmethod
    def set_hover_delay(cls, delay):
        """Set the hover delay for previews.
        
        Args:
            delay (int): Hover delay in milliseconds
        """
        cls._hover_delay = delay
    

    
    def on_context_menu(self, point):
        """Handle context menu request.
        
        Args:
            point: Point where context menu was requested
        """
        # Convert to global coordinates
        global_point = self.mapToGlobal(point)
        
        # Emit signal with image_id and global position
        self.context_menu_requested.emit(self.image_id, global_point)
