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
    
    def __init__(self, parent=None, num_images=0):
        """Initialize the export dialog.
        
        Args:
            parent (QWidget, optional): Parent widget
            num_images (int): Number of images being exported
        """
        super().__init__(parent)
        
        self.num_images = num_images
        self.export_destination = ""
        self.export_format = "original"  # Default to original format
        self.include_description = False
        self.export_workflow = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Export Options")
        self.setMinimumWidth(400)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Image count label
        if self.num_images > 0:
            count_label = QLabel(f"Exporting {self.num_images} image{'s' if self.num_images > 1 else ''}")
            count_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(count_label)
        
        # Format options
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout(format_group)
        
        # Format radio buttons
        self.original_radio = QRadioButton("Original Format (preserve original file format)")
        self.jpg_radio = QRadioButton("JPEG (.jpg)")
        self.png_radio = QRadioButton("PNG (.png)")
        
        # Set original format as default
        self.original_radio.setChecked(True)
        
        # Add format options to layout
        format_layout.addWidget(self.original_radio)
        format_layout.addWidget(self.jpg_radio)
        format_layout.addWidget(self.png_radio)
        
        layout.addWidget(format_group)
        
        # Description options
        desc_group = QGroupBox("Description Export")
        desc_layout = QVBoxLayout(desc_group)
        
        self.include_desc_check = QCheckBox("Include description as text file")
        self.desc_only_check = QCheckBox("Export description only (no image)")
        
        # Connect checkboxes to handle mutual exclusivity
        self.include_desc_check.stateChanged.connect(self.on_include_desc_changed)
        self.desc_only_check.stateChanged.connect(self.on_desc_only_changed)
        
        desc_layout.addWidget(self.include_desc_check)
        desc_layout.addWidget(self.desc_only_check)
        
        layout.addWidget(desc_group)
        
        # ComfyUI Workflow export option
        workflow_group = QGroupBox("ComfyUI Workflow Export")
        workflow_layout = QVBoxLayout(workflow_group)
        
        self.export_workflow_check = QCheckBox("Export ComfyUI workflow as JSON file")
        workflow_layout.addWidget(self.export_workflow_check)
        
        layout.addWidget(workflow_group)
        
        # Destination button
        dest_layout = QHBoxLayout()
        self.dest_label = QLabel("Export Destination: Not Selected")
        self.dest_button = QDialogButtonBox(QDialogButtonBox.StandardButton.Open)
        self.dest_button.button(QDialogButtonBox.StandardButton.Open).setText("Select Destination...")
        self.dest_button.button(QDialogButtonBox.StandardButton.Open).clicked.connect(self.select_destination)
        
        dest_layout.addWidget(self.dest_label)
        dest_layout.addWidget(self.dest_button)
        layout.addLayout(dest_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
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
            self.dest_label.setText(f"Export Destination: {display_path}")
    
    def validate_and_accept(self):
        """Validate the inputs and accept the dialog."""
        if not self.export_destination:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Missing Destination", 
                "Please select an export destination folder.",
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
