#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Folder panel UI component for StarImageBrowse
Displays and manages folders being monitored for images.
"""

import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QPushButton, QMenu, QMessageBox
)
from PyQt6.QtGui import QIcon, QAction, QPixmap
from PyQt6.QtCore import Qt, pyqtSignal, QSize
import webbrowser

logger = logging.getLogger("StarImageBrowse.ui.folder_panel")

class FolderPanel(QWidget):
    """Panel for displaying and managing monitored folders."""
    
    folder_selected = pyqtSignal(int, str)  # Signal emitted when a folder is selected (folder_id, path)
    folder_added = pyqtSignal(int, str)  # Signal emitted when a folder is added (folder_id, path)
    folder_removed = pyqtSignal(int)  # Signal emitted when a folder is removed (folder_id)
    add_folder_requested = pyqtSignal()  # Signal to request adding a new folder
    
    def __init__(self, db_manager, parent=None):
        """Initialize the folder panel.
        
        Args:
            db_manager: Database manager instance
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.db_manager = db_manager
        
        self.setup_ui()
        self.refresh_folders()
    
    def setup_ui(self):
        """Set up the folder panel UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Banner Image
        app_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        banner_path = app_dir / "banner.png"
        
        if banner_path.exists():
            banner_label = QLabel()
            pixmap = QPixmap(str(banner_path))
            scaled_pixmap = pixmap.scaled(360, 340, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            banner_label.setPixmap(scaled_pixmap)
            banner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(banner_label)
            
            # GitHub link
            github_link = QLabel('<a href="https://github.com/Starnodes2024/StarnodesImageManager">Visit Github</a>')
            github_link.setOpenExternalLinks(True)
            github_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(github_link)
            
            # Add some spacing
            layout.addSpacing(10)
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Folders")
        header_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(header_label)
        
        # Add New Folder button
        self.add_folder_button = QPushButton("+")
        self.add_folder_button.setToolTip("Add New Folder")
        self.add_folder_button.setFixedSize(24, 24)  # Make it a small button
        self.add_folder_button.clicked.connect(self.on_add_folder_clicked)
        header_layout.addWidget(self.add_folder_button)
        
        layout.addLayout(header_layout)
        
        # Folder tree
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_tree.itemClicked.connect(self.on_folder_clicked)
        self.folder_tree.customContextMenuRequested.connect(self.on_context_menu)
        layout.addWidget(self.folder_tree)
    
    def on_add_folder_clicked(self):
        """Handler for Add New Folder button click."""
        # Emit signal to request adding a new folder
        # This will be connected to the main window's on_add_folder method
        self.add_folder_requested.emit()
        
    def refresh_folders(self):
        """Refresh the folder list from the database."""
        self.folder_tree.clear()
        
        # Add "All Images" option at the top
        all_images_item = QTreeWidgetItem(["All Images"])
        all_images_item.setData(0, Qt.ItemDataRole.UserRole, -1)  # Special ID for All Images
        all_images_item.setToolTip(0, "View all images across all folders")
        self.folder_tree.addTopLevelItem(all_images_item)
        
        folders = self.db_manager.get_folders(enabled_only=False)
        
        if not folders:
            # No folders added yet
            no_folders_item = QTreeWidgetItem(["No folders added"])
            no_folders_item.setFlags(Qt.ItemFlag.NoItemFlags)  # Not selectable
            self.folder_tree.addTopLevelItem(no_folders_item)
            return
        
        # Add each folder to the tree
        for folder in folders:
            folder_id = folder["folder_id"]
            path = folder["path"]
            enabled = folder["enabled"]
            
            # Create folder item
            item = QTreeWidgetItem([os.path.basename(path)])
            item.setData(0, Qt.ItemDataRole.UserRole, folder_id)
            item.setToolTip(0, path)
            
            # Apply styling based on enabled status
            if not enabled:
                item.setForeground(0, Qt.GlobalColor.gray)
                item.setToolTip(0, f"{path} (disabled)")
            
            self.folder_tree.addTopLevelItem(item)
        
        # Expand all items
        self.folder_tree.expandAll()
    
    def on_folder_clicked(self, item, column):
        """Handle folder item click.
        
        Args:
            item: The clicked tree item
            column: The clicked column
        """
        folder_id = item.data(0, Qt.ItemDataRole.UserRole)
        
        if folder_id is not None:
            # Special case for All Images (-1)
            if folder_id == -1:
                # Emit signal with special ID for all images
                self.folder_selected.emit(-1, "All Images")
                return
                
            # Get folder path
            folders = self.db_manager.get_folders(enabled_only=False)
            folder_info = next((f for f in folders if f["folder_id"] == folder_id), None)
            
            if folder_info:
                # Emit folder selected signal
                self.folder_selected.emit(folder_id, folder_info["path"])
    
    def on_context_menu(self, position):
        """Show context menu for folder items.
        
        Args:
            position: Position where to show the menu
        """
        item = self.folder_tree.itemAt(position)
        
        if not item:
            return
        
        folder_id = item.data(0, Qt.ItemDataRole.UserRole)
        
        if folder_id is None:
            return
        
        # Get folder info
        folders = self.db_manager.get_folders(enabled_only=False)
        folder_info = next((f for f in folders if f["folder_id"] == folder_id), None)
        
        if not folder_info:
            return
        
        folder_path = folder_info["path"]
        enabled = folder_info["enabled"]
        
        # Create context menu
        menu = QMenu()
        
        # Add actions
        scan_action = menu.addAction("Scan Folder")
        
        menu.addSeparator()
        
        if enabled:
            enable_action = menu.addAction("Disable Folder")
        else:
            enable_action = menu.addAction("Enable Folder")
        
        menu.addSeparator()
        
        remove_action = menu.addAction("Remove Folder")
        
        # Show menu and get selected action
        action = menu.exec(self.folder_tree.mapToGlobal(position))
        
        # Handle selected action
        if action == scan_action:
            self.scan_folder(folder_id, folder_path)
        elif action == enable_action:
            self.toggle_folder_enabled(folder_id, not enabled)
        elif action == remove_action:
            self.remove_folder(folder_id)
    
    def scan_folder(self, folder_id, folder_path):
        """Scan a folder for images.
        
        Args:
            folder_id (int): ID of the folder to scan
            folder_path (str): Path of the folder to scan
        """
        # This will be implemented by the parent window
        pass
    
    def toggle_folder_enabled(self, folder_id, enabled):
        """Toggle whether a folder is enabled.
        
        Args:
            folder_id (int): ID of the folder to toggle
            enabled (bool): Whether the folder should be enabled
        """
        # TODO: Implement toggle folder enabled in database
        # For now, just refresh the display
        self.refresh_folders()
    
    def remove_folder(self, folder_id):
        """Remove a folder from monitoring.
        
        Args:
            folder_id (int): ID of the folder to remove
        """
        # Confirm removal
        confirm = QMessageBox.question(
            self, "Confirm Removal", 
            "Are you sure you want to remove this folder from monitoring? All image records for this folder will be deleted from the database.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        # Remove folder from database
        success = self.db_manager.remove_folder(folder_id)
        
        if success:
            # Emit signal
            self.folder_removed.emit(folder_id)
            
            # Refresh display
            self.refresh_folders()
        else:
            QMessageBox.critical(
                self, "Error", 
                "Failed to remove folder from database.",
                QMessageBox.StandardButton.Ok
            )
    
    def get_selected_folder_id(self):
        """Get the ID of the currently selected folder.
        
        Returns:
            int: ID of the selected folder, or None if no folder is selected
        """
        selected_items = self.folder_tree.selectedItems()
        
        if not selected_items:
            return None
        
        # Get the first selected item
        item = selected_items[0]
        
        # Return the folder ID stored in the item's user role data
        return item.data(0, Qt.ItemDataRole.UserRole)
    
    def get_selected_folder_path(self):
        """Get the path of the currently selected folder.
        
        Returns:
            str: Path of the selected folder, or None if no folder is selected
        """
        folder_id = self.get_selected_folder_id()
        
        if folder_id is None:
            return None
        
        # Get folder info from database
        folders = self.db_manager.get_folders(enabled_only=False)
        folder_info = next((f for f in folders if f["folder_id"] == folder_id), None)
        
        if not folder_info:
            return None
        
        return folder_info["path"]
