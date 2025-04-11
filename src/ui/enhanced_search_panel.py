#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced search panel UI component for StarImageBrowse
Provides comprehensive search functionality with multiple criteria and scopes.
"""

import logging
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QCompleter, QDateEdit,
    QGroupBox, QCheckBox, QRadioButton, QButtonGroup,
    QFrame, QSpinBox, QComboBox, QFormLayout,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QStringListModel, QDate, QSize

logger = logging.getLogger("StarImageBrowse.ui.enhanced_search_panel")

class EnhancedSearchPanel(QWidget):
    """Enhanced panel for searching images with multiple criteria and scopes."""
    
    # Signal emitted when search is requested with all parameters
    search_requested = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        """Initialize the enhanced search panel.
        
        Args:
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the search panel UI."""
        # Main layout with scrollable area to accommodate all search options
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scrollable area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # Container widget for scroll area
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(10)
        
        # Header
        header_label = QLabel("Search Images")
        header_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header_label)
        
        # Search scope group
        self.create_scope_group(layout)
        
        # Search criteria groups
        self.create_text_search_group(layout)
        self.create_date_range_group(layout)
        self.create_dimensions_group(layout)
        
        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.setMinimumHeight(32)
        self.search_button.clicked.connect(self.on_search)
        layout.addWidget(self.search_button)
        
        # Help text
        help_label = QLabel(
            "Select search criteria using the checkboxes. You can combine multiple criteria.\n"
            "For example, search for \"sunset\" images between certain dates with specific dimensions."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(help_label)
        
        # Add stretch to push everything to the top
        layout.addStretch(1)
        
        # Set scroll content
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
    def create_scope_group(self, parent_layout):
        """Create the search scope options group.
        
        Args:
            parent_layout (QLayout): Parent layout to add the group to
        """
        scope_group = QGroupBox("Search Location")
        scope_layout = QVBoxLayout()
        
        # Create a button group for radio buttons
        self.scope_group = QButtonGroup(self)
        
        # Current folder option (default)
        self.current_folder_radio = QRadioButton("Current Folder")
        self.current_folder_radio.setChecked(True)
        self.scope_group.addButton(self.current_folder_radio, 1)
        scope_layout.addWidget(self.current_folder_radio)
        
        # Current catalog option
        self.current_catalog_radio = QRadioButton("Current Catalog")
        self.scope_group.addButton(self.current_catalog_radio, 2)
        scope_layout.addWidget(self.current_catalog_radio)
        
        # All images option
        self.all_images_radio = QRadioButton("All Images")
        self.scope_group.addButton(self.all_images_radio, 3)
        scope_layout.addWidget(self.all_images_radio)
        
        scope_group.setLayout(scope_layout)
        parent_layout.addWidget(scope_group)
        
    def create_text_search_group(self, parent_layout):
        """Create the text search criteria group.
        
        Args:
            parent_layout (QLayout): Parent layout to add the group to
        """
        text_group = QGroupBox("Text Search")
        text_layout = QVBoxLayout()
        
        # Enable checkbox
        self.text_enabled = QCheckBox("Search by text")
        self.text_enabled.setChecked(True)  # Enable text search by default
        text_layout.addWidget(self.text_enabled)
        
        # Search input layout
        search_layout = QHBoxLayout()
        
        # Search input field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search keywords...")
        # Auto-enable text search when text is entered
        self.search_input.textChanged.connect(self._auto_enable_text_search)
        search_layout.addWidget(self.search_input)
        
        text_layout.addLayout(search_layout)
        
        # Search suggestions (will be populated later)
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search_input.setCompleter(self.completer)
        
        text_group.setLayout(text_layout)
        parent_layout.addWidget(text_group)
        
    def create_date_range_group(self, parent_layout):
        """Create the date range criteria group.
        
        Args:
            parent_layout (QLayout): Parent layout to add the group to
        """
        date_group = QGroupBox("Date Range")
        date_layout = QVBoxLayout()
        
        # Enable checkbox
        self.date_enabled = QCheckBox("Search by date modified")
        date_layout.addWidget(self.date_enabled)
        
        # Date selection form
        form_layout = QFormLayout()
        form_layout.setContentsMargins(20, 0, 0, 0)
        
        # From date
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        form_layout.addRow("From:", self.from_date)
        
        # To date
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        form_layout.addRow("To:", self.to_date)
        
        date_layout.addLayout(form_layout)
        date_group.setLayout(date_layout)
        parent_layout.addWidget(date_group)
        
    def create_dimensions_group(self, parent_layout):
        """Create the image dimensions criteria group.
        
        Args:
            parent_layout (QLayout): Parent layout to add the group to
        """
        dims_group = QGroupBox("Image Dimensions")
        dims_layout = QVBoxLayout()
        
        # Enable checkbox
        self.dimensions_enabled = QCheckBox("Search by image size")
        dims_layout.addWidget(self.dimensions_enabled)
        
        # Dimensions form
        form_layout = QFormLayout()
        form_layout.setContentsMargins(20, 0, 0, 0)
        
        # Width range
        width_layout = QHBoxLayout()
        self.min_width = QSpinBox()
        self.min_width.setRange(0, 10000)
        self.min_width.setSingleStep(10)
        self.min_width.setValue(0)
        
        self.max_width = QSpinBox()
        self.max_width.setRange(0, 100000)
        self.max_width.setSingleStep(100)
        self.max_width.setValue(10000)
        
        width_layout.addWidget(self.min_width)
        width_layout.addWidget(QLabel("to"))
        width_layout.addWidget(self.max_width)
        form_layout.addRow("Width (px):", width_layout)
        
        # Height range
        height_layout = QHBoxLayout()
        self.min_height = QSpinBox()
        self.min_height.setRange(0, 10000)
        self.min_height.setSingleStep(10)
        self.min_height.setValue(0)
        
        self.max_height = QSpinBox()
        self.max_height.setRange(0, 100000)
        self.max_height.setSingleStep(100)
        self.max_height.setValue(10000)
        
        height_layout.addWidget(self.min_height)
        height_layout.addWidget(QLabel("to"))
        height_layout.addWidget(self.max_height)
        form_layout.addRow("Height (px):", height_layout)
        
        # Dimension presets
        preset_layout = QHBoxLayout()
        preset_label = QLabel("Preset:")
        self.dimension_preset = QComboBox()
        self.dimension_preset.addItem("Custom")
        self.dimension_preset.addItem("HD (1280×720)")
        self.dimension_preset.addItem("Full HD (1920×1080)")
        self.dimension_preset.addItem("4K (3840×2160)")
        self.dimension_preset.addItem("8K (7680×4320)")
        self.dimension_preset.addItem("Square")
        self.dimension_preset.addItem("Portrait")
        self.dimension_preset.addItem("Landscape")
        
        self.dimension_preset.currentIndexChanged.connect(self.on_dimension_preset_changed)
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.dimension_preset)
        form_layout.addRow("", preset_layout)
        
        dims_layout.addLayout(form_layout)
        dims_group.setLayout(dims_layout)
        parent_layout.addWidget(dims_group)
        
    def on_dimension_preset_changed(self, index):
        """Handle dimension preset change.
        
        Args:
            index (int): Index of the selected preset
        """
        if index == 0:  # Custom
            return
        elif index == 1:  # HD
            self.min_width.setValue(1280)
            self.max_width.setValue(1280)
            self.min_height.setValue(720)
            self.max_height.setValue(720)
        elif index == 2:  # Full HD
            self.min_width.setValue(1920)
            self.max_width.setValue(1920)
            self.min_height.setValue(1080)
            self.max_height.setValue(1080)
        elif index == 3:  # 4K
            self.min_width.setValue(3840)
            self.max_width.setValue(3840)
            self.min_height.setValue(2160)
            self.max_height.setValue(2160)
        elif index == 4:  # 8K
            self.min_width.setValue(7680)
            self.max_width.setValue(7680)
            self.min_height.setValue(4320)
            self.max_height.setValue(4320)
        elif index == 5:  # Square
            self.min_width.setValue(0)
            self.max_width.setValue(10000)
            self.min_height.setValue(0)
            self.max_height.setValue(10000)
            # Logic for finding square images will be in the search function
            # For UI, we just keep the full range
        elif index == 6:  # Portrait
            self.min_width.setValue(0)
            self.max_width.setValue(10000)
            self.min_height.setValue(0)
            self.max_height.setValue(10000)
            # Logic for finding portrait images will be in the search function
        elif index == 7:  # Landscape
            self.min_width.setValue(0)
            self.max_width.setValue(10000)
            self.min_height.setValue(0)
            self.max_height.setValue(10000)
            # Logic for finding landscape images will be in the search function
    
    def on_search(self):
        """Handle search button click."""
        # Build search parameters dictionary
        search_params = {
            # Search scope
            'scope': 'folder' if self.current_folder_radio.isChecked() else 
                    'catalog' if self.current_catalog_radio.isChecked() else 'all',
            
            # Text search
            'text_enabled': self.text_enabled.isChecked(),
            'text_query': self.search_input.text().strip() if self.text_enabled.isChecked() else '',
            
            # Date range
            'date_enabled': self.date_enabled.isChecked(),
            'date_from': self.from_date.date().toPyDate() if self.date_enabled.isChecked() else None,
            'date_to': self.to_date.date().toPyDate() if self.date_enabled.isChecked() else None,
            
            # Dimensions
            'dimensions_enabled': self.dimensions_enabled.isChecked(),
            'min_width': self.min_width.value() if self.dimensions_enabled.isChecked() else None,
            'max_width': self.max_width.value() if self.dimensions_enabled.isChecked() else None,
            'min_height': self.min_height.value() if self.dimensions_enabled.isChecked() else None,
            'max_height': self.max_height.value() if self.dimensions_enabled.isChecked() else None,
            'dimension_preset': self.dimension_preset.currentIndex() if self.dimensions_enabled.isChecked() else 0
        }
        
        # Validate there's at least one search criteria enabled
        if (not search_params['text_enabled'] and 
            not search_params['date_enabled'] and 
            not search_params['dimensions_enabled']):
                # When no criteria explicitly enabled but text is entered, enable text search automatically
            if search_params['text_query']:
                search_params['text_enabled'] = True
                self.text_enabled.setChecked(True)
            
        # Emit search signal with all parameters
        self.search_requested.emit(search_params)
    
    def set_search_suggestions(self, suggestions):
        """Set the search suggestions for autocomplete.
        
        Args:
            suggestions (list): List of search suggestions
        """
        model = QStringListModel()
        model.setStringList(suggestions)
        self.completer.setModel(model)
    
    def _auto_enable_text_search(self, text):
        """Automatically enable text search when text is entered"""
        if text.strip():
            self.text_enabled.setChecked(True)
    
    def clear(self):
        """Clear all search inputs."""
        self.search_input.clear()
        self.text_enabled.setChecked(True)  # Keep text search enabled by default
        self.date_enabled.setChecked(False)
        self.dimensions_enabled.setChecked(False)
        
        # Reset to default values
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        self.to_date.setDate(QDate.currentDate())
        
        self.min_width.setValue(0)
        self.max_width.setValue(10000)
        self.min_height.setValue(0)
        self.max_height.setValue(10000)
        self.dimension_preset.setCurrentIndex(0)
        
        # Set default scope
        self.current_folder_radio.setChecked(True)
