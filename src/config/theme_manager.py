#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Theme manager for StarImageBrowse
Handles loading and applying UI themes from JSON files
"""

import os
import json
import logging
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger("StarImageBrowse.config.theme_manager")

class ThemeManager(QObject):
    """Manager for application themes from JSON files."""
    
    theme_changed = pyqtSignal(str)  # Signal emitted when the theme changes
    
    def __init__(self, config_manager=None):
        """Initialize the theme manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        super().__init__()
        self.config_manager = config_manager
        self.themes = {}  # {theme_id: theme_data}
        self.current_theme_id = None
        self.designs_dir = None
        
        # Default theme ID in case no theme is loaded
        self.default_theme_id = "light"
    
    def initialize(self, app_dir=None):
        """Initialize the theme manager and load themes.
        
        Args:
            app_dir (str, optional): Application directory. If None, uses the current directory
            
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            # Set designs directory
            if app_dir:
                self.designs_dir = os.path.join(app_dir, "designs")
            else:
                # Try to find designs folder relative to current file
                current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                self.designs_dir = os.path.join(current_dir, "designs")
            
            # Create designs directory if it doesn't exist
            os.makedirs(self.designs_dir, exist_ok=True)
            
            # Load themes
            self._load_themes()
            
            # Get current theme from config or use default
            if self.config_manager:
                self.current_theme_id = self.config_manager.get("ui", "theme", self.default_theme_id)
            else:
                self.current_theme_id = self.default_theme_id
            
            # Apply current theme
            self.apply_theme(self.current_theme_id)
            
            return True
        except Exception as e:
            logger.error(f"Error initializing theme manager: {e}")
            return False
    
    def _load_themes(self):
        """Load themes from the designs directory."""
        try:
            logger.info(f"Loading themes from {self.designs_dir}")
            self.themes = {}
            
            # Check if the directory exists
            if not os.path.exists(self.designs_dir):
                logger.warning(f"Designs directory not found: {self.designs_dir}")
                return
            
            # Get all JSON files in the designs directory
            theme_files = [f for f in os.listdir(self.designs_dir) if f.endswith('.json')]
            
            if not theme_files:
                logger.warning("No theme files found")
                return
            
            # Load each theme file
            for theme_file in theme_files:
                try:
                    theme_path = os.path.join(self.designs_dir, theme_file)
                    with open(theme_path, 'r', encoding='utf-8') as f:
                        theme_data = json.load(f)
                    
                    # Use the filename without extension as the theme ID
                    theme_id = os.path.splitext(theme_file)[0]
                    
                    # Add theme to the collection
                    self.themes[theme_id] = theme_data
                    logger.info(f"Loaded theme: {theme_data.get('name', theme_id)}")
                except Exception as e:
                    logger.error(f"Error loading theme {theme_file}: {e}")
            
            logger.info(f"Loaded {len(self.themes)} themes")
        except Exception as e:
            logger.error(f"Error loading themes: {e}")
    
    def get_theme_list(self):
        """Get a list of available themes.
        
        Returns:
            list: List of theme dictionaries with id and name
        """
        return [
            {
                "id": theme_id,
                "name": theme_data.get("name", theme_id)
            }
            for theme_id, theme_data in self.themes.items()
        ]
    
    def get_theme(self, theme_id):
        """Get a theme by ID.
        
        Args:
            theme_id (str): ID of the theme to get
            
        Returns:
            dict: Theme data or None if not found
        """
        return self.themes.get(theme_id)
    
    def get_current_theme(self):
        """Get the current theme.
        
        Returns:
            dict: Current theme data
        """
        return self.get_theme(self.current_theme_id)
    
    def apply_theme(self, theme_id):
        """Apply a theme to the application.
        
        Args:
            theme_id (str): ID of the theme to apply
            
        Returns:
            bool: True if theme was applied, False otherwise
        """
        try:
            # Get the theme data
            theme_data = self.get_theme(theme_id)
            
            if not theme_data:
                logger.warning(f"Theme not found: {theme_id}")
                
                # Try to use default theme as fallback
                if theme_id != self.default_theme_id:
                    logger.info(f"Falling back to default theme: {self.default_theme_id}")
                    return self.apply_theme(self.default_theme_id)
                
                return False
            
            # Create a stylesheet based on the theme
            stylesheet = self._create_stylesheet(theme_data)
            
            # Apply the stylesheet to the application
            app = QApplication.instance()
            if app:
                app.setStyleSheet(stylesheet)
                logger.info(f"Applied theme: {theme_data.get('name', theme_id)}")
            else:
                logger.warning("No QApplication instance found")
            
            # Update current theme
            self.current_theme_id = theme_id
            
            # Save current theme to config
            if self.config_manager:
                self.config_manager.set("ui", "theme", theme_id)
                self.config_manager.save()
            
            # Emit theme changed signal
            self.theme_changed.emit(theme_id)
            
            return True
        except Exception as e:
            logger.error(f"Error applying theme {theme_id}: {e}")
            return False
    
    def _create_stylesheet(self, theme_data):
        """Create a stylesheet based on the theme data.
        
        Args:
            theme_data (dict): Theme data
            
        Returns:
            str: Stylesheet string
        """
        try:
            colors = theme_data.get("colors", {})
            fonts = theme_data.get("fonts", {})
            
            # Build the stylesheet based on theme colors and fonts
            stylesheet = []
            
            # Global styles
            global_style = f"""
                /* Global styles */
                QWidget {{
                    background-color: {colors.get('window', {}).get('background', '#f5f5f5')};
                    color: {colors.get('window', {}).get('text', '#333333')};
                    font-family: {fonts.get('main', {}).get('family', 'Segoe UI')};
                    font-size: {fonts.get('main', {}).get('size', 10)}pt;
                }}
            """
            stylesheet.append(global_style)
            
            # Menu bar
            if "menuBar" in colors:
                menu_style = f"""
                    QMenuBar {{
                        background-color: {colors['menuBar'].get('background', '#f0f0f0')};
                        color: {colors['menuBar'].get('text', '#333333')};
                        border-bottom: 1px solid {colors['menuBar'].get('border', '#d0d0d0')};
                    }}
                    
                    QMenuBar::item {{
                        background-color: transparent;
                    }}
                    
                    QMenuBar::item:selected {{
                        background-color: {colors['menuBar'].get('hover', '#e0e0e0')};
                    }}
                    
                    QMenu {{
                        background-color: {colors['menuBar'].get('background', '#f0f0f0')};
                        color: {colors['menuBar'].get('text', '#333333')};
                        border: 1px solid {colors['menuBar'].get('border', '#d0d0d0')};
                    }}
                    
                    QMenu::item:selected {{
                        background-color: {colors['menuBar'].get('hover', '#e0e0e0')};
                    }}
                """
                stylesheet.append(menu_style)
            
            # Toolbar
            if "toolbar" in colors:
                toolbar_style = f"""
                    QToolBar {{
                        background-color: {colors['toolbar'].get('background', '#f0f0f0')};
                        color: {colors['toolbar'].get('text', '#333333')};
                        border-bottom: 1px solid {colors['toolbar'].get('border', '#d0d0d0')};
                        spacing: 5px;
                    }}
                    
                    QToolButton {{
                        background-color: transparent;
                        color: {colors['toolbar'].get('text', '#333333')};
                        border: none;
                        padding: 5px;
                    }}
                    
                    QToolButton:hover {{
                        background-color: {colors['toolbar'].get('hover', '#e0e0e0')};
                    }}
                    
                    QToolButton:pressed {{
                        background-color: {colors['toolbar'].get('border', '#d0d0d0')};
                    }}
                """
                stylesheet.append(toolbar_style)
            
            # Panels (folder, search, metadata)
            if "panel" in colors:
                panel_style = f"""
                    QFrame, QWidget#left_panel, QWidget#right_panel {{
                        background-color: {colors['panel'].get('background', '#ffffff')};
                        color: {colors['panel'].get('text', '#333333')};
                        border: 1px solid {colors['panel'].get('border', '#d0d0d0')};
                    }}
                    
                    QLabel {{
                        background-color: transparent;
                        color: {colors['panel'].get('text', '#333333')};
                        border: none;
                    }}
                    
                    QHeaderView::section {{
                        background-color: {colors['panel'].get('header', '#e5e5e5')};
                        color: {colors['panel'].get('text', '#333333')};
                        border: 1px solid {colors['panel'].get('border', '#d0d0d0')};
                        padding: 5px;
                    }}
                """
                stylesheet.append(panel_style)
            
            # Thumbnail browser
            if "thumbnail" in colors:
                thumbnail_style = f"""
                    ThumbnailWidget {{
                        background-color: {colors['thumbnail'].get('background', '#ffffff')};
                        color: {colors['thumbnail'].get('text', '#333333')};
                        border: 1px solid {colors['thumbnail'].get('border', '#d0d0d0')};
                    }}
                    
                    ThumbnailWidget[selected="true"] {{
                        background-color: {colors['thumbnail'].get('selected', '#e6f2ff')};
                        color: {colors['thumbnail'].get('selectedText', '#333333')};
                        border: 1px solid {colors['thumbnail'].get('border', '#d0d0d0')};
                    }}
                    
                    ThumbnailWidget QLabel {{
                        color: {colors['thumbnail'].get('text', '#333333')};
                    }}
                    
                    ThumbnailWidget QLabel#description_label {{
                        color: {colors['thumbnail'].get('textSecondary', '#666666')};
                    }}
                """
                stylesheet.append(thumbnail_style)
            
            # Buttons
            if "button" in colors:
                button_style = f"""
                    QPushButton {{
                        background-color: {colors['button'].get('background', '#f0f0f0')};
                        color: {colors['button'].get('text', '#333333')};
                        border: 1px solid {colors['button'].get('border', '#c0c0c0')};
                        border-radius: 3px;
                        padding: 5px 10px;
                        font-family: {fonts.get('button', {}).get('family', 'Segoe UI')};
                        font-size: {fonts.get('button', {}).get('size', 10)}pt;
                    }}
                    
                    QPushButton:hover {{
                        background-color: {colors['button'].get('hover', '#e0e0e0')};
                    }}
                    
                    QPushButton:pressed {{
                        background-color: {colors['button'].get('pressed', '#d0d0d0')};
                    }}
                    
                    QPushButton:disabled {{
                        background-color: {colors['button'].get('background', '#f0f0f0')};
                        color: #aaaaaa;
                        border: 1px solid #d0d0d0;
                    }}
                """
                stylesheet.append(button_style)
            
            # Input fields
            if "input" in colors:
                input_style = f"""
                    QLineEdit, QTextEdit, QPlainTextEdit {{
                        background-color: {colors['input'].get('background', '#ffffff')};
                        color: {colors['input'].get('text', '#333333')};
                        border: 1px solid {colors['input'].get('border', '#c0c0c0')};
                        border-radius: 3px;
                        padding: 3px;
                        selection-background-color: {colors['input'].get('focus', '#a0c8f0')};
                    }}
                    
                    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
                        border: 1px solid {colors['input'].get('focus', '#a0c8f0')};
                    }}
                    
                    QComboBox {{
                        background-color: {colors['input'].get('background', '#ffffff')};
                        color: {colors['input'].get('text', '#333333')};
                        border: 1px solid {colors['input'].get('border', '#c0c0c0')};
                        border-radius: 3px;
                        padding: 3px;
                    }}
                    
                    QComboBox::drop-down {{
                        subcontrol-origin: padding;
                        subcontrol-position: center right;
                        width: 20px;
                        border-left: 1px solid {colors['input'].get('border', '#c0c0c0')};
                    }}
                    
                    QComboBox QAbstractItemView {{
                        background-color: {colors['input'].get('background', '#ffffff')};
                        color: {colors['input'].get('text', '#333333')};
                        border: 1px solid {colors['input'].get('border', '#c0c0c0')};
                        selection-background-color: {colors['input'].get('focus', '#a0c8f0')};
                    }}
                """
                stylesheet.append(input_style)
            
            # Scroll bars
            if "scrollBar" in colors:
                scroll_style = f"""
                    QScrollBar:vertical {{
                        background-color: {colors['scrollBar'].get('background', '#f0f0f0')};
                        width: 12px;
                        margin: 0px;
                    }}
                    
                    QScrollBar::handle:vertical {{
                        background-color: {colors['scrollBar'].get('handle', '#c0c0c0')};
                        min-height: 20px;
                        border-radius: 6px;
                    }}
                    
                    QScrollBar::handle:vertical:hover {{
                        background-color: {colors['scrollBar'].get('handleHover', '#a0a0a0')};
                    }}
                    
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                        height: 0px;
                    }}
                    
                    QScrollBar:horizontal {{
                        background-color: {colors['scrollBar'].get('background', '#f0f0f0')};
                        height: 12px;
                        margin: 0px;
                    }}
                    
                    QScrollBar::handle:horizontal {{
                        background-color: {colors['scrollBar'].get('handle', '#c0c0c0')};
                        min-width: 20px;
                        border-radius: 6px;
                    }}
                    
                    QScrollBar::handle:horizontal:hover {{
                        background-color: {colors['scrollBar'].get('handleHover', '#a0a0a0')};
                    }}
                    
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                        width: 0px;
                    }}
                """
                stylesheet.append(scroll_style)
            
            # Status bar
            if "statusBar" in colors:
                status_style = f"""
                    QStatusBar {{
                        background-color: {colors['statusBar'].get('background', '#f0f0f0')};
                        color: {colors['statusBar'].get('text', '#333333')};
                        border-top: 1px solid {colors['statusBar'].get('border', '#d0d0d0')};
                    }}
                    
                    QStatusBar QLabel {{
                        background-color: transparent;
                        color: {colors['statusBar'].get('text', '#333333')};
                        font-family: {fonts.get('statusBar', {}).get('family', 'Segoe UI')};
                        font-size: {fonts.get('statusBar', {}).get('size', 9)}pt;
                    }}
                """
                stylesheet.append(status_style)
            
            # Dialog
            if "dialog" in colors:
                dialog_style = f"""
                    QDialog {{
                        background-color: {colors['dialog'].get('background', '#ffffff')};
                        color: {colors['dialog'].get('text', '#333333')};
                        border: 1px solid {colors['dialog'].get('border', '#d0d0d0')};
                    }}
                    
                    QDialog QLabel {{
                        background-color: transparent;
                        color: {colors['dialog'].get('text', '#333333')};
                    }}
                    
                    QDialog QGroupBox {{
                        font-weight: bold;
                        font-size: {fonts.get('header', {}).get('size', 12)}pt;
                    }}
                """
                stylesheet.append(dialog_style)
            
            # Progress bar
            if "progressBar" in colors:
                progress_style = f"""
                    QProgressBar {{
                        background-color: {colors['progressBar'].get('background', '#f0f0f0')};
                        color: {colors['progressBar'].get('text', '#ffffff')};
                        border: 1px solid {colors.get('window', {}).get('border', '#d0d0d0')};
                        border-radius: 3px;
                        text-align: center;
                    }}
                    
                    QProgressBar::chunk {{
                        background-color: {colors['progressBar'].get('progress', '#4b6eaf')};
                        width: 10px;
                    }}
                """
                stylesheet.append(progress_style)
            
            # Links
            if "link" in colors:
                link_style = f"""
                    QLabel[link="true"] {{
                        color: {colors['link'].get('text', '#0066cc')};
                        text-decoration: underline;
                    }}
                    
                    QLabel[link="true"]:hover {{
                        color: {colors['link'].get('hover', '#0055aa')};
                    }}
                    
                    QLabel[visited="true"] {{
                        color: {colors['link'].get('visited', '#551a8b')};
                    }}
                """
                stylesheet.append(link_style)
            
            # Combine all styles
            return "\n".join(stylesheet)
        except Exception as e:
            logger.error(f"Error creating stylesheet: {e}")
            return ""
