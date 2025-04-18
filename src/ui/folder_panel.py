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
    QTreeWidgetItem, QPushButton, QMenu, QMessageBox, QFrame
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
        
        # Banner Image and GitHub link in themed container
        app_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        # Get theme settings
        banner_bg_color = "#141417"  # Default if no theme found
        banner_link_color = "#78aeff"  # Default link color
        banner_filename = "banner.png"  # Default banner filename
        
        # Try to get theme colors from the main window's theme manager
        parent_widget = self
        while parent_widget.parent() is not None:
            parent_widget = parent_widget.parent()
            if hasattr(parent_widget, 'theme_manager'):
                theme = parent_widget.theme_manager.get_current_theme()
                if theme and 'colors' in theme:
                    if 'banner' in theme['colors']:
                        banner_bg_color = theme['colors']['banner'].get('background', banner_bg_color)
                        banner_link_color = theme['colors']['banner'].get('linkText', banner_link_color)
                if theme and 'paths' in theme:
                    banner_filename = theme['paths'].get('banner', banner_filename)
                break
        
        # Construct banner path
        banner_path = app_dir / banner_filename
        
        if banner_path.exists():
            # Create themed background container
            banner_container = QFrame()
            banner_container.setStyleSheet(f"background-color: {banner_bg_color}; padding: 10px;")
            container_layout = QVBoxLayout(banner_container)
            
            # Banner image
            banner_label = QLabel()
            pixmap = QPixmap(str(banner_path))
            scaled_pixmap = pixmap.scaled(360, 340, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            banner_label.setPixmap(scaled_pixmap)
            banner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container_layout.addWidget(banner_label)
            
            # GitHub link with themed color
            github_link = QLabel(f'<a href="https://github.com/Starnodes2024/StarnodesImageManager" style="color:{banner_link_color};">Vers 1.0.0 Visit Github</a>')
            github_link.setOpenExternalLinks(True)
            github_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
            github_link.setStyleSheet(f"color: {banner_link_color};")
            container_layout.addWidget(github_link)
            
            # Add container to main layout
            layout.addWidget(banner_container)
            
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
        self.add_folder_button.setFixedSize(30, 30)  # Increased size for better visibility
        self.add_folder_button.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 16px;
                background-color: #494949;
                border-radius: 15px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
        """)
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
        
        # Get total image count
        total_image_count = self.db_manager.get_image_count()
        
        # Add "All Images" option at the top
        all_images_item = QTreeWidgetItem([f"All Images ({total_image_count})"])
        all_images_item.setData(0, Qt.ItemDataRole.UserRole, -1)  # Special ID for All Images
        all_images_item.setToolTip(0, f"View all images across all folders - {total_image_count} total images")
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
            
            # Get image count for this folder
            image_count = self.db_manager.get_image_count_for_folder(folder_id)
            
            # Create folder item with image count
            item = QTreeWidgetItem([f"{os.path.basename(path)} ({image_count})"])
            item.setData(0, Qt.ItemDataRole.UserRole, folder_id)
            item.setToolTip(0, f"{path} - {image_count} images")
            
            # Apply styling based on enabled status
            if not enabled:
                item.setForeground(0, Qt.GlobalColor.gray)
                item.setToolTip(0, f"{path} (disabled) - {image_count} images")
            
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
