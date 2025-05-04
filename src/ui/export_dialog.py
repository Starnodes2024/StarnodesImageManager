#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Export dialog for StarImageBrowse
Provides a dialog for selecting export options.
"""

import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton, 
    QCheckBox, QLabel, QDialogButtonBox, QFileDialog
)
from PyQt6.QtCore import Qt

logger = logging.getLogger("StarImageBrowse.ui.export_dialog")

class ExportDialog(QDialog):
    """Dialog for selecting export options."""
    
    def __init__(self, parent=None, num_images=0, language_manager=None):
        """Initialize the export dialog.
        
        Args:
            parent (QWidget, optional): Parent widget
            num_images (int): Number of images being exported
            language_manager: Language manager instance
        """
        super().__init__(parent)
        
        self.language_manager = language_manager
        self.num_images = num_images
        self.export_destination = ""
        self.export_format = "original"  # Default to original format
        self.include_description = False
        self.export_workflow = False
        
        self.setup_ui()
        self.retranslateUi()
    
    def get_translation(self, key, default=None):
        """Get a translation for a key.
        
        Args:
            key (str): Key in the export section
            default (str, optional): Default value if translation not found
            
        Returns:
            str: Translated string or default value
        """
        if hasattr(self, 'language_manager') and self.language_manager:
            return self.language_manager.translate('export', key, default)
        return default
    
    def setup_ui(self):
        """Set up the dialog UI."""
        self.setMinimumWidth(400)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Image count label
        if self.num_images > 0:
            count_text = self.get_translation('exporting_images', 'Exporting {count} {plural}')
            count_text = count_text.format(
                count=self.num_images, 
                plural=self.get_translation('images' if self.num_images > 1 else 'image', 'images' if self.num_images > 1 else 'image')
            )
            self.count_label = QLabel(count_text)
            self.count_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(self.count_label)
        
        # Format options
        self.format_group = QGroupBox(self.get_translation('format_group', 'Export Format'))
        format_layout = QVBoxLayout(self.format_group)
        
        # Format radio buttons
        self.original_radio = QRadioButton(self.get_translation('original_format', 'Original Format (preserve original file format)'))
        self.jpg_radio = QRadioButton(self.get_translation('jpeg_format', 'JPEG (.jpg)'))
        self.png_radio = QRadioButton(self.get_translation('png_format', 'PNG (.png)'))
        
        # Set original format as default
        self.original_radio.setChecked(True)
        
        # Add format options to layout
        format_layout.addWidget(self.original_radio)
        format_layout.addWidget(self.jpg_radio)
        format_layout.addWidget(self.png_radio)
        
        layout.addWidget(self.format_group)
        
        # Description options
        self.desc_group = QGroupBox(self.get_translation('description_group', 'Description Export'))
        desc_layout = QVBoxLayout(self.desc_group)
        
        self.include_desc_check = QCheckBox(self.get_translation('include_description', 'Include description as text file'))
        self.desc_only_check = QCheckBox(self.get_translation('description_only', 'Export description only (no image)'))
        
        # Connect checkboxes to handle mutual exclusivity
        self.include_desc_check.stateChanged.connect(self.on_include_desc_changed)
        self.desc_only_check.stateChanged.connect(self.on_desc_only_changed)
        
        desc_layout.addWidget(self.include_desc_check)
        desc_layout.addWidget(self.desc_only_check)
        
        layout.addWidget(self.desc_group)
        
        # ComfyUI Workflow export option
        self.workflow_group = QGroupBox(self.get_translation('workflow_group', 'ComfyUI Workflow Export'))
        workflow_layout = QVBoxLayout(self.workflow_group)
        
        self.export_workflow_check = QCheckBox(self.get_translation('export_workflow', 'Export ComfyUI workflow as JSON file'))
        workflow_layout.addWidget(self.export_workflow_check)
        
        layout.addWidget(self.workflow_group)
        
        # Destination button
        dest_layout = QHBoxLayout()
        self.dest_label = QLabel(self.get_translation('destination_not_selected', 'Export Destination: Not Selected'))
        self.dest_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Open)
        self.dest_button.button(QDialogButtonBox.StandardButton.Open).setText(self.get_translation('select_destination', 'Select Destination...'))
        self.dest_button.button(QDialogButtonBox.StandardButton.Open).clicked.connect(self.select_destination)
        
        dest_layout.addWidget(self.dest_label)
        dest_layout.addWidget(self.dest_button)
        layout.addLayout(dest_layout)
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def retranslateUi(self):
        self.setWindowTitle(self.get_translation('dialog_title', 'Export Options'))
        # Update all UI elements with translated text
        if hasattr(self, 'count_label') and self.num_images > 0:
            count_text = self.get_translation('exporting_images', 'Exporting {count} {plural}')
            count_text = count_text.format(
                count=self.num_images, 
                plural=self.get_translation('images' if self.num_images > 1 else 'image', 'images' if self.num_images > 1 else 'image')
            )
            self.count_label.setText(count_text)
        if hasattr(self, 'format_group'):
            self.format_group.setTitle(self.get_translation('format_group', 'Export Format'))
        if hasattr(self, 'original_radio'):
            self.original_radio.setText(self.get_translation('original_format', 'Original Format (preserve original file format)'))
        if hasattr(self, 'jpg_radio'):
            self.jpg_radio.setText(self.get_translation('jpeg_format', 'JPEG (.jpg)'))
        if hasattr(self, 'png_radio'):
            self.png_radio.setText(self.get_translation('png_format', 'PNG (.png)'))
        if hasattr(self, 'desc_group'):
            self.desc_group.setTitle(self.get_translation('description_group', 'Description Export'))
        if hasattr(self, 'include_desc_check'):
            self.include_desc_check.setText(self.get_translation('include_description', 'Include description as text file'))
        if hasattr(self, 'desc_only_check'):
            self.desc_only_check.setText(self.get_translation('description_only', 'Export description only (no image)'))
        if hasattr(self, 'workflow_group'):
            self.workflow_group.setTitle(self.get_translation('workflow_group', 'Workflow Export'))
        if hasattr(self, 'export_workflow_check'):
            self.export_workflow_check.setText(self.get_translation('export_workflow', 'Export workflow file'))
        if hasattr(self, 'dest_label'):
            if self.export_destination:
                display_path = self.export_destination
                if len(display_path) > 40:
                    display_path = "..." + display_path[-37:]
                self.dest_label.setText(self.get_translation('destination_selected', 'Export Destination: {path}').format(path=display_path))
            else:
                self.dest_label.setText(self.get_translation('select_destination', 'Select export destination folder'))
        if hasattr(self, 'dest_button'):
            self.dest_button.button(self.dest_button.StandardButton.Open).setText(self.get_translation('select_destination', 'Select Destination...'))
        if hasattr(self, 'button_box'):
            self.button_box.button(self.button_box.StandardButton.Ok).setText(self.get_translation('ok', 'OK'))
            self.button_box.button(self.button_box.StandardButton.Cancel).setText(self.get_translation('cancel', 'Cancel'))

    def set_language_manager(self, language_manager):
        self.language_manager = language_manager
        self.retranslateUi()
    
    def on_include_desc_changed(self, state):
        """Handle changes to the include description checkbox.
        
        Args:
            state (int): State of the checkbox
        """
        if state == Qt.CheckState.Checked.value and self.desc_only_check.isChecked():
            # If include description is checked, uncheck description only
            self.desc_only_check.setChecked(False)
    
    def on_desc_only_changed(self, state):
        """Handle changes to the description only checkbox.
        
        Args:
            state (int): State of the checkbox
        """
        if state == Qt.CheckState.Checked.value:
            # If description only is checked, uncheck include description
            self.include_desc_check.setChecked(False)
            
            # Disable format options
            self.original_radio.setEnabled(False)
            self.jpg_radio.setEnabled(False)
            self.png_radio.setEnabled(False)
        else:
            # Re-enable format options
            self.original_radio.setEnabled(True)
            self.jpg_radio.setEnabled(True)
            self.png_radio.setEnabled(True)
    
    def select_destination(self):
        """Open a file dialog to select the export destination."""
        dest_folder = QFileDialog.getExistingDirectory(
            self, "Select Export Destination", 
            os.path.expanduser("~"), 
            QFileDialog.Option.ShowDirsOnly
        )
        
        if dest_folder:
            self.export_destination = dest_folder
            # Truncate display path if it's too long
            display_path = dest_folder
            if len(display_path) > 40:
                display_path = "..." + display_path[-37:]
            self.dest_label.setText(self.get_translation('destination_selected', 'Export Destination: {path}').format(path=display_path))
    
    def validate_and_accept(self):
        """Validate the inputs and accept the dialog."""
        if not self.export_destination:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, 
                self.get_translation('missing_destination_title', 'Missing Destination'), 
                self.get_translation('missing_destination_message', 'Please select an export destination folder.'),
                QMessageBox.StandardButton.Ok
            )
            return
        
        # Get the selected format
        if self.desc_only_check.isChecked():
            self.export_format = "txt_only"
        elif self.jpg_radio.isChecked():
            self.export_format = "jpg"
        elif self.png_radio.isChecked():
            self.export_format = "png"
        else:
            self.export_format = "original"
        
        # Get description option
        self.include_description = self.include_desc_check.isChecked()
        
        # Get workflow export option
        self.export_workflow = self.export_workflow_check.isChecked()
        
        # Accept the dialog
        self.accept()
    
    def get_export_options(self):
        """Get the selected export options.
        
        Returns:
            dict: Dictionary containing export options
        """
        return {
            "destination": self.export_destination,
            "format": self.export_format,
            "include_description": self.include_description,
            "description_only": self.desc_only_check.isChecked(),
            "export_workflow": self.export_workflow_check.isChecked()
        }
