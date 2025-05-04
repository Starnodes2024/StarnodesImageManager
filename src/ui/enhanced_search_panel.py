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
    
    def __init__(self, parent=None):
        """Initialize the enhanced search panel.
        
        Args:
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        # Try to get language manager from parent window
        self.language_manager = None
        parent_widget = self
        while parent_widget.parent() is not None:
            parent_widget = parent_widget.parent()
            if hasattr(parent_widget, 'language_manager'):
                self.language_manager = parent_widget.language_manager
                break
        
        self.setup_ui()
        self.retranslateUi()
    
    def setup_ui(self):
        """Set up the search panel UI."""
        # Main layout with scrollable area to accommodate all search options
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        # All text will be set in retranslateUi()
        
        # Create scrollable area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # Container widget for scroll area
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(10)
        
        # Header
        self.header_label = QLabel()
        self.header_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.header_label)
        
        # Search scope group
        self.create_scope_group(layout)
        
        # Search criteria groups
        self.create_text_search_group(layout)
        self.create_date_range_group(layout)
        self.create_dimensions_group(layout)
        
        # Search button
        self.search_button = QPushButton()
        self.search_button.setMinimumHeight(32)
        self.search_button.clicked.connect(self.on_search)
        layout.addWidget(self.search_button)
        
        # Help text
        self.help_label = QLabel()
        self.help_label.setWordWrap(True)
        self.help_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.help_label)
        
        # Add stretch to push everything to the top
        layout.addStretch(1)
        
        # Set scroll content
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

    def retranslateUi(self):
        self.header_label.setText(self.get_translation('search', 'title', 'Search Images'))
        self.search_button.setText(self.get_translation('search', 'search_button', 'Search'))
        help_text = self.get_translation('search', 'help_text', 
            "Select search criteria using the checkboxes. You can combine multiple criteria.\n"
            "For example, search for \"sunset\" images between certain dates with specific dimensions.")
        self.help_label.setText(help_text)
        # Add all other UI elements that need translation here

    def set_language_manager(self, language_manager):
        self.language_manager = language_manager
        self.retranslateUi()
    
    def create_scope_group(self, parent_layout):
        """Create the search scope options group.
        
        Args:
            parent_layout (QLayout): Parent layout to add the group to
        """
        scope_group = QGroupBox(self.get_translation('search', 'scope_group', 'Search Location'))
        scope_layout = QVBoxLayout()
        
        # Create a button group for radio buttons
        self.scope_group = QButtonGroup(self)
        
        # Current folder option (default)
        self.current_folder_radio = QRadioButton(self.get_translation('search', 'current_folder', 'Current Folder'))
        self.current_folder_radio.setChecked(True)
        self.scope_group.addButton(self.current_folder_radio, 1)
        scope_layout.addWidget(self.current_folder_radio)
        
        # Current catalog option
        self.current_catalog_radio = QRadioButton(self.get_translation('search', 'current_catalog', 'Current Catalog'))
        self.scope_group.addButton(self.current_catalog_radio, 2)
        scope_layout.addWidget(self.current_catalog_radio)
        
        # All images option
        self.all_images_radio = QRadioButton(self.get_translation('search', 'all_images', 'All Images'))
        self.scope_group.addButton(self.all_images_radio, 3)
        scope_layout.addWidget(self.all_images_radio)
        
        scope_group.setLayout(scope_layout)
        parent_layout.addWidget(scope_group)
        
    def create_text_search_group(self, parent_layout):
        """Create the text search criteria group.
        
        Args:
            parent_layout (QLayout): Parent layout to add the group to
        """
        text_group = QGroupBox(self.get_translation('search', 'text_search', 'Text Search'))
        text_layout = QVBoxLayout()
        
        # Enable checkbox
        self.text_enabled = QCheckBox(self.get_translation('search', 'enable_text_search', 'Enable Text Search'))
        self.text_enabled.setChecked(True)  # Enable by default
        text_layout.addWidget(self.text_enabled)
        
        # Search input with autocomplete
        search_layout = QHBoxLayout()
        search_label = QLabel(self.get_translation('search', 'search_label', 'Search:'))
        search_layout.addWidget(search_label)
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
        date_group = QGroupBox(self.get_translation('search', 'date_search', 'Date Range'))
        date_layout = QVBoxLayout()
        
        # Enable checkbox
        self.date_enabled = QCheckBox(self.get_translation('search', 'enable_date_range', 'Enable Date Range'))
        date_layout.addWidget(self.date_enabled)
        
        # Date range inputs
        date_range_layout = QFormLayout()
        date_range_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        
        # From date
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-1))  # Default to 1 month ago
        date_range_layout.addRow(self.get_translation('search', 'from_date', 'From:'), self.from_date)
        
        # To date
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())  # Default to today
        date_range_layout.addRow(self.get_translation('search', 'to_date', 'To:'), self.to_date)
        
        date_layout.addLayout(date_range_layout)
        date_group.setLayout(date_layout)
        parent_layout.addWidget(date_group)
        
    def create_dimensions_group(self, parent_layout):
        """Create the image dimensions criteria group.
        
        Args:
            parent_layout (QLayout): Parent layout to add the group to
        """
        try:
            dimensions_group = QGroupBox(self.get_translation('search', 'dimension_search', 'Image Dimensions'))
            dimensions_layout = QVBoxLayout()
            
            # Enable checkbox
            self.dimensions_enabled = QCheckBox(self.get_translation('search', 'enable_dimensions', 'Enable Dimension Filters'))
            dimensions_layout.addWidget(self.dimensions_enabled)
            
            # Dimensions form
            form_layout = QFormLayout()
            form_layout.setContentsMargins(20, 0, 0, 0)
            
            # Width range
            width_layout = QFormLayout()
            width_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            
            self.min_width = QSpinBox()
            self.min_width.setRange(0, 10000)
            self.min_width.setSingleStep(100)
            # Set fixed width to prevent layout issues
            self.min_width.setMinimumWidth(80)
            width_layout.addRow(self.get_translation('search', 'min_width', 'Min Width:'), self.min_width)
            
            self.max_width = QSpinBox()
            self.max_width.setRange(0, 10000)
            self.max_width.setValue(10000)  # Default to max
            self.max_width.setSingleStep(100)
            # Set fixed width to prevent layout issues
            self.max_width.setMinimumWidth(80)
            width_layout.addRow(self.get_translation('search', 'max_width', 'Max Width:'), self.max_width)
            
            form_layout.addRow(self.get_translation('search', 'width_px', 'Width (px):'), width_layout)
            
            # Height range
            height_layout = QFormLayout()
            height_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            
            self.min_height = QSpinBox()
            self.min_height.setRange(0, 10000)
            self.min_height.setSingleStep(100)
            # Set fixed width to prevent layout issues
            self.min_height.setMinimumWidth(80)
            height_layout.addRow(self.get_translation('search', 'min_height', 'Min Height:'), self.min_height)
            
            self.max_height = QSpinBox()
            self.max_height.setRange(0, 10000)
            self.max_height.setValue(10000)  # Default to max
            self.max_height.setSingleStep(100)
            # Set fixed width to prevent layout issues
            self.max_height.setMinimumWidth(80)
            height_layout.addRow(self.get_translation('search', 'max_height', 'Max Height:'), self.max_height)
            
            form_layout.addRow(self.get_translation('search', 'height_px', 'Height (px):'), height_layout)
            
            # Dimension presets
            preset_layout = QHBoxLayout()
            preset_label = QLabel(self.get_translation('search', 'preset_label', 'Preset:'))
            preset_layout.addWidget(preset_label)
            
            # Create combo box with error handling
            try:
                self.dimension_preset = QComboBox()
                # Set fixed width to prevent layout issues
                self.dimension_preset.setMinimumWidth(150)
                
                # Add items one by one with error handling
                presets = [
                    ('preset_custom', 'Custom'),
                    ('preset_hd720', 'HD (1280×720)'),
                    ('preset_fullhd', 'Full HD (1920×1080)'),
                    ('preset_4k', '4K (3840×2160)'),
                    ('preset_8k', '8K (7680×4320)'),
                    ('preset_square', 'Square'),
                    ('preset_portrait', 'Portrait'),
                    ('preset_landscape', 'Landscape')
                ]
                
                for key, default in presets:
                    try:
                        self.dimension_preset.addItem(self.get_translation('search', key, default))
                    except Exception as item_error:
                        logger.error(f"Error adding preset item {key}: {item_error}")
                        self.dimension_preset.addItem(default)
                
                # Connect signal after all items are added
                self.dimension_preset.currentIndexChanged.connect(self.on_dimension_preset_changed)
            except Exception as combo_error:
                logger.error(f"Error creating dimension preset combo box: {combo_error}")
                self.dimension_preset = QComboBox()
                self.dimension_preset.addItem('Custom')
            
            preset_layout.addWidget(preset_label)
            preset_layout.addWidget(self.dimension_preset)
            form_layout.addRow(self.get_translation('search', 'preset_row', ''), preset_layout)
            
            dimensions_layout.addLayout(form_layout)
            dimensions_group.setLayout(dimensions_layout)
            parent_layout.addWidget(dimensions_group)
            
        except Exception as e:
            logger.error(f"Error creating dimensions group: {e}")
            # Create a minimal fallback group if there's an error
            try:
                fallback_group = QGroupBox("Image Dimensions")
                fallback_layout = QVBoxLayout()
                fallback_label = QLabel("Dimension filters unavailable")
                fallback_layout.addWidget(fallback_label)
                fallback_group.setLayout(fallback_layout)
                parent_layout.addWidget(fallback_group)
                
                # Create empty widget references to prevent NoneType errors
                self.dimensions_enabled = QCheckBox()
                self.min_width = QSpinBox()
                self.max_width = QSpinBox()
                self.min_height = QSpinBox()
                self.max_height = QSpinBox()
                self.dimension_preset = QComboBox()
            except Exception as fallback_error:
                logger.error(f"Error creating fallback dimensions group: {fallback_error}")
        
    def on_dimension_preset_changed(self, index):
        """Handle dimension preset change.
        
        Args:
            index (int): Index of the selected preset
        """
        try:
            # Block signals temporarily to prevent cascading updates
            # which can trigger display scaling issues
            old_block_state_min_w = self.min_width.blockSignals(True)
            old_block_state_max_w = self.max_width.blockSignals(True)
            old_block_state_min_h = self.min_height.blockSignals(True)
            old_block_state_max_h = self.max_height.blockSignals(True)
            
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
        except Exception as e:
            logger.error(f"Error updating dimension preset: {e}")
        finally:
            # Restore signal blocking state
            try:
                self.min_width.blockSignals(old_block_state_min_w)
                self.max_width.blockSignals(old_block_state_max_w)
                self.min_height.blockSignals(old_block_state_min_h)
                self.max_height.blockSignals(old_block_state_max_h)
            except Exception as e:
                logger.error(f"Error restoring signal states: {e}")
    
    def on_search(self):
        """Handle search button click."""
        try:
            # Build search parameters dictionary with safe defaults
            search_params = {
                # Search scope
                'scope': 'all',
                
                # Text search
                'text_enabled': False,
                'text_query': '',
                
                # Date range
                'date_enabled': False,
                'date_from': None,
                'date_to': None,
                
                # Dimensions
                'dimensions_enabled': False,
                'min_width': None,
                'max_width': None,
                'min_height': None,
                'max_height': None,
                'dimension_preset': 0
            }
            
            # Safely get scope
            try:
                search_params['scope'] = 'folder' if self.current_folder_radio.isChecked() else \
                                        'catalog' if self.current_catalog_radio.isChecked() else 'all'
            except Exception as e:
                logger.error(f"Error getting search scope: {e}")
            
            # Safely get text search parameters
            try:
                search_params['text_enabled'] = self.text_enabled.isChecked()
                search_params['text_query'] = self.search_input.text().strip() if self.text_enabled.isChecked() else ''
            except Exception as e:
                logger.error(f"Error getting text search parameters: {e}")
            
            # Safely get date range parameters
            try:
                search_params['date_enabled'] = self.date_enabled.isChecked()
                if search_params['date_enabled']:
                    search_params['date_from'] = self.from_date.date().toPyDate()
                    search_params['date_to'] = self.to_date.date().toPyDate()
            except Exception as e:
                logger.error(f"Error getting date range parameters: {e}")
                search_params['date_enabled'] = False
            
            # Safely get dimension parameters
            try:
                search_params['dimensions_enabled'] = self.dimensions_enabled.isChecked()
                if search_params['dimensions_enabled']:
                    # Explicitly convert to integers to avoid type issues
                    try:
                        search_params['min_width'] = int(self.min_width.value())
                        search_params['max_width'] = int(self.max_width.value())
                        search_params['min_height'] = int(self.min_height.value())
                        search_params['max_height'] = int(self.max_height.value())
                        search_params['dimension_preset'] = int(self.dimension_preset.currentIndex())
                        
                        # Validate dimension values
                        if search_params['min_width'] < 0:
                            search_params['min_width'] = 0
                        if search_params['max_width'] > 10000:
                            search_params['max_width'] = 10000
                        if search_params['min_height'] < 0:
                            search_params['min_height'] = 0
                        if search_params['max_height'] > 10000:
                            search_params['max_height'] = 10000
                            
                        # Ensure min <= max
                        if search_params['min_width'] > search_params['max_width']:
                            search_params['min_width'], search_params['max_width'] = search_params['max_width'], search_params['min_width']
                        if search_params['min_height'] > search_params['max_height']:
                            search_params['min_height'], search_params['max_height'] = search_params['max_height'], search_params['min_height']
                        
                        # Log the dimension parameters for debugging
                        logger.info(f"Dimension search enabled with: width {search_params['min_width']}-{search_params['max_width']}, "
                                   f"height {search_params['min_height']}-{search_params['max_height']}, "
                                   f"preset {search_params['dimension_preset']}")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error converting dimension values: {e}")
                        # Set default values if conversion fails
                        search_params['min_width'] = 0
                        search_params['max_width'] = 10000
                        search_params['min_height'] = 0
                        search_params['max_height'] = 10000
                        search_params['dimension_preset'] = 0
            except Exception as e:
                logger.error(f"Error getting dimension parameters: {e}")
                search_params['dimensions_enabled'] = False
            
            # Validate there's at least one search criteria enabled
            if (not search_params['text_enabled'] and 
                not search_params['date_enabled'] and 
                not search_params['dimensions_enabled']):
                    # When no criteria explicitly enabled but text is entered, enable text search automatically
                if search_params['text_query']:
                    search_params['text_enabled'] = True
                    try:
                        self.text_enabled.setChecked(True)
                    except Exception as e:
                        logger.error(f"Error enabling text search checkbox: {e}")
            
            # Emit search signal with all parameters
            logger.info(f"Emitting search request with params: {search_params}")
            self.search_requested.emit(search_params)
            
        except Exception as e:
            logger.error(f"Error in search function: {e}")
            # Create minimal search params to avoid complete failure
            minimal_params = {
                'scope': 'all',
                'text_enabled': True,
                'text_query': '',
                'date_enabled': False,
                'dimensions_enabled': False,
                'date_from': None,
                'date_to': None,
                'min_width': None,
                'max_width': None,
                'min_height': None,
                'max_height': None,
                'dimension_preset': 0
            }
            self.search_requested.emit(minimal_params)
    
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
