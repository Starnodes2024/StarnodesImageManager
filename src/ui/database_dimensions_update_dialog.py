#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database dimensions update dialog for StarImageBrowse
Updates image dimensions in the database from existing images.
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox, QDialogButtonBox, QGroupBox,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot

from src.utils.image_dimensions_updater import ImageDimensionsUpdater

logger = logging.getLogger("StarImageBrowse.ui.database_dimensions_update_dialog")

class DatabaseDimensionsUpdateDialog(QDialog):
    """Dialog for updating image dimensions in the database."""
    
    def __init__(self, parent, db_manager, enhanced_search, language_manager=None):
        """Initialize the dialog.
        
        Args:
            parent: Parent widget
            db_manager: Database manager instance
            enhanced_search: Enhanced search instance
            language_manager: Language manager instance
        """
        super().__init__(parent)
        self.db_manager = db_manager
        self.enhanced_search = enhanced_search
        self.language_manager = language_manager
        self.updater = ImageDimensionsUpdater(db_manager, enhanced_search)
        self.setup_ui()
        
    def get_translation(self, key, default=None):
        """Get a translation for a key.
        
        Args:
            key (str): Key in the dimensions_update section
            default (str, optional): Default value if translation not found
            
        Returns:
            str: Translated string or default value
        """
        if hasattr(self, 'language_manager') and self.language_manager:
            return self.language_manager.translate('dimensions_update', key, default)
        return default
    
    def setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle(self.get_translation('dialog_title', 'Update Image Dimensions'))
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Info label
        info_text = self.get_translation('info_text',
            "This tool will scan image files and update width and height information in the database. "
            "This data is needed for dimension-based searching.\n\n"
            "Choose which images to update:"
        )
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Options group
        self.options_group = QGroupBox(self.get_translation('update_options', 'Update Options'))
        options_layout = QVBoxLayout()
        
        # Create a button group for radio buttons
        self.scope_group = QButtonGroup(self)
        
        # All images option (default)
        self.all_images_radio = QRadioButton(self.get_translation('all_images', 'All Images'))
        self.all_images_radio.setChecked(True)
        self.scope_group.addButton(self.all_images_radio, 1)
        options_layout.addWidget(self.all_images_radio)
        
        # Current folder option
        self.current_folder_radio = QRadioButton(self.get_translation('current_folder_only', 'Current Folder Only'))
        self.scope_group.addButton(self.current_folder_radio, 2)
        options_layout.addWidget(self.current_folder_radio)
        
        self.options_group.setLayout(options_layout)
        layout.addWidget(self.options_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel(self.get_translation('ready_status', 'Ready to update dimensions'))
        layout.addWidget(self.status_label)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.start_update)
        button_box.rejected.connect(self.reject)
        
        # Rename the buttons
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText(self.get_translation('start_update', 'Start Update'))
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText(self.get_translation('close', 'Close'))
        
        layout.addWidget(button_box)
        
        # Store buttons for later enabling/disabling
        self.start_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.close_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        
    def start_update(self):
        """Start the dimensions update process."""
        from PyQt6.QtCore import QThread, pyqtSignal
        
        # Disable start button
        self.start_button.setEnabled(False)
        self.options_group.setEnabled(False)
        
        # Function to run in separate thread
        class UpdateThread(QThread):
            update_progress = pyqtSignal(int, int)
            update_completed = pyqtSignal(dict)
            update_error = pyqtSignal(str)
            
            def __init__(self, updater, current_folder_id=None):
                super().__init__()
                self.updater = updater
                self.current_folder_id = current_folder_id
                
            def run(self):
                try:
                    def progress_callback(current, total):
                        self.update_progress.emit(current, total)
                    
                    if self.current_folder_id is not None:
                        results = self.updater.update_single_folder(
                            self.current_folder_id, 
                            progress_callback
                        )
                    else:
                        results = self.updater.update_all_images(progress_callback)
                        
                    self.update_completed.emit(results)
                    
                except Exception as e:
                    self.update_error.emit(str(e))
        
        # Get current folder if selected
        current_folder_id = None
        if self.current_folder_radio.isChecked() and hasattr(self.parent(), 'current_folder_id'):
            current_folder_id = self.parent().current_folder_id
            
            # Check if a folder is selected
            if not current_folder_id:
                QMessageBox.warning(
                    self,
                    self.get_translation('no_folder_title', 'No Folder Selected'),
                    self.get_translation('no_folder_message', 'Please select a folder before updating dimensions for the current folder.'),
                    QMessageBox.StandardButton.Ok
                )
                self.start_button.setEnabled(True)
                self.options_group.setEnabled(True)
                return
        
        # Create and start the thread
        self.update_thread = UpdateThread(self.updater, current_folder_id)
        self.update_thread.update_progress.connect(self.update_progress)
        self.update_thread.update_completed.connect(self.update_completed)
        self.update_thread.update_error.connect(self.update_error)
        self.update_thread.start()
        
        # Update status
        self.status_label.setText(self.get_translation('updating_status', 'Updating image dimensions...'))
        
    @pyqtSlot(int, int)
    def update_progress(self, current, total):
        """Update progress bar.
        
        Args:
            current (int): Current progress
            total (int): Total items to process
        """
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
            self.status_label.setText(self.get_translation('progress_status', 'Processed {current} of {total} images...').format(current=current, total=total))
        
    @pyqtSlot(dict)
    def update_completed(self, results):
        """Handle update completion.
        
        Args:
            results (dict): Update results
        """
        self.progress_bar.setValue(100)
        
        # Build status message
        status = self.get_translation('completion_status',
            'Update complete: {updated} images updated, {failed} failed, {not_found} not found'
        ).format(
            updated=results['updated_count'],
            failed=results['failed_count'],
            not_found=results['not_found_count']
        )
        self.status_label.setText(status)
        
        # Change close button text
        self.close_button.setText(self.get_translation('close', 'Close'))
        
        # Show completion message
        QMessageBox.information(
            self,
            self.get_translation('update_complete_title', 'Update Complete'),
            self.get_translation('update_complete_message', 'Image dimensions update completed.\n\n{status}').format(status=status),
            QMessageBox.StandardButton.Ok
        )
        
    @pyqtSlot(str)
    def update_error(self, error_message):
        """Handle update error.
        
        Args:
            error_message (str): Error message
        """
        self.status_label.setText(self.get_translation('error_status', 'Error: {message}').format(message=error_message))
        
        # Re-enable start button
        self.start_button.setEnabled(True)
        self.options_group.setEnabled(True)
        
        # Show error message
        QMessageBox.critical(
            self,
            self.get_translation('update_error_title', 'Update Error'),
            self.get_translation('update_error_message', 'An error occurred while updating image dimensions:\n{message}').format(message=error_message),
            QMessageBox.StandardButton.Ok
        )
