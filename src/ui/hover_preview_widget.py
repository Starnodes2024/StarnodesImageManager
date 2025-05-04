#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hover preview widget for StarImageBrowse
Shows a large preview of images when hovering over thumbnails
"""

import os
import logging
import re
from PyQt6.QtWidgets import QLabel, QApplication, QFrame
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt

logger = logging.getLogger("StarImageBrowse.ui.hover_preview_widget")

class HoverPreviewWidget(QFrame):
    """Widget for displaying a larger preview on hover."""
    
    def __init__(self, parent=None, language_manager=None):
        """Initialize the hover preview widget.
        
        Args:
            parent (QWidget, optional): Parent widget
            language_manager: Language manager instance for translations
        """
        super().__init__(parent)
        
        # Store language manager
        self.language_manager = language_manager
        
        # Set up UI
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Use stylesheet for border, not QFrame border
        self.setObjectName("hoverPreviewWidget")
        
        # Create label for preview
        self.preview_label = QLabel(self)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setContentsMargins(0, 0, 0, 0)
        
        # Set maximum preview size (actual size will be set dynamically)
        self.max_preview_size = 700
        self.border_width = 4  # Border thickness in px
        # Initial minimal size; will be updated on image load
        self.setFixedSize(2 * self.border_width + 1, 2 * self.border_width + 1)
        self.preview_label.setFixedSize(1, 1)
        self.preview_label.move(self.border_width, self.border_width)
        
        # Initial invisible state
        self.hide()
        
        # Update theme colors
        self.update_theme()
    
    def update_theme(self):
        """Update widget with current theme colors."""
        app = QApplication.instance()
        main_window = None
        
        # Default border color - use the selected background color of thumbnails
        border_color = "#6c06a7"  # Purple default
        
        # Try to get theme colors from the main window's theme manager
        if app:
            for widget in app.topLevelWidgets():
                if hasattr(widget, 'theme_manager'):
                    main_window = widget
                    theme = widget.theme_manager.get_current_theme()
                    if theme and 'colors' in theme:
                        if 'thumbnail' in theme['colors']:
                            theme_colors = theme['colors']['thumbnail']
                            # Use the selected background color for the border
                            border_color = theme_colors.get('selected', border_color)
                    break
        
        # Validate color format
        if not re.match(r"^#[0-9a-fA-F]{6}$", border_color):
            border_color = "#6c06a7"  # Default fallback if invalid
        
        # Set frame style directly on the widget (no selector) for maximum reliability
        self.setStyleSheet(f"background-color: white; border: 4px solid {border_color}; border-radius: 0px;")
        
    def set_language_manager(self, language_manager):
        """Set the language manager for translations.
        
        Args:
            language_manager: Language manager instance
        """
        self.language_manager = language_manager
    
    def get_translation(self, key, default=None):
        """Get a translation for a key.
        
        Args:
            key (str): Key in the hover_preview section
            default (str, optional): Default value if translation not found
            
        Returns:
            str: Translated string or default value
        """
        if hasattr(self, 'language_manager') and self.language_manager:
            return self.language_manager.translate('hover_preview', key, default)
        return default
    
    def load_preview(self, image_path, max_size=None):
        """Load an image preview at the specified size.
        
        Args:
            image_path (str): Path to the original image file
            max_size (int, optional): Maximum size for the preview
        """
        if max_size is not None:
            self.max_preview_size = max_size
        # No fixed widget/label size here; will set after loading image
        
        try:
            if not os.path.exists(image_path):
                logger.warning(f"Image not found for preview: {image_path}")
                self.preview_label.setText(self.get_translation('image_not_found', 'Image not found'))
                return False
            
            # Load image
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                logger.warning(f"Failed to load image for preview: {image_path}")
                self.preview_label.setText(self.get_translation('failed_to_load', 'Failed to load image'))
                return False
            
            # Scale maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.max_preview_size,
                self.max_preview_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            # Get scaled image size
            img_width = scaled_pixmap.width()
            img_height = scaled_pixmap.height()
            # Set label and widget size to fit image plus border
            self.preview_label.setFixedSize(img_width, img_height)
            self.setFixedSize(img_width + 2 * self.border_width, img_height + 2 * self.border_width)
            self.preview_label.move(self.border_width, self.border_width)
            # Set the preview
            self.preview_label.setPixmap(scaled_pixmap)
            return True
            
        except Exception as e:
            logger.error(f"Error loading preview for {image_path}: {str(e)}")
            self.preview_label.setText(self.get_translation('error_loading', 'Error loading preview'))
            return False
    
    def show_at(self, global_pos, desktop_rect=None):
        """Show the preview at the specified position, adjusted to fit on screen.
        
        Args:
            global_pos (QPoint): Global position to show the preview at
            desktop_rect (QRect, optional): Available desktop area
        """
        # Get desktop rect if not provided
        if not desktop_rect:
            desktop_rect = QApplication.primaryScreen().availableGeometry()
        
        # Calculate position to ensure preview stays on screen
        preview_width = self.width()
        preview_height = self.height()
        
        # Try to show preview to the right of the cursor
        pos_x = global_pos.x() + 20
        pos_y = global_pos.y() - preview_height // 2
        
        # Adjust if would go off right edge
        if pos_x + preview_width > desktop_rect.right():
            # Show to the left of the cursor instead
            pos_x = global_pos.x() - 20 - preview_width
        
        # Ensure top edge is on screen
        if pos_y < desktop_rect.top():
            pos_y = desktop_rect.top() + 10
        
        # Ensure bottom edge is on screen
        if pos_y + preview_height > desktop_rect.bottom():
            pos_y = desktop_rect.bottom() - preview_height - 10
        
        # Move to calculated position and show
        self.move(pos_x, pos_y)
        self.show()
